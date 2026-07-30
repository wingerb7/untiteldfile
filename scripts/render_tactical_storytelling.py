from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

import yaml

from analysis.normalize import load_and_normalize
from src.action_continuation import build_action_continuation_dataset
from src.action_graph import build_action_graph_dataset
from src.domain.models import ActionChain, NarrativeStep
from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.scene_builder import build_scene_plan
from src.narrative_adapter import build_continuation_narrative
from src.normalization import build_normalized_dataset
from src.perception import build_perception_dataset, validate_perception_dataset
from src.pipelines.render_analysis import caption_timing_diagnostics, render_scene_plan, scene_trace
from src.recognition import build_recognition_dataset
from src.semantic_resolution import build_semantic_resolution_dataset
from src.source_selection import PINNED_REVISION, select_source_documents
from src.synchronization import build_synchronized_dataset
from src.tactical_patterns import detect_return_combination_patterns
from src.tactical_story import build_tactical_story
from src.world_model import build_world_model_dataset, validate_world_model_dataset


ROOT = Path(__file__).resolve().parents[1]
OPEN_DATA = ROOT / "data/open-data/data"
OUTPUT = ROOT / "renders/storytelling"
FIXTURES = (
    ("locatelli", 3788754, 40, ROOT / "data/second_goal.json"),
    ("depay", 3869117, 20, ROOT / "data/depay_goal.json"),
    ("di_maria", 3869685, 52, ROOT / "data/possession_52.json"),
)


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def upstream(match_id: int, possession_id: int, *, include_perception: bool = False):
    events = json.loads((OPEN_DATA / f"events/{match_id}.json").read_text(encoding="utf-8"))
    frames = json.loads((OPEN_DATA / f"three-sixty/{match_id}.json").read_text(encoding="utf-8"))
    selected = select_source_documents(
        events,
        frames,
        {
            "source_dataset": "statsbomb-open-data",
            "source_revision": PINNED_REVISION,
            "match_id": match_id,
            "possession_id": possession_id,
        },
    )
    normalized = build_normalized_dataset(selected)
    synchronized = build_synchronized_dataset(normalized)
    world = validate_world_model_dataset(build_world_model_dataset(synchronized))
    perception = validate_perception_dataset(build_perception_dataset(world), source_hashes=world.source_hashes)
    recognition = build_recognition_dataset(perception)
    graph = build_action_graph_dataset(recognition)
    semantic = build_semantic_resolution_dataset(graph, recognition)
    continuation = build_action_continuation_dataset(graph, recognition, semantic)
    patterns = detect_return_combination_patterns(continuation, graph, recognition, semantic)
    result = (recognition, graph, semantic, continuation, patterns)
    return (*result, perception) if include_perception else result


def action_chain_for(
    recognition: Any,
    graph: Any,
    semantic: Any,
    continuation: Any,
    patterns: Any,
    names: dict[str, str],
) -> tuple[Any, ActionChain, str]:
    story = build_tactical_story(patterns, continuation, graph, recognition, semantic, names)
    if story is not None:
        match = patterns["matches"][0]
        action_by_role = {action["role"]: action for action in match["actions"]}
        overlay_roles = ("initial_pass", "teammate_carry", "return_pass")
        steps = [
            NarrativeStep(
                beat["beat_id"],
                beat["beat_type"],
                beat["end_event_uuid"],
                beat["actor_ids"][0],
                None,
                beat["caption"],
                {
                    "pattern_id": story["pattern_id"],
                    "supporting_action_node_ids": beat["supporting_action_node_ids"],
                    "overlay_event_id": action_by_role[overlay_roles[index]]["event_uuid"],
                    "arrow_type": "draw_carry_arrow" if index == 1 else "draw_pass_arrow",
                    "protagonist_id": match["initial_actor_id"],
                    "teammate_id": match["teammate_actor_id"],
                    "initial_pass_event_id": action_by_role["initial_pass"]["event_uuid"],
                    "teammate_receipt_event_id": action_by_role["teammate_receipt"]["event_uuid"],
                    "teammate_carry_event_id": action_by_role["teammate_carry"]["event_uuid"],
                    "return_pass_event_id": action_by_role["return_pass"]["event_uuid"],
                    "return_receipt_event_id": action_by_role["return_receipt"]["event_uuid"],
                    "shot_event_id": action_by_role["finish"]["event_uuid"],
                    "football_question": beat["football_question"],
                    "participant_roles": beat["participant_roles"],
                    "caption_schedule": beat["caption_schedule"],
                },
            )
            for index, beat in enumerate(story["beats"])
        ]
        chain = ActionChain(
            story["story_id"],
            "authenticated_tactical_pattern",
            steps[0].event_id,
            steps[-1].event_id,
            1.0,
            steps,
            {
                "pattern_dataset_sha256": patterns.sha256,
                "pattern_id": story["pattern_id"],
                "protagonist_id": match["initial_actor_id"],
                "teammate_id": match["teammate_actor_id"],
            },
        )
        return story, chain, "TACTICAL_PATTERN"

    narrative = build_continuation_narrative(continuation, graph, recognition, semantic, names)
    steps = [
        NarrativeStep(
            step["step_id"],
            step["step_type"],
            step["event_id"],
            step["actor_id"],
            None,
            step["caption"],
            {
                "continuation_node_id": step["action_graph_node_id"],
                "canonical_ordering_key": step["canonical_ordering_key"],
            },
        )
        for step in narrative["steps"]
    ]
    chain = ActionChain(
        narrative["chain_id"],
        "authenticated_player_action_continuation",
        steps[0].event_id,
        steps[-1].event_id,
        1.0,
        steps,
        {
            "continuation_dataset_sha256": continuation.sha256,
            "continuation_edge_ids": list(narrative["supporting_continuation_edge_ids"]),
            "episode": narrative["episode"],
        },
    )
    return narrative, chain, "FACTUAL_CONTINUATION_FALLBACK"


def render_fixture(slug: str, match_id: int, possession_id: int, source: Path) -> dict[str, Any]:
    out = OUTPUT / slug
    try:
        recognition, graph, semantic, continuation, patterns = upstream(match_id, possession_id)
    except Exception as exc:
        rejection = {
            "schema_id": "tip.storytelling_render_rejection",
            "fixture": slug,
            "match_id": match_id,
            "possession_id": possession_id,
            "status": "REJECTED_UPSTREAM",
            "error": str(exc),
        }
        write(out / "rejection.json", rejection)
        return rejection

    render_possession = load_and_normalize(source)
    names = {
        f"player:statsbomb:{event['player_id']}": event["player_name"]
        for event in render_possession["events"]
        if event.get("player_id") and event.get("player_name")
    }
    narrative, chain, narrative_mode = action_chain_for(
        recognition, graph, semantic, continuation, patterns, names
    )
    possession = load_normalized_possession(source)
    plan = build_scene_plan(possession, None, None, action_chain=chain, width=720, height=1280, fps=24)
    plan["narrative_window"] = {
        "window_start_event_id": chain.start_event_id,
        "window_end_event_id": chain.end_event_id,
    }
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    config["animation"].update(
        {
            "width": 720,
            "height": 1280,
            "fps": 24,
            "hook_hold_seconds": 0.0,
            "hook_text": "",
            "annotations_file": None,
            "camera_lookahead_seconds": 1.0,
            "camera_lookback_seconds": 0.25,
            "camera_ease": 0.055,
            "camera_zoom_out_ease": 0.075,
        }
    )
    mp4 = out / f"{slug}_storytelling.mp4"
    model = render_scene_plan(render_possession, plan, config, mp4)
    trace = {
        "schema_id": "tip.storytelling_render_trace",
        "narrative_sha256": narrative.sha256,
        "scene_trace": scene_trace(plan, model),
        "caption_timing": caption_timing_diagnostics(plan, model),
        "tactical_presentation": model.get("relevant_player_selection", {}).get("tactical_presentation"),
    }
    analysis = {
        "schema_id": "tip.storytelling_render_analysis",
        "analysis_status": "supported",
        "fixture": slug,
        "match_id": match_id,
        "possession_id": possession_id,
        "narrative_mode": narrative_mode,
        "planning_basis": plan.get("planning_basis"),
        "episode_count": len({scene.get("episode_id") for scene in plan["scenes"] if scene.get("episode_id")}),
        "limitations": [
            "Tactical meaning is limited to relations already validated upstream.",
            "No intent, defensive manipulation, causal inevitability, or newly detected space is asserted.",
            "StatsBomb 360 provides event snapshots rather than continuous tracking.",
        ],
    }
    write(out / "narrative.json", narrative.data)
    write(out / "scene_plan.json", plan)
    write(out / "trace.json", trace)
    write(out / "analysis.json", analysis)
    write(out / "action_chain.json", asdict(chain))
    return {"status": "RENDERED", "fixture": slug, "mp4": str(mp4), "mode": narrative_mode}


def main() -> None:
    results = [render_fixture(*fixture) for fixture in FIXTURES]
    write(OUTPUT / "render_results.json", {"schema_id": "tip.storytelling_render_results", "results": results})
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
