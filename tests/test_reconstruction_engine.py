from __future__ import annotations

from copy import deepcopy

import pytest

from src.reconstruction import ReconstructionError, build_reconstruction, reconstruction_state_at, validate_reconstruction
from src.world_model import build_world_model_from_reconstruction


def _match() -> dict:
    events = [
        {"id": "a", "index": 1, "timestamp": 0.0, "duration": 1.0, "type": "Carry", "player_id": 7, "player_name": "Seven", "team_id": 1, "start_location": [10.0, 10.0], "end_location": [20.0, 10.0], "visible_area": [0, 0, 40, 0, 40, 40, 0, 40]},
        {"id": "b", "index": 2, "timestamp": 1.0, "duration": 0.2, "type": "Carry", "player_id": 7, "player_name": "Seven", "team_id": 1, "start_location": [20.0, 10.0], "end_location": [21.0, 10.0], "visible_area": [0, 0, 40, 0, 40, 40, 0, 40]},
    ]
    frames = [
        {"event_id": "a", "event_index": 1, "timestamp": 0.0, "players": [{"location": [10.0, 10.0], "teammate": True, "keeper": False, "actor": True, "player_id": 7, "player_name": "Seven", "source_index": 0}]},
        {"event_id": "b", "event_index": 2, "timestamp": 1.0, "players": [{"location": [20.0, 10.0], "teammate": True, "keeper": False, "actor": True, "player_id": 7, "player_name": "Seven", "source_index": 0}]},
    ]
    return {"match_id": 1, "match_label": "test", "start_time": 0.0, "end_time": 1.2, "events": events, "frames": frames, "lineups": [], "source_documents": {}}


def test_reconstruction_is_repeatable_and_not_relevance_filtered() -> None:
    config = {"animation": {}, "tracking": {}, "relevance": {"maximum_total_outfield_players": 0}}
    first = build_reconstruction(_match(), config)
    second = build_reconstruction(_match(), config)
    assert first == second
    assert first["sha256"] == second["sha256"]
    assert first["policy"]["relevance_filtering"] is False
    assert first["keyframes"][0]["players"]


def test_pause_state_is_interpolated_and_fully_traceable() -> None:
    reconstruction = build_reconstruction(_match(), {"animation": {}, "tracking": {}})
    state = reconstruction_state_at(reconstruction, 0.5)
    assert state == reconstruction_state_at(reconstruction, 0.5)
    player = state["players"][0]
    assert player["identity"]["player_id"] == 7
    assert player["interpolation_state"] == "INTERPOLATED"
    assert player["location"] == [15.0, 10.0]
    assert player["provenance"]


def test_visible_unknown_or_unprovenanced_player_is_rejected() -> None:
    reconstruction = build_reconstruction(_match(), {"animation": {}, "tracking": {}})
    broken = deepcopy(reconstruction)
    player = broken["keyframes"][0]["players"][0]
    player["interpolation_state"] = "UNKNOWN"
    player["visible"] = True
    import hashlib, json
    body = {key: value for key, value in broken.items() if key != "sha256"}
    broken["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    with pytest.raises(ReconstructionError):
        validate_reconstruction(broken)


def test_world_model_is_a_read_only_consumer_of_reconstruction() -> None:
    reconstruction = build_reconstruction(_match(), {"animation": {}, "tracking": {}})
    before = deepcopy(reconstruction)
    world = build_world_model_from_reconstruction(reconstruction)
    assert reconstruction == before
    assert world["reconstruction_sha256"] == reconstruction["sha256"]
    assert world["policy"] == {"read_only_reconstruction": True, "analysis_may_mutate": False}
