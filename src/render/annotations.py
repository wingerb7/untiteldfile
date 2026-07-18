from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from matplotlib.axes import Axes
from matplotlib.patches import Circle, FancyArrowPatch, Polygon

from render.pitch import sb_to_plot


def load_annotations(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    annotation_path = Path(path)
    if not annotation_path.exists():
        return []
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    return list(payload.get("annotations", []))


def annotation_alpha(annotation: dict[str, Any], t: float) -> float:
    start = float(annotation.get("t_start", 0.0))
    end = float(annotation.get("t_end", 0.0))
    if t < start or t > end:
        return 0.0
    fade = min(0.35, max(0.001, (end - start) * 0.25))
    if t < start + fade:
        return (t - start) / fade
    if t > end - fade:
        return (end - t) / fade
    return 1.0


def active_annotations(annotations: list[dict[str, Any]], t: float) -> list[tuple[dict[str, Any], float]]:
    return [(annotation, annotation_alpha(annotation, t)) for annotation in annotations if annotation_alpha(annotation, t) > 0]


def draw_label(ax: Axes, point: tuple[float, float], label: str, color: str, alpha: float, dy: float = 2.2) -> Any:
    return ax.text(
        point[0],
        point[1] + dy,
        label,
        ha="center",
        va="center",
        color=color,
        fontsize=8.5,
        weight="bold",
        alpha=alpha,
        zorder=24,
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "#121912", "edgecolor": color, "linewidth": 0.8, "alpha": 0.72 * alpha},
    )


def draw_run_arrow(ax: Axes, annotation: dict[str, Any], color: str, alpha: float) -> list[Any]:
    points = [sb_to_plot(point) for point in annotation.get("path", [])]
    points = [point for point in points if point is not None]
    if len(points) < 2:
        return []
    artists: list[Any] = []
    for start, end in zip(points, points[1:], strict=False):
        arrow = FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=2.2,
            linestyle=(0, (3, 3)),
            color=color,
            alpha=0.9 * alpha,
            connectionstyle="arc3,rad=0.18",
            zorder=22,
        )
        ax.add_patch(arrow)
        artists.append(arrow)
    if annotation.get("label"):
        artists.append(draw_label(ax, points[-1], str(annotation["label"]), color, alpha, dy=3.0))
    return artists


def draw_pass_highlight(ax: Axes, annotation: dict[str, Any], color: str, alpha: float) -> list[Any]:
    start = sb_to_plot(annotation.get("from"))
    end = sb_to_plot(annotation.get("to"))
    if start is None or end is None:
        return []
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=13,
        linewidth=2.6,
        color=color,
        alpha=0.92 * alpha,
        connectionstyle="arc3,rad=-0.08",
        zorder=21,
    )
    ax.add_patch(arrow)
    artists: list[Any] = [arrow]
    if annotation.get("label"):
        mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        artists.append(draw_label(ax, mid, str(annotation["label"]), color, alpha, dy=2.4))
    return artists


def draw_space_zone(ax: Axes, annotation: dict[str, Any], color: str, alpha: float) -> list[Any]:
    points = [sb_to_plot(point) for point in annotation.get("polygon", [])]
    points = [point for point in points if point is not None]
    if len(points) < 3:
        return []
    polygon = Polygon(points, closed=True, facecolor=color, edgecolor=color, linewidth=1.4, hatch="///", alpha=0.18 * alpha, zorder=3)
    ax.add_patch(polygon)
    artists: list[Any] = [polygon]
    if annotation.get("label"):
        cx = sum(point[0] for point in points) / len(points)
        cy = sum(point[1] for point in points) / len(points)
        artists.append(draw_label(ax, (cx, cy), str(annotation["label"]), color, alpha, dy=0.0))
    return artists


def draw_player_highlight(ax: Axes, annotation: dict[str, Any], color: str, alpha: float, t: float) -> list[Any]:
    point = sb_to_plot([annotation.get("x"), annotation.get("y")])
    if point is None:
        return []
    pulse = 1.0 + 0.22 * (1.0 + math.sin(t * 8.0))
    ring = Circle(point, radius=3.4 * pulse, facecolor="none", edgecolor=color, linewidth=2.4, alpha=0.92 * alpha, zorder=23)
    ax.add_patch(ring)
    artists: list[Any] = [ring]
    if annotation.get("label"):
        artists.append(draw_label(ax, point, str(annotation["label"]), color, alpha, dy=-5.0))
    return artists


def draw_text_callout(ax: Axes, annotation: dict[str, Any], color: str, alpha: float) -> list[Any]:
    point = sb_to_plot([annotation.get("x"), annotation.get("y")])
    if point is None or not annotation.get("label"):
        return []
    return [draw_label(ax, point, str(annotation["label"]), color, alpha, dy=0.0)]


def draw_annotations(ax: Axes, annotations: list[dict[str, Any]], t: float, style: dict[str, str]) -> list[Any]:
    artists: list[Any] = []
    color = style.get("analysis", "#FFD84D")
    zone_color = style.get("space_zone", color)
    for annotation, alpha in active_annotations(annotations, t):
        kind = annotation.get("kind")
        if kind == "run_arrow":
            artists.extend(draw_run_arrow(ax, annotation, color, alpha))
        elif kind == "space_zone":
            artists.extend(draw_space_zone(ax, annotation, zone_color, alpha))
        elif kind == "player_highlight":
            artists.extend(draw_player_highlight(ax, annotation, color, alpha, t))
        elif kind == "pass_highlight":
            artists.extend(draw_pass_highlight(ax, annotation, color, alpha))
        elif kind == "text_callout":
            artists.extend(draw_text_callout(ax, annotation, style.get("analysis_alt", "#FFFFFF"), alpha))
    return artists
