from __future__ import annotations

from math import dist, inf, sqrt

from src.domain.models import PlayerSnapshot, Position


PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def distance(a: Position, b: Position) -> float:
    return dist((a.x, a.y), (b.x, b.y))


def distance_to_nearest_touchline(position: Position) -> float:
    return min(position.y, PITCH_WIDTH - position.y)


def lateral_spread(players: list[PlayerSnapshot]) -> float:
    if len(players) < 2:
        return 0.0
    ys = [player.position.y for player in players]
    return max(ys) - min(ys)


def ball_side(position: Position) -> str:
    return "left" if position.y < PITCH_WIDTH / 2 else "right"


def opposite_side(side: str) -> str:
    return "right" if side == "left" else "left"


def players_on_side(players: list[PlayerSnapshot], side: str) -> list[PlayerSnapshot]:
    if side == "left":
        return [player for player in players if player.position.y < PITCH_WIDTH / 2]
    return [player for player in players if player.position.y >= PITCH_WIDTH / 2]


def point_segment_distance(point: Position, start: Position, end: Position) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return distance(point, start)
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_sq
    t = clamp01(t)
    projection = Position(start.x + t * dx, start.y + t * dy)
    return distance(point, projection)


def minimum_distance_to_players(position: Position, players: list[PlayerSnapshot]) -> float:
    if not players:
        return inf
    return min(distance(position, player.position) for player in players)


def lane_length(start: Position, end: Position) -> float:
    return sqrt((end.x - start.x) ** 2 + (end.y - start.y) ** 2)
