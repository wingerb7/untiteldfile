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


@dataclass(frozen=True)
class TacticalFinding:
    finding_id: str
    pattern_type: str
    event_id: str
    confidence: float
    evidence: dict[str, Any]
    explanation_key: str
    limitations: list[str]
    players_involved: list[str] = field(default_factory=list)
    feature_values: dict[str, Any] = field(default_factory=dict)
    actors: list[str] = field(default_factory=list)
    receivers: list[str] = field(default_factory=list)
    created_space_for: list[str] = field(default_factory=list)
    enabled_by: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NarrativeStep:
    step_id: str
    step_type: str
    event_id: str
    actor_id: str | None
    receiver_id: str | None
    caption: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionChain:
    chain_id: str
    primary_finding_id: str
    start_event_id: str
    end_event_id: str
    score: float
    steps: list[NarrativeStep]
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SocialPacingProfile:
    name: str
    hook_duration: float
    transition_duration: float
    pre_action_context: float
    caption_hold_min: float
    caption_hold_max: float
    post_caption_play: float
    final_payoff_hold: float
    playback_speed: float


@dataclass(frozen=True)
class PlayerIdentityHook:
    player_name: str
    shirt_number: str | None
    team_context: str | None
    hook_text: str
    duration: float
    transition: str = "crossfade"
    portrait_path: str | None = None


@dataclass(frozen=True)
class SocialTacticalBeat:
    beat_id: str
    action_id: str
    start_boundary: str
    end_boundary: str
    focal_players: list[str]
    caption: str
    emphasis: str = "standard"
    overlays: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SocialVideoPlan:
    featured_player_id: str | None
    identity_hook: PlayerIdentityHook
    pacing_profile: SocialPacingProfile
    beats: list[SocialTacticalBeat]
    payoff_text: str | None = None
