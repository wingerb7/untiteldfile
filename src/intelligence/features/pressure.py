from __future__ import annotations

from math import dist, inf

from src.domain.models import PlayerSnapshot, Position


def _distance(a: Position, b: Position) -> float:
    return dist((a.x, a.y), (b.x, b.y))


def count_defenders_within_radius(position: Position, defenders: list[PlayerSnapshot], radius: float) -> int:
    return sum(1 for defender in defenders if _distance(position, defender.position) <= radius)


def nearest_defender_distance(position: Position, defenders: list[PlayerSnapshot]) -> float:
    if not defenders:
        return inf
    return min(_distance(position, defender.position) for defender in defenders)
