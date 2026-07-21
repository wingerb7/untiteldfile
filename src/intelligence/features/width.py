from __future__ import annotations

from dataclasses import dataclass

from src.domain.models import PlayerSnapshot, Position
from src.intelligence.features.geometry import PITCH_WIDTH, ball_side, distance_to_nearest_touchline, lateral_spread


@dataclass(frozen=True)
class WidthEvidence:
    distance_to_touchline: float
    team_width: float
    width_ratio: float
    is_wide: bool
    is_isolated_wide_player: bool


def estimate_width(
    position: Position,
    teammates: list[PlayerSnapshot],
    isolation_radius: float = 14.0,
    wide_touchline_distance: float = 12.0,
) -> WidthEvidence:
    team_width = lateral_spread(teammates)
    touchline_distance = distance_to_nearest_touchline(position)
    side = ball_side(position)
    same_side_teammates = [
        player
        for player in teammates
        if player.position != position and ball_side(player.position) == side
    ]
    isolated = all(
        abs(player.position.y - position.y) > isolation_radius or abs(player.position.x - position.x) > isolation_radius
        for player in same_side_teammates
    )
    return WidthEvidence(
        distance_to_touchline=round(touchline_distance, 3),
        team_width=round(team_width, 3),
        width_ratio=round(team_width / PITCH_WIDTH, 3),
        is_wide=touchline_distance <= wide_touchline_distance,
        is_isolated_wide_player=touchline_distance <= wide_touchline_distance and isolated,
    )
