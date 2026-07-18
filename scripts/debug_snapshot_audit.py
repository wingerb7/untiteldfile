from __future__ import annotations

import json
import math
import os
import sys
import argparse
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

from analysis.interpolate import TEAM_ATTACK, TEAM_DEFENSE, build_animation_model, state_at
from analysis.normalize import load_and_normalize
from render.pitch import PITCH_LENGTH, PITCH_WIDTH, draw_pitch, sb_to_plot
from render.styles import colors


METRIC_X = 105.0 / 120.0
METRIC_Y = 68.0 / 80.0


def load_raw_event(path: Path, event_id: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return next(event for event in payload["events"] if event["id"] == event_id)


def load_normalized_event(path: Path, event_id: str) -> dict[str, Any]:
    possession = load_and_normalize(path)
    return next(event for event in possession["events"] if event["id"] == event_id)


def timeline_start(model: dict[str, Any], event_id: str) -> float:
    return next(item.start for item in model["timeline"] if item.event["id"] == event_id)


def team_label(player: dict[str, Any]) -> str:
    return "attack" if player.get("teammate") else "defense"


def metric_delta(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    dx = (b["x"] - a["x"]) * METRIC_X
    dy = (b["y"] - a["y"]) * METRIC_Y
    return {"dx": dx, "dy": dy, "distance": math.hypot(dx, dy)}


def coord(location: list[float] | tuple[float, ...]) -> dict[str, float]:
    return {"x": float(location[0]), "y": float(location[1])}


def pause_players_by_source(state: dict[str, Any], event_id: str) -> dict[int, dict[str, Any]]:
    players = {}
    for player in state["players"]:
        if player.get("source_event_id") == event_id and player.get("source_index") is not None:
            players[int(player["source_index"])] = player
    return players


def draw_snapshot(
    ax: Any,
    title: str,
    players: list[dict[str, Any]],
    ball: list[float] | None,
    style: dict[str, str],
    coordinate_key: str = "location",
    show_coordinates: str | None = None,
) -> None:
    draw_pitch(ax, style, {"brand": {"pitch": {"stripe_count": 12}}})
    ax.set_title(title, color=style["text"], fontsize=12, weight="bold", pad=8)
    for idx, player in enumerate(players):
        location = player.get(coordinate_key)
        point = sb_to_plot(location)
        if point is None:
            continue
        color = style["attack"] if player.get("teammate") else style["defense"]
        marker = "s" if player.get("keeper") else "o"
        size = 115 if player.get("actor") else 70
        ax.scatter([point[0]], [point[1]], s=size, c=color, marker=marker, edgecolors="#111111", linewidths=0.8, zorder=5)
        label_parts = [str(player.get("source_index", idx))]
        if player.get("actor"):
            label_parts.append("actor")
        if player.get("keeper"):
            label_parts.append("GK")
        if show_coordinates:
            x, y = location[:2]
            label_parts.append(f"{show_coordinates} {float(x):.1f},{float(y):.1f}")
        ax.text(point[0] + 0.9, point[1] + 0.9, " ".join(label_parts), color=style["text"], fontsize=7, zorder=8)
    if ball:
        ball_point = sb_to_plot(ball)
        if ball_point:
            ax.scatter([ball_point[0]], [ball_point[1]], s=105, c=style["ball"], edgecolors="#111111", linewidths=0.9, zorder=9)
            ax.text(ball_point[0] + 0.9, ball_point[1] + 0.9, "ball", color=style["ball"], fontsize=8, weight="bold", zorder=10)


def render_single(path: Path, title: str, players: list[dict[str, Any]], ball: list[float] | None, style: dict[str, str]) -> None:
    fig, ax = plt.subplots(figsize=(8, 12), dpi=160)
    fig.patch.set_facecolor(style["field"])
    draw_snapshot(ax, title, players, ball, style)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def render_four_panel(
    path: Path,
    raw_players: list[dict[str, Any]],
    normalized_players: list[dict[str, Any]],
    pause_players: list[dict[str, Any]],
    ball: list[float],
    normalized_ball: list[float],
    pause_ball: list[float],
    style: dict[str, str],
) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(8, 22), dpi=150)
    fig.patch.set_facecolor(style["field"])
    draw_snapshot(axes[0], "Raw Freeze Frame", raw_players, ball, style, show_coordinates="raw")
    draw_snapshot(axes[1], "Normalized", normalized_players, normalized_ball, style, show_coordinates="norm")
    draw_snapshot(axes[2], "Tactical Pause State", pause_players, pause_ball, style, show_coordinates="pause")
    axes[3].set_facecolor("#101610")
    axes[3].set_xlim(0, PITCH_WIDTH)
    axes[3].set_ylim(0, PITCH_LENGTH)
    axes[3].axis("off")
    axes[3].set_title("Broadcast Screenshot", color=style["text"], fontsize=12, weight="bold", pad=8)
    axes[3].text(
        40,
        60,
        "Broadcast screenshot not available in workspace",
        ha="center",
        va="center",
        color=style["muted_text"],
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def validation_summary(rows: list[dict[str, Any]], ball_delta: dict[str, float]) -> dict[str, Any]:
    distances = [row["delta_normalized_to_pause_m"]["distance"] for row in rows if row.get("pause_coordinates")]
    return {
        "maximum_player_displacement_m": max(distances) if distances else None,
        "average_player_displacement_m": sum(distances) / len(distances) if distances else None,
        "maximum_ball_displacement_m": ball_delta["distance"],
        "average_ball_displacement_m": ball_delta["distance"],
        "players_moved_more_than_m": {
            "0.5": sum(distance > 0.5 for distance in distances),
            "1": sum(distance > 1.0 for distance in distances),
            "2": sum(distance > 2.0 for distance in distances),
            "5": sum(distance > 5.0 for distance in distances),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--event-id", required=True)
    args = parser.parse_args()
    data_path = args.input
    event_id = args.event_id
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    style = colors(config)
    output_dir = ROOT / "renders"
    raw_event = load_raw_event(data_path, event_id)
    normalized_event = load_normalized_event(data_path, event_id)
    possession = load_and_normalize(data_path)
    model = build_animation_model(possession, config)
    pause_time = timeline_start(model, event_id)
    pause_state = state_at(model, pause_time)
    pause_by_source = pause_players_by_source(pause_state, event_id)

    raw_players = [{**player, "source_index": idx} for idx, player in enumerate(raw_event["freeze_frame"])]
    normalized_players = normalized_event["freeze_frame"]
    pause_players = []
    rows = []
    for idx, normalized_player in enumerate(normalized_players):
        raw_player = raw_players[idx]
        pause_player = pause_by_source.get(idx)
        pause_location = pause_player["location"] if pause_player else None
        pause_players.append(
            {
                **normalized_player,
                "location": pause_location or normalized_player["location"],
                "source_index": idx,
                "actor": normalized_player.get("actor"),
                "keeper": normalized_player.get("keeper"),
                "teammate": normalized_player.get("teammate"),
            }
        )
        raw_coordinates = coord(raw_player["location"])
        normalized_coordinates = coord(normalized_player["location"])
        pause_coordinates = coord(pause_location) if pause_location else None
        delta_m = metric_delta(normalized_coordinates, pause_coordinates) if pause_coordinates else None
        delta_sb = (
            {
                "dx": pause_coordinates["x"] - normalized_coordinates["x"],
                "dy": pause_coordinates["y"] - normalized_coordinates["y"],
                "distance": math.dist((normalized_coordinates["x"], normalized_coordinates["y"]), (pause_coordinates["x"], pause_coordinates["y"])),
            }
            if pause_coordinates
            else None
        )
        rows.append(
            {
                "observation_index": idx,
                "team": team_label(normalized_player),
                "actor": bool(normalized_player.get("actor")),
                "keeper": bool(normalized_player.get("keeper")),
                "raw_coordinates": raw_coordinates,
                "normalized_coordinates": normalized_coordinates,
                "pause_coordinates": pause_coordinates,
                "delta_normalized_to_pause": delta_sb,
                "delta_normalized_to_pause_m": delta_m,
            }
        )

    raw_ball = raw_event["location"]
    normalized_ball = normalized_event["start_location"]
    pause_ball = pause_state["ball"]
    ball_delta = metric_delta(coord(normalized_ball), coord(pause_ball))
    report = {
        "event_id": event_id,
        "event_type": raw_event["type"],
        "player": raw_event["player"],
        "pause_state_source": {
            "function": "analysis.interpolate.state_at",
            "model_time": pause_time,
            "note": "This audits the exact renderer state at the selected event start.",
        },
        "coordinate_notes": {
            "raw": "StatsBomb 120x80 event freeze_frame coordinates",
            "normalized": "analysis.normalize.load_and_normalize output; this repository does not apply attacking-direction flipping for this possession",
            "pause": "state_at(build_animation_model(...), shot_timeline_start) player coordinates",
        },
        "players": rows,
        "ball": {
            "raw_coordinates": coord(raw_ball),
            "normalized_coordinates": coord(normalized_ball),
            "pause_coordinates": coord(pause_ball),
            "delta_normalized_to_pause_m": ball_delta,
        },
        "validation": validation_summary(rows, ball_delta),
        "divergence": {
            "raw_to_normalized": "none detected" if all(row["raw_coordinates"] == row["normalized_coordinates"] for row in rows) else "coordinates differ before pause state",
            "normalized_to_pause": "none detected"
            if all((row["delta_normalized_to_pause_m"] or {}).get("distance", 0.0) <= 1e-9 for row in rows)
            else "pause geometry differs from normalized freeze frame",
            "first_possible_pipeline_stage": "none detected"
            if all((row["delta_normalized_to_pause_m"] or {}).get("distance", 0.0) <= 1e-9 for row in rows)
            else "analysis.interpolate.state_at / frame-state selection",
        },
    }

    render_single(output_dir / "debug_snapshot_raw.png", "Raw StatsBomb Freeze Frame", raw_players, raw_ball, style)
    render_single(output_dir / "debug_snapshot_normalized.png", "Normalized Freeze Frame", normalized_players, normalized_ball, style)
    render_single(output_dir / "debug_snapshot_pause.png", "Tactical Pause State", pause_players, pause_ball, style)
    render_four_panel(
        output_dir / "debug_snapshot_4panel.png",
        raw_players,
        normalized_players,
        pause_players,
        raw_ball,
        normalized_ball,
        pause_ball,
        style,
    )
    (output_dir / "debug_snapshot_comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(report["validation"], indent=2))


if __name__ == "__main__":
    main()
