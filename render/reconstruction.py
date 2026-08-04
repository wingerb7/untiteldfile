from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.animation import FFMpegWriter
from matplotlib.patches import Polygon
import numpy as np

from render.pitch import draw_pitch, sb_to_plot
from render.styles import colors
from src.reconstruction import reconstruction_state_at, validate_reconstruction


def _offsets(players: list[dict[str, Any]]) -> np.ndarray:
    points = [sb_to_plot(player["location"]) for player in players]
    return np.array(points) if points else np.empty((0, 2))


def render_reconstruction(
    reconstruction: dict[str, Any],
    config: dict[str, Any],
    output_path: str | Path,
    *,
    visual_qa: bool = False,
    uncertainty_presentation: bool = False,
    selection_timeline: bool = False,
) -> None:
    """Render only reconstructed state. No analysis/story object is accepted."""
    validate_reconstruction(reconstruction)
    output_path = Path(output_path)
    animation = config.get("animation", {})
    fps = int(animation.get("fps", 30))
    width = int(animation.get("width", 1080))
    height = int(animation.get("height", 1920))
    dpi = 100
    style = colors(config)
    figure = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    figure.patch.set_facecolor(style["field"])
    axis = figure.add_axes([0.06, 0.08, 0.88, 0.84])
    draw_pitch(axis, style, config)
    title = figure.text(0.5, 0.96, reconstruction.get("match_label") or str(reconstruction["match_id"]), ha="center", color=style["text"], fontsize=18)
    clock = figure.text(0.5, 0.035, "", ha="center", color=style["text"], fontsize=13)
    attack = axis.scatter([], [], s=86, c=style["attack"], edgecolors=style["player_edge"], zorder=5)
    defense = axis.scatter([], [], s=86, c=style["defense"], edgecolors=style["player_edge"], zorder=5)
    ball = axis.scatter([], [], s=55, c=style["ball"], edgecolors=style["player_edge"], zorder=7)
    ghosts = axis.scatter([], [], s=110, facecolors="none", edgecolors="#B9C7BE", linewidths=1.2, alpha=0.32, zorder=4)
    labels: list[Any] = []
    area_patch: Polygon | None = None
    reconstruction_duration = float(reconstruction["duration"])
    selection = reconstruction.get("window_selection") or {}
    selection_start = float(selection.get("start_timestamp", reconstruction["start_timestamp"]))
    selection_duration = float(selection.get("duration_seconds", reconstruction_duration))
    source_offset = float(reconstruction["start_timestamp"]) - selection_start
    duration = selection_duration if selection_timeline else reconstruction_duration

    def update(frame_index: int) -> list[Any]:
        nonlocal area_patch
        presentation_timestamp = min(duration, frame_index / fps)
        timestamp = min(
            reconstruction_duration,
            max(0.0, presentation_timestamp - source_offset),
        ) if selection_timeline else presentation_timestamp
        state = reconstruction_state_at(reconstruction, timestamp)
        players = state["players"]
        teammates = [player for player in players if player.get("teammate")]
        opponents = [player for player in players if not player.get("teammate")]
        attack.set_offsets(_offsets(teammates))
        defense.set_offsets(_offsets(opponents))
        attack.set_facecolors([to_rgba(style["attack"], 1.0 if player["interpolation_state"] == "OBSERVED" else max(0.25, 0.65 * float(player["confidence"]))) for player in teammates] or [to_rgba(style["attack"], 1.0)])
        defense.set_facecolors([to_rgba(style["defense"], 1.0 if player["interpolation_state"] == "OBSERVED" else max(0.25, 0.65 * float(player["confidence"]))) for player in opponents] or [to_rgba(style["defense"], 1.0)])
        point = sb_to_plot(state.get("ball"))
        ball.set_offsets(np.array([point]) if point else np.empty((0, 2)))
        ghost_players = []
        if uncertainty_presentation:
            lifetime = float(config.get("reconstruction_window", {}).get("uncertainty_display_lifetime_seconds", 0.75))
            left = max((frame for frame in reconstruction["keyframes"] if frame["timestamp"] <= timestamp), default=None, key=lambda frame: frame["timestamp"])
            if left is not None:
                visible_ids = {player["tracking_id"] for player in players}
                for player in left["players"]:
                    last = player.get("last_observed_timestamp")
                    if player["tracking_id"] not in visible_ids and player.get("last_known_position") and last is not None and 0 <= timestamp - last <= lifetime:
                        ghost_players.append(player)
        ghosts.set_offsets(np.array([sb_to_plot(player["last_known_position"]) for player in ghost_players]) if ghost_players else np.empty((0, 2)))
        clock.set_text(f"{timestamp:07.2f}s  {state.get('event_id', '')}")
        for label in labels:
            label.remove()
        labels.clear()
        if area_patch is not None:
            area_patch.remove()
            area_patch = None
        if visual_qa:
            area = state.get("visible_area")
            if isinstance(area, list) and len(area) >= 8 and len(area) % 2 == 0:
                points = [sb_to_plot(area[index:index + 2]) for index in range(0, len(area), 2)]
                area_patch = Polygon(points, closed=True, fill=False, edgecolor="#FFD84D", linestyle="--", linewidth=1.2, alpha=0.8, zorder=3)
                axis.add_patch(area_patch)
            for player in players:
                x, y = sb_to_plot(player["location"])
                identity = player.get("identity") or {}
                identity_text = identity.get("player_name") or identity.get("player_id") or player["tracking_id"]
                source = (player.get("source") or {}).get("kind", "UNKNOWN")
                last = player.get("last_observed_timestamp")
                age = player.get("interpolation_duration")
                age_text = f"{age:.2f}s" if age is not None else "?"
                source_event = (player.get("source") or {}).get("event_id", "?")
                text = f"{identity_text}\n{player['interpolation_state']} {player['confidence']:.2f} age={age_text}\nlast={last if last is not None else '?'} {source}\nsource={source_event}"
                labels.append(axis.text(x + 1.1, y + 1.1, text, color=style["text"], fontsize=6, zorder=9, bbox={"facecolor": style["field"], "alpha": 0.65, "edgecolor": "none", "pad": 1}))
            for player in ghost_players:
                x, y = sb_to_plot(player["last_known_position"])
                labels.append(axis.text(x + 1.1, y + 1.1, f"{player['tracking_id']}\nUNKNOWN display-only", color=style["muted_text"], fontsize=6, zorder=9))
            ball_source = state.get("ball_source") or {}
            labels.append(axis.text(1, 118, f"BALL {state.get('ball_state')} source={ball_source.get('event_id', '?')}", color=style["ball"], fontsize=7, zorder=9, bbox={"facecolor": style["field"], "alpha": 0.7, "edgecolor": "none"}))
        return [attack, defense, ball, ghosts, title, clock, *labels, *([area_patch] if area_patch else [])]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = FFMpegWriter(fps=fps, metadata={"title": "Deterministic StatsBomb reconstruction"}, bitrate=4500)
    with writer.saving(figure, str(output_path), dpi):
        for frame_index in range(max(1, int(duration * fps) + 1)):
            update(frame_index)
            writer.grab_frame()
    plt.close(figure)
