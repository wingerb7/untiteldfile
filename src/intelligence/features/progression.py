from __future__ import annotations

from src.domain.enums import AttackingDirection
from src.domain.models import Position


GOAL_X = {
    AttackingDirection.LEFT_TO_RIGHT: 120.0,
    AttackingDirection.RIGHT_TO_LEFT: 0.0,
}


def calculate_forward_progress(start: Position, end: Position, attacking_direction: str) -> float:
    direction = AttackingDirection(attacking_direction)
    if direction == AttackingDirection.LEFT_TO_RIGHT:
        return end.x - start.x
    return start.x - end.x


def calculate_goal_distance_reduction(start: Position, end: Position, attacking_direction: str) -> float:
    direction = AttackingDirection(attacking_direction)
    goal_x = GOAL_X[direction]
    start_distance = abs(goal_x - start.x)
    end_distance = abs(goal_x - end.x)
    return start_distance - end_distance
