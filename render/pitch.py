from __future__ import annotations

from typing import Any

from matplotlib.axes import Axes
from matplotlib.patches import Arc, Circle, Rectangle


PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0


def sb_to_plot(location: list[float] | tuple[float, float] | None) -> tuple[float, float] | None:
    if not location or len(location) < 2:
        return None
    return float(location[1]), float(location[0])


def draw_pitch(ax: Axes, style: dict[str, str], config: dict[str, Any]) -> None:
    field = style["field"]
    line = style["pitch_lines"]
    ax.set_facecolor(field)
    ax.set_xlim(-3, PITCH_WIDTH + 3)
    ax.set_ylim(-3, PITCH_LENGTH + 3)
    ax.set_aspect("equal")
    ax.axis("off")

    stripe = style.get("field_stripe", "#184834")
    stripe_count = int(config.get("brand", {}).get("pitch", {}).get("stripe_count", 10))
    stripe_height = PITCH_LENGTH / max(1, stripe_count)
    for idx in range(stripe_count):
        if idx % 2 == 0:
            ax.add_patch(
                Rectangle(
                    (0, idx * stripe_height),
                    PITCH_WIDTH,
                    stripe_height,
                    facecolor=stripe,
                    edgecolor="none",
                    alpha=0.32,
                    zorder=0,
                )
            )

    lw = 2.2
    ax.add_patch(Rectangle((0, 0), PITCH_WIDTH, PITCH_LENGTH, fill=False, edgecolor=line, linewidth=lw))
    ax.plot([0, PITCH_WIDTH], [60, 60], color=line, linewidth=lw)
    ax.add_patch(Circle((40, 60), 10, fill=False, edgecolor=line, linewidth=lw))
    ax.scatter([40], [60], s=18, color=line, zorder=2)

    # Bottom goal and boxes.
    ax.add_patch(Rectangle((18, 0), 44, 18, fill=False, edgecolor=line, linewidth=lw))
    ax.add_patch(Rectangle((30, 0), 20, 6, fill=False, edgecolor=line, linewidth=lw))
    ax.scatter([40], [12], s=18, color=line, zorder=2)
    ax.add_patch(Arc((40, 12), 20, 20, theta1=36, theta2=144, color=line, linewidth=lw))
    ax.plot([36, 44], [0, 0], color=line, linewidth=4)

    # Attacking goal and boxes.
    ax.add_patch(Rectangle((18, 102), 44, 18, fill=False, edgecolor=line, linewidth=lw))
    ax.add_patch(Rectangle((30, 114), 20, 6, fill=False, edgecolor=line, linewidth=lw))
    ax.scatter([40], [108], s=18, color=line, zorder=2)
    ax.add_patch(Arc((40, 108), 20, 20, theta1=216, theta2=324, color=line, linewidth=lw))
    ax.plot([36, 44], [120, 120], color=line, linewidth=4)
