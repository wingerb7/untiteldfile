from __future__ import annotations

import pytest

from analysis.interpolate import (
    TEAM_ATTACK,
    TEAM_DEFENSE,
    ObservationStatus,
    TrackingConfig,
    build_animation_model,
    build_frame_states,
    interpolated_frame_state,
    state_at,
)
from analysis.relevance import RelevanceConfig, select_relevant_players


def player(x: float, y: float, teammate: bool, player_id: int, keeper: bool = False) -> dict:
    return {
        "location": [x, y],
        "teammate": teammate,
        "keeper": keeper,
        "team_id": None,
        "player_id": player_id,
        "player_name": f"Player {player_id}",
    }


def event(
    event_id: str,
    event_type: str,
    timestamp: float,
    actor_id: int,
    start: list[float],
    end: list[float] | None = None,
    recipient_id: int | None = None,
) -> dict:
    return {
        "id": event_id,
        "index": int(timestamp * 10),
        "timestamp": timestamp,
        "type": event_type,
        "player_id": actor_id,
        "player_name": f"Player {actor_id}",
        "team_id": TEAM_ATTACK,
        "start_location": start,
        "end_location": end,
        "recipient_id": recipient_id,
        "recipient_name": None if recipient_id is None else f"Player {recipient_id}",
        "freeze_frame": [],
    }


def frame(event_id: str, timestamp: float, players: list[dict]) -> dict:
    return {"event_id": event_id, "event_index": int(timestamp * 10), "timestamp": timestamp, "players": players}


def timeline(events: list[dict]) -> list[object]:
    return [type("Timeline", (), {"event": item, "start": float(idx)})() for idx, item in enumerate(events)]


def build(events: list[dict], frames: list[dict]):
    return build_frame_states({"events": events, "frames": frames}, timeline(events), TrackingConfig())


def track_id_for_player(states, player_id: int) -> str:
    for state in states:
        for item in state.players:
            if item.player_id == player_id:
                return item.tracking_id
    raise AssertionError(f"player {player_id} not tracked")


def base_scene():
    events = [
        event("p1", "Pass", 0.0, 10, [40, 40], [55, 42], recipient_id=11),
        event("s1", "Shot", 1.0, 11, [90, 38], [120, 40]),
    ]
    players = [
        player(40, 40, True, 10),
        player(55, 42, True, 11),
        player(47, 28, True, 12),
        player(35, 72, True, 13),
        player(10, 5, True, 14),
        player(42, 41, False, 20),
        player(55, 45, False, 21),
        player(58, 25, False, 22),
        player(58, 58, False, 23),
        player(92, 40, False, 24),
        player(117, 40, False, 1, keeper=True),
        player(5, 75, False, 29),
    ]
    frames = [frame("p1", 0.0, players), frame("s1", 1.0, [{**item, "location": [item["location"][0] + 2, item["location"][1]]} for item in players])]
    return events, frames


def test_actor_and_pass_recipient_are_selected() -> None:
    events, frames = base_scene()
    states, _ = build(events, frames)
    selection = select_relevant_players({"events": events}, states)
    assert track_id_for_player(states, 10) in selection.selected_track_ids
    assert track_id_for_player(states, 11) in selection.selected_track_ids


def test_shot_actor_and_goalkeeper_are_selected() -> None:
    events, frames = base_scene()
    states, _ = build(events, frames)
    selection = select_relevant_players({"events": events}, states)
    assert track_id_for_player(states, 11) in selection.selected_track_ids
    assert track_id_for_player(states, 1) in selection.selected_track_ids


def test_selected_finding_participants_are_selected() -> None:
    events, frames = base_scene()
    states, _ = build(events, frames)
    selection = select_relevant_players(
        {"events": events},
        states,
        selected_finding={"player_id": 12, "recipient_id": 13},
    )
    assert track_id_for_player(states, 12) in selection.selected_track_ids
    assert track_id_for_player(states, 13) in selection.selected_track_ids


def test_nearest_presser_and_defensive_line_players_are_selected() -> None:
    events, frames = base_scene()
    states, _ = build(events, frames)
    selection = select_relevant_players({"events": events}, states)
    reasons = {track_id: set(value) for track_id, value in selection.reasons_by_track.items()}
    assert any("nearest_presser" in value for value in reasons.values())
    assert sum("defensive_line_context" in value for value in reasons.values()) >= 2


def test_irrelevant_distant_tracks_are_suppressed_without_forcing_full_team() -> None:
    events, frames = base_scene()
    states, _ = build(events, frames)
    selection = select_relevant_players({"events": events}, states, RelevanceConfig(maximum_total_outfield_players=8))
    distant_attacker = track_id_for_player(states, 14)
    distant_defender = track_id_for_player(states, 29)
    assert distant_attacker not in selection.selected_track_ids
    assert distant_defender not in selection.selected_track_ids
    assert len(selection.selected_track_ids) < 11


def test_selection_is_stable_across_scene_window() -> None:
    events, frames = base_scene()
    states, _ = build(events, frames)
    selection = select_relevant_players({"events": events}, states)
    assert selection.selected_track_ids == select_relevant_players({"events": events}, states).selected_track_ids


def test_non_selected_players_are_not_rendered_by_state_at() -> None:
    events, frames = base_scene()
    model = build_animation_model({"events": events, "frames": frames, "start_time": 0.0}, {"animation": {}, "tracking": {}, "relevance": {"maximum_total_outfield_players": 7}})
    rendered_ids = {item["tracking_id"] for item in state_at(model, 0.0)["players"]}
    selected_ids = set(model["relevant_player_selection"]["selected_track_ids"])
    assert rendered_ids == selected_ids
    assert track_id_for_player(model["frame_states"], 29) not in rendered_ids


def test_core_actor_survives_short_observation_gap() -> None:
    events = [
        event("c1", "Carry", 0.0, 10, [30, 30], [36, 30]),
        event("gap", "Dribble", 1.0, 10, [36, 30], [38, 30]),
        event("c2", "Carry", 2.0, 10, [38, 30], [42, 30]),
    ]
    frames = [frame("c1", 0.0, [player(30, 30, True, 10)]), frame("gap", 1.0, []), frame("c2", 2.0, [player(38, 30, True, 10)])]
    model = build_animation_model({"events": events, "frames": frames, "start_time": 0.0}, {"animation": {}, "tracking": {"identity_max_gap_seconds": 3.0}, "relevance": {}})
    assert track_id_for_player(model["frame_states"], 10) in set(model["relevant_player_selection"]["selected_track_ids"])
    assert any(item["player_id"] == 10 for item in state_at(model, 1.0)["players"])


def test_excessive_inferred_displacement_is_held() -> None:
    states, _ = build(
        [event("a", "Carry", 0.0, 10, [10, 10]), event("b", "Carry", 1.0, 10, [100, 70])],
        [frame("a", 0.0, [player(10, 10, True, 10)]), frame("b", 1.0, [player(100, 70, True, 10)])],
    )
    midpoint = interpolated_frame_state(states, 0.5)
    assert midpoint is not None
    rendered = next(item for item in midpoint.players if item.player_id == 10)
    assert rendered.status in {ObservationStatus.PREDICTED_OR_HELD, ObservationStatus.INTERPOLATED}
    assert rendered.position.x == pytest.approx(10.0)
    assert rendered.position.y == pytest.approx(10.0)


def test_selected_tracks_respect_limits_and_validation_invariants() -> None:
    events, frames = base_scene()
    states, _ = build(events, frames)
    selection = select_relevant_players({"events": events}, states, RelevanceConfig(maximum_attackers=4, maximum_defenders=4, maximum_total_outfield_players=7))
    assert len(selection.attacking_track_ids) <= 4
    assert len([track_id for track_id in selection.defending_track_ids if track_id in selection.selected_track_ids]) <= 4
    assert len(selection.selected_track_ids) <= 8


def test_mandatory_participants_are_not_trimmed_by_strict_limits() -> None:
    events = [
        event("c1", "Carry", 0.0, 10, [30, 30], [34, 30]),
        event("p1", "Pass", 1.0, 11, [40, 40], [50, 40], recipient_id=12),
        event("s1", "Shot", 2.0, 12, [90, 40], [120, 40]),
    ]
    players = [
        player(30, 30, True, 10),
        player(40, 40, True, 11),
        player(50, 40, True, 12),
        player(80, 40, False, 20),
    ]
    frames = [frame(item["id"], item["timestamp"], players) for item in events]
    states, _ = build(events, frames)

    selection = select_relevant_players(
        {"events": events},
        states,
        RelevanceConfig(maximum_attackers=1, maximum_defenders=1, maximum_total_outfield_players=1),
    )

    mandatory_ids = {track_id_for_player(states, player_id) for player_id in (10, 11, 12)}
    assert mandatory_ids <= selection.selected_track_ids
    assert mandatory_ids <= selection.mandatory_track_ids
    assert any("mandatory_attacking_team_limit_exceeded" in warning for warning in selection.warnings)
    assert any("mandatory_outfield_limit_exceeded" in warning for warning in selection.warnings)


def test_low_confidence_selected_actor_remains_rendered_with_low_alpha() -> None:
    events = [
        event("c1", "Carry", 0.0, 10, [30, 30], [34, 30]),
        event("gap1", "Carry", 1.0, 10, [34, 30], [36, 30]),
        event("gap2", "Carry", 2.0, 10, [36, 30], [38, 30]),
    ]
    frames = [
        frame("c1", 0.0, [player(30, 30, True, 10)]),
        frame("gap1", 1.0, []),
        frame("gap2", 2.0, []),
    ]
    model = build_animation_model(
        {"events": events, "frames": frames, "start_time": 0.0},
        {
            "animation": {},
            "tracking": {
                "max_missing_snapshots": 0,
                "continuity_horizon_seconds": 5.0,
                "uncertainty_growth_per_second": 0.8,
            },
            "relevance": {},
        },
    )

    rendered = next(item for item in state_at(model, model["frame_states"][-1].timestamp)["players"] if item["player_id"] == 10)
    assert rendered["status"] == ObservationStatus.MISSING_BUT_ALIVE.value
    assert rendered["confidence"] < 0.55
    assert rendered["visible"] is True
    assert rendered["alpha"] < 1.0
    assert model["tracking_diagnostics"]["selected_but_not_rendered"]["summary"]["mandatory_total"] == 0
