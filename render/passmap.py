from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCAL_CACHE = ROOT / "renders" / ".cache"
LOCAL_MPLCONFIG = ROOT / "renders" / ".matplotlib"
LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
LOCAL_MPLCONFIG.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(LOCAL_CACHE))
os.environ.setdefault("MPLCONFIGDIR", str(LOCAL_MPLCONFIG))

import matplotlib.pyplot as plt
import yaml
from mplsoccer import VerticalPitch


CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_possession(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def xy(location: list[float] | None) -> tuple[float, float] | None:
    if not location or len(location) < 2:
        return None
    return float(location[0]), float(location[1])


def draw_comet_line(ax: Any, pitch: VerticalPitch, start: tuple[float, float], end: tuple[float, float], color: str, lw: float) -> None:
    segments = 10
    for idx in range(segments):
        t0 = idx / segments
        t1 = (idx + 1) / segments
        x0 = start[0] + (end[0] - start[0]) * t0
        y0 = start[1] + (end[1] - start[1]) * t0
        x1 = start[0] + (end[0] - start[0]) * t1
        y1 = start[1] + (end[1] - start[1]) * t1
        pitch.lines(x0, y0, x1, y1, ax=ax, color=color, lw=lw * (0.25 + 0.75 * t1), alpha=0.25 + 0.75 * t1)


def draw_passes(ax: Any, pitch: VerticalPitch, events: list[dict[str, Any]], config: dict[str, Any]) -> None:
    colors = config["brand"]["colors"]
    widths = config["brand"]["line_widths"]
    sizes = config["brand"]["marker_sizes"]

    pass_number = 1
    for event in events:
        start = xy(event.get("location"))
        end = xy(event.get("pass_end_location"))
        if event.get("type") != "Pass" or not start or not end:
            continue

        draw_comet_line(ax, pitch, start, end, colors["pass"], widths["pass"])
        pitch.scatter(*start, ax=ax, s=sizes["pass_start"], color=colors["pass"], edgecolors=colors["text"], linewidth=0.7, zorder=4)

        label_x = start[0] + (end[0] - start[0]) * 0.55
        label_y = start[1] + (end[1] - start[1]) * 0.55
        pitch.scatter(label_x, label_y, ax=ax, s=sizes["pass_number"], color=colors["field"], edgecolors=colors["pass"], linewidth=1.5, zorder=5)
        pitch.annotate(
            str(pass_number),
            xy=(label_x, label_y),
            ax=ax,
            ha="center",
            va="center",
            color=colors["text"],
            fontsize=8,
            weight="bold",
            zorder=6,
        )
        pass_number += 1


def draw_carries(ax: Any, pitch: VerticalPitch, events: list[dict[str, Any]], config: dict[str, Any]) -> None:
    colors = config["brand"]["colors"]
    widths = config["brand"]["line_widths"]

    for event in events:
        start = xy(event.get("location"))
        end = xy(event.get("carry_end_location"))
        if event.get("type") != "Carry" or not start or not end:
            continue
        pitch.lines(*start, *end, ax=ax, color=colors["carry"], lw=widths["carry"], linestyle=(0, (1.5, 3.5)), alpha=0.85, zorder=3)


def draw_shot(ax: Any, pitch: VerticalPitch, events: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any] | None:
    colors = config["brand"]["colors"]
    widths = config["brand"]["line_widths"]
    sizes = config["brand"]["marker_sizes"]

    shot = next((event for event in events if event.get("type") == "Shot"), None)
    if not shot:
        return None

    start = xy(shot.get("location"))
    end = xy(shot.get("shot_end_location")) or (120.0, 40.0)
    if start:
        pitch.lines(*start, *end, ax=ax, color=colors["shot"], lw=widths["shot"], alpha=0.95, zorder=4)
        pitch.scatter(*start, ax=ax, s=sizes["shot"], color=colors["shot"], edgecolors=colors["text"], linewidth=0.9, zorder=5)
    pitch.scatter(end[0], end[1], ax=ax, marker="*", s=sizes["goal_star"], color=colors["shot"], edgecolors=colors["text"], linewidth=0.9, zorder=6)
    return shot


def draw_shot_defenders(ax: Any, pitch: VerticalPitch, shot: dict[str, Any] | None, config: dict[str, Any]) -> None:
    if not shot:
        return

    colors = config["brand"]["colors"]
    sizes = config["brand"]["marker_sizes"]
    defenders = [player for player in shot.get("freeze_frame", []) if player.get("teammate") is False and xy(player.get("location"))]
    if not defenders:
        return

    xs = [xy(player["location"])[0] for player in defenders]
    ys = [xy(player["location"])[1] for player in defenders]
    pitch.scatter(xs, ys, ax=ax, s=sizes["defender"], color=colors["defender"], edgecolors=colors["text"], linewidth=0.6, alpha=0.95, zorder=5)


def render_passmap(payload: dict[str, Any], config: dict[str, Any]) -> plt.Figure:
    colors = config["brand"]["colors"]
    pitch_config = config["render"]["pitch"]
    fig_config = config["render"]["figure"]

    pitch = VerticalPitch(
        pitch_type=pitch_config["type"],
        pitch_color=colors["field"],
        line_color=colors["pitch_lines"],
        linewidth=1.2,
        half=False,
        pad_top=2,
        pad_bottom=2,
        pad_left=2,
        pad_right=2,
    )

    fig, ax = pitch.draw(figsize=(fig_config["width"], fig_config["height"]), constrained_layout=False)
    fig.patch.set_facecolor(colors["field"])
    ax.set_facecolor(colors["field"])

    events = payload["events"]
    draw_passes(ax, pitch, events, config)
    draw_carries(ax, pitch, events, config)
    shot = draw_shot(ax, pitch, events, config)
    draw_shot_defenders(ax, pitch, shot, config)

    text = config["render"]["text"]
    fig.text(0.5, 0.965, text["title"], ha="center", va="top", color=colors["text"], fontsize=30, weight="bold")
    fig.text(0.5, 0.932, payload["match_label"], ha="center", va="top", color=colors["muted_text"], fontsize=12)
    fig.text(0.5, 0.035, text["source"], ha="center", va="bottom", color=colors["muted_text"], fontsize=10)

    return fig


def main() -> None:
    config = load_config()
    possession_path = ROOT / config["data"]["possession_file"]
    payload = load_possession(possession_path)
    output_path = ROOT / config["render"]["output_file"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig = render_passmap(payload, config)
    fig.savefig(output_path, dpi=config["render"]["figure"]["dpi"], facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
