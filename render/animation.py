from __future__ import annotations

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

import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
import numpy as np
import yaml

from analysis.interpolate import build_animation_model, state_at
from analysis.normalize import load_and_normalize
from render.pitch import draw_pitch, sb_to_plot
from render.styles import colors


CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def split_players(players: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    visible_players = [player for player in players if player.get("visible", True)]
    attackers = [player for player in visible_players if player.get("teammate")]
    defenders = [player for player in visible_players if not player.get("teammate")]
    return attackers, defenders


def coordinates(players: list[dict[str, Any]]) -> tuple[list[float], list[float]]:
    points = [sb_to_plot(player.get("location")) for player in players]
    points = [point for point in points if point is not None]
    return [point[0] for point in points], [point[1] for point in points]


def actor_player(players: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((player for player in players if player.get("actor")), None)


def alpha_list(players: list[dict[str, Any]]) -> list[float]:
    return [float(player.get("alpha", 1.0)) for player in players]


def offsets(xs: list[float], ys: list[float]) -> Any:
    if not xs:
        return np.empty((0, 2))
    return np.column_stack([xs, ys])


def single_offset(point: tuple[float, float] | None) -> Any:
    if point is None:
        return np.empty((0, 2))
    return np.array([point])


def render_animation(model: dict[str, Any], config: dict[str, Any], output_path: Path) -> None:
    animation_config = config["animation"]
    fps = int(animation_config.get("fps", 30))
    width = int(animation_config.get("width", 1080))
    height = int(animation_config.get("height", 1920))
    dpi = 100
    style = colors(config)

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor(style["field"])
    ax = fig.add_axes([0.08, 0.12, 0.84, 0.78])
    draw_pitch(ax, style, config)

    title = fig.text(0.5, 0.955, "POSSESSION 52", ha="center", va="top", color=style["text"], fontsize=30, weight="bold")
    subtitle = fig.text(0.5, 0.925, model["possession"].get("match_label") or "", ha="center", va="top", color=style["muted_text"], fontsize=14)
    event_text = fig.text(0.5, 0.075, "", ha="center", va="bottom", color=style["text"], fontsize=18, weight="bold")
    detail_text = fig.text(0.5, 0.05, "", ha="center", va="bottom", color=style["muted_text"], fontsize=13)
    timeline_line = fig.add_axes([0.18, 0.035, 0.64, 0.008])
    timeline_line.set_facecolor(style["muted_text"])
    timeline_line.set_xlim(0, model["duration"])
    timeline_line.set_ylim(0, 1)
    timeline_line.axis("off")
    progress_bar = timeline_line.axvspan(0, 0, color=style["ball"], ymin=0, ymax=1)

    attack_scatter = ax.scatter([], [], s=80, c=style["attack"], edgecolors=style["actor_edge"], linewidths=0.8, zorder=5)
    defense_scatter = ax.scatter([], [], s=76, c=style["defense"], edgecolors=style["actor_edge"], linewidths=0.8, zorder=5)
    actor_scatter = ax.scatter([], [], s=190, facecolors="none", edgecolors=style["actor_edge"], linewidths=2.4, zorder=7)
    ball_scatter = ax.scatter([], [], s=64, c=style["ball"], edgecolors=style["actor_edge"], linewidths=0.9, zorder=8)
    action_line, = ax.plot([], [], color=style["ball"], linewidth=2.0, alpha=0.0, zorder=4)
    xg_text = ax.text(40, 116, "", ha="center", va="center", color=style["ball"], fontsize=16, weight="bold", zorder=9)

    total_frames = max(1, int(model["duration"] * fps))

    def update(frame_idx: int) -> list[Any]:
        nonlocal progress_bar
        t = min(model["duration"], frame_idx / fps)
        state = state_at(model, t)
        attackers, defenders = split_players(state["players"])
        ax_x, ax_y = coordinates(attackers)
        dx, dy = coordinates(defenders)

        attack_scatter.set_offsets(offsets(ax_x, ax_y))
        defense_scatter.set_offsets(offsets(dx, dy))
        attack_scatter.set_alpha(0.95)
        defense_scatter.set_alpha(0.95)

        actor = actor_player(state["players"])
        actor_point = sb_to_plot(actor.get("location")) if actor else None
        actor_scatter.set_offsets(single_offset(actor_point))

        ball_point = sb_to_plot(state["ball"])
        ball_scatter.set_offsets(single_offset(ball_point))

        event = state["event"] or {}
        start = sb_to_plot(event.get("start_location"))
        end = sb_to_plot(event.get("end_location"))
        if event.get("type") in {"Pass", "Shot"} and start and ball_point:
            action_line.set_data([start[0], ball_point[0]], [start[1], ball_point[1]])
            action_line.set_alpha(0.7 if event.get("type") == "Shot" else 0.35)
        else:
            action_line.set_data([], [])
            action_line.set_alpha(0.0)

        event_name = event.get("type", "")
        player_name = event.get("player_name") or ""
        event_text.set_text(f"{event_name}  |  {player_name}".strip())
        if event.get("type") == "Shot" and event.get("xg") is not None:
            xg = float(event["xg"])
            detail_text.set_text(f"xG {xg:.3f}")
            xg_text.set_text(f"xG {xg:.3f}")
        else:
            detail_text.set_text("Argentina attack reconstruction from StatsBomb 360")
            xg_text.set_text("")

        progress_bar.remove()
        progress_bar = timeline_line.axvspan(0, t, color=style["ball"], ymin=0, ymax=1)

        return [
            attack_scatter,
            defense_scatter,
            actor_scatter,
            ball_scatter,
            action_line,
            title,
            subtitle,
            event_text,
            detail_text,
            xg_text,
            progress_bar,
        ]

    writer = FFMpegWriter(fps=fps, metadata={"title": "Possession 52"}, bitrate=4500)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with writer.saving(fig, str(output_path), dpi):
        for frame_idx in range(total_frames):
            update(frame_idx)
            writer.grab_frame()
    plt.close(fig)


def main() -> None:
    config = load_config()
    possession = load_and_normalize(ROOT / config["data"]["possession_file"])
    model = build_animation_model(possession, config)
    output_path = ROOT / config["animation"]["output_file"]
    render_animation(model, config, output_path)
    print(f"Wrote {output_path} ({model['duration']:.2f}s)")


if __name__ == "__main__":
    main()
