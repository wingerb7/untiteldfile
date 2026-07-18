from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path("config.yaml")


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def event_type(event: dict[str, Any]) -> str | None:
    value = event.get("type")
    if isinstance(value, dict):
        return value.get("name")
    return value


def nested_name(event: dict[str, Any], key: str) -> str | None:
    value = event.get(key)
    if isinstance(value, dict):
        return value.get("name")
    return value


def nested_value(event: dict[str, Any], path: list[str]) -> Any:
    current: Any = event
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def clean_value(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, list):
        return [clean_value(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_value(item) for key, item in value.items()}
    return value


def first_present(event: dict[str, Any], flat_key: str, nested_path: list[str]) -> Any:
    flat_value = clean_value(event.get(flat_key))
    if flat_value is not None:
        return flat_value
    return clean_value(nested_value(event, nested_path))


def normalize_event(event: dict[str, Any], frame_by_event_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    event_id = event.get("id")
    type_name = event_type(event)
    frame = frame_by_event_id.get(event_id, {})
    event_player_id = nested_value(event, ["player", "id"])
    event_player_name = nested_name(event, "player")
    event_team_name = nested_name(event, "team")
    freeze_frame = clean_value(frame.get("freeze_frame", []))
    for player in freeze_frame:
        if player.get("actor"):
            player.setdefault("player_id", event_player_id)
            player.setdefault("player_name", event_player_name)
            player.setdefault("team_name", event_team_name)

    return {
        "id": event_id,
        "index": event.get("index"),
        "period": event.get("period"),
        "timestamp": event.get("timestamp"),
        "duration": clean_value(event.get("duration")),
        "minute": event.get("minute"),
        "second": event.get("second"),
        "type": type_name,
        "play_pattern": nested_name(event, "play_pattern"),
        "possession_team": nested_name(event, "possession_team"),
        "player_id": event_player_id,
        "player": event_player_name,
        "team_id": nested_value(event, ["team", "id"]),
        "team": event_team_name,
        "location": clean_value(event.get("location")),
        "pass_recipient": nested_name(event.get("pass", {}), "recipient") if isinstance(event.get("pass"), dict) else None,
        "recipient_id": nested_value(event, ["pass", "recipient", "id"]),
        "pass_outcome": nested_name(event.get("pass", {}), "outcome") if isinstance(event.get("pass"), dict) else None,
        "pass_end_location": first_present(event, "pass_end_location", ["pass", "end_location"]),
        "carry_end_location": first_present(event, "carry_end_location", ["carry", "end_location"]),
        "shot_end_location": first_present(event, "shot_end_location", ["shot", "end_location"]),
        "shot_outcome": clean_value(event.get("shot_outcome"))
        or (nested_name(event.get("shot", {}), "outcome") if isinstance(event.get("shot"), dict) else None),
        "shot_statsbomb_xg": first_present(event, "shot_statsbomb_xg", ["shot", "statsbomb_xg"]),
        "freeze_frame": freeze_frame,
        "visible_area": frame.get("visible_area"),
    }


def dataframe_to_records(df: Any) -> list[dict[str, Any]]:
    records = df.to_dict(orient="records")
    return [clean_value(json.loads(json.dumps(record, default=str))) for record in records]


def load_with_statsbombpy(match_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from statsbombpy import sb

    events_df = sb.events(match_id=match_id)
    frames_df = sb.frames(match_id=match_id)
    return dataframe_to_records(events_df), dataframe_to_records(frames_df)


def ensure_open_data_repo(open_data_dir: Path) -> None:
    if (open_data_dir / "data" / "events").exists():
        return

    open_data_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            "https://github.com/statsbomb/open-data.git",
            str(open_data_dir),
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(open_data_dir), "sparse-checkout", "set", "data/events", "data/three-sixty"], check=True)


def load_from_open_data(match_id: int, open_data_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    env_dir = os.environ.get("STATSBOMB_OPEN_DATA_DIR")
    if env_dir:
        open_data_dir = Path(env_dir)

    ensure_open_data_repo(open_data_dir)
    base = open_data_dir / "data"
    with (base / "events" / f"{match_id}.json").open("r", encoding="utf-8") as f:
        events = json.load(f)
    with (base / "three-sixty" / f"{match_id}.json").open("r", encoding="utf-8") as f:
        frames = json.load(f)
    return events, frames


def load_match_data(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    match_id = int(config["match"]["match_id"])
    open_data_dir = Path(config["data"]["open_data_dir"])

    try:
        events, frames = load_with_statsbombpy(match_id)
        return events, frames, "statsbombpy"
    except Exception as exc:
        print(f"statsbombpy failed ({exc}); falling back to StatsBomb open-data clone.")
        events, frames = load_from_open_data(match_id, open_data_dir)
        return events, frames, "open-data"


def build_frame_index(frames: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    frame_by_event_id: dict[str, dict[str, Any]] = {}

    for frame in frames:
        event_id = frame.get("event_uuid") or frame.get("id")
        if not event_id:
            continue

        if "freeze_frame" in frame:
            frame_by_event_id[event_id] = {
                "visible_area": clean_value(frame.get("visible_area")),
                "freeze_frame": clean_value(frame.get("freeze_frame", [])),
            }
            continue

        grouped_frame = frame_by_event_id.setdefault(
            event_id,
            {"visible_area": clean_value(frame.get("visible_area")), "freeze_frame": []},
        )
        grouped_frame["freeze_frame"].append(
            {
                "location": clean_value(frame.get("location")),
                "teammate": clean_value(frame.get("teammate")),
                "actor": clean_value(frame.get("actor")),
                "keeper": clean_value(frame.get("keeper")),
            }
        )

    return frame_by_event_id


def build_possession_payload(config: dict[str, Any]) -> dict[str, Any]:
    events, frames, source = load_match_data(config)
    possession_id = int(config["match"]["possession_id"])

    frame_by_event_id = build_frame_index(frames)
    included_types = {"Pass", "Ball Receipt*", "Carry", "Shot"}
    possession_events = [
        event
        for event in events
        if int(event.get("possession", -1)) == possession_id and event_type(event) in included_types
    ]
    possession_events.sort(key=lambda event: event.get("index", 0))

    normalized_events = [normalize_event(event, frame_by_event_id) for event in possession_events]

    return {
        "match_id": int(config["match"]["match_id"]),
        "possession_id": possession_id,
        "match_label": config["match"]["label"],
        "source": source,
        "coordinate_system": {
            "provider": "StatsBomb",
            "length": config["render"]["pitch"]["length"],
            "width": config["render"]["pitch"]["width"],
        },
        "events": normalized_events,
    }


def main() -> None:
    config = load_config()
    payload = build_possession_payload(config)
    output_path = Path(config["data"]["possession_file"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)

    frame_count = sum(1 for event in payload["events"] if event["freeze_frame"])
    print(f"Wrote {output_path} ({len(payload['events'])} events, {frame_count} freeze frames).")


if __name__ == "__main__":
    main()
