from __future__ import annotations

from src.domain.models import PlayerSnapshot, Position
from src.intelligence.features.pressure import nearest_defender_distance


def calculate_receiver_space(receiver_position: Position, defenders: list[PlayerSnapshot]) -> float:
    return nearest_defender_distance(receiver_position, defenders)
