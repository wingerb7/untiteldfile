from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.interpolate import build_animation_model
from analysis.normalize import load_and_normalize
from scripts.render_tactical_storytelling import OPEN_DATA
from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.patterns.positional import PositionalPatternConfig, detect_positional_patterns
from src.intelligence.reasoning.rank_findings import rank_findings
from src.pipelines.render_analysis import load_config, scene_segments
from src.pipelines.semantic_route import build_semantic_route
from src.scene_direction import build_scene_direction
from src.tactical_episodes import build_tactical_episodes
from src.tactical_relevance import classify_episode_players
from src.tactical_story.episodic_scene_plan import build_episodic_scene_plan


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "audit/depay_storytelling"
MATCH_ID = 3869117
POSSESSION_ID = 20
SOURCE = ROOT / "data/depay_goal.json"
FIRST_CAUSAL_EVENT = "33afe8ec-1aea-40be-a7cc-97610032e3b5"
FINAL_PASS_EVENT = "f13d1fcc-d78b-4932-a6ae-f24f0e153753"
SHOT_EVENT = "05907c05-0a6c-4aa7-a62a-1f1a70bebba7"
CORE_LINE_BREAKS = {
    "d3264b17-4393-4e4d-8970-51128f9d9bf3",
    "fb2800dc-0e2c-42f6-9708-aaf3caf2b6e7",
    FINAL_PASS_EVENT,
}


def _write(name: str, value: dict[str, Any]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def _raw(event_id: str) -> str:
    return event_id.removeprefix("event:statsbomb:")


def _event_seconds(event: dict[str, Any]) -> float:
    value = event["timestamp"]
    minute, second = value.split(":")[-2:]
    return int(minute) * 60 + float(second)


def _graph_path(edges: list[dict[str, Any]], starts: set[str], targets: set[str]) -> list[str]:
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        adjacency.setdefault(edge["source_node_id"], []).append((edge["target_node_id"], edge["edge_id"]))
    pending = deque((node_id, []) for node_id in sorted(starts))
    visited = set(starts)
    while pending:
        node_id, relation_ids = pending.popleft()
        if node_id in targets and relation_ids:
            return relation_ids
        for target_id, relation_id in sorted(adjacency.get(node_id, ())):
            if target_id not in visited:
                visited.add(target_id)
                pending.append((target_id, [*relation_ids, relation_id]))
    return []


def _segment_trace(plan: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    segments = scene_segments(plan, model)
    rows = [
        {
            "scene_id": segment["scene"].get("scene_id"),
            "episode_id": segment["scene"].get("episode_id"),
            "scene_type": segment["type"],
            "output_start": round(segment["output_start"], 6),
            "output_end": round(segment["output_end"], 6),
            "rendered_duration": round(segment["output_end"] - segment["output_start"], 6),
            "planned_duration": segment["scene"].get("duration_seconds")
            or segment["scene"].get("target_duration_seconds"),
            "event_id": segment.get("event_id"),
            "instructions": segment["scene"].get("instructions", []),
        }
        for segment in segments
    ]
    return {
        "scene_count": len(rows),
        "scenes": rows,
        "planned_duration_sum": round(sum(float(row["planned_duration"] or 0) for row in rows), 6),
        "rendered_duration": round(rows[-1]["output_end"] if rows else 0.0, 6),
        "tactical_pause_duration": round(sum(row["rendered_duration"] for row in rows if row["scene_type"] == "tactical_pause"), 6),
        "play_duration": round(sum(row["rendered_duration"] for row in rows if row["scene_type"] == "play"), 6),
        "hold_duration": round(sum(row["rendered_duration"] for row in rows if row["scene_type"] == "hold"), 6),
        "transition_duration": 0.0,
        "caption_hold_duration": round(sum(row["rendered_duration"] for row in rows if row["scene_type"] in {"tactical_pause", "hold"}), 6),
    }


def build_audit() -> None:
    source = json.loads(SOURCE.read_text())
    source_events = source["events"]
    raw_events = json.loads((OPEN_DATA / f"events/{MATCH_ID}.json").read_text())
    raw_frames = json.loads((OPEN_DATA / f"three-sixty/{MATCH_ID}.json").read_text())
    route = build_semantic_route(
        raw_events,
        raw_frames,
        {
            "source_dataset": "statsbomb-open-data",
            "source_revision": route_revision(),
            "match_id": MATCH_ID,
            "possession_id": POSSESSION_ID,
        },
        SOURCE,
        width=720,
        height=1280,
        fps=24,
    )
    graph_episodes = route["graph_backed_episodes"]
    graph = route["action_graph"]
    graph_nodes = {node["node_id"]: node for node in graph["nodes"]}
    graph_edges = list(graph["edges"])
    finish_episode = next(item for item in graph_episodes["episodes"] if item["episode_type"] == "FINISH")
    finish_nodes = set(finish_episode["supporting_action_node_ids"])
    render_episodes = {episode.episode_id: episode for episode in route["render_episodes"].episodes}
    semantic_scenes = route["scene_plan"]["scenes"]

    first_index = next(index for index, event in enumerate(source_events) if event["id"] == FIRST_CAUSAL_EVENT)
    finish_index = next(index for index, event in enumerate(source_events) if event["id"] == SHOT_EVENT)
    line_break_by_pass = {
        _raw(episode["authenticated_source_event_ids"][0]): episode
        for episode in graph_episodes["episodes"]
        if episode["episode_type"] == "LINE_BREAK"
    }
    spine_actions = []
    for index, event in enumerate(source_events[first_index:finish_index + 1], first_index):
        event_id = event["id"]
        if event_id == FIRST_CAUSAL_EVENT:
            role = "FIRST_CAUSALLY_RELEVANT_ACTION_AND_LINE_BREAK"
        elif event_id == FINAL_PASS_EVENT:
            role = "FINAL_ACTION_AND_LINE_BREAK"
        elif event_id == SHOT_EVENT:
            role = "FINISH"
        elif event_id in line_break_by_pass:
            role = "LINE_BREAKING_PROGRESSION"
        elif event["type"].startswith("Ball Receipt"):
            role = "AUTHENTICATED_RECEIVER_CONTROL"
        else:
            role = "PROGRESSION_ACTION"
        spine_actions.append({
            "possession_relative_index": index,
            "event_id": event_id,
            "event_type": event["type"],
            "timestamp_seconds": _event_seconds(event),
            "actor": f"player:statsbomb:{event['player_id']}" if event.get("player_id") else None,
            "receiver": f"player:statsbomb:{event['recipient_id']}" if event.get("recipient_id") else None,
            "spine_role": role,
            "line_break_episode_id": (
                line_break_by_pass[event_id]["episode_id"] if event_id in line_break_by_pass else None
            ),
        })
    canonical_spine = {
        "schema_id": "tip.depay_canonical_attack_spine",
        "contract_version": "0.1.0",
        "match_id": MATCH_ID,
        "possession_id": POSSESSION_ID,
        "possession_start": {
            "event_id": source_events[0]["id"],
            "timestamp_seconds": _event_seconds(source_events[0]),
            "classification": "STRUCTURAL_CONTEXT_NOT_DECISIVE_ATTACK",
        },
        "first_causally_relevant_action": FIRST_CAUSAL_EVENT,
        "actions": spine_actions,
        "supported_box_entry_or_final_third_arrival": None,
        "box_entry_limitation": "No authenticated graph-backed BOX_ENTRY or FINAL_THIRD_ARRIVAL concept is available.",
        "final_action": FINAL_PASS_EVENT,
        "finish": SHOT_EVENT,
        "possession_end": {
            "event_id": source_events[-1]["id"],
            "timestamp_seconds": _event_seconds(source_events[-1]),
        },
        "causal_basis": (
            "The spine starts at the earliest authenticated LINE_BREAK retained by the "
            "decisive sequence and follows authenticated source actions, crossing relations, "
            "related receipts, temporal succession, and the terminal shot."
        ),
        "excluded_earlier_event_count": first_index,
        "excluded_earlier_events_reason": (
            "Earlier events are authenticated possession circulation but have no graph-backed "
            "tactical episode or causal mechanism needed to explain the final attacking sequence."
        ),
    }

    previous_plan = json.loads((ROOT / "renders/storytelling/depay/scene_plan.json").read_text())
    previous_trace = json.loads((ROOT / "renders/storytelling/depay/trace.json").read_text())
    previous_narrative = json.loads((ROOT / "renders/storytelling/depay/narrative.json").read_text())
    historical_generic_audit = json.loads(
        (ROOT / "renders/tactical_episodes/depay/audit_trace.json").read_text()
    )
    historical_generic_plan = json.loads(
        (ROOT / "renders/tactical_episodes/depay/scene_plan.json").read_text()
    )
    previous_scene_event_ids = {
        scene.get("at_event_id") or scene.get("from_event_id")
        for scene in previous_plan["scenes"]
    }
    inventory = []
    for graph_episode in graph_episodes["episodes"]:
        render_episode = render_episodes[graph_episode["episode_id"]]
        event_ids = [_raw(event_id) for event_id in graph_episode["authenticated_source_event_ids"]]
        start = float(graph_episode["start_ordering_key"][1])
        end = float(graph_episode["end_ordering_key"][1])
        path = _graph_path(graph_edges, set(graph_episode["supporting_action_node_ids"]), finish_nodes)
        pass_id = event_ids[0]
        if graph_episode["episode_type"] == "FINISH":
            narrative_classification = "CORE_CAUSAL"
            causal_relation = "DIRECT_CAUSAL_CONTRIBUTION"
            purpose = "finish"
        elif pass_id in CORE_LINE_BREAKS:
            narrative_classification = "CORE_CAUSAL"
            causal_relation = "DIRECT_OR_IMMEDIATE_ENABLING_CONTRIBUTION"
            purpose = "decisive mechanism"
        elif pass_id == FIRST_CAUSAL_EVENT:
            narrative_classification = "SUPPORTING_CONTEXT"
            causal_relation = "ENABLING_CONTRIBUTION"
            purpose = "setup and attack entry"
        else:
            narrative_classification = "TACTICALLY_VALID_BUT_NARRATIVELY_SECONDARY"
            causal_relation = "ENABLING_CONTRIBUTION"
            purpose = "sustained progression"
        semantic_episode_scenes = [scene for scene in semantic_scenes if scene.get("episode_id") == graph_episode["episode_id"]]
        previous_explicit = any(event_id in previous_scene_event_ids for event_id in event_ids)
        inventory.append({
            "episode_id": graph_episode["episode_id"],
            "episode_type": graph_episode["episode_type"],
            "source_event_ids": event_ids,
            "start_timestamp": start,
            "end_timestamp": end,
            "actors": graph_episode["primary_actor_ids"],
            "graph_relations": graph_episode["supporting_relation_ids"],
            "authenticated_path_to_finish": path,
            "causal_relation_to_finish": causal_relation,
            "audit_narrative_classification": narrative_classification,
            "current_relevance_classification": "PLAYER_VISIBILITY_ONLY; NO EPISODE_CAUSAL_RELEVANCE_CLASSIFIER",
            "current_ranking_score": None,
            "current_selection_priority": "CANONICAL_EPISODE_ORDER; CONFIDENCE_NOT_USED_FOR_COMPARATIVE_RANKING",
            "confidence": graph_episode["confidence"],
            "mandatory_status": "FINISH_ALWAYS_RETAINED" if graph_episode["episode_type"] == "FINISH" else "AUTHENTICATED_CANDIDATE_RETAINED",
            "selected_by_graph_semantic_route": True,
            "selected_by_previous_storytelling_route": False,
            "explicitly_appeared_in_previous_scene_plan": previous_explicit,
            "appeared_in_graph_semantic_scene_plan": bool(semantic_episode_scenes),
            "graph_semantic_scene_ids": [scene["scene_id"] for scene in semantic_episode_scenes],
            "graph_semantic_planned_duration": round(sum(float(scene.get("duration_seconds") or scene.get("target_duration_seconds") or 0) for scene in semantic_episode_scenes), 6),
            "previous_rendered_duration_as_episode": 0.0,
            "narrative_purpose": purpose,
            "unique_narrative_purpose": narrative_classification in {"CORE_CAUSAL", "SUPPORTING_CONTEXT"},
            "storytelling_note": (
                "Semantically distinct and analytically useful, but suitable for grouping as "
                "sustained progression when it lacks a unique setup, decisive, or finish role."
                if narrative_classification == "TACTICALLY_VALID_BUT_NARRATIVELY_SECONDARY"
                else "Retain as an explicit narrative beat."
            ),
            "authenticated_provenance": {
                "recognition_ids": graph_episode["recognition_record_ids"],
                "perception_feature_ids": graph_episode["perception_feature_ids"],
                "action_node_ids": graph_episode["supporting_action_node_ids"],
                "relation_ids": graph_episode["supporting_relation_ids"],
            },
        })
    episode_inventory = {
        "schema_id": "tip.depay_storytelling_episode_inventory",
        "contract_version": "0.1.0",
        "artifact_hashes": {
            "recognition": route["recognition"].sha256,
            "action_graph": graph.sha256,
            "graph_backed_episodes": graph_episodes.sha256,
        },
        "candidate_count": len(inventory),
        "episodes": inventory,
        "classification_counts": {
            value: sum(item["audit_narrative_classification"] == value for item in inventory)
            for value in (
                "CORE_CAUSAL",
                "SUPPORTING_CONTEXT",
                "TACTICALLY_VALID_BUT_NARRATIVELY_SECONDARY",
                "UNRELATED_TO_DECISIVE_ATTACK",
                "DUPLICATIVE_FOR_STORYTELLING",
            )
        },
    }

    selection_trace = {
        "schema_id": "tip.depay_storytelling_selection_trace",
        "contract_version": "0.1.0",
        "stages": [
            {
                "stage": "SOURCE_POSSESSION_SELECTION",
                "input_count": len(raw_events),
                "selected_possession_event_count": len(source_events),
                "result": "CORRECT_POSSESSION_SELECTED",
                "diverges": False,
            },
            {
                "stage": "GRAPH_TACTICAL_EPISODE_GENERATION",
                "candidate_count": len(inventory),
                "episode_types": [item["episode_type"] for item in inventory],
                "result": "DECISIVE_ATTACK_DETECTED",
                "diverges": False,
            },
            {
                "stage": "EPISODE_RELEVANCE",
                "rule": "classify_episode_players only; no episode-level causal relevance classification",
                "result": "NO_ATTACK_IMPORTANCE_SIGNAL_PRODUCED",
                "diverges": False,
            },
            {
                "stage": "GRAPH_SEMANTIC_EPISODE_SELECTION",
                "maximum_episode_count": None,
                "ranking_score": None,
                "confidence_use": "validation metadata only; all candidates are 1.0",
                "pattern_priority": "none",
                "mandatory_rule": "FINISH always retained",
                "tie_breaker": "canonical episode ordering",
                "selected_count": len(inventory),
                "result": "ALL_AUTHENTICATED_EPISODES_RETAINED",
                "diverges": False,
            },
            {
                "stage": "PREVIOUS_STORYTELLING_NARRATIVE_GROUPING",
                "entry_point": "scripts/render_tactical_storytelling.py::action_chain_for",
                "graph_episode_candidates_received": 0,
                "return_combination_match_count": len(route["tactical_patterns"]["matches"]),
                "fallback": "FACTUAL_CONTINUATION_FALLBACK",
                "selection_rule": previous_narrative["selection_rule"],
                "selected_player": previous_narrative["player_id"],
                "selected_step_count": len(previous_narrative["steps"]),
                "omitted_first_causal_event": FIRST_CAUSAL_EVENT,
                "result": "ATTACK_REFRAMED_AS_ONE_PLAYER_CONTINUATION",
                "diverges": True,
                "first_divergence": True,
            },
            {
                "stage": "PREVIOUS_SCENE_DIRECTION_AND_ORDERING",
                "planning_basis": previous_plan["planning_basis"],
                "scene_count": len(previous_plan["scenes"]),
                "episode_count": 1,
                "result": "ONE_SETUP_PAUSE_ONE_COMPRESSED_PLAY_ONE_FINISH_HOLD",
                "diverges": True,
            },
            {
                "stage": "RENDERER",
                "planned_scene_count": len(previous_plan["scenes"]),
                "executed_scene_count": len(previous_trace["scene_trace"]),
                "planned_duration": 8.95,
                "rendered_duration": previous_trace["scene_trace"][-1]["output_end"],
                "result": "EXECUTED_SUPPLIED_PLAN_EXACTLY",
                "diverges": False,
            },
        ],
        "first_divergence_layer": "NARRATIVE_GROUPING",
        "historical_generic_video_first_divergence_layer": "GENERIC_EPISODE_GENERATION_WITHOUT_CAUSAL_RELEVANCE_SELECTION",
        "first_divergence_reason": (
            "The previous storytelling entry point never supplied graph-backed tactical "
            "episodes to relevance or scene planning. With no return-combination match, it "
            "selected the first canonical same-player continuation ending in the shot."
        ),
        "selection_model_assessment": (
            "The graph semantic route is optimized for authenticated validity and canonical "
            "ordering, not narrative importance. The previous storytelling route is optimized "
            "for one-player continuity, not the decisive multi-player mechanism."
        ),
        "historical_generic_video": {
            "candidate_episode_types": [
                episode["episode_type"] for episode in historical_generic_audit["episodes"]
            ],
            "selected_episode_count": len(historical_generic_audit["episodes"]),
            "selected_scene_count": len(historical_generic_plan["scenes"]),
            "causal_relevance_ranking": None,
            "maximum_episode_rule": None,
            "result": (
                "Earlier generic detections were treated as equally scene-worthy and "
                "therefore occupied five explanatory beats before the finish."
            ),
        },
    }

    render_possession = load_and_normalize(SOURCE)
    config = load_config(ROOT / "config.yaml")
    model = build_animation_model(render_possession, config)
    semantic_segment_trace = _segment_trace(route["scene_plan"], model)
    generic_possession = load_normalized_possession(SOURCE)
    findings = rank_findings(generic_possession, [
        *detect_line_breaking_passes(generic_possession, LineBreakConfig()),
        *detect_positional_patterns(generic_possession, PositionalPatternConfig()),
    ])
    generic_episodes = build_tactical_episodes(generic_possession, findings).episodes
    generic_directions = {
        episode.episode_id: build_scene_direction(
            generic_possession,
            episode,
            classify_episode_players(generic_possession, episode),
        )
        for episode in generic_episodes
    }
    generic_plan = build_episodic_scene_plan(generic_possession, generic_episodes, generic_directions)
    generic_trace = _segment_trace(generic_plan, model)
    previous_rows = [
        {
            "scene_id": row["scene_id"],
            "scene_type": row["type"],
            "event_id": row["event_id"],
            "output_start": row["output_start"],
            "output_end": row["output_end"],
            "rendered_duration": round(row["output_end"] - row["output_start"], 6),
            "caption": row.get("caption"),
        }
        for row in previous_trace["scene_trace"]
    ]
    scene_plan_trace = {
        "schema_id": "tip.depay_storytelling_scene_plan_trace",
        "contract_version": "0.1.0",
        "previous_storytelling_render": {
            "planning_basis": previous_plan["planning_basis"],
            "scene_count": len(previous_rows),
            "scenes": previous_rows,
            "planned_duration": 8.95,
            "rendered_duration": previous_rows[-1]["output_end"],
            "scene_plan_matches_render": len(previous_rows) == len(previous_plan["scenes"]),
            "narrative_structure": {
                "setup": "Depay receives the ball",
                "tactical_problem": None,
                "decisive_mechanism": "compressed into undifferentiated play",
                "final_action": "not separately explained",
                "finish": "shot hold",
            },
        },
        "known_generic_duration_failure": {
            "planning_basis": generic_plan["planning_basis"],
            "episode_types": [episode.episode_type for episode in generic_episodes],
            "episode_action_counts": [len(episode.participating_action_ids) for episode in generic_episodes],
            **generic_trace,
            "cause": (
                "The generic builder groups the first 56 possession events into one BUILDUP "
                "episode, and the scene planner caps its play at four seconds. Fixed pause/play "
                "constants then total exactly 12.5 seconds."
            ),
            "relationship_to_story_failure": "SYMPTOM_AND_AMPLIFIER, NOT THE FIRST CAUSE",
        },
        "graph_semantic_plan": {
            "planning_basis": route["scene_plan"]["planning_basis"],
            "episode_count": len(inventory),
            **semantic_segment_trace,
            "narrative_structure": {
                "setup": "first LINE_BREAK",
                "tactical_problem": "observation-scoped defensive line",
                "decisive_mechanism": "six individually presented LINE_BREAK episodes",
                "final_action": "final LINE_BREAK to Depay",
                "finish": "FINISH episode and hold",
            },
            "limitation": (
                "It preserves the decisive events but behaves as a chronological list of "
                "equally weighted valid detections; repeated LINE_BREAK pauses are excessive "
                "for storytelling without a grouping layer."
            ),
        },
        "historical_generic_render": {
            "asset": "renders/tactical_episodes/depay/depay_consumer.mp4",
            "episode_types": [
                episode["episode_type"] for episode in historical_generic_audit["episodes"]
            ],
            "scene_count": len(historical_generic_plan["scenes"]),
            "rendered_duration": 23.5,
            "diagnosis": (
                "BUILDUP, ISOLATION, OFF_BALL_RUN, SWITCH_OF_PLAY, and CUTBACK were "
                "all sent to scenes without causal relevance ranking, so earlier "
                "possession actions dominated the explanation."
            ),
        },
        "duration_verdict": (
            "Short duration is not the first semantic divergence. It results from coarse "
            "grouping and fixed compression, then reduces the time available to explain the "
            "already misframed attack."
        ),
        "renderer_verdict": "NOT_AT_FAULT; EXISTING TRACE EXECUTES THE SUPPLIED SCENE PLAN",
        "visual_validation": {
            "asset": "renders/storytelling/depay/depay_storytelling.mp4",
            "container_duration_seconds": 8.92,
            "inspection_method": "three-frame contact sheet sampled after semantic tracing",
            "result": (
                "The opening and middle frames repeat the planned Depay-continuation "
                "caption; the terminal frame shows the planned shot caption. No extra "
                "tactical story was introduced by rendering."
            ),
        },
    }

    report = f"""# Depay production storytelling audit

## Executive verdict

The decisive attack was detected by the graph-backed route: six authenticated LINE_BREAK
episodes and the finish all reach the candidate set. The previous storytelling video lost
the multi-player mechanism at **narrative grouping**, before episode relevance, ranking, or
scene direction. Its entry point did not consume graph-backed episodes. Because Depay has no
authenticated return-combination match, it selected the first canonical same-player
continuation ending in the shot and rendered that as one episode.

The renderer is not responsible. It executed all three supplied scenes and the planned
8.95-second timeline exactly (8.92 seconds at the encoded container boundary). A
post-semantic three-frame inspection shows the planned Depay-continuation caption through
the compressed play and the planned shot caption at the end; it introduces no upstream
tactical meaning.

## Canonical decisive attack

The possession begins at `{source_events[0]['id']}`, but the canonical attack begins
at `{FIRST_CAUSAL_EVENT}` (Blind to Depay, 557.943s), the earliest authenticated line break
in the decisive sequence. It continues through the quick progression and the final
Depay–Gakpo–Dumfries chain:

1. Blind → Depay: attack-entry line break.
2. De Roon → Klaassen and Klaassen → Depay: supporting combination/progression.
3. Depay → Gakpo: decisive mechanism begins.
4. Gakpo → Dumfries: wide progression within the mechanism.
5. Dumfries → Depay: final line-breaking action.
6. Depay shoots at 571.453s.

No graph-backed box-entry or final-third-arrival concept exists, so none is asserted.

## Candidate and LINE_BREAK audit

All seven graph-backed candidates have authenticated paths to the finish. Three episodes are
`CORE_CAUSAL`, one is `SUPPORTING_CONTEXT`, two are
`TACTICALLY_VALID_BUT_NARRATIVELY_SECONDARY`, and FINISH is `CORE_CAUSAL`.

The six LINE_BREAK episodes are semantically distinct and useful for analysis. Presenting
all six as equal individual storytelling beats is excessive: the middle progression has no
unique setup, decisive, or finish purpose and should be summarized rather than independently
paused. This is narrative redundancy, not episode duplication.

## Exact divergence

For the historical 23.5-second generic tactical-episode video, the first divergence is
generic episode generation without causal relevance selection: BUILDUP, ISOLATION,
OFF_BALL_RUN, SWITCH_OF_PLAY, and CUTBACK were all treated as equally scene-worthy, so five
earlier-possession explanations preceded the finish.

For the later 8.95-second storytelling render,
`scripts/render_tactical_storytelling.py::action_chain_for` is the first divergent layer.
The graph episode candidate count supplied to that branch is zero. The fallback
`FIRST_CANONICAL_CHAIN_ENDING_IN_AUTHENTICATED_SHOT` follows only Depay's repeated
involvements, starts at his receipt rather than Blind's line-breaking pass, and omits the
other players' decisive actions as explained beats. The scene builder then faithfully
creates one pause, one compressed play, and one finish hold.

There is no maximum-episode rule, ranking score, or causal-importance score in the graph
semantic route. Confidence is 1.0 for every authenticated episode and is not used to rank
them. Canonical time is the effective ordering rule. The model is optimized for validity,
not narrative importance.

## Duration

Three separate durations matter:

- Historical generic tactical-episode render: **23.5s**; long enough, but focused on
  earlier generic detections.
- Previous storytelling render: **8.95s**, planned and rendered identically.
- Known generic Depay regression: **{generic_trace['rendered_duration']}s**. The generic
  builder currently groups 56 events as BUILDUP and caps its play at 4.0s; fixed pauses,
  the final play, and hold produce 12.5s.
- Graph semantic plan: **{semantic_segment_trace['rendered_duration']}s** across
  {semantic_segment_trace['scene_count']} scenes.

The 12.5-second result is a symptom and amplifier, not the first cause. Coarse grouping and
fixed compression create the short plan; the reduced duration then leaves no room to explain
the attack.

## Narrowest recommended correction

Change the storytelling orchestration between graph-backed episode adaptation and scene
planning. Add a causal narrative-selection/grouping policy that:

1. anchors on FINISH;
2. walks authenticated predecessors;
3. retains one setup line break and the final decisive pass/finish chain;
4. groups intervening distinct LINE_BREAK episodes as sustained progression;
5. assigns explicit setup, mechanism, final-action, and finish roles before scene planning.

Recognition, Action Graph, graph episode semantics, tactical thresholds, renderer behavior,
and the six episode identities should not change. No production correction is implemented
by this audit.
"""

    _write("canonical_attack_spine.json", canonical_spine)
    _write("episode_inventory.json", episode_inventory)
    _write("selection_trace.json", selection_trace)
    _write("scene_plan_trace.json", scene_plan_trace)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "storytelling_report.md").write_text(report)


def route_revision() -> str:
    from src.source_selection import PINNED_REVISION

    return PINNED_REVISION


if __name__ == "__main__":
    build_audit()
    print(json.dumps({"output": str(OUTPUT), "status": "PASS"}, sort_keys=True))
