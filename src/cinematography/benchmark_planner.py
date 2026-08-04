from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from src.reconstruction import validate_reconstruction


SCHEMA_ID = "tip.benchmark_cinematography_plan"
CONTRACT_VERSION = "0.1.0"
SUPPORTED_CHAINS = {
    ("PASS", "BALL_RECEIPT", "SHOT"): "FAST_COMBINATION",
    ("PASS", "BALL_RECEIPT", "CARRY", "SHOT"): "CARRY_FINISH",
    ("PASS", "BALL_RECEIPT", "CARRY", "PASS", "BALL_RECEIPT", "SHOT"): "TWO_STAGE_BUILDUP",
}


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _beat(
    beat_id: str,
    kind: str,
    start: float,
    end: float,
    *,
    event_ids: list[str],
    primary_location: list[float] | None,
    secondary_location: list[float] | None = None,
    intention: str,
) -> dict[str, Any]:
    return {
        "beat_id": beat_id,
        "kind": kind,
        "source_start": round(max(0.0, start), 6),
        "source_end": round(max(start, end), 6),
        "event_ids": event_ids,
        "primary_location": primary_location,
        "secondary_location": secondary_location,
        "intention": intention,
    }


def build_benchmark_cinematography_plan(reconstruction: dict[str, Any]) -> dict[str, Any]:
    """Build the intentionally narrow Goals 1-3 directing plan.

    No generic event-family fallback is provided: an unsupported action chain is
    rejected so the vertical slice cannot silently become a broad planner.
    """
    validate_reconstruction(reconstruction)
    events = reconstruction["events"]
    chain = tuple(str(event["action"]) for event in events)
    strategy = SUPPORTED_CHAINS.get(chain)
    if strategy is None:
        raise ValueError(f"UNSUPPORTED_BENCHMARK_ACTION_CHAIN:{','.join(chain)}")

    beats: list[dict[str, Any]] = []
    first = events[0]
    beats.append(_beat(
        "beat_01", "ESTABLISH", 0.0, min(0.35, float(first.get("duration_seconds") or 0.35)),
        event_ids=[first["event_id"]], primary_location=first.get("ball_start"),
        secondary_location=first.get("ball_end"), intention="ORIENT_OWNER_RECEIVER_AND_ATTACKING_DIRECTION",
    ))

    index = 2
    for event_index, event in enumerate(events):
        action = event["action"]
        timestamp = float(event["timestamp"])
        duration = float(event.get("duration_seconds") or 0.0)
        next_event = events[event_index + 1] if event_index + 1 < len(events) else None
        if action == "PASS":
            beats.append(_beat(
                f"beat_{index:02d}", "PASS_HANDOFF", timestamp, timestamp + duration,
                event_ids=[event["event_id"]] + ([next_event["event_id"]] if next_event and next_event["action"] == "BALL_RECEIPT" else []),
                primary_location=event.get("ball_start"), secondary_location=event.get("ball_end"),
                intention="TRANSFER_ATTENTION_FROM_PASSER_TO_VERIFIED_RECEIVER",
            ))
            index += 1
        elif action == "BALL_RECEIPT":
            beats.append(_beat(
                f"beat_{index:02d}", "RECEIPT", timestamp, timestamp + 0.125,
                event_ids=[event["event_id"]], primary_location=event.get("ball_start"),
                intention="MAKE_CHANGE_OF_PROTAGONIST_LEGIBLE",
            ))
            index += 1
        elif action == "CARRY":
            beats.append(_beat(
                f"beat_{index:02d}", "CARRY", timestamp, timestamp + duration,
                event_ids=[event["event_id"]], primary_location=event.get("ball_start"),
                secondary_location=event.get("ball_end"), intention="KEEP_ACTOR_AND_BALL_AS_ONE_FOCAL_UNIT",
            ))
            index += 1
        elif action == "SHOT":
            beats.append(_beat(
                f"beat_{index:02d}", "SHOT", timestamp, timestamp + duration,
                event_ids=[event["event_id"]], primary_location=event.get("ball_start"),
                secondary_location=event.get("ball_end"), intention="PRESERVE_SHOOTER_BALL_GOAL_RELATIONSHIP",
            ))
            index += 1

    last = events[-1]
    last_end = float(last["timestamp"]) + float(last.get("duration_seconds") or 0.0)
    beats.append(_beat(
        f"beat_{index:02d}", "OUTCOME_HOLD", last_end, min(float(reconstruction["duration"]), last_end + 0.35),
        event_ids=[last["event_id"]], primary_location=last.get("ball_end"),
        intention="LET_THE_GOAL_REGISTER",
    ))

    receipt_times = [float(event["timestamp"]) for event in events if event["action"] == "BALL_RECEIPT"]
    # Goal 2 is the clarity control: less intervention. The compressed Goals 1
    # and 3 receive a longer perceptual separation at receipt.
    receipt_hold = 0.08 if strategy == "CARRY_FINISH" else 0.18
    holds = [{"source_time": round(value, 6), "duration": receipt_hold, "reason": "RECEIPT_EMPHASIS"} for value in receipt_times]
    holds.append({"source_time": round(last_end, 6), "duration": 0.8, "reason": "OUTCOME_HOLD"})

    selection = reconstruction.get("window_selection") or {}
    selection_start = float(selection.get("start_timestamp", reconstruction["start_timestamp"]))
    source_offset = float(reconstruction["start_timestamp"]) - selection_start
    base_duration = float(selection.get("duration_seconds", reconstruction["duration"]))
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "contract_version": CONTRACT_VERSION,
        "reconstruction_sha256": reconstruction["sha256"],
        "strategy": strategy,
        "action_chain": list(chain),
        "beats": beats,
        "timing": {
            "base_presentation_duration": base_duration,
            "source_offset": source_offset,
            "holds": holds,
            "presentation_duration": base_duration + sum(float(hold["duration"]) for hold in holds),
        },
        "renderer_policy": {
            "ball_visibility": "ADAPTIVE_HALO_AND_MINIMUM_SCREEN_SIZE",
            "player_emphasis": "PRIMARY_AND_INCOMING_RECEIVER",
            "camera": "BEAT_DIRECTED_CONTINUOUS_FRAME",
            "cuts": False,
        },
        "scope": "VIEWER_BENCHMARK_GOALS_1_TO_3_ONLY",
    }
    payload["sha256"] = sha256(_canonical(payload)).hexdigest()
    return payload


def source_time_at(plan: dict[str, Any], presentation_time: float, reconstruction_duration: float) -> float:
    """Map editorial time to immutable reconstruction time using frame holds."""
    timing = plan["timing"]
    source_offset = float(timing["source_offset"])
    base_presentation = max(0.0, float(presentation_time))
    accumulated = 0.0
    for hold in timing["holds"]:
        hold_base_time = float(hold["source_time"]) + source_offset
        hold_start = hold_base_time + accumulated
        hold_duration = float(hold["duration"])
        if base_presentation < hold_start:
            break
        if base_presentation <= hold_start + hold_duration:
            return min(reconstruction_duration, max(0.0, float(hold["source_time"])))
        accumulated += hold_duration
    return min(reconstruction_duration, max(0.0, base_presentation - accumulated - source_offset))
