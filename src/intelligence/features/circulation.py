from __future__ import annotations

from src.domain.models import Event
from src.intelligence.features.geometry import lane_length


def ball_circulation_speed(previous: Event | None, current: Event) -> float | None:
    if previous is None or not previous.end_position or not current.end_position:
        return None
    elapsed = current.timestamp - previous.timestamp
    if elapsed <= 0:
        return None
    return round(lane_length(previous.end_position, current.end_position) / elapsed, 3)
