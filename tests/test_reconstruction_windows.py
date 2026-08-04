from __future__ import annotations

from copy import deepcopy

from src.reconstruction import build_window_reconstruction, reconstruction_state_at, select_reconstruction_window


def event(event_id: str, index: int, timestamp: float, action: str = "Pass", period: int = 1, duration: float = 1.0) -> dict:
    return {"id": event_id, "index": index, "timestamp": timestamp, "duration": duration, "period": period, "type": action, "player_id": 7, "player_name": "Seven", "team_id": 1, "start_location": [10.0 + index, 10.0], "end_location": [15.0 + index, 10.0], "visible_area": [0, 0, 120, 0, 120, 80, 0, 80]}


def frame(event_id: str, index: int, timestamp: float, x: float = 10.0) -> dict:
    return {"event_id": event_id, "event_index": index, "timestamp": timestamp, "players": [{"location": [x, 10.0], "teammate": True, "keeper": False, "actor": True, "player_id": 7, "player_name": "Seven", "source_index": 0}]}


def match() -> dict:
    events = [event("a", 1, 10.0), event("b", 2, 11.0, "Ball Receipt*", duration=0.0), event("c", 3, 12.0, "Carry")]
    frames = [frame("a", 1, 10.0, 10.0), frame("b", 2, 11.0, 15.0), frame("c", 3, 12.0, 18.0)]
    return {"match_id": 1, "match_label": "window", "start_time": 10.0, "end_time": 13.0, "events": events, "frames": frames, "lineups": [], "source_documents": {}, "source_validation_errors": []}


def test_selector_returns_supported_bounded_single_period_window() -> None:
    selection = select_reconstruction_window(match(), event_id="a", sequence_end_event_id="c", pre_roll_seconds=0.0, post_roll_seconds=0.0)
    assert selection["admission"] == "ACCEPTED"
    assert selection["selected_actions"] == ["PASS", "BALL_RECEIPT", "CARRY"]
    assert selection["period"] == 1
    assert selection["duration_seconds"] == 3.0


def test_selector_rejects_unsupported_action_and_period_crossing() -> None:
    unsupported = match()
    unsupported["events"][0]["type"] = "Pressure"
    assert select_reconstruction_window(unsupported, event_id="a")["admission"] == "REJECTED_UNSUPPORTED_ACTION"
    crossing = match()
    crossing["events"][2]["period"] = 2
    assert select_reconstruction_window(crossing, event_id="a", sequence_end_event_id="c")["admission"] == "REJECTED_PERIOD_BOUNDARY"


def test_action_ball_trajectory_ends_and_does_not_snap_to_next_event() -> None:
    result = build_window_reconstruction(match(), event_id="a", sequence_end_event_id="c", pre_roll_seconds=0.0, post_roll_seconds=0.0)
    reconstruction = result["reconstruction"]
    assert reconstruction is not None
    assert reconstruction_state_at(reconstruction, 0.5)["ball_state"] == "INTERPOLATED"
    assert reconstruction_state_at(reconstruction, 0.999)["ball"][0] > 15.9
    assert reconstruction_state_at(reconstruction, 1.0)["ball"] == [12.0, 10.0]
    # Receipt is an anchored state, never a trajectory to the carry.
    assert reconstruction_state_at(reconstruction, 1.1)["ball_state"] == "OBSERVED"
    assert reconstruction_state_at(reconstruction, 1.2)["ball_state"] == "UNKNOWN"


def test_period_isolation_and_motion_gate_produce_unknown_not_fabricated_motion() -> None:
    source = match()
    result = build_window_reconstruction(source, event_id="a", sequence_end_event_id="c", pre_roll_seconds=0.0, post_roll_seconds=0.0, config={"reconstruction_window": {"maximum_player_speed_mps": 1.0}})
    reconstruction = result["reconstruction"]
    assert reconstruction is not None
    assert reconstruction_state_at(reconstruction, 0.5)["players"] == []
    before = deepcopy(reconstruction)
    assert reconstruction_state_at(reconstruction, 0.5)["players"] == []
    assert reconstruction == before


def test_source_validation_rejection_is_explicit_and_not_renderable() -> None:
    source = match()
    source["source_validation_errors"] = ["SOURCE_EVENT_INDEX_TIME_ORDER_INVALID"]
    result = build_window_reconstruction(source, event_id="a")
    assert result["selection"]["admission"] == "REJECTED_INSUFFICIENT_OBSERVATION"
    assert result["reconstruction"] is None


def test_reconstruction_association_never_uses_legacy_tolerance_to_exceed_speed_gate() -> None:
    source = match()
    source["events"] = [event("a", 1, 10.0), event("b", 2, 10.1)]
    source["frames"] = [frame("a", 1, 10.0, 10.0), frame("b", 2, 10.1, 12.0)]
    result = build_window_reconstruction(source, event_id="a", sequence_end_event_id="b", pre_roll_seconds=0.0, post_roll_seconds=0.0, config={"reconstruction_window": {"maximum_player_speed_mps": 9.5}})
    reconstruction = result["reconstruction"]
    assert reconstruction is not None
    observed_tracks = [{player["tracking_id"] for player in keyframe["players"] if player["interpolation_state"] == "OBSERVED"} for keyframe in reconstruction["keyframes"]]
    assert observed_tracks[0].isdisjoint(observed_tracks[1])
    assert reconstruction_state_at(reconstruction, 0.05)["players"] == []
