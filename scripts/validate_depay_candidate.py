from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from ingest import build_frame_index, event_type, nested_name, normalize_event


MATCH_ID = 3869117
BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
OUTPUT_PATH = Path("renders/depay_candidate_validation.json")
PAYLOAD_PATH = Path("data/depay_goal.json")


def read_open_data(path: str) -> Any:
    with urllib.request.urlopen(f"{BASE_URL}/{path}", timeout=30) as response:
        return json.load(response)


def shot_outcome(event: dict[str, Any]) -> str | None:
    shot = event.get("shot")
    if isinstance(shot, dict):
        return nested_name(shot, "outcome")
    return None


def goal_candidates(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event_type(event) == "Shot"
        and nested_name(event, "team") == "Netherlands"
        and shot_outcome(event) == "Goal"
    ]


def possession_payload(
    match: dict[str, Any],
    events: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    possession_id: int,
    label: str,
) -> dict[str, Any]:
    frame_by_event_id = build_frame_index(frames)
    included_types = {"Pass", "Ball Receipt*", "Carry", "Shot"}
    possession_events = [
        event
        for event in events
        if int(event.get("possession", -1)) == possession_id and event_type(event) in included_types
    ]
    possession_events.sort(key=lambda event: int(event.get("index") or 0))
    return {
        "match_id": int(match["match_id"]),
        "possession_id": possession_id,
        "match_label": label,
        "source": "statsbomb-open-data",
        "coordinate_system": {"provider": "StatsBomb", "length": 120, "width": 80},
        "events": [normalize_event(event, frame_by_event_id) for event in possession_events],
    }


def freeze_frame_density(payload: dict[str, Any]) -> float:
    events = payload.get("events", [])
    if not events:
        return 0.0
    return round(sum(1 for event in events if event.get("freeze_frame")) / len(events), 3)


def score_payload(payload: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    events = payload.get("events", [])
    passes = [event for event in events if event.get("type") == "Pass"]
    density = freeze_frame_density(payload)
    score = round(0.45 * density + 0.30 * min(1.0, len(events) / 20.0) + 0.25 * min(1.0, len(passes) / 8.0), 3)
    return score, {"event_count": len(events), "pass_count": len(passes), "freeze_frame_density": density}


def main() -> None:
    matches = read_open_data("matches/43/106.json")
    match = next(
        item
        for item in matches
        if item.get("match_id") == MATCH_ID
        and item.get("home_team", {}).get("home_team_name") == "Netherlands"
        and item.get("away_team", {}).get("away_team_name") == "United States"
    )
    events = read_open_data(f"events/{MATCH_ID}.json")
    frames = read_open_data(f"three-sixty/{MATCH_ID}.json")

    candidates = []
    for goal in goal_candidates(events):
        label = f"Netherlands vs United States, {nested_name(goal, 'player')} goal"
        payload = possession_payload(match, events, frames, int(goal["possession"]), label)
        score, metrics = score_payload(payload)
        candidates.append(
            {
                "goal_event_id": goal["id"],
                "goal_player": nested_name(goal, "player"),
                "minute": goal.get("minute"),
                "second": goal.get("second"),
                "possession_id": int(goal["possession"]),
                "score": score,
                **metrics,
            }
        )

    depay = next((candidate for candidate in candidates if candidate["goal_player"] == "Memphis Depay"), None)
    selected = depay if depay and depay["freeze_frame_density"] >= 0.75 else max(candidates, key=lambda item: item["score"])
    selected_payload = possession_payload(
        match,
        events,
        frames,
        int(selected["possession_id"]),
        f"Netherlands 3-1 United States, FIFA World Cup 2022 ({selected['goal_player']} goal)",
    )

    report = {
        "match_verified": True,
        "match_id": MATCH_ID,
        "match_date": match.get("match_date"),
        "events_available": len(events),
        "three_sixty_frames_available": len(frames),
        "requested_goal": "Memphis Depay goal",
        "source_note": "The source data attributes the first Depay goal assist to Denzel Dumfries, not Daley Blind.",
        "candidates": candidates,
        "selected_candidate": selected,
        "selection_reason": "requested_candidate_suitable"
        if selected is depay
        else "requested_candidate_missing_or_low_360_density_next_best_same_match",
        "output_payload": str(PAYLOAD_PATH),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    PAYLOAD_PATH.write_text(json.dumps(selected_payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
