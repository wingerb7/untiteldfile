from __future__ import annotations

from dataclasses import asdict, dataclass
from math import inf

from src.domain.models import PlayerSnapshot, Position
from src.intelligence.features.geometry import minimum_distance_to_players
from src.intelligence.features.passing_lanes import PassingLaneEvidence


@dataclass(frozen=True)
class ReceiverFreedomEvidence:
    nearest_defender_distance: float | None
    lane_openness: float
    freedom: float
    is_free: bool


def estimate_receiver_freedom(
    receiver_position: Position,
    defenders: list[PlayerSnapshot],
    lane: PassingLaneEvidence,
    free_distance: float = 6.0,
) -> ReceiverFreedomEvidence:
    nearest = minimum_distance_to_players(receiver_position, defenders)
    distance_component = 1.0 if nearest == inf else min(1.0, nearest / free_distance)
    freedom = 0.6 * distance_component + 0.4 * lane.openness
    return ReceiverFreedomEvidence(
        nearest_defender_distance=None if nearest == inf else round(nearest, 3),
        lane_openness=lane.openness,
        freedom=round(freedom, 3),
        is_free=freedom >= 0.65,
    )


def receiver_freedom_payload(evidence: ReceiverFreedomEvidence) -> dict:
    return asdict(evidence)
