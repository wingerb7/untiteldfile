from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from math import dist, isfinite
from typing import Any

from scipy.optimize import linear_sum_assignment

from analysis.relevance import relevance_config, select_relevant_players
from src.domain.models import Position


MIN_EVENT_SECONDS = 0.22
SB_PITCH_LENGTH = 120.0
SB_PITCH_WIDTH = 80.0
METRIC_PITCH_LENGTH = 105.0
METRIC_PITCH_WIDTH = 68.0
TEAM_ATTACK = "attacking_team"
TEAM_DEFENSE = "defending_team"


@dataclass(frozen=True)
class TimelineEvent:
    event: dict[str, Any]
    source_time: float
    start: float
    end: float


@dataclass(frozen=True)
class TrackingConfig:
    maximum_speed_mps: float = 9.5
    movement_tolerance_m: float = 2.0
    max_missing_snapshots: int = 1
    continuity_horizon_seconds: float = 8.0
    max_alive_missing_snapshots: int = 8
    uncertainty_growth_per_second: float = 0.09
    missing_visibility_floor: float = 0.35
    duplicate_suppression_radius_m: float = 2.5
    event_anchor_tolerance_m: float = 4.0
    soft_event_anchor_tolerance_m: float = 6.0
    unmatched_cost: float = 1_000_000.0
    identity_max_gap_seconds: float = 12.0
    identity_reacquisition_tolerance_m: float = 5.0
    enable_team_shape_propagation: bool = False
    stale_fade_start_seconds: float = 0.75
    stale_omit_seconds: float = 2.0
    stale_visibility_hysteresis_seconds: float = 0.25


@dataclass(frozen=True)
class PlayerObservation:
    observation_id: str
    team_id: str
    position: Position
    is_teammate: bool
    is_goalkeeper: bool
    source_event_id: str
    timestamp: float
    source_index: int
    actor: bool = False
    player_id: Any = None
    player_name: str | None = None


class TrackStatus(str, Enum):
    ACTIVE = "active"
    OBSERVED = "observed"
    PREDICTED_OR_HELD = "predicted_or_held"
    MISSING_BUT_ALIVE = "missing_but_alive"
    TEMPORARILY_MISSING = "temporarily_missing"
    TERMINATED = "terminated"


class ObservationStatus(str, Enum):
    OBSERVED = "OBSERVED"
    INTERPOLATED = "INTERPOLATED"
    PREDICTED_OR_HELD = "PREDICTED_OR_HELD"
    MISSING_BUT_ALIVE = "MISSING_BUT_ALIVE"
    UNKNOWN = "UNKNOWN"


@dataclass
class PlayerTrack:
    tracking_id: str
    team_id: str
    is_teammate: bool
    is_goalkeeper: bool
    last_position: Position
    last_timestamp: float
    status: TrackStatus
    missing_snapshots: int = 0
    last_observation_id: str | None = None
    source_event_id: str | None = None
    source_index: int | None = None
    actor: bool = False
    player_id: Any = None
    player_name: str | None = None
    identity_observed: bool = False
    identity_confidence: float = 0.35
    position_confidence: float = 1.0
    last_observed_timestamp: float | None = None
    previous_position: Position | None = None
    previous_timestamp: float | None = None
    anchored_event_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EventAnchor:
    player_id: Any
    player_name: str | None
    role: str
    timestamp: float
    location: Position
    event_id: str
    event_type: str
    strength: str
    team_id: str | None = None


@dataclass(frozen=True)
class FramePlayerState:
    tracking_id: str
    team_id: str
    position: Position
    is_teammate: bool
    is_goalkeeper: bool
    observed: bool
    visible: bool
    status: ObservationStatus = ObservationStatus.OBSERVED
    confidence: float = 1.0
    identity_confidence: float = 1.0
    position_confidence: float = 1.0
    source_event_id: str | None = None
    observation_id: str | None = None
    source_index: int | None = None
    actor: bool = False
    player_id: Any = None
    player_name: str | None = None
    alpha: float = 1.0
    individual_confidence: float = 1.0
    team_confidence: float = 1.0
    motion_confidence: float = 1.0
    last_observed_timestamp: float | None = None


@dataclass(frozen=True)
class FrameState:
    timestamp: float
    event_id: str
    players: list[FramePlayerState]
    validation_errors: list[str] = field(default_factory=list)


class TrackingValidationError(ValueError):
    def __init__(self, message: str, details: dict[str, Any]):
        super().__init__(f"{message}: {details}")
        self.details = details


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smootherstep(t: float) -> float:
    t = clamp(t)
    return t * t * t * (t * (t * 6 - 15) + 10)


def lerp_position(a: Position, b: Position, t: float) -> Position:
    return Position(lerp(a.x, b.x, t), lerp(a.y, b.y, t))


def position_to_location(position: Position) -> list[float]:
    return [position.x, position.y]


def player_state_to_dict(player: FramePlayerState) -> dict[str, Any]:
    return {
        "track_id": player.tracking_id,
        "tracking_id": player.tracking_id,
        "team_id": player.team_id,
        "teammate": player.is_teammate,
        "keeper": player.is_goalkeeper,
        "location": position_to_location(player.position),
        "observed": player.observed,
        "visible": player.visible,
        "status": player.status.value,
        "confidence": clamp(float(player.confidence)),
        "identity_confidence": clamp(float(player.identity_confidence)),
        "position_confidence": clamp(float(player.position_confidence)),
        "source_event_id": player.source_event_id,
        "observation_id": player.observation_id,
        "source_index": player.source_index,
        "actor": player.actor,
        "player_id": player.player_id,
        "player_name": player.player_name,
        "alpha": player.alpha,
        "individual_confidence": clamp(float(player.individual_confidence)),
        "team_confidence": clamp(float(player.team_confidence)),
        "motion_confidence": clamp(float(player.motion_confidence)),
        "last_observed_timestamp": player.last_observed_timestamp,
    }


def tracking_config(config: dict[str, Any]) -> TrackingConfig:
    values = config.get("tracking", {})
    return TrackingConfig(
        maximum_speed_mps=float(values.get("maximum_speed_mps", TrackingConfig.maximum_speed_mps)),
        movement_tolerance_m=float(values.get("movement_tolerance_m", TrackingConfig.movement_tolerance_m)),
        max_missing_snapshots=int(values.get("max_missing_snapshots", TrackingConfig.max_missing_snapshots)),
        continuity_horizon_seconds=float(
            values.get("continuity_horizon_seconds", TrackingConfig.continuity_horizon_seconds)
        ),
        max_alive_missing_snapshots=int(
            values.get("max_alive_missing_snapshots", TrackingConfig.max_alive_missing_snapshots)
        ),
        uncertainty_growth_per_second=float(
            values.get("uncertainty_growth_per_second", TrackingConfig.uncertainty_growth_per_second)
        ),
        missing_visibility_floor=float(
            values.get("missing_visibility_floor", TrackingConfig.missing_visibility_floor)
        ),
        duplicate_suppression_radius_m=float(
            values.get("duplicate_suppression_radius_m", TrackingConfig.duplicate_suppression_radius_m)
        ),
        event_anchor_tolerance_m=float(values.get("event_anchor_tolerance_m", TrackingConfig.event_anchor_tolerance_m)),
        soft_event_anchor_tolerance_m=float(
            values.get("soft_event_anchor_tolerance_m", TrackingConfig.soft_event_anchor_tolerance_m)
        ),
        unmatched_cost=float(values.get("unmatched_cost", TrackingConfig.unmatched_cost)),
        identity_max_gap_seconds=float(values.get("identity_max_gap_seconds", TrackingConfig.identity_max_gap_seconds)),
        identity_reacquisition_tolerance_m=float(
            values.get("identity_reacquisition_tolerance_m", TrackingConfig.identity_reacquisition_tolerance_m)
        ),
        enable_team_shape_propagation=bool(
            values.get("enable_team_shape_propagation", TrackingConfig.enable_team_shape_propagation)
        ),
        stale_fade_start_seconds=float(
            values.get("stale_fade_start_seconds", TrackingConfig.stale_fade_start_seconds)
        ),
        stale_omit_seconds=float(values.get("stale_omit_seconds", TrackingConfig.stale_omit_seconds)),
        stale_visibility_hysteresis_seconds=float(
            values.get("stale_visibility_hysteresis_seconds", TrackingConfig.stale_visibility_hysteresis_seconds)
        ),
    )


def build_event_timeline(possession: dict[str, Any], config: dict[str, Any]) -> list[TimelineEvent]:
    events = possession["events"]
    if not events:
        return []

    animation_config = config.get("animation", {})
    playback_speed = max(0.1, float(animation_config.get("playback_speed", 1.0)))
    start_hold = max(0.0, float(animation_config.get("start_hold_seconds", 1.0)))
    start_time = possession["start_time"]

    timeline = []
    for idx, event in enumerate(events):
        source_time = event["timestamp"] - start_time
        start = start_hold + source_time / playback_speed
        if idx + 1 < len(events):
            next_source_time = events[idx + 1]["timestamp"] - start_time
            end = start_hold + next_source_time / playback_speed
        else:
            duration = max(float(event.get("duration") or 0.0), 0.65)
            end = start + duration / playback_speed
        if end <= start:
            end = start + MIN_EVENT_SECONDS
        timeline.append(TimelineEvent(event=event, source_time=source_time, start=start, end=end))

    for idx in range(1, len(timeline)):
        previous = timeline[idx - 1]
        current = timeline[idx]
        if current.start < previous.end:
            shifted = TimelineEvent(current.event, current.source_time, previous.end, max(previous.end + MIN_EVENT_SECONDS, current.end))
            timeline[idx] = shifted

    return timeline


def total_animation_seconds(timeline: list[TimelineEvent], config: dict[str, Any]) -> float:
    end_hold = max(0.0, float(config.get("animation", {}).get("end_hold_seconds", 1.5)))
    return (timeline[-1].end if timeline else 0.0) + end_hold


def team_id_for_player(player: dict[str, Any]) -> str:
    if player.get("team_id"):
        return str(player["team_id"])
    return TEAM_ATTACK if player.get("teammate") else TEAM_DEFENSE


def supported_pitch_position(location: list[float] | tuple[float, ...] | None) -> bool:
    return bool(location and len(location) >= 2 and isfinite(float(location[0])) and isfinite(float(location[1])) and 0.0 <= float(location[0]) <= SB_PITCH_LENGTH and 0.0 <= float(location[1]) <= SB_PITCH_WIDTH)


def observations_from_frame(frame: dict[str, Any], timeline_time: float, invalid_positions: list[dict[str, Any]] | None = None) -> list[PlayerObservation]:
    observations = []
    event_id = str(frame["event_id"])
    for idx, player in enumerate(frame.get("players", [])):
        location = player["location"]
        if not supported_pitch_position(location):
            if invalid_positions is not None:
                invalid_positions.append({"event_id": event_id, "source_index": int(player.get("source_index", idx)), "player_id": player.get("player_id"), "player_name": player.get("player_name"), "location": list(location) if isinstance(location, (list, tuple)) else location, "resolution": "EXCLUDED_INVALID_SOURCE_POSITION_LAST_VALID_TRACK_STATE_PRESERVED"})
            continue
        team_id = team_id_for_player(player)
        observations.append(
            PlayerObservation(
                observation_id=f"{event_id}:{idx}",
                team_id=team_id,
                position=Position(float(location[0]), float(location[1])),
                is_teammate=bool(player.get("teammate")),
                is_goalkeeper=bool(player.get("keeper")),
                source_event_id=event_id,
                timestamp=timeline_time,
                source_index=int(player.get("source_index", idx)),
                actor=bool(player.get("actor")),
                player_id=player.get("player_id"),
                player_name=player.get("player_name"),
            )
        )
    return observations


def metric_distance(a: Position, b: Position) -> float:
    ax = a.x / SB_PITCH_LENGTH * METRIC_PITCH_LENGTH
    ay = a.y / SB_PITCH_WIDTH * METRIC_PITCH_WIDTH
    bx = b.x / SB_PITCH_LENGTH * METRIC_PITCH_LENGTH
    by = b.y / SB_PITCH_WIDTH * METRIC_PITCH_WIDTH
    return dist((ax, ay), (bx, by))


def maximum_distance_m(track: PlayerTrack, observation: PlayerObservation, config: TrackingConfig) -> float:
    delta_time = observation.timestamp - track.last_timestamp
    if not isfinite(delta_time) or delta_time <= 0:
        return config.movement_tolerance_m
    uncertainty_allowance = (1.0 - clamp(track.position_confidence)) * config.maximum_speed_mps * min(
        delta_time, config.continuity_horizon_seconds
    )
    missed_allowance = min(track.missing_snapshots, config.max_alive_missing_snapshots) * config.movement_tolerance_m
    return config.maximum_speed_mps * delta_time + config.movement_tolerance_m + uncertainty_allowance + missed_allowance


def identity_maximum_distance_m(track: PlayerTrack, observation: PlayerObservation, config: TrackingConfig) -> float:
    return maximum_distance_m(track, observation, config) + config.identity_reacquisition_tolerance_m


def eligible_tracks(tracks: dict[str, PlayerTrack], team_id: str, is_goalkeeper: bool) -> list[PlayerTrack]:
    return [
        track
        for track in tracks.values()
        if track.status != TrackStatus.TERMINATED and track.team_id == team_id and track.is_goalkeeper == is_goalkeeper
    ]


def player_identity(value: Any, name: str | None = None) -> str | None:
    if value is None:
        text_name = str(name).strip() if name is not None else ""
        return f"name:{text_name}" if text_name else None
    text = str(value)
    return f"id:{text}" if text else None


def observation_identity(observation: PlayerObservation) -> str | None:
    return player_identity(observation.player_id, observation.player_name)


def track_identity(track: PlayerTrack) -> str | None:
    return player_identity(track.player_id, track.player_name)


def authenticated_identities_conflict(track: PlayerTrack, observation: PlayerObservation) -> bool:
    """True only when both sides carry different authenticated identities."""
    left = track_identity(track)
    right = observation_identity(observation)
    return left is not None and right is not None and left != right


def event_team_id(event: dict[str, Any]) -> str | None:
    value = event.get("team_id")
    return str(value) if value is not None else None


def position_from_location(location: list[float] | None) -> Position | None:
    if not location or len(location) < 2:
        return None
    return Position(float(location[0]), float(location[1]))


def event_anchors_for_event(event: dict[str, Any], timestamp: float) -> list[EventAnchor]:
    anchors: list[EventAnchor] = []
    start = position_from_location(event.get("start_location"))
    end = position_from_location(event.get("end_location"))
    event_id = str(event.get("id"))
    event_type = str(event.get("type") or "")
    actor_id = event.get("player_id")
    actor_name = event.get("player_name")
    team_id = event_team_id(event)
    if event_type in {"Pass", "Carry", "Shot", "Dribble", "Ball Receipt*"} and start is not None and (actor_id is not None or actor_name):
        anchors.append(
            EventAnchor(actor_id, actor_name, "actor", timestamp, start, event_id, event_type, "hard", team_id)
        )
    recipient_id = event.get("recipient_id")
    recipient_name = event.get("recipient_name")
    if event_type == "Pass" and end is not None and (recipient_id is not None or recipient_name):
        anchors.append(
            EventAnchor(recipient_id, recipient_name, "recipient", timestamp, end, event_id, event_type, "soft", team_id)
        )
    return anchors


def anchor_identity(anchor: EventAnchor) -> str | None:
    return player_identity(anchor.player_id, anchor.player_name)


def apply_event_anchors(
    observations: list[PlayerObservation],
    anchors: list[EventAnchor],
    config: TrackingConfig,
) -> list[PlayerObservation]:
    if not anchors:
        return observations
    updated = list(observations)
    used_observations: set[str] = set()
    for anchor in anchors:
        identity = anchor_identity(anchor)
        if identity is None:
            continue
        tolerance = config.event_anchor_tolerance_m if anchor.strength == "hard" else config.soft_event_anchor_tolerance_m
        candidates = []
        for observation in updated:
            if observation.observation_id in used_observations:
                continue
            if anchor.team_id is not None and observation.team_id not in {anchor.team_id, TEAM_ATTACK}:
                continue
            if anchor.team_id is None and not observation.is_teammate:
                continue
            existing_identity = observation_identity(observation)
            if existing_identity is not None and existing_identity != identity:
                continue
            distance = metric_distance(observation.position, anchor.location)
            if distance <= tolerance:
                candidates.append((distance, observation))
        if not candidates:
            continue
        _, chosen = min(candidates, key=lambda item: item[0])
        used_observations.add(chosen.observation_id)
        idx = updated.index(chosen)
        updated[idx] = replace(
            chosen,
            player_id=anchor.player_id if anchor.player_id is not None else chosen.player_id,
            player_name=anchor.player_name if anchor.player_name is not None else chosen.player_name,
            actor=chosen.actor or anchor.role == "actor",
        )
    return updated


def identity_matches(
    tracks: dict[str, PlayerTrack],
    observations: list[PlayerObservation],
    config: TrackingConfig,
    preferred_track_ids: dict[str, str] | None = None,
) -> tuple[list[tuple[PlayerTrack, PlayerObservation]], list[PlayerObservation], set[str]]:
    matches: list[tuple[PlayerTrack, PlayerObservation]] = []
    used_tracks: set[str] = set()
    used_observations: set[str] = set()
    preferred_track_ids = preferred_track_ids or {}
    for observation in observations:
        identity = observation_identity(observation)
        if identity is None:
            continue
        candidates = [
            track
            for track in tracks.values()
            if track.tracking_id not in used_tracks
            and track_identity(track) == identity
            and track.team_id == observation.team_id
            and track.is_goalkeeper == observation.is_goalkeeper
            and 0.0 <= observation.timestamp - track.last_timestamp <= config.identity_max_gap_seconds
            and metric_distance(track.last_position, observation.position) <= identity_maximum_distance_m(track, observation, config)
        ]
        if not candidates:
            continue
        track = min(
            candidates,
            key=lambda candidate: (
                int(candidate.tracking_id.split("_")[-1]),
                metric_distance(candidate.last_position, observation.position),
            ),
        )
        matches.append((track, observation))
        used_tracks.add(track.tracking_id)
        used_observations.add(observation.observation_id)
    unmatched = [observation for observation in observations if observation.observation_id not in used_observations]
    return matches, unmatched, used_tracks


def retire_duplicate_identity_tracks(tracks: dict[str, PlayerTrack], matched_track: PlayerTrack) -> None:
    identity = track_identity(matched_track)
    if identity is None:
        return
    for track in tracks.values():
        if track.tracking_id == matched_track.tracking_id or track.status == TrackStatus.TERMINATED:
            continue
        if track.team_id == matched_track.team_id and track.is_goalkeeper == matched_track.is_goalkeeper and track_identity(track) == identity:
            track.status = TrackStatus.TERMINATED
            track.position_confidence = 0.0
            track.identity_confidence = 0.0


def assign_group(
    tracks: list[PlayerTrack],
    observations: list[PlayerObservation],
    config: TrackingConfig,
    association_diagnostics: list[dict[str, Any]] | None = None,
) -> tuple[list[tuple[PlayerTrack, PlayerObservation]], list[PlayerObservation]]:
    if not tracks or not observations:
        return [], observations

    matrix = []
    for track in tracks:
        row = []
        for observation in observations:
            if track.team_id != observation.team_id or track.is_goalkeeper != observation.is_goalkeeper:
                row.append(config.unmatched_cost)
                continue
            distance_m = metric_distance(track.last_position, observation.position)
            reachable = distance_m <= maximum_distance_m(track, observation, config)
            if authenticated_identities_conflict(track, observation) and reachable:
                row.append(config.unmatched_cost)
                if association_diagnostics is not None:
                    association_diagnostics.append(
                        {
                            "reason_code": "IDENTITY_CONFLICT",
                            "track_id": track.tracking_id,
                            "track_identity": track_identity(track),
                            "observation_id": observation.observation_id,
                            "observation_identity": observation_identity(observation),
                            "source_event_id": observation.source_event_id,
                            "source_index": observation.source_index,
                            "model_time": observation.timestamp,
                        }
                    )
                continue
            row.append(distance_m if reachable else config.unmatched_cost)
        matrix.append(row)

    # An exactly tied spatial fallback has no evidence-based winner. Leave the
    # observation unmatched so a deterministic new track is created instead of
    # silently choosing an identity/history.
    for col, observation in enumerate(observations):
        viable = [(matrix[row][col], tracks[row]) for row in range(len(tracks)) if matrix[row][col] < config.unmatched_cost]
        if len(viable) < 2:
            continue
        minimum = min(cost for cost, _ in viable)
        tied = sorted(track.tracking_id for cost, track in viable if abs(cost - minimum) <= 1e-9)
        if len(tied) < 2:
            continue
        for row in range(len(tracks)):
            matrix[row][col] = config.unmatched_cost
        if association_diagnostics is not None:
            association_diagnostics.append(
                {
                    "reason_code": "ASSOCIATION_AMBIGUITY",
                    "track_ids": tied,
                    "observation_id": observation.observation_id,
                    "observation_identity": observation_identity(observation),
                    "source_event_id": observation.source_event_id,
                    "source_index": observation.source_index,
                    "model_time": observation.timestamp,
                }
            )

    rows, cols = linear_sum_assignment(matrix)
    matches: list[tuple[PlayerTrack, PlayerObservation]] = []
    matched_observation_ids: set[str] = set()
    matched_track_ids: set[str] = set()
    for row, col in zip(rows, cols, strict=False):
        if matrix[row][col] >= config.unmatched_cost:
            continue
        track = tracks[row]
        observation = observations[col]
        if track.tracking_id in matched_track_ids or observation.observation_id in matched_observation_ids:
            continue
        matches.append((track, observation))
        matched_track_ids.add(track.tracking_id)
        matched_observation_ids.add(observation.observation_id)

    unmatched = [observation for observation in observations if observation.observation_id not in matched_observation_ids]
    return matches, unmatched


def group_key(observation: PlayerObservation | PlayerTrack) -> tuple[str, bool]:
    return observation.team_id, observation.is_goalkeeper


def create_track(observation: PlayerObservation, sequence: int) -> PlayerTrack:
    has_identity = observation.player_id is not None or observation.player_name is not None
    return PlayerTrack(
        tracking_id=f"track_{sequence}",
        team_id=observation.team_id,
        is_teammate=observation.is_teammate,
        is_goalkeeper=observation.is_goalkeeper,
        last_position=observation.position,
        last_timestamp=observation.timestamp,
        status=TrackStatus.OBSERVED,
        last_observation_id=observation.observation_id,
        source_event_id=observation.source_event_id,
        source_index=observation.source_index,
        actor=observation.actor,
        player_id=observation.player_id,
        player_name=observation.player_name,
        identity_observed=has_identity,
        identity_confidence=1.0 if has_identity else 0.35,
        position_confidence=1.0,
        last_observed_timestamp=observation.timestamp,
    )


def update_track(track: PlayerTrack, observation: PlayerObservation) -> None:
    if authenticated_identities_conflict(track, observation):
        raise TrackingValidationError(
            "authenticated player identity conflict",
            {
                "code": "IDENTITY_CONFLICT",
                "track_id": track.tracking_id,
                "track_identity": track_identity(track),
                "observation_id": observation.observation_id,
                "observation_identity": observation_identity(observation),
            },
        )
    track.previous_position = track.last_position
    track.previous_timestamp = track.last_timestamp
    track.last_position = observation.position
    track.last_timestamp = observation.timestamp
    track.status = TrackStatus.OBSERVED
    track.missing_snapshots = 0
    track.last_observation_id = observation.observation_id
    track.source_event_id = observation.source_event_id
    track.source_index = observation.source_index
    track.actor = observation.actor
    has_identity = observation.player_id is not None or observation.player_name is not None
    track.identity_observed = track.identity_observed or has_identity
    if observation.player_id is not None:
        track.player_id = observation.player_id
    if observation.player_name is not None:
        track.player_name = observation.player_name
    track.identity_confidence = 1.0 if has_identity else max(track.identity_confidence, 0.45)
    track.position_confidence = 1.0
    track.last_observed_timestamp = observation.timestamp


def missing_track_state(track: PlayerTrack, timestamp: float, config: TrackingConfig) -> None:
    track.missing_snapshots += 1
    last_observed = track.last_observed_timestamp if track.last_observed_timestamp is not None else track.last_timestamp
    elapsed = max(0.0, timestamp - last_observed)
    identity_bonus = 1.5 if track_identity(track) is not None and track.identity_confidence >= 0.75 else 0.0
    if track.missing_snapshots > config.max_alive_missing_snapshots or elapsed > config.continuity_horizon_seconds + identity_bonus:
        track.status = TrackStatus.TERMINATED
        track.position_confidence = 0.0
        track.identity_confidence = clamp(track.identity_confidence * 0.85)
    elif track.missing_snapshots > config.max_missing_snapshots:
        track.status = TrackStatus.MISSING_BUT_ALIVE
        track.position_confidence = clamp(1.0 - elapsed * config.uncertainty_growth_per_second)
        track.identity_confidence = clamp(track.identity_confidence * 0.96)
    else:
        track.status = TrackStatus.PREDICTED_OR_HELD
        track.position_confidence = clamp(1.0 - elapsed * config.uncertainty_growth_per_second * 0.75)
        track.identity_confidence = clamp(track.identity_confidence * 0.98)


def frame_player_from_track(track: PlayerTrack) -> FramePlayerState:
    observed = track.status in {TrackStatus.ACTIVE, TrackStatus.OBSERVED}
    confidence = clamp(track.identity_confidence * 0.55 + track.position_confidence * 0.45)
    visible = track.status != TrackStatus.TERMINATED
    if observed:
        status = ObservationStatus.OBSERVED
    elif track.status == TrackStatus.PREDICTED_OR_HELD:
        status = ObservationStatus.PREDICTED_OR_HELD
    elif track.status == TrackStatus.MISSING_BUT_ALIVE:
        status = ObservationStatus.MISSING_BUT_ALIVE
    else:
        status = ObservationStatus.UNKNOWN
    return FramePlayerState(
        tracking_id=track.tracking_id,
        team_id=track.team_id,
        position=track.last_position,
        is_teammate=track.is_teammate,
        is_goalkeeper=track.is_goalkeeper,
        observed=observed,
        visible=visible,
        status=status,
        confidence=1.0 if observed else confidence,
        identity_confidence=1.0 if observed and track_identity(track) is not None else track.identity_confidence,
        position_confidence=1.0 if observed else track.position_confidence,
        source_event_id=track.source_event_id,
        observation_id=track.last_observation_id,
        source_index=track.source_index,
        actor=track.actor,
        player_id=track.player_id if track.identity_observed else None,
        player_name=track.player_name if track.identity_observed else None,
        alpha=1.0 if observed else max(0.28, min(0.72, confidence)),
        last_observed_timestamp=track.last_observed_timestamp,
    )


def suppress_duplicate_or_excess_players(players: list[FramePlayerState], config: TrackingConfig) -> list[FramePlayerState]:
    observed = [player for player in players if player.observed and player.visible]
    kept: list[FramePlayerState] = list(observed)
    visible_by_team: dict[str, int] = {}
    for player in observed:
        visible_by_team[player.team_id] = visible_by_team.get(player.team_id, 0) + 1

    for player in sorted(
        (item for item in players if not item.observed),
        key=lambda item: (item.identity_confidence, item.position_confidence, item.confidence),
        reverse=True,
    ):
        if not player.visible:
            kept.append(player)
            continue
        if visible_by_team.get(player.team_id, 0) >= 11:
            kept.append(replace(player, visible=False, alpha=0.0))
            continue
        duplicate = any(
            existing.visible
            and existing.team_id == player.team_id
            and existing.is_goalkeeper == player.is_goalkeeper
            and metric_distance(existing.position, player.position) <= config.duplicate_suppression_radius_m
            for existing in kept
        )
        if duplicate:
            kept.append(replace(player, visible=False, alpha=0.0))
            continue
        kept.append(player)
        visible_by_team[player.team_id] = visible_by_team.get(player.team_id, 0) + 1
    return kept


def validate_frame_state(frame: FrameState) -> list[str]:
    errors = []
    visible_players = [player for player in frame.players if player.visible]
    seen_ids: set[str] = set()
    duplicates: list[str] = []
    for player in visible_players:
        if player.tracking_id in seen_ids:
            duplicates.append(player.tracking_id)
        seen_ids.add(player.tracking_id)
    if duplicates:
        errors.append(f"duplicate tracking IDs at {frame.timestamp:.3f}: {sorted(set(duplicates))}")

    for team_id in {TEAM_ATTACK, TEAM_DEFENSE} | {player.team_id for player in visible_players}:
        team_players = [player for player in visible_players if player.team_id == team_id]
        if len(team_players) > 11:
            errors.append(
                f"team {team_id} has {len(team_players)} visible players at {frame.timestamp:.3f}: "
                f"{[player.tracking_id for player in team_players]}"
            )
        keepers = [player for player in team_players if player.is_goalkeeper]
        if len(keepers) > 1:
            errors.append(
                f"team {team_id} has {len(keepers)} visible goalkeepers at {frame.timestamp:.3f}: "
                f"{[player.tracking_id for player in keepers]}"
            )

    for player in visible_players:
        if player.team_id not in {TEAM_ATTACK, TEAM_DEFENSE} and not player.team_id:
            errors.append(f"player {player.tracking_id} has invalid team id {player.team_id!r}")
    return errors


def raise_if_invalid_frame(frame: FrameState) -> None:
    errors = validate_frame_state(frame)
    if errors:
        details = {
            "timestamp": frame.timestamp,
            "event_id": frame.event_id,
            "errors": errors,
            "players": [
                {
                    "tracking_id": player.tracking_id,
                    "team_id": player.team_id,
                    "visible": player.visible,
                    "observed": player.observed,
                    "source_event_id": player.source_event_id,
                    "observation_id": player.observation_id,
                }
                for player in frame.players
            ],
        }
        raise TrackingValidationError("invalid frame state", details)


def build_frame_states(
    possession: dict[str, Any],
    timeline: list[TimelineEvent],
    config: TrackingConfig,
) -> tuple[list[FrameState], dict[str, Any]]:
    event_times = {item.event["id"]: item.start for item in timeline}
    tracks: dict[str, PlayerTrack] = {}
    identity_track_ids: dict[str, str] = {}
    next_track_id = 1
    states: list[FrameState] = []
    diagnostics: list[dict[str, Any]] = []
    duplicate_tracking_ids = 0
    frames_over_11 = 0
    max_visible = {TEAM_ATTACK: 0, TEAM_DEFENSE: 0}
    created_by_team = {TEAM_ATTACK: 0, TEAM_DEFENSE: 0}
    invalid_source_positions: list[dict[str, Any]] = []
    association_diagnostics: list[dict[str, Any]] = []

    for frame in possession["frames"]:
        timestamp = event_times.get(frame["event_id"], 0.0)
        event = next((item.event for item in timeline if item.event["id"] == frame["event_id"]), {})
        anchors = event_anchors_for_event(event, timestamp)
        observations = apply_event_anchors(observations_from_frame(frame, timestamp, invalid_source_positions), anchors, config)
        observation_groups: dict[tuple[str, bool], list[PlayerObservation]] = {}
        for observation in observations:
            observation_groups.setdefault(group_key(observation), []).append(observation)

        matches: list[tuple[PlayerTrack, PlayerObservation]] = []
        identity_group_matches, unmatched_observations, identity_matched_track_ids = identity_matches(
            tracks,
            observations,
            config,
            identity_track_ids,
        )
        matches.extend(identity_group_matches)
        unmatched_observation_ids = {observation.observation_id for observation in unmatched_observations}
        for key, group_observations in observation_groups.items():
            team_id, is_goalkeeper = key
            group_tracks = [
                track
                for track in eligible_tracks(tracks, team_id, is_goalkeeper)
                if track.tracking_id not in identity_matched_track_ids
            ]
            group_observations = [
                observation
                for observation in group_observations
                if observation.observation_id in unmatched_observation_ids
            ]
            group_matches, group_unmatched = assign_group(
                group_tracks, group_observations, config, association_diagnostics
            )
            matches.extend(group_matches)
            matched_ids = {observation.observation_id for _, observation in group_matches}
            unmatched_observations = [
                observation
                for observation in unmatched_observations
                if observation.observation_id not in matched_ids
            ]

        matched_track_ids = {track.tracking_id for track, _ in matches}
        matched_observation_ids = [observation.observation_id for _, observation in matches]
        if len(matched_track_ids) != len(matches):
            duplicate_tracking_ids += 1
        if len(set(matched_observation_ids)) != len(matched_observation_ids):
            duplicate_tracking_ids += 1

        for track, observation in matches:
            update_track(track, observation)
            identity = observation_identity(observation)
            if identity is not None:
                retire_duplicate_identity_tracks(tracks, track)
                identity_track_ids[identity] = track.tracking_id

        for track in tracks.values():
            if track.status != TrackStatus.TERMINATED and track.tracking_id not in matched_track_ids:
                missing_track_state(track, timestamp, config)

        new_tracks = []
        for observation in unmatched_observations:
            track = create_track(observation, next_track_id)
            next_track_id += 1
            tracks[track.tracking_id] = track
            identity = observation_identity(observation)
            if identity is not None:
                identity_track_ids[identity] = track.tracking_id
            new_tracks.append(track)
            created_by_team[track.team_id] = created_by_team.get(track.team_id, 0) + 1

        frame_state = FrameState(
            timestamp=timestamp,
            event_id=str(frame["event_id"]),
            players=suppress_duplicate_or_excess_players(
                [frame_player_from_track(track) for track in tracks.values() if track.status != TrackStatus.TERMINATED],
                config,
            ),
        )
        validation_errors = validate_frame_state(frame_state)
        if validation_errors:
            frames_over_11 += int(any("visible players" in error for error in validation_errors))
        frame_state = FrameState(frame_state.timestamp, frame_state.event_id, frame_state.players, validation_errors)
        raise_if_invalid_frame(frame_state)
        states.append(frame_state)

        visible_tracks = {
            TEAM_ATTACK: len([player for player in frame_state.players if player.visible and player.team_id == TEAM_ATTACK]),
            TEAM_DEFENSE: len([player for player in frame_state.players if player.visible and player.team_id == TEAM_DEFENSE]),
        }
        max_visible[TEAM_ATTACK] = max(max_visible[TEAM_ATTACK], visible_tracks[TEAM_ATTACK])
        max_visible[TEAM_DEFENSE] = max(max_visible[TEAM_DEFENSE], visible_tracks[TEAM_DEFENSE])
        observation_counts = {
            TEAM_ATTACK: len([observation for observation in observations if observation.team_id == TEAM_ATTACK]),
            TEAM_DEFENSE: len([observation for observation in observations if observation.team_id == TEAM_DEFENSE]),
        }
        diagnostics.append(
            {
                "timestamp": timestamp,
                "event_id": frame["event_id"],
                "observations": observation_counts,
                "visible_tracks": visible_tracks,
                "matched_tracks": len(matches),
                "new_tracks": len(new_tracks),
                "temporarily_missing_tracks": len(
                    [
                        track
                        for track in tracks.values()
                        if track.status in {TrackStatus.TEMPORARILY_MISSING, TrackStatus.PREDICTED_OR_HELD}
                    ]
                ),
                "missing_but_alive_tracks": len(
                    [track for track in tracks.values() if track.status == TrackStatus.MISSING_BUT_ALIVE]
                ),
                "terminated_tracks": len([track for track in tracks.values() if track.status == TrackStatus.TERMINATED]),
                "validation_errors": validation_errors,
            }
        )

    states, bridge_diagnostics = bridge_known_player_gaps(states, config)
    team_shape_summary: dict[str, Any] = {"enabled": False, "frames_changed": 0, "players_adjusted": 0}
    team_shape_frames: list[dict[str, Any]] = []
    if config.enable_team_shape_propagation:
        from analysis.team_shape import propagate_team_shape

        balls_by_event_id = {
            str(event.get("id")): event.get("start_location") or event.get("end_location")
            for event in possession.get("events", [])
        }
        states, team_shape_diagnostics = propagate_team_shape(states, balls_by_event_id=balls_by_event_id)
        team_shape_summary = {"enabled": True, **team_shape_diagnostics.summary}
        team_shape_frames = team_shape_diagnostics.frames
        for state in states:
            raise_if_invalid_frame(state)

    summary = {
        "maximum_visible_players_per_team": max_visible,
        "total_tracks_created": created_by_team,
        "frames_over_11_players": frames_over_11,
        "duplicate_tracking_ids": duplicate_tracking_ids,
        "identity_bridges": bridge_diagnostics,
        "team_shape": team_shape_summary,
        "invalid_source_position_count": len(invalid_source_positions),
        "identity_conflict_count": sum(
            row.get("reason_code") == "IDENTITY_CONFLICT" for row in association_diagnostics
        ),
        "association_ambiguity_count": sum(
            row.get("reason_code") == "ASSOCIATION_AMBIGUITY" for row in association_diagnostics
        ),
    }
    association_diagnostics.sort(
        key=lambda row: (
            float(row["model_time"]),
            str(row.get("track_id") or ",".join(row.get("track_ids", []))),
            str(row["observation_id"]),
        )
    )
    return states, {
        "frames": diagnostics,
        "summary": summary,
        "team_shape": team_shape_frames,
        "invalid_source_positions": invalid_source_positions,
        "association_conflicts": association_diagnostics,
    }


def player_key(player: FramePlayerState) -> tuple[str, str]:
    return player.team_id, str(player.player_id)


def bridge_confidence(left: FramePlayerState, right: FramePlayerState, span: float, config: TrackingConfig) -> float:
    speed = metric_distance(left.position, right.position) / max(0.001, span)
    if speed > config.maximum_speed_mps:
        return 0.0
    speed_component = 1.0 - clamp(speed / max(0.001, config.maximum_speed_mps)) * 0.60
    gap_component = 1.0 - clamp(span / max(0.001, config.identity_max_gap_seconds)) * 0.30
    return clamp(speed_component * gap_component)


def bridge_known_player_gaps(states: list[FrameState], config: TrackingConfig) -> tuple[list[FrameState], dict[str, Any]]:
    anchors: dict[tuple[str, str], list[tuple[int, FramePlayerState]]] = {}
    for idx, frame in enumerate(states):
        for player in frame.players:
            if not player.visible or not player.observed or player.player_id is None:
                continue
            anchors.setdefault(player_key(player), []).append((idx, player))

    mutable_frames = [list(frame.players) for frame in states]
    inserted_states = 0
    bridged_players: set[str] = set()
    for _, player_anchors in anchors.items():
        for (left_idx, left), (right_idx, right) in zip(player_anchors, player_anchors[1:], strict=False):
            if right_idx <= left_idx + 1:
                continue
            span = states[right_idx].timestamp - states[left_idx].timestamp
            if span <= 0.0 or span > config.identity_max_gap_seconds:
                continue
            confidence = bridge_confidence(left, right, span, config)
            if confidence <= 0.0:
                continue
            for idx in range(left_idx + 1, right_idx):
                frame = states[idx]
                if any(
                    player.visible
                    and player.player_id == left.player_id
                    and player.team_id == left.team_id
                    and player.tracking_id != left.tracking_id
                    for player in mutable_frames[idx]
                ):
                    continue
                progress = smootherstep((frame.timestamp - states[left_idx].timestamp) / span)
                bridge_player = FramePlayerState(
                    tracking_id=left.tracking_id,
                    team_id=left.team_id,
                    position=lerp_position(left.position, right.position, progress),
                    is_teammate=left.is_teammate,
                    is_goalkeeper=left.is_goalkeeper,
                    observed=False,
                    visible=True,
                    status=ObservationStatus.INTERPOLATED,
                    confidence=confidence,
                    identity_confidence=left.identity_confidence,
                    position_confidence=confidence,
                    source_event_id=left.source_event_id,
                    observation_id=left.observation_id,
                    source_index=left.source_index,
                    actor=False,
                    player_id=left.player_id,
                    player_name=left.player_name,
                    alpha=1.0,
                )
                same_track_idx = next(
                    (
                        player_idx
                        for player_idx, player in enumerate(mutable_frames[idx])
                        if player.visible and player.tracking_id == left.tracking_id
                    ),
                    None,
                )
                if same_track_idx is None:
                    if sum(1 for player in mutable_frames[idx] if player.visible and player.team_id == left.team_id) >= 11:
                        continue
                    mutable_frames[idx].append(bridge_player)
                else:
                    existing = mutable_frames[idx][same_track_idx]
                    if existing.observed and existing.source_event_id == frame.event_id:
                        mutable_frames[idx][same_track_idx] = replace(
                            existing,
                            player_id=left.player_id,
                            player_name=left.player_name,
                        )
                    else:
                        mutable_frames[idx][same_track_idx] = bridge_player
                inserted_states += 1
                bridged_players.add(str(left.player_id))

    bridged_states = []
    frames_with_bridge = 0
    for original, players in zip(states, mutable_frames, strict=True):
        validation_errors = validate_frame_state(FrameState(original.timestamp, original.event_id, players))
        frame = FrameState(original.timestamp, original.event_id, players, validation_errors)
        raise_if_invalid_frame(frame)
        frames_with_bridge += int(len(players) != len(original.players))
        bridged_states.append(frame)
    return bridged_states, {"players": sorted(bridged_players), "inserted_states": inserted_states, "frames": frames_with_bridge}


def exact_frame_state_at(states: list[FrameState], t: float, tolerance: float = 1e-9) -> FrameState | None:
    return next((state for state in states if abs(state.timestamp - t) <= tolerance), None)


def receiver_like(player: FramePlayerState, event: dict[str, Any] | None) -> bool:
    end = (event or {}).get("end_location")
    if not end:
        return False
    return dist((player.position.x, player.position.y), (float(end[0]), float(end[1]))) <= 3.0


def interpolation_role(player: FramePlayerState, event: dict[str, Any] | None) -> str:
    event_player_id = player_identity((event or {}).get("player_id"))
    if player.actor and (player.player_id is None or player_identity(player.player_id) == event_player_id):
        return "ball_carrier"
    if player.player_id is not None:
        return "off_ball_run"
    if receiver_like(player, event):
        return "receiver"
    if player.is_goalkeeper:
        return "goalkeeper"
    if not player.is_teammate:
        return "defender"
    return "support"


def interpolation_confidence(previous: FramePlayerState, current: FramePlayerState, span: float, event: dict[str, Any] | None) -> float:
    distance_m = metric_distance(previous.position, current.position)
    speed_mps = distance_m / max(0.001, span)
    role = interpolation_role(current, event)
    caps = {
        "ball_carrier": 9.5,
        "off_ball_run": 13.75,
        "receiver": 9.5,
        "goalkeeper": 2.5,
        "defender": 6.0,
        "support": 5.0,
    }
    cap = caps[role]
    if speed_mps > cap:
        return 0.0
    speed_component = 1.0 - clamp(speed_mps / max(0.001, cap)) * 0.55
    time_component = 1.0 - clamp(span / 4.0) * 0.25
    return clamp(speed_component * time_component)


def held_interpolation_confidence(player: FramePlayerState, elapsed: float) -> float:
    return clamp(player.identity_confidence * 0.55 + max(0.0, player.position_confidence - elapsed * 0.10) * 0.45)


def interpolated_frame_state(states: list[FrameState], t: float, event: dict[str, Any] | None = None) -> FrameState | None:
    if not states:
        return None
    exact = exact_frame_state_at(states, t)
    if exact is not None:
        return exact
    if t <= states[0].timestamp:
        return states[0]
    if t >= states[-1].timestamp:
        return states[-1]

    left = states[0]
    right = states[-1]
    for idx in range(len(states) - 1):
        if states[idx].timestamp <= t <= states[idx + 1].timestamp:
            left = states[idx]
            right = states[idx + 1]
            break

    span = max(0.001, right.timestamp - left.timestamp)
    progress = smootherstep((t - left.timestamp) / span)
    left_by_id = {player.tracking_id: player for player in left.players if player.visible}
    right_by_id = {player.tracking_id: player for player in right.players if player.visible}
    players = []
    for player in right.players:
        if not player.visible:
            continue
        previous = left_by_id.get(player.tracking_id)
        if previous is None:
            continue
        confidence = interpolation_confidence(previous, player, span, event)
        if confidence <= 0.0:
            confidence = held_interpolation_confidence(previous, max(0.0, t - left.timestamp))
            players.append(
                FramePlayerState(
                    tracking_id=player.tracking_id,
                    team_id=player.team_id,
                    position=previous.position,
                    is_teammate=player.is_teammate,
                    is_goalkeeper=player.is_goalkeeper,
                    observed=False,
                    visible=True,
                    status=ObservationStatus.PREDICTED_OR_HELD,
                    confidence=confidence,
                    identity_confidence=min(previous.identity_confidence, player.identity_confidence),
                    position_confidence=confidence,
                    source_event_id=previous.source_event_id,
                    observation_id=previous.observation_id,
                    source_index=previous.source_index,
                    actor=previous.actor,
                    player_id=previous.player_id,
                    player_name=previous.player_name,
                    alpha=max(0.28, min(0.72, confidence)),
                    last_observed_timestamp=previous.last_observed_timestamp,
                )
            )
            continue
        confidence = clamp(confidence * (1.0 - abs(progress - 0.5) * 0.18))
        position = lerp_position(previous.position, player.position, progress)
        players.append(
            FramePlayerState(
                tracking_id=player.tracking_id,
                team_id=player.team_id,
                position=position,
                is_teammate=player.is_teammate,
                is_goalkeeper=player.is_goalkeeper,
                observed=False,
                visible=True,
                status=ObservationStatus.INTERPOLATED,
                confidence=confidence,
                identity_confidence=min(previous.identity_confidence, player.identity_confidence),
                position_confidence=confidence,
                source_event_id=player.source_event_id,
                observation_id=player.observation_id,
                source_index=player.source_index,
                actor=player.actor,
                player_id=player.player_id,
                player_name=player.player_name,
                alpha=1.0,
                last_observed_timestamp=previous.last_observed_timestamp,
            )
        )
    represented = {player.tracking_id for player in players}
    for player in left.players:
        if not player.visible or player.tracking_id in represented or player.tracking_id in right_by_id:
            continue
        elapsed = max(0.0, t - left.timestamp)
        confidence = held_interpolation_confidence(player, elapsed)
        players.append(
            replace(
                player,
                observed=False,
                visible=True,
                status=ObservationStatus.PREDICTED_OR_HELD,
                confidence=confidence,
                position_confidence=clamp(player.position_confidence - elapsed * 0.10),
                alpha=max(0.28, min(0.72, confidence)),
            )
        )
    for player in right.players:
        if not player.visible or player.tracking_id in represented or player.tracking_id in left_by_id:
            continue
        if player.player_id is not None and any(
            left_player.player_id == player.player_id and left_player.team_id == player.team_id
            for left_player in left_by_id.values()
        ):
            continue
        # A future-only endpoint is not evidence for showing the player early.
        # Keep it absent until its first supported observation.
    frame = FrameState(timestamp=t, event_id=right.event_id, players=suppress_duplicate_or_excess_players(players, TrackingConfig()))
    raise_if_invalid_frame(frame)
    return frame


def active_event(timeline: list[TimelineEvent], t: float) -> TimelineEvent | None:
    if not timeline:
        return None
    if t < timeline[0].start:
        return timeline[0]
    for item in timeline:
        if item.start <= t <= item.end:
            return item
    return timeline[-1]


def event_progress(item: TimelineEvent | None, t: float) -> float:
    if item is None:
        return 0.0
    return clamp((t - item.start) / max(0.001, item.end - item.start))


def ball_location_for_event(item: TimelineEvent | None, t: float) -> list[float] | None:
    if item is None:
        return None
    event = item.event
    progress = smootherstep(event_progress(item, t))
    start = event.get("start_location")
    end = event.get("end_location") or start

    if event["type"] in {"Pass", "Carry", "Shot"} and start and end:
        return [lerp(start[0], end[0], progress), lerp(start[1], end[1], progress)]
    if event["type"] == "Ball Receipt*" and start:
        return start
    return start or end


HOLD_REASON_CODES = (
    "HOLD_MISSING_PREVIOUS_ENDPOINT",
    "HOLD_MISSING_NEXT_ENDPOINT",
    "HOLD_ASSOCIATION_AMBIGUITY",
    "HOLD_IDENTITY_CONFLICT",
    "HOLD_SPEED_CAP_REJECTION",
    "HOLD_LIFECYCLE_STATE",
    "HOLD_NO_FUTURE_SUPPORTED_OBSERVATION",
)


def interpolation_hold_diagnostics(
    states: list[FrameState],
    events_by_id: dict[str, dict[str, Any]],
    association_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Describe every unsupported static interpolation choice without inventing motion."""
    if not states:
        return []
    rows: list[dict[str, Any]] = []
    future_observed: dict[tuple[int, str], bool] = {}
    for idx, state in enumerate(states):
        later = states[idx + 1 :]
        for player in state.players:
            future_observed[(idx, player.tracking_id)] = any(
                candidate.tracking_id == player.tracking_id and candidate.status == ObservationStatus.OBSERVED
                for frame in later
                for candidate in frame.players
            )

    def reference(player: FramePlayerState | None) -> dict[str, Any] | None:
        if player is None:
            return None
        return {
            "event_id": player.source_event_id,
            "observation_id": player.observation_id,
            "source_index": player.source_index,
        }

    def add(reason: str, track_id: str, left: FrameState, right: FrameState, previous: FramePlayerState | None, next_player: FramePlayerState | None) -> None:
        source = previous or next_player
        last_observed = source.last_observed_timestamp if source is not None else None
        rows.append(
            {
                "reason_code": reason,
                "track_id": track_id,
                "model_time_interval": [left.timestamp, right.timestamp],
                "evidence_age_seconds": None if last_observed is None else max(0.0, left.timestamp - last_observed),
                "previous_observation": reference(previous),
                "next_observation": reference(next_player),
                "lifecycle_state": None if source is None else source.status.value,
                "confidence": None if source is None else clamp(float(source.confidence)),
            }
        )

    for idx, (left, right) in enumerate(zip(states, states[1:], strict=False)):
        left_by_id = {player.tracking_id: player for player in left.players if player.visible}
        right_by_id = {player.tracking_id: player for player in right.players if player.visible}
        for track_id in sorted(set(left_by_id) | set(right_by_id)):
            previous = left_by_id.get(track_id)
            next_player = right_by_id.get(track_id)
            if previous is None:
                add("HOLD_MISSING_PREVIOUS_ENDPOINT", track_id, left, right, None, next_player)
                continue
            if next_player is None:
                reason = (
                    "HOLD_MISSING_NEXT_ENDPOINT"
                    if future_observed.get((idx, track_id), False)
                    else "HOLD_NO_FUTURE_SUPPORTED_OBSERVATION"
                )
                add(reason, track_id, left, right, previous, None)
                continue
            same_position = metric_distance(previous.position, next_player.position) <= 1e-9
            event = events_by_id.get(str(right.event_id))
            if interpolation_confidence(previous, next_player, max(0.001, right.timestamp - left.timestamp), event) <= 0.0:
                add("HOLD_SPEED_CAP_REJECTION", track_id, left, right, previous, next_player)
            elif same_position and (
                previous.status not in {ObservationStatus.OBSERVED, ObservationStatus.INTERPOLATED}
                or next_player.status not in {ObservationStatus.OBSERVED, ObservationStatus.INTERPOLATED}
            ):
                add("HOLD_LIFECYCLE_STATE", track_id, left, right, previous, next_player)

    for event in association_events:
        reason = event.get("reason_code")
        if reason not in {"IDENTITY_CONFLICT", "ASSOCIATION_AMBIGUITY"}:
            continue
        time = float(event["model_time"])
        right = next((state for state in states if state.timestamp >= time), states[-1])
        left = max((state for state in states if state.timestamp <= time), key=lambda state: state.timestamp, default=states[0])
        track_ids = [event["track_id"]] if event.get("track_id") else list(event.get("track_ids") or [])
        for track_id in sorted(track_ids):
            previous = next((player for player in left.players if player.tracking_id == track_id), None)
            next_player = next((player for player in right.players if player.tracking_id == track_id), None)
            add(f"HOLD_{reason}", track_id, left, right, previous, next_player)

    return sorted(
        rows,
        key=lambda row: (
            float(row["model_time_interval"][0]),
            float(row["model_time_interval"][1]),
            str(row["track_id"]),
            str(row["reason_code"]),
        ),
    )


def build_animation_model(possession: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    timeline = build_event_timeline(possession, config)
    resolved_tracking_config = tracking_config(config)
    frame_states, diagnostics = build_frame_states(possession, timeline, resolved_tracking_config)
    diagnostics["interpolation_holds"] = interpolation_hold_diagnostics(
        frame_states,
        {str(event.get("id")): event for event in possession.get("events", [])},
        diagnostics.get("association_conflicts", []),
    )
    diagnostics["hold_reason_codes"] = list(HOLD_REASON_CODES)
    model = {
        "possession": possession,
        "timeline": timeline,
        "frame_states": frame_states,
        "tracking_diagnostics": diagnostics,
        "team_shape_metrics": {"summary": {"enabled": resolved_tracking_config.enable_team_shape_propagation}, "segments": []},
        "presentation_policy": {
            "stale_fade_start_seconds": resolved_tracking_config.stale_fade_start_seconds,
            "stale_omit_seconds": resolved_tracking_config.stale_omit_seconds,
            "stale_visibility_hysteresis_seconds": resolved_tracking_config.stale_visibility_hysteresis_seconds,
        },
        "duration": total_animation_seconds(timeline, config),
        "tracking_architecture": {
            "event_freeze_frame": "tactical geometry source of truth",
            "reconstructed_tracks": "animation continuity only",
            "team_shape_propagation": "disabled by default; opt-in via tracking.enable_team_shape_propagation",
            "renderer_tracks": "filtered by deterministic relevant-player scene selection",
            "state_at": "renderer-state accessor; not authoritative semantic reconstruction state",
        },
    }
    return apply_relevant_player_selection(model, config)


def apply_relevant_player_selection(
    model: dict[str, Any],
    config: dict[str, Any],
    event_ids: set[str] | None = None,
    selected_finding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if event_ids:
        selection_possession = {
            **model["possession"],
            "events": [event for event in model["possession"].get("events", []) if str(event.get("id")) in event_ids],
        }
    else:
        selection_possession = model["possession"]
    relevant_selection = select_relevant_players(
        selection_possession,
        model["frame_states"],
        relevance_config(config),
        selected_finding=selected_finding,
    )
    model["relevant_player_selection"] = relevant_selection.to_dict()
    model["relevant_player_selection"]["event_ids"] = sorted(event_ids) if event_ids else None
    diagnostics = model.setdefault("tracking_diagnostics", {})
    diagnostics["selected_but_not_rendered"] = selected_but_not_rendered_diagnostics(model)
    return model


def selected_but_not_rendered_diagnostics(model: dict[str, Any]) -> dict[str, Any]:
    selection = model.get("relevant_player_selection") or {}
    selected_track_ids = set(selection.get("selected_track_ids") or [])
    mandatory_track_ids = set(selection.get("mandatory_track_ids") or [])
    if not selected_track_ids:
        return {"frames": [], "summary": {"total": 0, "mandatory_total": 0}}

    frames = []
    totals_by_reason: dict[str, int] = {}
    mandatory_total = 0
    frame_states = model.get("frame_states", [])
    track_frame_indices: dict[str, list[int]] = {}
    for idx, frame in enumerate(frame_states):
        for player in frame.players:
            track_frame_indices.setdefault(player.tracking_id, []).append(idx)

    for frame_idx, frame in enumerate(frame_states):
        by_track = {player.tracking_id: player for player in frame.players}
        rows = []
        for track_id in sorted(selected_track_ids):
            player = by_track.get(track_id)
            reason = None
            if player is None:
                indices = track_frame_indices.get(track_id, [])
                if not indices or frame_idx < indices[0]:
                    continue
                reason = "terminated" if frame_idx > indices[-1] else "missing from reconstructed state"
            elif player.tracking_id in mandatory_track_ids:
                reason = None
            elif player.status == ObservationStatus.UNKNOWN and not player.visible:
                reason = "terminated"
            elif not player.visible:
                if float(player.confidence) <= 0.05:
                    reason = "confidence-hidden"
                elif float(player.alpha) <= 0.0:
                    reason = "suppressed"
                else:
                    reason = "other"
            if reason is None:
                continue
            totals_by_reason[reason] = totals_by_reason.get(reason, 0) + 1
            is_mandatory = track_id in mandatory_track_ids
            mandatory_total += int(is_mandatory)
            rows.append({"track_id": track_id, "reason": reason, "mandatory": is_mandatory})
        frames.append(
            {
                "event_id": frame.event_id,
                "timestamp": frame.timestamp,
                "selected_but_not_rendered": rows,
            }
        )
    return {
        "frames": frames,
        "summary": {
            "total": sum(totals_by_reason.values()),
            "mandatory_total": mandatory_total,
            "by_reason": totals_by_reason,
        },
    }


def state_at(model: dict[str, Any], t: float) -> dict[str, Any]:
    item = active_event(model["timeline"], t)
    event = item.event if item else None
    frame_state = interpolated_frame_state(model["frame_states"], t, event)
    selection = model.get("relevant_player_selection") or {}
    selected_track_ids = set(selection.get("selected_track_ids") or [])
    mandatory_track_ids = set(selection.get("mandatory_track_ids") or [])
    context_track_ids = set(selection.get("context_track_ids") or [])
    optional_track_ids = set(selection.get("optional_track_ids") or [])
    policy = model.get("presentation_policy") or {}
    fade_start = max(0.0, float(policy.get("stale_fade_start_seconds", 0.75)))
    omit_at = max(fade_start + 0.001, float(policy.get("stale_omit_seconds", 2.0)))
    hysteresis = max(0.0, float(policy.get("stale_visibility_hysteresis_seconds", 0.25)))
    players = []
    for player in frame_state.players if frame_state else []:
        if selected_track_ids and player.tracking_id not in selected_track_ids:
            continue
        if not player.visible and player.tracking_id not in mandatory_track_ids:
            continue
        if not player.visible and player.tracking_id in mandatory_track_ids:
            player = replace(player, visible=True, alpha=max(0.28, min(0.72, float(player.confidence))))
        last_observed = player.last_observed_timestamp
        evidence_age = max(0.0, t - last_observed) if last_observed is not None else float("inf")
        mandatory = player.tracking_id in mandatory_track_ids
        role = "mandatory" if mandatory else "context" if player.tracking_id in context_track_ids else "optional"

        lifecycle_alpha = {
            ObservationStatus.OBSERVED: 1.0,
            ObservationStatus.INTERPOLATED: 0.78,
            ObservationStatus.PREDICTED_OR_HELD: 0.52,
            ObservationStatus.MISSING_BUT_ALIVE: 0.24,
            ObservationStatus.UNKNOWN: 0.16,
        }[player.status]
        lifecycle_alpha *= clamp(float(player.confidence))
        if player.status == ObservationStatus.OBSERVED:
            lifecycle_alpha = 1.0

        freshness_alpha = 1.0
        if evidence_age > fade_start:
            fade_progress = clamp((evidence_age - fade_start) / (omit_at - fade_start))
            freshness_alpha = 1.0 - 0.88 * fade_progress
        if evidence_age > omit_at:
            freshness_alpha = 0.0 if hysteresis <= 0.0 else 0.12 * clamp(
                1.0 - (evidence_age - omit_at) / hysteresis
            )
        if not mandatory and evidence_age >= omit_at + hysteresis:
            continue
        # Mandatory action participants remain locatable, but never masquerade as observed.
        minimum_uncertain_alpha = 0.20 if mandatory and player.status != ObservationStatus.OBSERVED else 0.0
        render_alpha = max(minimum_uncertain_alpha, lifecycle_alpha * freshness_alpha)
        if not mandatory and render_alpha <= 0.01:
            continue
        player = replace(player, alpha=render_alpha)
        payload = player_state_to_dict(player)
        payload.update(
            {
                "evidence_age_seconds": None if not isfinite(evidence_age) else evidence_age,
                "relevance_role": role,
                "presentation_eligible": True,
                "visibility_transition_seconds": hysteresis,
            }
        )
        players.append(payload)

    return {
        "time": t,
        "event": event,
        "event_progress": event_progress(item, t),
        "frame_state": None if frame_state is None else asdict(frame_state),
        "players": players,
        "ball": ball_location_for_event(item, t),
    }
