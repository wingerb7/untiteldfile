from __future__ import annotations

import pytest

from analysis.interpolate import (
    ObservationStatus,
    TEAM_ATTACK,
    TEAM_DEFENSE,
    FramePlayerState,
    FrameState,
    TrackingConfig,
    TrackingValidationError,
    build_frame_states,
    interpolated_frame_state,
    raise_if_invalid_frame,
)
from render.animation import split_players
from src.domain.models import Event, NormalizedPossession, PlayerSnapshot, Position
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes


def player(x: float, y: float, teammate: bool, keeper: bool = False) -> dict:
    return {"location": [x, y], "teammate": teammate, "keeper": keeper, "team_id": None}


def frame(event_id: str, players: list[dict], index: int = 1) -> dict:
    return {"event_id": event_id, "event_index": index, "timestamp": float(index), "players": players}


def possession(frames: list[dict]) -> dict:
    return {"frames": frames}


def states(frames: list[dict], config: TrackingConfig | None = None) -> list[FrameState]:
    timeline = [
        type("Timeline", (), {"event": {"id": item["event_id"]}, "start": float(idx)})()
        for idx, item in enumerate(frames)
    ]
    built, _ = build_frame_states(possession(frames), timeline, config or TrackingConfig())
    return built


def visible(frame_state: FrameState) -> list[FramePlayerState]:
    return [item for item in frame_state.players if item.visible]


def test_one_to_one_assignment_two_observations_cannot_share_track() -> None:
    built = states(
        [
            frame("a", [player(10, 10, True)]),
            frame("b", [player(11, 10, True), player(12, 10, True)]),
        ]
    )
    ids = [item.tracking_id for item in visible(built[-1])]
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_team_isolation_tracks_never_match_other_team() -> None:
    built = states(
        [
            frame("a", [player(10, 10, True)]),
            frame("b", [player(10.5, 10, False)]),
        ]
    )
    defender = visible(built[-1])[0]
    assert defender.team_id == TEAM_DEFENSE
    assert defender.tracking_id != visible(built[0])[0].tracking_id


def test_goalkeeper_isolation() -> None:
    built = states(
        [
            frame("a", [player(10, 10, True, keeper=True)]),
            frame("b", [player(10.5, 10, True, keeper=False)]),
        ]
    )
    outfielder = visible(built[-1])[0]
    assert outfielder.is_goalkeeper is False
    assert outfielder.tracking_id != visible(built[0])[0].tracking_id


def test_unmatched_observation_creates_one_new_track() -> None:
    built = states([frame("a", [player(10, 10, True), player(20, 20, True)])])
    assert len(visible(built[0])) == 2
    assert len({item.tracking_id for item in visible(built[0])}) == 2


def test_temporary_disappearance_and_termination() -> None:
    built = states(
        [
            frame("a", [player(10, 10, True)]),
            frame("b", []),
            frame("c", []),
        ],
        TrackingConfig(max_missing_snapshots=1),
    )
    assert len(visible(built[0])) == 1
    assert len(visible(built[1])) == 0
    assert len(built[1].players) == 1
    assert len(built[2].players) == 0


def test_reappearance_matches_temporarily_missing_track_if_plausible() -> None:
    built = states(
        [
            frame("a", [player(10, 10, True)]),
            frame("b", []),
            frame("c", [player(10.5, 10, True)]),
        ],
        TrackingConfig(max_missing_snapshots=2),
    )
    assert visible(built[2])[0].tracking_id == visible(built[0])[0].tracking_id


def test_identified_player_gap_is_bridged_with_same_track() -> None:
    runner_a = {**player(10, 10, True), "player_id": 7038, "player_name": "Runner", "actor": True}
    runner_c = {**player(18, 10, True), "player_id": 7038, "player_name": "Runner", "actor": True}
    built = states(
        [
            frame("a", [runner_a], index=0),
            frame("b", [], index=1),
            frame("c", [runner_c], index=2),
        ],
        TrackingConfig(max_missing_snapshots=0, identity_max_gap_seconds=5.0),
    )
    bridged = visible(built[1])
    assert len(bridged) == 1
    assert bridged[0].player_id == 7038
    assert bridged[0].tracking_id == visible(built[0])[0].tracking_id == visible(built[2])[0].tracking_id
    assert bridged[0].status == ObservationStatus.INTERPOLATED
    assert bridged[0].observed is False


def test_impossible_movement_creates_new_track_instead_of_teleporting() -> None:
    built = states(
        [
            frame("a", [player(10, 10, True)]),
            frame("b", [player(100, 70, True)]),
        ],
        TrackingConfig(maximum_speed_mps=1.0, movement_tolerance_m=0.1),
    )
    assert visible(built[1])[0].tracking_id != visible(built[0])[0].tracking_id


def test_exact_event_timestamp_returns_observed_snapshot_not_interpolation() -> None:
    built = states(
        [
            frame("a", [player(10, 10, True)]),
            frame("b", [player(20, 20, True), player(30, 30, True)]),
        ]
    )
    exact = interpolated_frame_state(built, built[0].timestamp)
    assert exact is not None
    assert [(item.position.x, item.position.y) for item in visible(exact)] == [(10.0, 10.0)]
    assert all(item.status == ObservationStatus.OBSERVED for item in visible(exact))
    assert all(item.confidence == 1.0 for item in visible(exact))


def test_between_events_returns_interpolated_status_and_confidence() -> None:
    built = states(
        [
            frame("a", [player(10, 10, True)]),
            frame("b", [player(11, 10, True)]),
        ]
    )
    midpoint = interpolated_frame_state(built, (built[0].timestamp + built[1].timestamp) / 2.0)
    assert midpoint is not None
    players = visible(midpoint)
    assert len(players) == 1
    assert players[0].status == ObservationStatus.INTERPOLATED
    assert players[0].observed is False
    assert 0.0 <= players[0].confidence <= 1.0


def test_frame_with_more_than_11_visible_players_raises() -> None:
    players = [
        FramePlayerState(f"t{i}", TEAM_ATTACK, Position(float(i), 0.0), True, False, True, True)
        for i in range(12)
    ]
    with pytest.raises(TrackingValidationError):
        raise_if_invalid_frame(FrameState(1.0, "event", players))


def test_duplicate_tracking_id_validation_raises() -> None:
    players = [
        FramePlayerState("same", TEAM_ATTACK, Position(1.0, 0.0), True, False, True, True),
        FramePlayerState("same", TEAM_ATTACK, Position(2.0, 0.0), True, False, True, True),
    ]
    with pytest.raises(TrackingValidationError):
        raise_if_invalid_frame(FrameState(1.0, "event", players))


def test_renderer_split_players_only_returns_visible_players() -> None:
    attackers, defenders = split_players(
        [
            {"teammate": True, "visible": True},
            {"teammate": True, "visible": False},
            {"teammate": False, "visible": True},
        ]
    )
    assert len(attackers) == 1
    assert len(defenders) == 1


def test_tactical_detection_uses_event_freeze_frame_not_reconstructed_tracks() -> None:
    defenders = [
        PlayerSnapshot("d1", TEAM_DEFENSE, Position(50, 25), False, False),
        PlayerSnapshot("d2", TEAM_DEFENSE, Position(51, 40), False, False),
        PlayerSnapshot("d3", TEAM_DEFENSE, Position(52, 55), False, False),
    ]
    event = Event("pass", "Pass", 0.0, 52, TEAM_ATTACK, "p", Position(40, 40), Position(65, 40), None, None, defenders)
    normalized = NormalizedPossession(52, TEAM_ATTACK, TEAM_DEFENSE, [event], 0.0, 1.0, "test")
    findings = detect_line_breaking_passes(normalized, LineBreakConfig())
    assert findings
    assert findings[0].event_id == "pass"
