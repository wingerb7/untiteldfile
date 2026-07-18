from __future__ import annotations

import textwrap
from typing import Any

import numpy as np
from matplotlib.axes import Axes

from render.pitch import sb_to_plot


def empty_offsets() -> Any:
    return np.empty((0, 2))


def point_offset(point: tuple[float, float] | None) -> Any:
    if point is None:
        return empty_offsets()
    return np.array([point])


def create_overlay_artists(ax: Axes, fig: Any, style: dict[str, str]) -> dict[str, Any]:
    return {
        "passer_highlight": ax.scatter([], [], s=270, facecolors="none", edgecolors=style["ball"], linewidths=3.0, zorder=11),
        "receiver_highlight": ax.scatter([], [], s=270, facecolors="none", edgecolors=style["ball"], linewidths=3.0, zorder=11),
        "pass_arrow": ax.annotate(
            "",
            xy=(0, 0),
            xytext=(0, 0),
            arrowprops={"arrowstyle": "->", "color": style["ball"], "lw": 3.2, "alpha": 0.0},
            zorder=10,
        ),
        "defensive_line": ax.plot([], [], color=style["text"], linewidth=2.4, linestyle=(0, (5, 4)), alpha=0.0, zorder=9)[0],
        "caption": fig.text(
            0.5,
            0.875,
            "",
            ha="center",
            va="center",
            color=style["text"],
            fontsize=14,
            weight="bold",
            bbox={"boxstyle": "round,pad=0.45", "facecolor": "#0B2019", "edgecolor": style["ball"], "alpha": 0.92},
            zorder=20,
        ),
    }


def clear_overlays(artists: dict[str, Any]) -> None:
    artists["passer_highlight"].set_offsets(empty_offsets())
    artists["receiver_highlight"].set_offsets(empty_offsets())
    artists["pass_arrow"].set_position((0, 0))
    artists["pass_arrow"].xy = (0, 0)
    artists["pass_arrow"].arrow_patch.set_alpha(0.0)
    artists["defensive_line"].set_data([], [])
    artists["defensive_line"].set_alpha(0.0)
    artists["caption"].set_text("")
    artists["caption"].set_alpha(0.0)


def execute_instruction(instruction: dict[str, Any], event: dict[str, Any], artists: dict[str, Any]) -> None:
    instruction_type = instruction.get("type")
    if instruction_type == "highlight_player":
        target = instruction.get("target")
        location = event.get("start_location") if target == "passer" else event.get("end_location")
        point = sb_to_plot(location)
        if target == "passer":
            artists["passer_highlight"].set_offsets(point_offset(point))
        elif target == "receiver":
            artists["receiver_highlight"].set_offsets(point_offset(point))
    elif instruction_type == "draw_pass_arrow":
        start = sb_to_plot(event.get("start_location"))
        end = sb_to_plot(event.get("end_location"))
        if start and end:
            artists["pass_arrow"].set_position(start)
            artists["pass_arrow"].xy = end
            artists["pass_arrow"].arrow_patch.set_alpha(0.95)
    elif instruction_type == "draw_defensive_line":
        line_x = instruction.get("x")
        if line_x is not None:
            artists["defensive_line"].set_data([0, 80], [float(line_x), float(line_x)])
            artists["defensive_line"].set_alpha(0.85)
    elif instruction_type == "show_caption":
        artists["caption"].set_text(textwrap.fill(str(instruction.get("text") or ""), width=64))
        artists["caption"].set_alpha(1.0)
