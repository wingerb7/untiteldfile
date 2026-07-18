from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from math import dist, isfinite
from typing import Any

from scipy.optimize import linear_sum_assignment

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
    unmatched_cost: float = 1_000_000.0
    identity_max_gap_seconds: float = 12.0
    identity_reacquisition_tolerance_m: float = 5.0


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
    TEMPORARILY_MISSING = "temporarily_missing"
    TERMINATED = "terminated"


class ObservationStatus(str, Enum):
    OBSERVED = "OBSERVED"
    INTERPOLATED = "INTERPOLATED"
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
    source_event_id: str | None = None
    observation_id: str | None = None
    source_index: int | None = None
    actor: bool = False
    player_id: Any = None
    player_name: str | None = None
    alpha: float = 1.0


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
        "source_event_id": player.source_event_id,
        "observation_id": player.observation_id,
        "source_index": player.source_index,
        "actor": player.actor,
        "player_id": player.player_id,
        "player_name": player.player_name,
        "alpha": player.alpha,
    }


def tracking_config(config: dict[str, Any]) -> TrackingConfig:
    values = config.get("tracking", {})
    return TrackingConfig(
        maximum_speed_mps=float(values.get("maximum_speed_mps", TrackingConfig.maximum_speed_mps)),
        movement_tolerance_m=float(values.get("movement_tolerance_m", TrackingConfig.movement_tolerance_m)),
        max_missing_snapshots=int(values.get("max_missing_snapshots", TrackingConfig.max_missing_snapshots)),
        unmatched_cost=float(values.get("unmatched_cost", TrackingConfig.unmatched_cost)),
        identity_max_gap_seconds=float(values.get("identity_max_gap_seconds", TrackingConfig.identity_max_gap_seconds)),
        identity_reacquisition_tolerance_m=float(
            values.get("identity_reacquisition_tolerance_m", TrackingConfig.identity_reacquisition_tolerance_m)
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


def observations_from_frame(frame: dict[str, Any], timeline_time: float) -> list[PlayerObservation]:
    observations = []
    event_id = str(frame["event_id"])
    for idx, player in enumerate(frame.get("players", [])):
        location = player["location"]
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
    return config.maximum_speed_mps * delta_time + config.movement_tolerance_m


def identity_maximum_distance_m(track: PlayerTrack, observation: PlayerObservation, config: TrackingConfig) -> float:
    return maximum_distance_m(track, observation, config) + config.identity_reacquisition_tolerance_m


def eligible_tracks(tracks: dict[str, PlayerTrack], team_id: str, is_goalkeeper: bool) -> list[PlayerTrack]:
    return [
        track
        for track in tracks.values()
        if track.status != TrackStatus.TERMINATED and track.team_id == team_id and track.is_goalkeeper == is_goalkeeper
    ]


def player_identity(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


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
        identity = player_identity(observation.player_id)
        if identity is None:
            continue
        preferred = tracks.get(preferred_track_ids.get(identity, ""))
        if (
            preferred is not None
            and preferred.tracking_id not in used_tracks
            and preferred.team_id == observation.team_id
            and preferred.is_goalkeeper == observation.is_goalkeeper
            and 0.0 <= observation.timestamp - preferred.last_timestamp <= config.identity_max_gap_seconds
            and metric_distance(preferred.last_position, observation.position) <= identity_maximum_distance_m(preferred, observation, config)
        ):
            matches.append((preferred, observation))
            used_tracks.add(preferred.tracking_id)
            used_observations.add(observation.observation_id)
            continue
        candidates = [
            track
            for track in tracks.values()
            if track.tracking_id not in used_tracks
            and player_identity(track.player_id) == identity
            and track.team_id == observation.team_id
            and track.is_goalkeeper == observation.is_goalkeeper
            and 0.0 <= observation.timestamp - track.last_timestamp <= config.identity_max_gap_seconds
            and metric_distance(track.last_position, observation.position) <= identity_maximum_distance_m(track, observation, config)
        ]
        if not candidates:
            continue
        track = min(candidates, key=lambda candidate: metric_distance(candidate.last_position, observation.position))
        matches.append((track, observation))
        used_tracks.add(track.tracking_id)
        used_observations.add(observation.observation_id)
    unmatched = [observation for observation in observations if observation.observation_id not in used_observations]
    return matches, unmatched, used_tracks


def assign_group(
    tracks: list[PlayerTrack],
    observations: list[PlayerObservation],
    config: TrackingConfig,
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
            row.append(distance_m if distance_m <= maximum_distance_m(track, observation, config) else config.unmatched_cost)
        matrix.append(row)

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
    return PlayerTrack(
        tracking_id=f"track_{sequence}",
        team_id=observation.team_id,
        is_teammate=observation.is_teammate,
        is_goalkeeper=observation.is_goalkeeper,
        last_position=observation.position,
        last_timestamp=observation.timestamp,
        status=TrackStatus.ACTIVE,
        last_observation_id=observation.observation_id,
        source_event_id=observation.source_event_id,
        source_index=observation.source_index,
        actor=observation.actor,
        player_id=observation.player_id,
        player_name=observation.player_name,
        identity_observed=observation.player_id is not None,
    )


def update_track(track: PlayerTrack, observation: PlayerObservation) -> None:
    track.last_position = observation.position
    track.last_timestamp = observation.timestamp
    track.status = TrackStatus.ACTIVE
    track.missing_snapshots = 0
    track.last_observation_id = observation.observation_id
    track.source_event_id = observation.source_event_id
    track.source_index = observation.source_index
    track.actor = observation.actor
    track.identity_observed = observation.player_id is not None
    if observation.player_id is not None:
        track.player_id = observation.player_id
    if observation.player_name is not None:
        track.player_name = observation.player_name


def missing_track_state(track: PlayerTrack, config: TrackingConfig) -> None:
    track.missing_snapshots += 1
    if track.missing_snapshots > config.max_missing_snapshots:
        track.status = TrackStatus.TERMINATED
    else:
        track.status = TrackStatus.TEMPORARILY_MISSING


def frame_player_from_track(track: PlayerTrack) -> FramePlayerState:
    observed = track.status == TrackStatus.ACTIVE
    visible = observed
    status = ObservationStatus.OBSERVED if observed else ObservationStatus.UNKNOWN
    return FramePlayerState(
        tracking_id=track.tracking_id,
        team_id=track.team_id,
        position=track.last_position,
        is_teammate=track.is_teammate,
        is_goalkeeper=track.is_goalkeeper,
        observed=observed,
        visible=visible,
        status=status,
        confidence=1.0 if observed else 0.0,
        source_event_id=track.source_event_id,
        observation_id=track.last_observation_id,
        source_index=track.source_index,
        actor=track.actor,
        player_id=track.player_id if track.identity_observed else None,
        player_name=track.player_name if track.identity_observed else None,
        alpha=1.0 if visible else 0.0,
    )


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

    for frame in possession["frames"]:
        timestamp = event_times.get(frame["event_id"], 0.0)
        observations = observations_from_frame(frame, timestamp)
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
            group_matches, group_unmatched = assign_group(group_tracks, group_observations, config)
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
            identity = player_identity(observation.player_id)
            if identity is not None:
                identity_track_ids[identity] = track.tracking_id

        for track in tracks.values():
            if track.status != TrackStatus.TERMINATED and track.tracking_id not in matched_track_ids:
                missing_track_state(track, config)

        new_tracks = []
        for observation in unmatched_observations:
            track = create_track(observation, next_track_id)
            next_track_id += 1
            tracks[track.tracking_id] = track
            identity = player_identity(observation.player_id)
            if identity is not None:
                identity_track_ids[identity] = track.tracking_id
            new_tracks.append(track)
            created_by_team[track.team_id] = created_by_team.get(track.team_id, 0) + 1

        frame_state = FrameState(
            timestamp=timestamp,
            event_id=str(frame["event_id"]),
            players=[frame_player_from_track(track) for track in tracks.values() if track.status != TrackStatus.TERMINATED],
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
                "temporarily_missing_tracks": len([track for track in tracks.values() if track.status == TrackStatus.TEMPORARILY_MISSING]),
                "terminated_tracks": len([track for track in tracks.values() if track.status == TrackStatus.TERMINATED]),
                "validation_errors": validation_errors,
            }
        )

    states, bridge_diagnostics = bridge_known_player_gaps(states, config)

    summary = {
        "maximum_visible_players_per_team": max_visible,
        "total_tracks_created": created_by_team,
        "frames_over_11_players": frames_over_11,
        "duplicate_tracking_ids": duplicate_tracking_ids,
        "identity_bridges": bridge_diagnostics,
    }
    return states, {"frames": diagnostics, "summary": summary}


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
                if any(player.visible and player.player_id == left.player_id and player.team_id == left.team_id for player in mutable_frames[idx]):
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
    players = []
    minimum_confidence = 0.35
    for player in right.players:
        if not player.visible:
            continue
        previous = left_by_id.get(player.tracking_id)
        if previous is None:
            continue
        confidence = interpolation_confidence(previous, player, span, event)
        if confidence < minimum_confidence:
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
                source_event_id=player.source_event_id,
                observation_id=player.observation_id,
                source_index=player.source_index,
                actor=player.actor,
                player_id=player.player_id,
                player_name=player.player_name,
                alpha=1.0,
            )
        )
    frame = FrameState(timestamp=t, event_id=right.event_id, players=players)
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


def build_animation_model(possession: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    timeline = build_event_timeline(possession, config)
    frame_states, diagnostics = build_frame_states(possession, timeline, tracking_config(config))
    return {
        "possession": possession,
        "timeline": timeline,
        "frame_states": frame_states,
        "tracking_diagnostics": diagnostics,
        "duration": total_animation_seconds(timeline, config),
        "tracking_architecture": {
            "event_freeze_frame": "tactical geometry source of truth",
            "reconstructed_tracks": "animation continuity only",
        },
    }


def state_at(model: dict[str, Any], t: float) -> dict[str, Any]:
    item = active_event(model["timeline"], t)
    event = item.event if item else None
    frame_state = interpolated_frame_state(model["frame_states"], t, event)
    players = [player_state_to_dict(player) for player in (frame_state.players if frame_state else []) if player.visible]

    return {
        "time": t,
        "event": event,
        "event_progress": event_progress(item, t),
        "frame_state": None if frame_state is None else asdict(frame_state),
        "players": players,
        "ball": ball_location_for_event(item, t),
    }
