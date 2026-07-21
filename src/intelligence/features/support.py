from __future__ import annotations

from src.domain.models import PlayerSnapshot, Position
from src.intelligence.features.geometry import distance
from src.intelligence.features.passing_lanes import estimate_passing_lane


def count_support_options(
    ball_position: Position,
    teammates: list[PlayerSnapshot],
    defenders: list[PlayerSnapshot],
    maximum_distance: float = 28.0,
    minimum_lane_openness: float = 0.45,
) -> int:
    options = 0
    for teammate in teammates:
        if distance(ball_position, teammate.position) > maximum_distance:
            continue
        lane = estimate_passing_lane(ball_position, teammate.position, defenders)
        if lane.openness >= minimum_lane_openness:
            options += 1
    return options
