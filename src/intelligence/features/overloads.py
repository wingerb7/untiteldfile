from __future__ import annotations

from dataclasses import dataclass

from src.domain.models import PlayerSnapshot, Position
from src.intelligence.features.geometry import distance


@dataclass(frozen=True)
class OverloadEvidence:
    attackers: int
    defenders: int
    margin: int
    radius: float
    has_overload: bool


def estimate_local_overload(
    position: Position,
    attackers: list[PlayerSnapshot],
    defenders: list[PlayerSnapshot],
    radius: float = 12.0,
) -> OverloadEvidence:
    attacker_count = sum(1 for player in attackers if distance(position, player.position) <= radius)
    defender_count = sum(1 for player in defenders if distance(position, player.position) <= radius)
    margin = attacker_count - defender_count
    return OverloadEvidence(attacker_count, defender_count, margin, radius, margin > 0)
