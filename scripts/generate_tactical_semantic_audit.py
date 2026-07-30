from __future__ import annotations

"""Read-only semantic/causal/render-grounding audit of the generated tactical
episodes for Depay and Locatelli (Di Maria is attempted and documented as
upstream-rejected, per its existing source-selection restriction -- it is not
bypassed).

This script does not change episode generation, causal reasoning, scene
direction, or captioning. It loads the already-generated
`renders/tactical_episodes/{depay,locatelli}/*.json` output, runs the
deterministic validators in `src/tactical_validation`, combines them with a
hand-authored football-meaning judgement for each episode (grounded in the raw
event positions -- see the "geometric_evidence" field on every episode), and
writes the eight deliverables requested for this sprint's audit into
`audit/tactical_semantic_review/`.
"""

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.identity_bridge import IdentityResolutionState, resolve_render_target  # noqa: E402
from src.source_selection import PINNED_REVISION, SourceSelectionError, select_source_documents  # noqa: E402
from src.tactical_validation import (  # noqa: E402
    build_position_index,
    run_all_episode_validators,
    validate_causal_transition,
)

OUT = ROOT / "audit" / "tactical_semantic_review"
RENDERS = ROOT / "renders" / "tactical_episodes"
ATTACKING_GOAL_X = 120.0

FIXTURES = {
    "depay": {"match_id": "3869117", "possession_id": 20, "raw": ROOT / "data/depay_goal.json"},
    "locatelli": {"match_id": "3788754", "possession_id": 40, "raw": ROOT / "data/second_goal.json"},
}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")


def _load_fixture(slug: str) -> dict[str, Any]:
    meta = FIXTURES[slug]
    raw_events = json.loads(meta["raw"].read_text())["events"]
    episodes = json.loads((RENDERS / slug / "tactical_episodes.json").read_text())["episodes"]
    directions = json.loads((RENDERS / slug / "scene_directions.json").read_text())["directions"]
    audit_trace = json.loads((RENDERS / slug / "audit_trace.json").read_text())
    scene_plan = json.loads((RENDERS / slug / "scene_plan.json").read_text())
    return {
        "meta": meta,
        "raw_events": raw_events,
        "episodes": episodes,
        "directions": {d["episode_id"]: d for d in directions},
        "audit_trace": {e["episode_id"]: e for e in audit_trace["episodes"]},
        "scenes": {s["episode_id"]: s for s in scene_plan["scenes"] if s.get("type") == "tactical_pause"},
        "all_scenes": scene_plan["scenes"],
        "by_id": {e["id"]: e for e in raw_events},
        "order": {e["id"]: i for i, e in enumerate(raw_events)},
        "name_by_id": {
            **{str(e["player_id"]): e["player"] for e in raw_events if e.get("player_id")},
            **{str(e["recipient_id"]): e["pass_recipient"] for e in raw_events if e.get("recipient_id")},
        },
    }


def _di_maria_status() -> dict[str, Any]:
    open_data = ROOT / "data/open-data/data"
    match_id, possession_id = 3869685, 52
    request = {
        "source_dataset": "statsbomb-open-data",
        "source_revision": PINNED_REVISION,
        "match_id": match_id,
        "possession_id": possession_id,
    }
    try:
        events = json.loads((open_data / f"events/{match_id}.json").read_text())
        frames = json.loads((open_data / f"three-sixty/{match_id}.json").read_text())
        select_source_documents(events, frames, request)
        return {"status": "SELECTED", "detail": "unexpected: selection succeeded"}
    except SourceSelectionError as exc:
        return {
            "status": "REJECTED_UPSTREAM",
            "error_code": str(exc),
            "match_id": match_id,
            "possession_id": possession_id,
            "detail": (
                "select_source_documents() rejects this fixture before any tactical episode, causal, "
                "identity, or render-grounding logic runs. This is the fixture's existing negative-fixture "
                "contract (see tests/test_action_graph.py::test_locatelli_and_depay_succeed_and_di_maria_fails_before_action_graph). "
                "Per instructions this restriction was not bypassed: no tactical episodes exist for Di Maria "
                "to validate, and none of the validators in this audit were run against it."
            ),
        }


def _event_summary(fixture: dict, event_id: str) -> dict[str, Any]:
    event = fixture["by_id"].get(event_id, {})
    return {
        "event_id": event_id,
        "type": event.get("type"),
        "timestamp": event.get("timestamp"),
        "player": event.get("player"),
        "player_id": str(event.get("player_id")) if event.get("player_id") else None,
        "location": event.get("location"),
        "end_location": event.get("pass_end_location") or event.get("carry_end_location") or event.get("shot_end_location"),
    }


def _model_time(fixture: dict, episode: dict) -> dict[str, str | None]:
    start = fixture["by_id"].get(episode["start_event_id"], {})
    end = fixture["by_id"].get(episode["end_event_id"], {})
    return {"start_model_time": start.get("timestamp"), "end_model_time": end.get("timestamp")}


def _names(fixture: dict, ids: list[str]) -> list[dict[str, str | None]]:
    return [{"id": pid, "name": fixture["name_by_id"].get(pid), "is_synthetic_observation": pid.startswith("recon:")} for pid in ids]


# ---------------------------------------------------------------------------
# Hand-authored football-meaning judgement per episode, grounded in the raw
# geometric evidence pulled above. `validity` mirrors the run's PASS/WARN/FAIL
# vocabulary; `WARN` covers episodes whose evidence is internally consistent
# but which fail the tactical-significance bar (zone, stakes) the spec asks
# for; `FAIL` covers episodes whose own evidence contradicts their label.
# ---------------------------------------------------------------------------

DEPAY_JUDGEMENTS = {
    "episode:874d063e70100624": {  # BUILDUP
        "validity": "PASS",
        "why_valid": "Explicit placeholder for pre-tactical circulation; makes no specific tactical claim beyond 'the team is still probing', which the 3-event span (Blind -> Van Dijk pass + carry) supports.",
        "plausible_alternatives": [],
        "why_alternatives_rejected": "BUILDUP is the only type in the catalogue that does not assert a specific mechanism, so it cannot be falsified the way the others can.",
    },
    "episode:283efcb45602010a": {  # ISOLATION
        "validity": "FAIL",
        "why_valid": (
            "INVALID. The 'isolated attacker' the free_man_creation detector fires on is the pass recipient of Van Dijk's "
            "pass at (41.2, 28.7) -> (7.8, 38.8): Andries Noppert, the Netherlands goalkeeper, receiving a backward safety "
            "pass 112m from the opponent's goal. The spec requires an ISOLATION to identify 'the isolated attacker'; the "
            "goalkeeper is not an attacker and this is not an attacking isolation, it is routine defensive-third possession "
            "retention. The detector's free_man_creation signal (no defender within 39m) fires because nobody presses a "
            "goalkeeper receiving the ball in his own third, not because a tactical mismatch was created."
        ),
        "plausible_alternatives": ["BUILDUP (folded into surrounding circulation)", "PRESS_ESCAPE (rejected: no presser was ever close enough to escape)"],
        "why_alternatives_rejected": "BUILDUP is the correct label: this is exactly the 'patient circulation... without yet breaking' the BUILDUP template describes.",
    },
    "episode:9ab6fb5db66ef047": {  # OFF_BALL_RUN
        "validity": "WARN",
        "why_valid": (
            "WEAK. The late_support detector fires because Van Dijk (first touched the ball 12 events earlier, as the very "
            "first pass of the possession) receives again. His net displacement over the span is a lateral drift within the "
            "defensive third (approx. (27.2, 31.9) -> (34.9, 44.6)), not a 'meaningful displacement... that attacks or "
            "creates relevant space' as the spec requires. This is a center-back recycling possession, not a supporting "
            "run into an attacking zone."
        ),
        "plausible_alternatives": ["BUILDUP (folded into surrounding circulation)"],
        "why_alternatives_rejected": "No alternative finding-episode type fits better; the honest label is 'no distinct tactical idea here yet'.",
    },
    "episode:f3ac99e003eee69e": {  # SWITCH_OF_PLAY
        "validity": "FAIL",
        "why_valid": (
            "OBJECTIVELY INVALID. The episode's own evidence states changed_side=false: the pass runs (34.9, 44.6) -> "
            "(41.8, 77.0), staying on the same side of the pitch (y stays >= 40 throughout) and simply advancing the ball "
            "into the right-wide channel to the overlapping fullback Dumfries. lateral_change=32.4m alone triggered the "
            "detector because its confidence formula is lateral-distance-only once above threshold; it does not require "
            "changed_side to be true. This is progression to a flank, not a switch of the point of attack."
        ),
        "plausible_alternatives": ["WIDE_PROGRESSION (weak: still deep, minimal forward-x progress)", "BUILDUP"],
        "why_alternatives_rejected": "WIDE_PROGRESSION requires the receiver to meaningfully stretch an engaged defense; at (41.8, 77.0) in the middle third this is not yet threatening. BUILDUP is the honest label.",
    },
    "episode:e869ff80d404c7d9": {  # CUTBACK
        "validity": "FAIL",
        "why_valid": (
            "SEVERELY INVALID. The decisive pass (26.8, 63.9) -> (8.8, 38.5) is received by Andries Noppert -- the "
            "Netherlands GOALKEEPER -- 111m from the opponent's goal. backward_x=18.0 satisfied the cutback_candidate "
            "threshold purely on y-zone geometry (from_wide_zone / target_central) and raw backward distance, with zero "
            "constraint on proximity to the attacking goal. A cutback must satisfy an origin-zone AND receiving-zone "
            "requirement near the box (spec Section 1); this pass's receiving zone is the team's own penalty area, not "
            "the opponent's. The caption 'Creates a more central, lower-angle opportunity than continuing forward' is "
            "false for this instance: the pass creates no scoring opportunity, it returns the ball to the keeper."
        ),
        "plausible_alternatives": ["BUILDUP (folded into surrounding circulation)"],
        "why_alternatives_rejected": (
            "The real cutback of this possession occurs later and unlabelled: Dumfries' pass (108.7, 68.3) -> (104.9, 43.7), "
            "backward_x=3.8, from a wide zone into the box, immediately received by Depay who scores. It satisfies both "
            "cutback_candidate (confidence 0.64) and box_arrival (confidence 0.75) but lost the MAX_FINDING_EPISODES=4 cap "
            "to four defensive-third patterns that saturated to confidence 1.0 -- see root-cause report."
        ),
    },
    "episode:2785afffc30cf649": {  # FINISH
        "validity": "WARN",
        "why_valid": (
            "The FINISH label itself is defensible (a shot did conclude the possession), but its 37-event span silently "
            "absorbs the possession's actual decisive mechanism -- Gakpo's progressive carry (62.9, 37.0) -> (81.2, 52.0), "
            "his pass to Dumfries in the box, and Dumfries' cutback pass to Depay -- without surfacing any of it as its "
            "own episode. The caption 'The build-up concludes with a shot' and cause 'The build-up concludes with a shot' "
            "are true but tactically empty: they do not identify the mechanism that actually created the goal."
        ),
        "plausible_alternatives": ["Split into BOX_ARRIVAL/CUTBACK (Dumfries -> Depay) + FINISH (Depay's shot)"],
        "why_alternatives_rejected": "See corrected sequence: this split is the corrected recommendation, not a rejected alternative.",
    },
}

LOCATELLI_JUDGEMENTS = {
    "episode:9f53225404c3a0cb": {  # BUILDUP
        "validity": "PASS",
        "why_valid": "Single-event placeholder (Donnarumma carry) before the first pattern hit; makes no falsifiable tactical claim.",
        "plausible_alternatives": [],
        "why_alternatives_rejected": "n/a",
    },
    "episode:a7f121e0cf4571fd": {  # ISOLATION
        "validity": "FAIL",
        "why_valid": (
            "INVALID, same defect as Depay. Donnarumma's pass (8.8, 26.7) -> (17.1, 40.9) is received by Leonardo "
            "Bonucci, a center-back, 103m from the opponent's goal, during a routine goalkeeper distribution. No defender "
            "presses a goalkeeper's outlet pass in the defensive third; that absence of pressure is not an attacking "
            "isolation."
        ),
        "plausible_alternatives": ["BUILDUP"],
        "why_alternatives_rejected": "BUILDUP is the honest label for this circulation.",
    },
    "episode:f84f5d48a3d06af8": {  # CUTBACK
        "validity": "FAIL",
        "why_valid": (
            "INVALID, same defect as Depay's CUTBACK. The decisive pass (41.7, 72.1) -> (25.9, 49.9) is a backward pass "
            "from Di Lorenzo back to Bonucci in the middle/defensive third, 94m from goal -- not a pull-back from the "
            "byline into the box. backward_x=15.8 and the wide-then-central y-geometry satisfied the detector with no "
            "notion of pitch zone."
        ),
        "plausible_alternatives": ["BUILDUP"],
        "why_alternatives_rejected": (
            "The real cutback-shaped ball of this possession is Berardi's pass (117.4, 55.5) -> (116.2, 39.2) into "
            "Locatelli in the box for the shot, but it fails the detector's own from_wide_zone (|55.5-40|=15.5 < 22) and "
            "backward_x (1.2 < 3.0) thresholds, so it is not classified as anything at all -- see root-cause report."
        ),
    },
    "episode:d98b2e3d758a88c4": {  # SWITCH_OF_PLAY
        "validity": "WARN",
        "why_valid": (
            "Internally consistent (changed_side=true, unlike Depay's instance) but tactically insignificant: the pass "
            "(28.0, 49.9) -> (35.2, 25.8) happens between Bonucci and Acerbi, two central defenders, still inside Italy's "
            "own half with negligible forward progress toward goal. It is a genuine side change by the letter of the "
            "detector, but does not 'unbalance the defense' in any dangerous sense, so the caption overstates its stakes."
        ),
        "plausible_alternatives": ["BUILDUP"],
        "why_alternatives_rejected": "Downgraded rather than rejected outright: unlike Depay's case, the evidence does not contradict the label, only its significance.",
    },
    "episode:e0f5c262eb612cd4": {  # OFF_BALL_RUN
        "validity": "WARN",
        "why_valid": (
            "Same defect as Depay's OFF_BALL_RUN. Acerbi 'reappears' 12 events after his first involvement, but his span "
            "(35.2, 25.8) -> (29.5, 45.5) nets -5.7m of goal-distance progress: lateral repositioning during circulation, "
            "not a run that attacks or creates relevant space."
        ),
        "plausible_alternatives": ["BUILDUP"],
        "why_alternatives_rejected": "No stronger alternative finding exists for this span.",
    },
    "episode:e6e35b12273b76b8": {  # FINISH
        "validity": "WARN",
        "why_valid": (
            "Same defect as Depay's FINISH: its 32-event span absorbs the actual decisive mechanism -- Locatelli's "
            "raking switch to Berardi (46.1, 40.2) -> (74.3, 79.6), Berardi's driving carry into the box "
            "(74.3, 79.6) -> (117.4, 55.5), and his pass back to Locatelli for the shot -- without surfacing any of it."
        ),
        "plausible_alternatives": ["Split into BOX_ARRIVAL (Berardi's carry) + FINISH (pass back + shot)"],
        "why_alternatives_rejected": "See corrected sequence: this split is the corrected recommendation.",
    },
}

JUDGEMENTS = {"depay": DEPAY_JUDGEMENTS, "locatelli": LOCATELLI_JUDGEMENTS}

CORRECTED_SEQUENCES = {
    "depay": {
        "original_sequence": ["BUILDUP", "ISOLATION", "OFF_BALL_RUN", "SWITCH_OF_PLAY", "CUTBACK", "FINISH"],
        "corrected_sequence": ["BUILDUP", "CUTBACK", "FINISH"],
        "corrected_episodes": [
            {
                "episode_type": "BUILDUP",
                "span_event_ids": "df062304-317d-4ecc-940e-848563aa6140 .. 108.7,68.3 pass start (idx 308-368)",
                "rationale": "Absorbs the original ISOLATION, OFF_BALL_RUN, SWITCH_OF_PLAY, and CUTBACK episodes: none clear the tactical-significance bar (all occur in the defensive/middle third with no meaningful goal-distance progress; two anchor on passes received by the goalkeeper).",
            },
            {
                "episode_type": "CUTBACK",
                "span_event_ids": "Dumfries pass (108.7,68.3) -> (104.9,43.7)",
                "rationale": "The possession's actual cutback: backward_x=3.8, played from a wide zone (|68.3-40|=28.3) into the box, immediately received by the scorer.",
            },
            {
                "episode_type": "FINISH",
                "span_event_ids": "Depay ball receipt + shot (idx 370-371)",
                "rationale": "Unchanged in kind, but now correctly scoped to just the finish, since the mechanism that created it is its own episode.",
            },
        ],
    },
    "locatelli": {
        "original_sequence": ["BUILDUP", "ISOLATION", "CUTBACK", "SWITCH_OF_PLAY", "OFF_BALL_RUN", "FINISH"],
        "corrected_sequence": ["BUILDUP", "BOX_ARRIVAL", "FINISH"],
        "corrected_episodes": [
            {
                "episode_type": "BUILDUP",
                "span_event_ids": "Donnarumma carry .. Locatelli's switch pass to Berardi (idx 1043-1085)",
                "rationale": "Absorbs the original ISOLATION, CUTBACK, SWITCH_OF_PLAY, and OFF_BALL_RUN episodes for the same reason as Depay: none clear the tactical-significance bar.",
            },
            {
                "episode_type": "BOX_ARRIVAL",
                "span_event_ids": "Berardi carry (74.3,79.6) -> (117.4,55.5)",
                "rationale": "The possession's actual decisive action: a driving carry from the switch reception directly into the penalty area. Already detected by the existing box_arrival detector (confidence 0.75) but discarded by the confidence-based episode cap.",
            },
            {
                "episode_type": "FINISH",
                "span_event_ids": "Berardi pass to Locatelli + shot (idx 1090-1092)",
                "rationale": "Correctly scoped to the pass-back and shot; the box entry that created it is now its own episode.",
            },
        ],
    },
}


def _build_episode_audit(slug: str, fixture: dict) -> list[dict[str, Any]]:
    entries = []
    for episode in fixture["episodes"]:
        eid = episode["episode_id"]
        direction = fixture["directions"][eid]
        trace = fixture["audit_trace"][eid]
        judgement = JUDGEMENTS[slug][eid]
        entries.append(
            {
                "episode_id": eid,
                "episode_type": episode["episode_type"],
                **_model_time(fixture, episode),
                "participating_event_ids": episode["participating_action_ids"],
                "participating_action_graph_node_ids": None,
                "action_graph_linkage_gap": (
                    "No linkage exists: TacticalEpisode.participating_action_ids are raw StatsBomb event UUIDs from the "
                    "legacy pipeline (src/ingest/possession_loader.py); action_graph.ActionNode.node_id is a sha256 of "
                    "(recognition_id, action_type) from the separate formal pipeline. Neither pipeline references the "
                    "other's identifiers. See identity_bridge_audit.json for the same gap applied to player identity."
                ),
                "primary_actors": _names(fixture, episode["primary_actor_ids"]),
                "relevant_defenders": _names(fixture, episode["relevant_defender_ids"]),
                "detector_evidence": episode["evidence"],
                "geometric_evidence": {
                    "event_trace": [_event_summary(fixture, eid_) for eid_ in episode["participating_action_ids"] if fixture["by_id"].get(eid_, {}).get("location")],
                },
                "confidence": episode["confidence"],
                "validity": judgement["validity"],
                "why_valid_or_invalid": judgement["why_valid"],
                "plausible_alternative_classifications": judgement["plausible_alternatives"],
                "why_alternatives_rejected": judgement["why_alternatives_rejected"],
                "opponents_retained": trace["opponents_retained"],
                "scene_visible_players": direction["visible_players"],
                "scene_highlighted_players": direction["highlighted_players"],
            }
        )
    return entries


def _build_causal_graph(slug: str, fixture: dict) -> dict[str, Any]:
    episodes = fixture["episodes"]
    original_edges = []
    for a, b in zip(episodes, episodes[1:]):
        edge = {
            "source_episode_id": a["episode_id"],
            "target_episode_id": b["episode_id"],
            "relation": "IMPLIED_BY_ADJACENCY_ONLY",
            "supporting_evidence": {"adjacent": True},
            "confidence": 0.0,
        }
        result = validate_causal_transition(edge)
        original_edges.append({**edge, "validator_outcome": result.outcome.value, "validator_detail": result.detail})

    corrected_edges = []
    if slug == "depay":
        corrected_edges = [
            {
                "source_episode_id": "corrected:BUILDUP",
                "target_episode_id": "corrected:CUTBACK",
                "relation": "ENABLES",
                "created_intermediate_advantage": "Possession is retained and progressed to a wide, advanced position without turnover, making a delivery into the box possible.",
                "supporting_evidence": {"no_turnover_in_span": True, "possession_retained_events": 61},
                "confidence": 0.4,
                "note": "Low confidence: 'possession was not lost' is necessary but not sufficient evidence of enabling the cutback specifically; no defender-displacement or space-creation measurement exists in current data.",
            },
            {
                "source_episode_id": "corrected:CUTBACK",
                "target_episode_id": "corrected:FINISH",
                "relation": "CREATES",
                "created_intermediate_advantage": "A pass from a wide attacking position lands inside the penalty area directly at the scorer's feet, immediately followed by the shot.",
                "supporting_evidence": {"end_position_in_box": True, "immediate_next_event_is_shot": True, "backward_x": 3.8},
                "confidence": 0.85,
            },
        ]
    else:
        corrected_edges = [
            {
                "source_episode_id": "corrected:BUILDUP",
                "target_episode_id": "corrected:BOX_ARRIVAL",
                "relation": "ENABLES",
                "created_intermediate_advantage": "Possession is retained and switched to Berardi in space, making the driving carry into the box possible.",
                "supporting_evidence": {"no_turnover_in_span": True, "possession_retained_events": 42},
                "confidence": 0.4,
                "note": "Same low-confidence caveat as Depay's BUILDUP->CUTBACK edge.",
            },
            {
                "source_episode_id": "corrected:BOX_ARRIVAL",
                "target_episode_id": "corrected:FINISH",
                "relation": "CREATES",
                "created_intermediate_advantage": "The carry ends inside the penalty area; the very next action is a pass back to the arriving midfielder who shoots immediately.",
                "supporting_evidence": {"end_position_in_box": True, "immediate_next_event_is_pass_then_shot": True},
                "confidence": 0.8,
            },
        ]

    return {
        "schema_id": "tip.tactical_semantic_review.causal_graph",
        "fixture": slug,
        "original_sequence_transitions": original_edges,
        "original_sequence_verdict": (
            "Every adjacent pair in the originally generated sequence is supported only by chronological adjacency. "
            "None of CREATES/ENABLES/FORCES/OPENS/ATTRACTS/RELEASES/EXPLOITS/FINISHES can be asserted between them "
            "with the evidence the episodes themselves carry (each episode's `evidence` field describes only its own "
            "internal pattern, never how it caused the next episode's outcome). All original transitions are REJECTED."
        ),
        "corrected_sequence_transitions": corrected_edges,
    }


def _build_identity_bridge_audit(slug: str, fixture: dict) -> dict[str, Any]:
    records = []
    for episode in fixture["episodes"]:
        direction = fixture["directions"][episode["episode_id"]]
        visible = tuple(direction["visible_players"])
        for pid in episode["relevant_defender_ids"]:
            resolution = resolve_render_target(pid, visible)
            records.append(
                {
                    "episode_id": episode["episode_id"],
                    "episode_type": episode["episode_type"],
                    "defender_id": pid,
                    "resolution_state": resolution.state.value,
                    "reason": resolution.reason,
                    "renderer_displayed_intended_player": resolution.state != IdentityResolutionState.UNRESOLVED,
                }
            )
    return {
        "schema_id": "tip.tactical_semantic_review.identity_bridge_audit",
        "fixture": slug,
        "bridge_contract": {
            "module": "src/identity_bridge.py",
            "states": ["AUTHENTICATED_TRACK", "OBSERVATION_ONLY", "AMBIGUOUS_TRACK_SET", "UNRESOLVED"],
            "does_not_redesign_reconstruction": True,
            "does_not_fabricate_identity": True,
            "summary": (
                "Legacy-pipeline `relevant_defender_ids` are always `recon:{event_id}:{idx}` synthetic freeze-frame "
                "snapshot ids (src/ingest/possession_loader.py), which resolve_identity() classifies as OBSERVATION_ONLY: "
                "single-observation-scoped, no cross-event persistence. `primary_actor_ids` are raw StatsBomb player_ids, "
                "which resolve to AUTHENTICATED_TRACK. No AMBIGUOUS_TRACK_SET or UNRESOLVED case is produced by the "
                "current builder because it always emits exactly one nearest-defender id per episode rather than "
                "surfacing genuine ambiguity or absence -- see identity_gap_findings."
            ),
        },
        "identity_gap_findings": [
            "Reconstruction/world-model identity (src/world_model.py: IDENTIFIED/OBSERVATION_SCOPED, per-state lifecycle) "
            "and action-graph event_id space are entirely disconnected from the legacy tactical_episodes/tactical_relevance "
            "pipeline's tracking_id space; there is no code path that could resolve a legacy `recon:` id back to a "
            "world-model entity even if one existed.",
            "The tactical_episodes builder always returns exactly one relevant_defender_id (the single nearest defender) "
            "even when the evidence for that pick is weak (see e.g. SWITCH_OF_PLAY/CUTBACK 'defender controlling the "
            "passing lane' entries retained at relevance_score=0.0 in audit_trace.json) -- the bridge contract's "
            "AMBIGUOUS_TRACK_SET state exists to let a future caller represent that honestly instead of forcing a single "
            "pick.",
        ],
        "defender_resolution_records": records,
    }


def _build_render_grounding_audit(slug: str, fixture: dict) -> dict[str, Any]:
    entries = []
    for episode in fixture["episodes"]:
        eid = episode["episode_id"]
        direction = fixture["directions"][eid]
        scene = fixture["scenes"][eid]
        checks = []

        visible = set(direction["visible_players"])
        actor_missing = [a for a in episode["primary_actor_ids"] if a not in visible]
        checks.append({"check": "primary_actor_visible", "outcome": "FAIL" if actor_missing else "PASS", "detail": f"missing: {actor_missing}" if actor_missing else "all primary actors listed in visible_players"})

        defender_dependent = episode["episode_type"] in {"ISOLATION", "CUTBACK", "SWITCH_OF_PLAY", "PRESS_ESCAPE", "OVERLOAD"}
        defender_missing = [d for d in episode["relevant_defender_ids"] if d not in visible] if defender_dependent else []
        checks.append(
            {
                "check": "named_defender_visible_when_message_depends_on_them",
                "outcome": "FAIL" if defender_missing else ("PASS" if defender_dependent else "N/A"),
                "detail": f"missing: {defender_missing}" if defender_missing else "n/a or satisfied",
            }
        )

        checks.append(
            {
                "check": "tactically_relevant_space_in_viewport",
                "outcome": "WARN",
                "detail": (
                    "camera_intent is a symbolic label (e.g. 'track_switch_across_pitch'), not a numeric viewport bound; "
                    "this audit cannot deterministically verify pixel-level containment from the scene plan alone. "
                    "Downgraded to WARN rather than asserting an unverifiable PASS."
                ),
            }
        )

        overlay_evidence_ok = True
        overlay_detail = "primary_overlay is consistent with the episode's evidence type"
        if episode["episode_type"] == "SWITCH_OF_PLAY" and episode["evidence"].get("feature_values", {}).get("changed_side") is not True:
            overlay_evidence_ok = False
            overlay_detail = "primary_overlay draws a switch-of-play pass arrow, but the episode's own evidence shows changed_side=False"
        checks.append({"check": "primary_overlay_matches_episode_evidence", "outcome": "PASS" if overlay_evidence_ok else "FAIL", "detail": overlay_detail})

        caption_timing_ok = scene["caption_timing"]["lead_seconds"] <= scene["duration_seconds"]
        checks.append(
            {
                "check": "caption_before_or_during_action",
                "outcome": "PASS" if caption_timing_ok else "FAIL",
                "detail": f"lead_seconds={scene['caption_timing']['lead_seconds']}, duration_seconds={scene['duration_seconds']}",
            }
        )

        checks.append(
            {
                "check": "scene_visible_long_enough_to_understand",
                "outcome": "PASS" if scene["duration_seconds"] >= 1.0 else "WARN",
                "detail": f"duration_seconds={scene['duration_seconds']}",
            }
        )

        judgement = JUDGEMENTS[slug][eid]
        checks.append(
            {
                "check": "claimed_tactical_concept_is_visually_observable",
                "outcome": "FAIL" if judgement["validity"] == "FAIL" else ("WARN" if judgement["validity"] == "WARN" else "PASS"),
                "detail": "inherits the episode's semantic validity finding: a scene cannot visually ground a tactical claim that the underlying evidence does not support, regardless of what is rendered on screen.",
            }
        )

        overall = "FAIL" if any(c["outcome"] == "FAIL" for c in checks) else ("WARN" if any(c["outcome"] == "WARN" for c in checks) else "PASS")
        entries.append({"episode_id": eid, "episode_type": episode["episode_type"], "scene_id": scene["scene_id"], "checks": checks, "overall": overall})
    return {"schema_id": "tip.tactical_semantic_review.render_grounding_audit", "fixture": slug, "scenes": entries}


def _build_caption_evidence_audit(slug: str, fixture: dict) -> dict[str, Any]:
    entries = []
    for episode in fixture["episodes"]:
        eid = episode["episode_id"]
        judgement = JUDGEMENTS[slug][eid]
        caption = f"{episode['cause']} {episode['created_advantage']}".strip()
        overstates = judgement["validity"] in {"FAIL", "WARN"}
        entries.append(
            {
                "episode_id": eid,
                "episode_type": episode["episode_type"],
                "caption": caption,
                "traced_to_episode_id": eid,
                "traced_to_causal_relation": None,
                "causal_relation_gap": "No causal relation exists to trace to; see causal_graph.json (original_sequence_verdict).",
                "supporting_event_ids": episode["participating_action_ids"],
                "supporting_observation_frames": "not applicable in the legacy pipeline (no frame-id-scoped observation records; evidence is StatsBomb event + freeze-frame derived)",
                "confidence": episode["confidence"],
                "caption_is_static_template": True,
                "caption_template_note": (
                    "This caption is not computed from this instance's evidence; it is looked up verbatim from "
                    "src/tactical_episodes/engine.py::_TEMPLATES by episode_type. Every episode of this type in every "
                    "fixture receives the identical sentence regardless of its actual geometry."
                ),
                "overstates_evidence": overstates,
                "overstatement_detail": judgement["why_valid"] if overstates else None,
                "corrected_caption_intent": (
                    None
                    if judgement["validity"] == "PASS"
                    else "Do not caption this instance as its current type; fold into the surrounding BUILDUP with no specific tactical claim (see corrected sequence)."
                ),
                "implies_unobservable_intent": episode["episode_type"] in {"ISOLATION", "CUTBACK", "SWITCH_OF_PLAY"} and overstates,
                "names_unreliably_resolved_player": any(pid.startswith("recon:") for pid in episode["relevant_defender_ids"]),
                "describes_outcome_before_it_occurs": False,
                "claims_defensive_manipulation_without_evidence": episode["episode_type"] == "SWITCH_OF_PLAY"
                and "Defenders must shift across the pitch" in caption
                and overstates,
            }
        )
    return {"schema_id": "tip.tactical_semantic_review.caption_evidence_audit", "fixture": slug, "captions": entries}


def main() -> None:
    di_maria = _di_maria_status()
    fixtures = {slug: _load_fixture(slug) for slug in FIXTURES}

    episode_semantic_audit = {
        "schema_id": "tip.tactical_semantic_review.episode_semantic_audit",
        "di_maria": di_maria,
        "fixtures": {slug: {"match_id": FIXTURES[slug]["match_id"], "possession_id": FIXTURES[slug]["possession_id"], "episodes": _build_episode_audit(slug, fx)} for slug, fx in fixtures.items()},
    }
    causal_graph = {"schema_id": "tip.tactical_semantic_review.causal_graph", "di_maria": di_maria, "fixtures": {slug: _build_causal_graph(slug, fx) for slug, fx in fixtures.items()}}
    identity_bridge_audit = {"schema_id": "tip.tactical_semantic_review.identity_bridge_audit", "di_maria": di_maria, "fixtures": {slug: _build_identity_bridge_audit(slug, fx) for slug, fx in fixtures.items()}}
    render_grounding_audit = {"schema_id": "tip.tactical_semantic_review.render_grounding_audit", "di_maria": di_maria, "fixtures": {slug: _build_render_grounding_audit(slug, fx) for slug, fx in fixtures.items()}}
    caption_evidence_audit = {"schema_id": "tip.tactical_semantic_review.caption_evidence_audit", "di_maria": di_maria, "fixtures": {slug: _build_caption_evidence_audit(slug, fx) for slug, fx in fixtures.items()}}

    automated_validator_report = {
        "schema_id": "tip.tactical_semantic_review.automated_validator_report",
        "di_maria": di_maria,
        "fixtures": {},
    }
    for slug, fx in fixtures.items():
        results = run_all_episode_validators(fx["episodes"], fx["directions"], fx["raw_events"], attacking_goal_x=ATTACKING_GOAL_X)
        automated_validator_report["fixtures"][slug] = {
            "counts": {
                "PASS": sum(r.outcome.value == "PASS" for r in results),
                "WARN": sum(r.outcome.value == "WARN" for r in results),
                "FAIL": sum(r.outcome.value == "FAIL" for r in results),
            },
            "results": [{"check": r.check, "subject_id": r.subject_id, "outcome": r.outcome.value, "detail": r.detail, "evidence": r.evidence} for r in results],
        }

    _write(OUT / "episode_semantic_audit.json", episode_semantic_audit)
    _write(OUT / "causal_graph.json", causal_graph)
    _write(OUT / "identity_bridge_audit.json", identity_bridge_audit)
    _write(OUT / "render_grounding_audit.json", render_grounding_audit)
    _write(OUT / "caption_evidence_audit.json", caption_evidence_audit)
    _write(OUT / "automated_validator_report.json", automated_validator_report)
    _write(OUT / "corrected_episode_sequences.json", {"schema_id": "tip.tactical_semantic_review.corrected_sequences", "di_maria": di_maria, "fixtures": CORRECTED_SEQUENCES})

    print("Wrote audit deliverables to", OUT)
    for slug in fixtures:
        counts = automated_validator_report["fixtures"][slug]["counts"]
        print(f"  {slug}: automated validators PASS={counts['PASS']} WARN={counts['WARN']} FAIL={counts['FAIL']}")


if __name__ == "__main__":
    main()
