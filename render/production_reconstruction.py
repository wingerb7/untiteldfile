from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
import numpy as np

from render.pitch import PITCH_LENGTH, PITCH_WIDTH, draw_pitch, sb_to_plot
from src.reconstruction import reconstruction_state_at, validate_reconstruction


Variant = Literal["minimal", "polished"]


def _selection_clock(reconstruction: dict[str, Any], presentation_time: float) -> float:
    selection = reconstruction.get("window_selection") or {}
    selection_start = float(selection.get("start_timestamp", reconstruction["start_timestamp"]))
    source_offset = float(reconstruction["start_timestamp"]) - selection_start
    return min(float(reconstruction["duration"]), max(0.0, presentation_time - source_offset))


def _presentation_duration(reconstruction: dict[str, Any]) -> float:
    selection = reconstruction.get("window_selection") or {}
    return float(selection.get("duration_seconds", reconstruction["duration"]))


def _camera_path(reconstruction: dict[str, Any], duration: float, fps: int) -> np.ndarray:
    frame_count = max(1, int(round(duration * fps)) + 1)
    targets = np.empty(frame_count, dtype=float)
    for index in range(frame_count):
        source_time = _selection_clock(reconstruction, min(duration, (index / fps) + 0.28))
        state = reconstruction_state_at(reconstruction, source_time)
        ball = state.get("ball")
        if ball:
            target = float(ball[0])
        else:
            visible = [float(player["location"][0]) for player in state["players"]]
            target = float(np.median(visible)) if visible else PITCH_LENGTH / 2
        targets[index] = target

    # A zero-phase exponential pass removes frame-to-frame camera noise while
    # retaining gentle anticipation. It changes framing only, never state.
    alpha = 0.075
    forward = targets.copy()
    for index in range(1, frame_count):
        forward[index] = forward[index - 1] + alpha * (targets[index] - forward[index - 1])
    smooth = forward.copy()
    for index in range(frame_count - 2, -1, -1):
        smooth[index] = smooth[index + 1] + alpha * (forward[index] - smooth[index + 1])
    return np.clip(smooth, 29.0, PITCH_LENGTH - 29.0)


def _pitch_style() -> dict[str, str]:
    return {
        "field": "#123D2B",
        "field_stripe": "#1B5138",
        "pitch_lines": "#E9F1E9",
    }


def render_production_reconstruction(
    reconstruction: dict[str, Any],
    output_path: str | Path,
    *,
    variant: Variant,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
) -> None:
    """Render canonical reconstructed state with presentation-only styling."""
    validate_reconstruction(reconstruction)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = _presentation_duration(reconstruction)
    frame_count = max(1, int(round(duration * fps)) + 1)
    dpi = 120
    style = _pitch_style()

    figure = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    figure.patch.set_facecolor("#091E16")
    axis = figure.add_axes([0.0, 0.0, 1.0, 1.0])
    draw_pitch(axis, style, {"brand": {"pitch": {"stripe_count": 12}}})
    axis.set_facecolor(style["field"])

    # Team colours are fixture presentation metadata only. The reconstruction's
    # teammate/opponent relation remains the sole grouping input.
    attack_colour = "#F36C21"  # Netherlands orange
    defense_colour = "#76B7E5"  # Argentina sky blue
    edge_colour = "#F7FAF7"
    shadow_colour = "#07130E"
    camera = _camera_path(reconstruction, duration, fps)

    # A fixed action crop is the baseline; the polished version follows the same
    # action with a restrained smoothed camera.
    fixed_center = float(np.median(camera))
    view_height = 58.0 if variant == "minimal" else 52.0

    player_shadow = axis.scatter([], [], s=270 if variant == "polished" else 220, c=shadow_colour, alpha=0.34, linewidths=0, zorder=4)
    attack = axis.scatter([], [], s=205 if variant == "polished" else 175, c=attack_colour, edgecolors=edge_colour, linewidths=2.0, zorder=6)
    defense = axis.scatter([], [], s=205 if variant == "polished" else 175, c=defense_colour, edgecolors=edge_colour, linewidths=2.0, zorder=6)
    ball_halo = axis.scatter([], [], s=250, c="#FFFFFF", alpha=0.20, linewidths=0, zorder=7)
    ball = axis.scatter([], [], s=92 if variant == "polished" else 78, c="#FFFFFF", edgecolors="#111A15", linewidths=2.2, zorder=9)

    def offsets(players: list[dict[str, Any]], *, shadow: bool = False) -> np.ndarray:
        result = []
        for player in players:
            point = sb_to_plot(player["location"])
            if point:
                result.append((point[0] + (0.45 if shadow else 0.0), point[1] - (0.55 if shadow else 0.0)))
        return np.asarray(result, dtype=float) if result else np.empty((0, 2))

    def update(frame_index: int) -> None:
        presentation_time = min(duration, frame_index / fps)
        state = reconstruction_state_at(reconstruction, _selection_clock(reconstruction, presentation_time))
        players = state["players"]
        teammates = [player for player in players if player.get("teammate")]
        opponents = [player for player in players if not player.get("teammate")]
        attack.set_offsets(offsets(teammates))
        defense.set_offsets(offsets(opponents))
        player_shadow.set_offsets(offsets(players, shadow=True))

        ball_point = sb_to_plot(state.get("ball"))
        ball_offsets = np.asarray([ball_point], dtype=float) if ball_point else np.empty((0, 2))
        ball.set_offsets(ball_offsets)
        ball_halo.set_offsets(ball_offsets)

        center = camera[min(frame_index, len(camera) - 1)] if variant == "polished" else fixed_center
        low = max(-2.5, min(PITCH_LENGTH + 2.5 - view_height, center - view_height / 2))
        axis.set_xlim(-4.0, PITCH_WIDTH + 4.0)
        axis.set_ylim(low, low + view_height)
        axis.set_aspect("equal", adjustable="box")

    writer = FFMpegWriter(
        fps=fps,
        codec="libx264",
        bitrate=10000,
        metadata={"title": f"Production football reconstruction — {variant}"},
        extra_args=["-pix_fmt", "yuv420p", "-preset", "slow", "-crf", "17"],
    )
    with writer.saving(figure, str(output_path), dpi):
        for frame_index in range(frame_count):
            update(frame_index)
            writer.grab_frame(facecolor=figure.get_facecolor())
    plt.close(figure)
