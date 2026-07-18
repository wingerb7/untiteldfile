from __future__ import annotations

import json
import math
import os
import sys
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
import yaml
from matplotlib.patches import Circle

from analysis.interpolate import FrameState, build_animation_model, metric_distance, state_at
from analysis.normalize import load_and_normalize
from render.pitch import draw_pitch, sb_to_plot
from render.styles import colors


def frame_by_event(possession: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(frame["event_id"]): frame for frame in possession["frames"]}


def raw_frame_by_event(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(event["id"]): list(event.get("freeze_frame") or []) for event in payload.get("events", [])}


def frame_state_by_event(model: dict[str, Any]) -> dict[str, FrameState]:
    return {state.event_id: state for state in model["frame_states"]}


def locations_equal(left: list[float], right: list[float], tolerance: float = 1e-9) -> bool:
    return abs(float(left[0]) - float(right[0])) <= tolerance and abs(float(left[1]) - float(right[1])) <= tolerance


def validate_event_snapshot(frame: dict[str, Any], raw_players: list[dict[str, Any]], state: FrameState) -> dict[str, Any]:
    visible = {
        int(player.source_index): player
        for player in state.players
        if player.visible and player.source_event_id == frame["event_id"] and player.source_index is not None
    }
    mismatches = []
    for idx, observed in enumerate(frame.get("players", [])):
        raw_player = raw_players[idx] if idx < len(raw_players) else None
        if raw_player is None:
            mismatches.append({"source_index": idx, "reason": "missing from raw freeze frame"})
        elif not locations_equal(raw_player["location"], observed["location"]):
            mismatches.append(
                {
                    "source_index": idx,
                    "reason": "normalization changed raw freeze-frame coordinates",
                    "raw": raw_player["location"],
                    "normalized": observed["location"],
                }
            )
        player = visible.get(idx)
        if player is None:
            mismatches.append({"source_index": idx, "reason": "missing from frame state"})
            continue
        if not locations_equal(observed["location"], [player.position.x, player.position.y]):
            mismatches.append(
                {
                    "source_index": idx,
                    "reason": "position changed",
                    "observed": observed["location"],
                    "state": [player.position.x, player.position.y],
                }
            )
        if player.status.value != "OBSERVED" or player.confidence != 1.0:
            mismatches.append(
                {
                    "source_index": idx,
                    "reason": "observed player status/confidence changed",
                    "status": player.status.value,
                    "confidence": player.confidence,
                }
            )
    return {
        "event_id": frame["event_id"],
        "players_checked": len(frame.get("players", [])),
        "raw_players_checked": len(raw_players),
        "perfect_match": not mismatches,
        "mismatches": mismatches,
    }


def timeline_debug(possession: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    events = possession["events"]
    starts = {item.event["id"]: item.start for item in model["timeline"]}
    for idx, event in enumerate(events):
        previous_event = events[idx - 1] if idx > 0 else None
        next_event = events[idx + 1] if idx + 1 < len(events) else None
        delta_prev = None if previous_event is None else float(event["timestamp"]) - float(previous_event["timestamp"])
        delta_next = None if next_event is None else float(next_event["timestamp"]) - float(event["timestamp"])
        rows.append(
            {
                "event_id": event["id"],
                "event_index": event["index"],
                "event_type": event["type"],
                "event_timestamp": event["timestamp"],
                "previous_event_id": None if previous_event is None else previous_event["id"],
                "next_event_id": None if next_event is None else next_event["id"],
                "delta_time_from_previous": delta_prev,
                "delta_time_to_next": delta_next,
                "freeze_frame_available": bool(event.get("freeze_frame")),
                "animation_timestamp": starts.get(event["id"]),
            }
        )
    return rows


def interpolation_segment_report(model: dict[str, Any]) -> list[dict[str, Any]]:
    states = model["frame_states"]
    segments = []
    for left, right in zip(states, states[1:], strict=False):
        midpoint = left.timestamp + (right.timestamp - left.timestamp) / 2.0
        state = state_at(model, midpoint)
        interpolated = [player for player in state["players"] if player.get("status") == "INTERPOLATED"]
        confidences = [float(player["confidence"]) for player in interpolated]
        segments.append(
            {
                "from_event_id": left.event_id,
                "to_event_id": right.event_id,
                "t_start": left.timestamp,
                "t_end": right.timestamp,
                "sample_timestamp": midpoint,
                "interpolated_players": len(interpolated),
                "average_confidence": sum(confidences) / len(confidences) if confidences else None,
                "minimum_confidence": min(confidences) if confidences else None,
            }
        )
    return segments


def validate_confidence(model: dict[str, Any]) -> list[str]:
    errors = []
    for state in model["frame_states"]:
        for player in state.players:
            if not 0.0 <= float(player.confidence) <= 1.0:
                errors.append(f"{state.event_id}:{player.tracking_id} confidence out of bounds {player.confidence}")
    for segment in interpolation_segment_report(model):
        sampled = state_at(model, segment["sample_timestamp"])
        for player in sampled["players"]:
            if not 0.0 <= float(player["confidence"]) <= 1.0:
                errors.append(f"{segment['from_event_id']}->{segment['to_event_id']} {player['tracking_id']} confidence out of bounds")
    return errors


def draw_fidelity_state(path: Path, model: dict[str, Any], t: float, title: str, style: dict[str, str]) -> None:
    state = state_at(model, t)
    fig, ax = plt.subplots(figsize=(8, 12), dpi=160)
    fig.patch.set_facecolor(style["field"])
    draw_pitch(ax, style, {"brand": {"pitch": {"stripe_count": 12}}})
    ax.set_title(title, color=style["text"], fontsize=12, weight="bold", pad=8)
    for player in state["players"]:
        point = sb_to_plot(player.get("location"))
        if point is None:
            continue
        fill = style["attack"] if player.get("teammate") else style["defense"]
        edge = {"OBSERVED": "#31D158", "INTERPOLATED": "#FF9F0A", "UNKNOWN": "#9CA3AF"}.get(player.get("status"), "#FFFFFF")
        disc = Circle(point, radius=1.65, facecolor=fill, edgecolor=edge, linewidth=2.0, zorder=6)
        ax.add_patch(disc)
        ax.text(
            point[0] + 1.4,
            point[1] + 1.4,
            f"{player['status']} {float(player['confidence']):.2f}",
            color=edge,
            fontsize=7,
            weight="bold",
            zorder=9,
        )
    ball = sb_to_plot(state.get("ball"))
    if ball:
        ax.scatter([ball[0]], [ball[1]], s=95, c=style["ball"], edgecolors="#111111", linewidths=0.8, zorder=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def exact_event_samples(model: dict[str, Any]) -> list[float]:
    states = model["frame_states"]
    if not states:
        return []
    samples = [states[0].timestamp]
    if len(states) > 2:
        samples.append(states[len(states) // 2].timestamp)
    if len(states) > 1:
        samples.append((states[0].timestamp + states[1].timestamp) / 2.0)
        samples.append((states[-2].timestamp + states[-1].timestamp) / 2.0)
    return samples[:4]


def main() -> None:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    data_path = ROOT / config["data"]["possession_file"]
    possession = load_and_normalize(data_path)
    model = build_animation_model(possession, config)
    frames = frame_by_event(possession)
    raw_frames = raw_frame_by_event(data_path)
    states = frame_state_by_event(model)

    snapshot_results = [validate_event_snapshot(frame, raw_frames.get(event_id, []), states[event_id]) for event_id, frame in frames.items()]
    segments = interpolation_segment_report(model)
    confidence_values = [segment["average_confidence"] for segment in segments if segment["average_confidence"] is not None]
    confidence_errors = validate_confidence(model)
    perfect_matches = sum(result["perfect_match"] for result in snapshot_results)
    low_confidence_segments = sum(
        (segment["minimum_confidence"] is not None and float(segment["minimum_confidence"]) < 0.55) for segment in segments
    )
    report = {
        "events_checked": len(snapshot_results),
        "perfect_snapshot_matches": perfect_matches,
        "interpolated_segments": len(segments),
        "average_interpolation_confidence": sum(confidence_values) / len(confidence_values) if confidence_values else None,
        "low_confidence_segments": low_confidence_segments,
        "snapshot_results": snapshot_results,
        "segments": segments,
        "validation_errors": confidence_errors,
        "guarantees": {
            "event_snapshots_exact": perfect_matches == len(snapshot_results),
            "interpolation_only_between_neighbouring_events": True,
            "confidence_in_range": not confidence_errors,
        },
    }
    output_dir = ROOT / "renders"
    (output_dir / "event_timeline_debug.json").write_text(json.dumps(timeline_debug(possession, model), indent=2, ensure_ascii=True), encoding="utf-8")
    (output_dir / "fidelity_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    style = colors(config)
    for idx, sample in enumerate(exact_event_samples(model), start=1):
        draw_fidelity_state(output_dir / f"debug_fidelity_{idx:02d}.png", model, sample, f"Fidelity debug t={sample:.2f}", style)
    print(json.dumps({key: report[key] for key in ["events_checked", "perfect_snapshot_matches", "interpolated_segments", "average_interpolation_confidence", "low_confidence_segments"]}, indent=2))


if __name__ == "__main__":
    main()
