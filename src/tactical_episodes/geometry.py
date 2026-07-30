from __future__ import annotations

from src.domain.enums import AttackingDirection
from src.domain.models import PlayerSnapshot, Position
from src.intelligence.features.geometry import PITCH_WIDTH, distance
from src.intelligence.features.progression import GOAL_X

# Standard analytics convention: dividing the pitch width into five vertical
# channels (wing / half-space / centre / half-space / wing) of equal size.
_CHANNEL_WIDTH = PITCH_WIDTH / 5.0
_HALF_SPACE_BANDS = (
    (_CHANNEL_WIDTH, 2 * _CHANNEL_WIDTH),
    (3 * _CHANNEL_WIDTH, 4 * _CHANNEL_WIDTH),
)

# Standard StatsBomb penalty box: 18 yards deep, 44 yards wide, centred on goal.
_BOX_DEPTH = 18.0
_BOX_HALF_WIDTH = 22.0

# A tight marking distance commonly used to define "under pressure".
PRESS_DISTANCE_M = 5.0


def nearest_defender(position: Position, defenders: list[PlayerSnapshot]) -> PlayerSnapshot | None:
    if not defenders:
        return None
    return min(defenders, key=lambda defender: distance(position, defender.position))


def is_in_half_space(position: Position) -> bool:
    return any(low <= position.y <= high for low, high in _HALF_SPACE_BANDS)


def is_in_box(position: Position, attacking_direction: str = AttackingDirection.LEFT_TO_RIGHT.value) -> bool:
    goal_x = GOAL_X[AttackingDirection(attacking_direction)]
    within_depth = abs(goal_x - position.x) <= _BOX_DEPTH
    within_width = abs(position.y - PITCH_WIDTH / 2) <= _BOX_HALF_WIDTH
    return within_depth and within_width
