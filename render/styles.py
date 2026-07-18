from __future__ import annotations

from typing import Any


DEFAULT_STYLE = {
    "field": "#12382B",
    "pitch_lines": "#EAF2E6",
    "attack": "#46A7FF",
    "defense": "#E84A4A",
    "ball": "#FFD84D",
    "actor_edge": "#FFFFFF",
    "text": "#FFFFFF",
    "muted_text": "#B9C7BE",
    "timeline": "#FFFFFF",
}


def colors(config: dict[str, Any]) -> dict[str, str]:
    configured = config.get("brand", {}).get("colors", {})
    return {**DEFAULT_STYLE, **configured}
