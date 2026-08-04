from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SUPPORTED_ACTIONS = {
    "Pass": "PASS",
    "Ball Receipt*": "BALL_RECEIPT",
    "Carry": "CARRY",
    "Shot": "SHOT",
}


@dataclass(frozen=True)
class WindowConfig:
    target_min_seconds: float = 3.0
    target_max_seconds: float = 8.0
    hard_max_seconds: float = 12.0
    maximum_observation_gap_seconds: float = 4.0
    maximum_interpolation_seconds: float = 3.0
    maximum_anonymous_association_gap_seconds: float = 2.5
    maximum_authenticated_association_gap_seconds: float = 4.0
    maximum_player_speed_mps: float = 9.5
    maximum_player_displacement_m: float = 28.5
    observed_support_seconds: float = 0.125
    unknown_rejection_percentage: float = 55.0
    maximum_track_fragmentation_ratio: float = 2.0
    quality_sample_hz: int = 8


def window_config(config: dict[str, Any] | None) -> WindowConfig:
    values = (config or {}).get("reconstruction_window", {})
    return WindowConfig(**{
        field: type(getattr(WindowConfig, field))(values.get(field, getattr(WindowConfig, field)))
        for field in WindowConfig.__dataclass_fields__
    })


def select_reconstruction_window(
    match: dict[str, Any],
    *,
    event_id: str | None = None,
    event_index: int | None = None,
    sequence_end_event_id: str | None = None,
    pre_roll_seconds: float = 1.0,
    post_roll_seconds: float = 1.0,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select a reconstructable source window without tactical ranking."""
    resolved = window_config(config)
    events = sorted(match.get("events", []), key=lambda event: (float(event["timestamp"]), int(event.get("index", 0))))
    anchor = next((event for event in events if event_id is not None and str(event["id"]) == str(event_id)), None)
    if anchor is None and event_index is not None:
        anchor = next((event for event in events if int(event.get("index", -1)) == int(event_index)), None)
    if anchor is None:
        return _rejected("REJECTED_UNSUPPORTED_ACTION", "ANCHOR_EVENT_NOT_FOUND", event_id, event_index)
    action = SUPPORTED_ACTIONS.get(str(anchor.get("type")))
    if action is None:
        return _rejected("REJECTED_UNSUPPORTED_ACTION", f"UNSUPPORTED_ACTION:{anchor.get('type')}", event_id, event_index)
    period = anchor.get("period")
    end_event = anchor
    if sequence_end_event_id is not None:
        end_event = next((event for event in events if str(event["id"]) == str(sequence_end_event_id)), None)
        if end_event is None:
            return _rejected("REJECTED_UNSUPPORTED_ACTION", "SEQUENCE_END_EVENT_NOT_FOUND", event_id, event_index)
        if end_event.get("period") != period:
            return _rejected("REJECTED_PERIOD_BOUNDARY", "SEQUENCE_CROSSES_PERIOD", event_id, event_index)
    start = max(float(anchor["timestamp"]) - max(0.0, pre_roll_seconds), min(float(event["timestamp"]) for event in events if event.get("period") == period))
    end_anchor = float(end_event["timestamp"]) + max(0.0, float(end_event.get("duration") or 0.0))
    end = min(end_anchor + max(0.0, post_roll_seconds), max(float(event["timestamp"]) + max(0.0, float(event.get("duration") or 0.0)) for event in events if event.get("period") == period))
    if end - start > resolved.hard_max_seconds:
        return _rejected("REJECTED_EXCESSIVE_GAP", f"WINDOW_DURATION_EXCEEDS_{resolved.hard_max_seconds:.3f}s", event_id, event_index)
    selected = [event for event in events if event.get("period") == period and start <= float(event["timestamp"]) <= end and str(event.get("type")) in SUPPORTED_ACTIONS]
    if not selected:
        return _rejected("REJECTED_INSUFFICIENT_OBSERVATION", "NO_SUPPORTED_EVENTS_IN_WINDOW", event_id, event_index)
    frame_ids = {frame["event_id"] for frame in match.get("frames", []) if frame.get("players")}
    supported_frames = [event for event in selected if event["id"] in frame_ids]
    gaps = [float(right["timestamp"]) - float(left["timestamp"]) for left, right in zip(supported_frames, supported_frames[1:])]
    longest_gap = max(gaps, default=0.0)
    if len(supported_frames) < 2:
        admission = "REJECTED_INSUFFICIENT_OBSERVATION"
        reasons = ["FEWER_THAN_TWO_360_OBSERVATIONS"]
    elif longest_gap > resolved.maximum_observation_gap_seconds:
        admission = "REJECTED_EXCESSIVE_GAP"
        reasons = [f"OBSERVATION_GAP_{longest_gap:.3f}s_EXCEEDS_{resolved.maximum_observation_gap_seconds:.3f}s"]
    elif match.get("source_validation_errors"):
        admission = "REJECTED_INSUFFICIENT_OBSERVATION"
        reasons = list(match["source_validation_errors"])
    else:
        admission = "ACCEPTED"
        reasons = []
    return {
        "schema_id": "tip.reconstruction_window_selection",
        "contract_version": "1.0.0",
        "admission": admission,
        "reasons": reasons,
        "match_id": match.get("match_id"),
        "anchor_event_id": anchor["id"],
        "anchor_event_index": anchor.get("index"),
        "sequence_end_event_id": end_event["id"],
        "period": period,
        "start_timestamp": start,
        "end_timestamp": end,
        "duration_seconds": end - start,
        "selected_event_ids": [event["id"] for event in selected],
        "selected_actions": [SUPPORTED_ACTIONS[event["type"]] for event in selected],
        "available_360_frame_ids": [event["id"] for event in supported_frames],
        "source_360_frame_count": len(supported_frames),
        "longest_observation_gap_seconds": longest_gap,
        "configuration": resolved.__dict__,
    }


def materialize_window(match: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    if not str(selection.get("admission", "")).startswith("ACCEPTED"):
        raise ValueError(f"cannot materialize rejected reconstruction window: {selection.get('admission')}")
    ids = set(selection["selected_event_ids"])
    result = dict(match)
    result["events"] = []
    for event in match["events"]:
        if event["id"] not in ids:
            continue
        bounded = dict(event)
        bounded["duration"] = min(max(0.0, float(event.get("duration") or 0.0)), max(0.0, float(selection["end_timestamp"]) - float(event["timestamp"])))
        result["events"].append(bounded)
    result["frames"] = [frame for frame in match["frames"] if frame["event_id"] in ids]
    result["start_time"] = selection["start_timestamp"]
    result["end_time"] = selection["end_timestamp"]
    result["reconstruction_window"] = selection
    return result


def _rejected(admission: str, reason: str, event_id: str | None, event_index: int | None) -> dict[str, Any]:
    return {"schema_id": "tip.reconstruction_window_selection", "contract_version": "1.0.0", "admission": admission, "reasons": [reason], "anchor_event_id": event_id, "anchor_event_index": event_index, "selected_event_ids": [], "selected_actions": [], "available_360_frame_ids": [], "source_360_frame_count": 0}
