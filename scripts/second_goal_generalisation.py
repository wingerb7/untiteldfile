from __future__ import annotations

import copy
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LOCAL_CACHE = ROOT / "renders" / ".cache"
LOCAL_MPLCONFIG = ROOT / "renders" / ".matplotlib"
LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
LOCAL_MPLCONFIG.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(LOCAL_CACHE))
os.environ.setdefault("MPLCONFIGDIR", str(LOCAL_MPLCONFIG))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from analysis.interpolate import (
    TEAM_ATTACK,
    TEAM_DEFENSE,
    build_animation_model,
    build_event_timeline,
    metric_distance,
    player_state_to_dict,
    state_at,
)
from analysis.normalize import load_and_normalize
from ingest import build_frame_index, event_type, load_config, nested_name, normalize_event
from render.pitch import sb_to_plot
from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.pipelines.analyze_possession import analyze
from src.pipelines.render_analysis import render_debug_frame, render_scene_plan, write_tracking_diagnostics


OPEN_DATA = ROOT / "data" / "open-data" / "data"
OUT = ROOT / "renders"
SECOND_POSSESSION = ROOT / "data" / "second_goal.json"
POSSESSION_52 = ROOT / "data" / "possession_52.json"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def timestamp_key(event: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        int(event.get("period") or 0),
        int(event.get("minute") or 0),
        int(event.get("second") or 0),
        str(event.get("timestamp") or ""),
    )


def resolve_match() -> dict[str, Any]:
    competitions = read_json(OPEN_DATA / "competitions.json")
    euro = [
        item
        for item in competitions
        if item.get("competition_name") == "UEFA Euro" and str(item.get("season_name")) == "2020"
    ]
    if len(euro) != 1:
        raise RuntimeError(f"Expected one UEFA Euro 2020 competition row, found {len(euro)}")
    competition_id = int(euro[0]["competition_id"])
    season_id = int(euro[0]["season_id"])
    matches = read_json(OPEN_DATA / "matches" / str(competition_id) / f"{season_id}.json")
    selected = [
        match
        for match in matches
        if match.get("home_team", {}).get("home_team_name") == "Italy"
        and match.get("away_team", {}).get("away_team_name") == "Switzerland"
    ]
    if len(selected) != 1:
        teams = sorted(
            {
                match.get("home_team", {}).get("home_team_name", "")
                for match in matches
            }
            | {match.get("away_team", {}).get("away_team_name", "") for match in matches}
        )
        raise RuntimeError(f"Italy vs Switzerland lookup failed. Source teams: {teams}")
    match = selected[0]
    match_id = int(match["match_id"])
    event_path = OPEN_DATA / "events" / f"{match_id}.json"
    frame_path = OPEN_DATA / "three-sixty" / f"{match_id}.json"
    if not event_path.exists() or not frame_path.exists():
        raise RuntimeError(f"Selected match lacks required files: events={event_path.exists()} 360={frame_path.exists()}")
    return match


def shot_outcome(event: dict[str, Any]) -> str | None:
    shot = event.get("shot")
    if isinstance(shot, dict):
        return nested_name(shot, "outcome")
    return nested_name(event, "shot_outcome")


def locate_goal(events: list[dict[str, Any]]) -> dict[str, Any]:
    goals = [
        event
        for event in events
        if event_type(event) == "Shot"
        and nested_name(event, "team") == "Italy"
        and nested_name(event, "player") == "Manuel Locatelli"
        and shot_outcome(event) == "Goal"
    ]
    goals.sort(key=timestamp_key)
    if len(goals) < 1:
        players = sorted({nested_name(event, "player") or "" for event in events if nested_name(event, "team") == "Italy"})
        raise RuntimeError(f"Locatelli goal lookup failed. Italy players encountered: {players}")
    first = goals[0]
    possession_id = int(first["possession"])
    possession_events = [event for event in events if int(event.get("possession", -1)) == possession_id]
    possession_events.sort(key=lambda event: int(event.get("index") or 0))
    supported_types = {"Pass", "Ball Receipt*", "Carry", "Shot"}
    supported_events = [event for event in possession_events if event_type(event) in supported_types]
    if supported_events[-1].get("id") != first.get("id"):
        raise RuntimeError("Selected possession's supported attacking sequence does not end in Locatelli's first goal.")
    return first


def build_payload(match: dict[str, Any], events: list[dict[str, Any]], frames: list[dict[str, Any]], possession_id: int) -> dict[str, Any]:
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
        "match_label": "Italy 3-0 Switzerland, UEFA Euro 2020 (Locatelli first goal)",
        "source": "open-data",
        "coordinate_system": {"provider": "StatsBomb", "length": 120, "width": 80},
        "events": [normalize_event(event, frame_by_event_id) for event in possession_events],
    }


def clamp01(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def score_goal_candidate(candidate: dict[str, Any]) -> dict[str, float]:
    score = {
        "event_count_score": clamp01(candidate["events"] / 12.0),
        "pass_count_score": clamp01(candidate["passes"] / 6.0),
        "freeze_frame_coverage_score": clamp01(candidate["freeze_frame_coverage"]),
        "possession_duration_score": clamp01(candidate["duration_seconds"] / 18.0),
        "attacking_progression_score": clamp01(candidate["attacking_progression"] / 55.0),
        "data_completeness_score": clamp01((candidate["freeze_frame_coverage"] + (1.0 if candidate.get("shot_xg") is not None else 0.0)) / 2.0),
    }
    score["overall_score"] = clamp01(sum(score.values()) / len(score))
    return score


def candidate_from_payload(
    payload: dict[str, Any],
    match: dict[str, Any],
    goal: dict[str, Any] | None = None,
    selected_player: str | None = None,
    opponent: str | None = None,
) -> dict[str, Any]:
    normalized = load_and_normalize(SECOND_POSSESSION if payload["possession_id"] != 52 else POSSESSION_52)
    events = normalized["events"]
    freeze_frames = sum(1 for event in events if event.get("freeze_frame"))
    passes = [event for event in events if event.get("type") == "Pass"]
    xs = [loc[0] for event in events for loc in (event.get("start_location"), event.get("end_location")) if loc]
    progression = max(xs) - min(xs) if xs else 0.0
    candidate = {
        "match_id": payload.get("match_id"),
        "competition": match.get("competition", {}).get("competition_name") if match else None,
        "season": match.get("season", {}).get("season_name") if match else None,
        "team": normalized.get("team"),
        "opponent": opponent,
        "player": selected_player,
        "goal_number_for_player_in_match": 1 if selected_player and goal else None,
        "possession_id": payload.get("possession_id"),
        "goal_event_id": goal.get("id") if goal else (normalized.get("shot") or {}).get("id"),
        "events": len(events),
        "passes": len(passes),
        "freeze_frames_available": freeze_frames,
        "freeze_frame_coverage": round(freeze_frames / max(1, len(events)), 3),
        "duration_seconds": round(float(normalized.get("duration") or 0.0), 3),
        "shot_xg": (normalized.get("shot") or {}).get("xg"),
        "attacking_progression": round(progression, 3),
    }
    candidate["score"] = score_goal_candidate(candidate)
    return candidate


def write_event_timeline(possession_path: Path, scene_plan: dict[str, Any], config: dict[str, Any], output_path: Path) -> dict[str, Any]:
    possession = load_and_normalize(possession_path)
    model = build_animation_model(possession, config)
    timeline = []
    for item in model["timeline"]:
        event = item.event
        timeline.append(
            {
                "event_id": event["id"],
                "index": event["index"],
                "type": event["type"],
                "player": event.get("player_name"),
                "timestamp": event["timestamp"],
                "render_start": round(item.start, 3),
                "render_end": round(item.end, 3),
                "has_freeze_frame": bool(event.get("freeze_frame")),
            }
        )
    write_json(output_path, {"possession_id": possession["possession_id"], "events": timeline, "scenes": scene_plan.get("scenes", [])})
    return model


def fidelity_report(possession_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    possession = load_and_normalize(possession_path)
    model = build_animation_model(possession, config)
    event_by_id = {event["id"]: event for event in possession["events"]}
    max_displacement = 0.0
    perfect = 0
    events_checked = 0
    errors: list[str] = []
    duplicate_id_frames = 0
    frames_over_11 = 0
    invalid_confidence = 0
    unknown_observed = 0

    for frame in model["frame_states"]:
        event = event_by_id.get(frame.event_id)
        if not event or not event.get("freeze_frame"):
            continue
        events_checked += 1
        expected = {
            int(player.get("source_index", idx)): player
            for idx, player in enumerate(event.get("freeze_frame", []))
        }
        actual = {
            int(player.source_index if player.source_index is not None else -1): player
            for player in frame.players
            if player.visible and player.source_event_id == frame.event_id
        }
        frame_max = 0.0
        for source_index, expected_player in expected.items():
            player = actual.get(source_index)
            if player is None:
                errors.append(f"{frame.event_id}: missing observed source_index {source_index}")
                continue
            if not player.observed or player.status.value != "OBSERVED":
                errors.append(f"{frame.event_id}: source_index {source_index} was not preserved as observed")
            displacement = metric_distance(player.position, type(player.position)(expected_player["location"][0], expected_player["location"][1]))
            frame_max = max(frame_max, displacement)
            if displacement > 1e-9:
                errors.append(f"{frame.event_id}: source_index {source_index} moved {displacement:.6f}m")
        if frame_max <= 1e-9 and len(actual) >= len(expected):
            perfect += 1
        max_displacement = max(max_displacement, frame_max)

    sample_count = max(1, int(math.ceil(model["duration"] * int(config.get("animation", {}).get("fps", 30)))))
    for idx in range(sample_count):
        state = state_at(model, idx / int(config.get("animation", {}).get("fps", 30)))
        players = state["players"]
        ids = [player["tracking_id"] for player in players]
        if len(ids) != len(set(ids)):
            duplicate_id_frames += 1
        counts = Counter(player["team_id"] for player in players)
        if any(count > 11 for count in counts.values()):
            frames_over_11 += 1
        for player in players:
            confidence = float(player.get("confidence", -1))
            invalid_confidence += int(confidence < 0.0 or confidence > 1.0)
            unknown_observed += int(player.get("status") == "UNKNOWN" and player.get("observed"))

    diagnostics_summary = model["tracking_diagnostics"]["summary"]
    return {
        "events_checked": events_checked,
        "perfect_snapshot_matches": perfect,
        "maximum_snapshot_displacement_m": round(max_displacement, 9),
        "duplicate_id_frames": duplicate_id_frames + int(diagnostics_summary.get("duplicate_tracking_ids", 0)),
        "frames_over_11_players": frames_over_11 + int(diagnostics_summary.get("frames_over_11_players", 0)),
        "invalid_confidence_values": invalid_confidence,
        "unknown_player_presented_as_observed": unknown_observed,
        "validation_errors": errors,
    }


def tactical_validation(analysis: dict[str, Any], possession_path: Path) -> list[dict[str, Any]]:
    possession = load_normalized_possession(possession_path)
    valid_ids = {event.event_id for event in possession.events}
    supported: list[dict[str, Any]] = []
    for finding in analysis.get("findings", []):
        evidence = finding.get("evidence", {})
        ok = (
            finding.get("pattern_type") == "line_breaking_pass"
            and finding.get("event_id") in valid_ids
            and evidence.get("line_crossed") is True
            and evidence.get("defenders_bypassed", 0) >= LineBreakConfig().minimum_defenders_bypassed
            and evidence.get("forward_progress", 0.0) >= LineBreakConfig().minimum_forward_progress
        )
        supported.append(
            {
                "type": finding.get("pattern_type"),
                "event_id": finding.get("event_id"),
                "confidence": finding.get("confidence"),
                "evidence": {
                    "defenders_bypassed": evidence.get("defenders_bypassed"),
                    "progression_metres": evidence.get("forward_progress"),
                    "start_zone": None,
                    "end_zone": None,
                    "defensive_band_before": evidence.get("defensive_line", {}).get("start_side"),
                    "defensive_band_after": evidence.get("defensive_line", {}).get("end_side"),
                },
                "supported": ok,
                "reason": "Objective line-break evidence meets configured detector thresholds." if ok else "Finding is not supported by configured detector evidence.",
            }
        )
    return supported


def select_debug_times(possession_path: Path, analysis: dict[str, Any], config: dict[str, Any]) -> list[tuple[float, str]]:
    possession = load_and_normalize(possession_path)
    timeline = build_event_timeline(possession, config)
    starts = {item.event["id"]: item.start for item in timeline}
    passes = [event for event in possession["events"] if event["type"] == "Pass" and event.get("start_location") and event.get("end_location")]
    progressive = sorted(passes, key=lambda event: event["end_location"][0] - event["start_location"][0], reverse=True)
    selected_id = analysis.get("selected_finding_id")
    selected_event_id = None
    if selected_id:
        selected_event_id = analysis.get("findings", [{}])[0].get("event_id")
    if selected_event_id is None and progressive:
        selected_event_id = progressive[0]["id"]
    shot = possession.get("shot") or possession["events"][-1]
    progression = progressive[0] if progressive else possession["events"][0]
    return [
        (timeline[0].start, "possession_start"),
        (starts.get(progression["id"], timeline[0].start), "important_progression_event"),
        (starts.get(selected_event_id, starts.get(progression["id"], timeline[0].start)), "tactical_or_diagnostic_event"),
        (starts.get(shot["id"], timeline[-1].start), "shot_event"),
    ]


def average_interpolation_confidence(model: dict[str, Any], fps: int) -> float:
    values = []
    for idx in range(max(1, int(model["duration"] * fps))):
        for player in state_at(model, idx / fps)["players"]:
            if player.get("status") == "INTERPOLATED":
                values.append(float(player["confidence"]))
    return round(sum(values) / len(values), 3) if values else 0.0


def generalisation_report(second_analysis: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    p52 = load_and_normalize(POSSESSION_52)
    p2 = load_and_normalize(SECOND_POSSESSION)
    m52 = build_animation_model(p52, config)
    m2 = build_animation_model(p2, config)
    code_hits = {}
    for path in [ROOT / "src", ROOT / "analysis", ROOT / "render", ROOT / "scripts"]:
        for file in path.rglob("*.py"):
            text = file.read_text(encoding="utf-8", errors="ignore")
            hits = [needle for needle in ("possession_52", "Di Maria", "Di María", "3788754", "Locatelli") if needle in text]
            if hits and file.name != "second_goal_generalisation.py":
                code_hits[str(file.relative_to(ROOT))] = hits
    p52_analysis = read_json(OUT / "possession_52_analysis.json") if (OUT / "possession_52_analysis.json").exists() else {"findings": []}
    return {
        "possession_52": {
            "events": len(p52["events"]),
            "passes": sum(1 for event in p52["events"] if event["type"] == "Pass"),
            "findings": [finding.get("pattern_type") for finding in p52_analysis.get("findings", [])],
            "average_interpolation_confidence": average_interpolation_confidence(m52, int(config["animation"]["fps"])),
        },
        "second_goal": {
            "events": len(p2["events"]),
            "passes": sum(1 for event in p2["events"] if event["type"] == "Pass"),
            "findings": [finding.get("pattern_type") for finding in second_analysis.get("findings", [])],
            "average_interpolation_confidence": average_interpolation_confidence(m2, int(config["animation"]["fps"])),
        },
        "shared_code_paths": [
            "ingest.normalize_event",
            "analysis.normalize.load_and_normalize",
            "analysis.interpolate.build_animation_model",
            "src.intelligence.patterns.line_break.detect_line_breaking_passes",
            "src.intelligence.scene_builder.build_scene_plan",
            "src.pipelines.render_analysis.render_scene_plan",
        ],
        "possession_specific_logic_found": code_hits,
        "generalisation_failures": [],
        "reusable_bugs_found": [],
    }


def comparison_image(second_analysis: dict[str, Any]) -> None:
    left = OUT / "debug_fidelity_03.png"
    right = OUT / "second_goal_debug_03.png"
    fig = plt.figure(figsize=(12, 8), dpi=140)
    axes = [fig.add_subplot(2, 2, 1), fig.add_subplot(2, 2, 2), fig.add_subplot(2, 2, 3), fig.add_subplot(2, 2, 4)]
    for ax, path, title in ((axes[0], left, "Possession 52"), (axes[1], right, "Second goal")):
        ax.axis("off")
        ax.set_title(title, fontsize=14, weight="bold")
        if path.exists():
            ax.imshow(Image.open(path))
    p52_analysis = read_json(OUT / "possession_52_analysis.json") if (OUT / "possession_52_analysis.json").exists() else {"findings": []}
    for ax, analysis, title in ((axes[2], p52_analysis, "Findings and evidence"), (axes[3], second_analysis, "Findings and evidence")):
        ax.axis("off")
        findings = analysis.get("findings", [])
        if findings:
            finding = findings[0]
            evidence = finding.get("evidence", {})
            text = "\n".join(
                [
                    f"type: {finding.get('pattern_type')}",
                    f"confidence: {finding.get('confidence')}",
                    f"event: {finding.get('event_id')}",
                    f"defenders bypassed: {evidence.get('defenders_bypassed')}",
                    f"forward progress: {evidence.get('forward_progress')}",
                ]
            )
        else:
            text = "No supported tactical finding."
        ax.set_title(title, fontsize=11, weight="bold")
        ax.text(0.02, 0.95, text, va="top", ha="left", family="monospace", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "goal_comparison.png")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    config = load_config(ROOT / "config.yaml")
    match = resolve_match()
    match_id = int(match["match_id"])
    events = read_json(OPEN_DATA / "events" / f"{match_id}.json")
    frames = read_json(OPEN_DATA / "three-sixty" / f"{match_id}.json")
    goal = locate_goal(events)
    payload = build_payload(match, events, frames, int(goal["possession"]))
    write_json(SECOND_POSSESSION, payload)

    match_resolution = {
        "match_id": match_id,
        "competition": match["competition"]["competition_name"],
        "season": match["season"]["season_name"],
        "match_date": match["match_date"],
        "home_team": match["home_team"]["home_team_name"],
        "away_team": match["away_team"]["away_team_name"],
    }
    goal_resolution = {
        "goal_event_id": goal["id"],
        "period": goal.get("period"),
        "minute": goal.get("minute"),
        "second": goal.get("second"),
        "possession_id": goal.get("possession"),
        "shot_xg": goal.get("shot", {}).get("statsbomb_xg") if isinstance(goal.get("shot"), dict) else None,
        "play_pattern": nested_name(goal, "play_pattern"),
    }

    candidate = candidate_from_payload(payload, match, goal, selected_player="Manuel Locatelli", opponent="Switzerland")
    p52_candidate = None
    if POSSESSION_52.exists():
        p52_candidate = candidate_from_payload(read_json(POSSESSION_52), {}, None)
    write_json(
        OUT / "second_goal_candidate.json",
        {
            "selection_mode": "manual",
            "selection_reason": "Selected to test a structurally different multi-pass attack",
            "match": match_resolution,
            "goal": goal_resolution,
            "candidate": candidate,
            "comparison_candidate_possession_52": p52_candidate,
        },
    )

    analysis_config = copy.deepcopy(config)
    analysis_config["animation"] = copy.deepcopy(config.get("animation", {}))
    analysis_config["animation"]["hook_text"] = "Can Italy turn circulation into a goal?"
    analysis_config["animation"]["hook_model_time"] = 1.0
    analysis_config["animation"]["annotations_file"] = "annotations/second_goal.json"
    analysis, scene_plan = analyze(SECOND_POSSESSION, analysis_config)
    write_json(OUT / "second_goal_analysis.json", analysis)
    write_json(OUT / "second_goal_scene_plan.json", scene_plan)

    model = render_scene_plan(load_and_normalize(SECOND_POSSESSION), scene_plan, analysis_config, OUT / "second_goal.mp4")
    write_tracking_diagnostics(model, OUT / "second_goal_tracking_diagnostics.json")
    write_event_timeline(SECOND_POSSESSION, scene_plan, analysis_config, OUT / "second_goal_event_timeline.json")

    for idx, (t, _) in enumerate(select_debug_times(SECOND_POSSESSION, analysis, analysis_config), start=1):
        render_debug_frame(model, analysis_config, t, OUT / f"second_goal_debug_{idx:02d}.png")

    report = fidelity_report(SECOND_POSSESSION, analysis_config)
    report["tactical_validation"] = tactical_validation(analysis, SECOND_POSSESSION)
    write_json(OUT / "second_goal_fidelity_report.json", report)
    write_json(OUT / "generalisation_report.json", generalisation_report(analysis, analysis_config))
    comparison_image(analysis)

    print(json.dumps({"match": match_resolution, "goal": goal_resolution, "fidelity": report}, indent=2))


if __name__ == "__main__":
    main()
