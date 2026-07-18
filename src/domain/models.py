from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Position:
    x: float
    y: float


@dataclass(frozen=True)
class PlayerSnapshot:
    tracking_id: str
    team_id: str
    position: Position
    is_teammate: bool
    is_goalkeeper: bool
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    timestamp: float
    possession_id: int
    team_id: str | None
    player_id: str | None
    start_position: Position | None
    end_position: Position | None
    recipient_id: str | None
    outcome: str | None
    freeze_frame: list[PlayerSnapshot]
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedPossession:
    possession_id: int
    attacking_team_id: str | None
    defending_team_id: str | None
    events: list[Event]
    start_timestamp: float
    end_timestamp: float
    source_name: str
    source_match_id: str | None = None
    limitations: list[str] = field(default_factory=list)
