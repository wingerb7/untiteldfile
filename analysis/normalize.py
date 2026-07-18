from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_END_FIELDS = {
    "Pass": "pass_end_location",
    "Carry": "carry_end_location",
    "Shot": "shot_end_location",
}


def timestamp_to_seconds(value: str | int | float | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)

    parts = str(value).split(":")
    if len(parts) != 3:
        return 0.0
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def clean_location(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) < 2:
        return None
    return [float(value[0]), float(value[1])]


def normalize_freeze_frame(raw_frame: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    frame = []
    for idx, player in enumerate(raw_frame or []):
        location = clean_location(player.get("location"))
        if location is None:
            continue
        frame.append(
            {
                "player_id": player.get("player_id"),
                "player_name": player.get("player_name"),
                "team_id": player.get("team_id"),
                "teammate": bool(player.get("teammate")),
                "actor": bool(player.get("actor")),
                "keeper": bool(player.get("keeper")),
                "location": location,
                "source_index": idx,
            }
        )
    return frame


def normalize_event(raw_event: dict[str, Any], next_timestamp: float | None) -> dict[str, Any]:
    event_type = raw_event.get("type") or "Unknown"
    timestamp = timestamp_to_seconds(raw_event.get("timestamp"))
    end_field = SUPPORTED_END_FIELDS.get(event_type)
    start_location = clean_location(raw_event.get("location"))
    end_location = clean_location(raw_event.get(end_field)) if end_field else None

    raw_duration = raw_event.get("duration")
    if raw_duration is None and next_timestamp is not None:
        raw_duration = max(0.0, next_timestamp - timestamp)
    duration = max(0.0, float(raw_duration or 0.0))

    return {
        "id": raw_event.get("id"),
        "index": int(raw_event.get("index") or 0),
        "period": raw_event.get("period"),
        "minute": raw_event.get("minute"),
        "second": raw_event.get("second"),
        "type": event_type,
        "timestamp": timestamp,
        "duration": duration,
        "player_id": raw_event.get("player_id"),
        "player_name": raw_event.get("player"),
        "team_id": raw_event.get("team_id"),
        "team_name": raw_event.get("team"),
        "play_pattern": raw_event.get("play_pattern"),
        "possession_team": raw_event.get("possession_team"),
        "start_location": start_location,
        "end_location": end_location,
        "recipient_id": raw_event.get("recipient_id") or raw_event.get("recipient_id"),
        "recipient_name": raw_event.get("pass_recipient"),
        "outcome": raw_event.get("shot_outcome") or raw_event.get("pass_outcome"),
        "xg": raw_event.get("shot_statsbomb_xg"),
        "freeze_frame": normalize_freeze_frame(raw_event.get("freeze_frame")),
        "visible_area": raw_event.get("visible_area"),
    }


def normalize_possession(payload: dict[str, Any]) -> dict[str, Any]:
    raw_events = sorted(payload.get("events", []), key=lambda event: int(event.get("index") or 0))
    raw_timestamps = [timestamp_to_seconds(event.get("timestamp")) for event in raw_events]

    events = []
    for idx, raw_event in enumerate(raw_events):
        next_timestamp = raw_timestamps[idx + 1] if idx + 1 < len(raw_timestamps) else None
        events.append(normalize_event(raw_event, next_timestamp))

    if events:
        start_time = events[0]["timestamp"]
        end_time = max(event["timestamp"] + event["duration"] for event in events)
        if end_time <= start_time:
            end_time = events[-1]["timestamp"]
    else:
        start_time = 0.0
        end_time = 0.0

    frames = [
        {
            "event_id": event["id"],
            "event_index": event["index"],
            "timestamp": event["timestamp"],
            "players": event["freeze_frame"],
        }
        for event in events
    ]
    shot = next((event for event in events if event["type"] == "Shot"), None)

    return {
        "possession_id": int(payload.get("possession_id") or 0),
        "match_id": payload.get("match_id"),
        "match_label": payload.get("match_label"),
        "team": next((event["team_name"] for event in events if event.get("team_name")), None),
        "start_time": start_time,
        "end_time": end_time,
        "duration": max(0.0, end_time - start_time),
        "events": events,
        "frames": frames,
        "shot": shot,
    }


def load_and_normalize(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return normalize_possession(json.load(f))
