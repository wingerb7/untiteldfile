from __future__ import annotations

from dataclasses import dataclass
from math import inf

from src.domain.models import PlayerSnapshot, Position
from src.intelligence.features.geometry import lane_length, point_segment_distance


@dataclass(frozen=True)
class PassingLaneEvidence:
    defenders_in_lane: int
    minimum_defender_distance: float | None
    lane_length: float
    openness: float
    is_open: bool


def estimate_passing_lane(
    start: Position,
    end: Position,
    defenders: list[PlayerSnapshot],
    lane_width: float = 3.0,
    open_distance: float = 6.0,
) -> PassingLaneEvidence:
    distances = [point_segment_distance(defender.position, start, end) for defender in defenders]
    minimum = min(distances) if distances else inf
    blockers = sum(1 for value in distances if value <= lane_width)
    openness = min(1.0, minimum / open_distance) if minimum != inf else 1.0
    if blockers:
        openness *= 1.0 / (1.0 + blockers)
    return PassingLaneEvidence(
        defenders_in_lane=blockers,
        minimum_defender_distance=None if minimum == inf else round(minimum, 3),
        lane_length=round(lane_length(start, end), 3),
        openness=round(openness, 3),
        is_open=blockers == 0 and openness >= 0.65,
    )
