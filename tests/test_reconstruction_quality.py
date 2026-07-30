from __future__ import annotations

import matplotlib.pyplot as plt
from pathlib import Path
import yaml

from analysis.interpolate import ObservationStatus, build_animation_model, state_at
from analysis.normalize import load_and_normalize
from src.pipelines.render_analysis import draw_player_disc


def _event(event_id: str, timestamp: float, player_id: int = 1) -> dict:
    return {
        "id": event_id,
        "type": "Carry",
        "timestamp": timestamp,
        "duration": 0.2,
        "player_id": player_id,
        "player_name": f"Player {player_id}",
        "start_location": [30.0, 30.0],
        "end_location": [31.0, 30.0],
    }


def _frame(event_id: str, timestamp: float, present: bool = True) -> dict:
    players = []
    if present:
        players.append(
            {
                "location": [30.0, 30.0],
                "teammate": True,
                "keeper": False,
                "player_id": 1,
                "player_name": "Player 1",
            }
        )
    return {"event_id": event_id, "event_index": int(timestamp), "timestamp": timestamp, "players": players}


def _stale_model() -> tuple[dict, str]:
    events = [_event("a", 0.0), _event("b", 1.0), _event("c", 2.0), _event("d", 3.0)]
    frames = [_frame("a", 0.0), _frame("b", 1.0, False), _frame("c", 2.0, False), _frame("d", 3.0, False)]
    model = build_animation_model(
        {"events": events, "frames": frames, "start_time": 0.0},
        {
            "animation": {"start_hold_seconds": 0.0},
            "tracking": {
                "max_missing_snapshots": 0,
                "continuity_horizon_seconds": 5.0,
                "stale_fade_start_seconds": 0.75,
                "stale_omit_seconds": 2.0,
                "stale_visibility_hysteresis_seconds": 0.25,
            },
            "relevance": {},
        },
    )
    track_id = model["frame_states"][0].players[0].tracking_id
    return model, track_id


def test_optional_stale_track_fades_then_is_omitted_deterministically() -> None:
    model, track_id = _stale_model()
    model["relevant_player_selection"] = {
        "selected_track_ids": [track_id],
        "mandatory_track_ids": [],
        "context_track_ids": [],
        "optional_track_ids": [track_id],
    }
    fading = next(player for player in state_at(model, 1.0)["players"] if player["tracking_id"] == track_id)
    assert fading["status"] == ObservationStatus.MISSING_BUT_ALIVE.value
    assert 0.0 < fading["alpha"] < 1.0
    threshold = next(player for player in state_at(model, 2.0)["players"] if player["tracking_id"] == track_id)
    assert 0.0 < threshold["alpha"] < fading["alpha"]
    assert state_at(model, 2.25)["players"] == []
    assert state_at(model, 2.25)["players"] == state_at(model, 2.25)["players"]


def test_mandatory_stale_protagonist_remains_with_explicit_uncertainty() -> None:
    model, track_id = _stale_model()
    model["relevant_player_selection"] = {
        "selected_track_ids": [track_id],
        "mandatory_track_ids": [track_id],
        "context_track_ids": [],
        "optional_track_ids": [],
    }
    player = next(player for player in state_at(model, 3.0)["players"] if player["tracking_id"] == track_id)
    assert player["status"] == ObservationStatus.MISSING_BUT_ALIVE.value
    assert player["relevance_role"] == "mandatory"
    assert player["evidence_age_seconds"] == 3.0
    assert 0.0 < player["alpha"] <= 0.20


def test_normal_renderer_applies_lifecycle_alpha_and_line_style() -> None:
    fig, ax = plt.subplots()
    player = {
        "location": [40.0, 30.0],
        "tracking_id": "track_1",
        "status": "MISSING_BUT_ALIVE",
        "alpha": 0.24,
        "confidence": 0.4,
        "actor": False,
    }
    artists = draw_player_disc(ax, player, {}, "#ffffff", "#000000", "#000000")
    assert artists[0].get_alpha() == 0.24
    assert artists[1].get_alpha() == 0.24
    assert artists[0].get_linestyle() != "solid"
    plt.close(fig)


def test_hold_diagnostics_are_deterministic_and_complete() -> None:
    first, _ = _stale_model()
    second, _ = _stale_model()
    assert first["tracking_diagnostics"]["interpolation_holds"] == second["tracking_diagnostics"]["interpolation_holds"]
    assert set(first["tracking_diagnostics"]["hold_reason_codes"]) == {
        "HOLD_MISSING_PREVIOUS_ENDPOINT",
        "HOLD_MISSING_NEXT_ENDPOINT",
        "HOLD_ASSOCIATION_AMBIGUITY",
        "HOLD_IDENTITY_CONFLICT",
        "HOLD_SPEED_CAP_REJECTION",
        "HOLD_LIFECYCLE_STATE",
        "HOLD_NO_FUTURE_SUPPORTED_OBSERVATION",
    }
    for row in first["tracking_diagnostics"]["interpolation_holds"]:
        assert set(row) == {
            "reason_code",
            "track_id",
            "model_time_interval",
            "evidence_age_seconds",
            "previous_observation",
            "next_observation",
            "lifecycle_state",
            "confidence",
        }


def test_locatelli_fixture_has_no_locatelli_bonucci_or_immobile_xhaka_track_history() -> None:
    root = Path(__file__).resolve().parents[1]
    possession = load_and_normalize(root / "data/second_goal.json")
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    model = build_animation_model(possession, config)
    histories: dict[str, set[str]] = {}
    for frame in model["frame_states"]:
        for player in frame.players:
            if player.player_name:
                histories.setdefault(player.tracking_id, set()).add(player.player_name)
    forbidden = [
        {"Manuel Locatelli", "Leonardo Bonucci"},
        {"Ciro Immobile", "Granit Xhaka"},
    ]
    assert all(not pair <= names for names in histories.values() for pair in forbidden)


def test_visibility_hysteresis_prevents_one_frame_disappear_reappear() -> None:
    events = [_event("a", 0.0), _event("b", 1.0), _event("c", 2.0), _event("d", 3.0)]
    frames = [_frame("a", 0.0), _frame("b", 1.0, False), _frame("c", 2.0, False), _frame("d", 3.0, True)]
    model = build_animation_model(
        {"events": events, "frames": frames, "start_time": 0.0},
        {
            "animation": {"start_hold_seconds": 0.0},
            "tracking": {
                "max_missing_snapshots": 0,
                "continuity_horizon_seconds": 5.0,
                "stale_fade_start_seconds": 0.75,
                "stale_omit_seconds": 2.0,
                "stale_visibility_hysteresis_seconds": 0.25,
            },
            "relevance": {},
        },
    )
    track_id = model["frame_states"][0].players[0].tracking_id
    model["relevant_player_selection"] = {
        "selected_track_ids": [track_id],
        "mandatory_track_ids": [],
        "context_track_ids": [],
        "optional_track_ids": [track_id],
    }
    visible = [
        any(player["tracking_id"] == track_id for player in state_at(model, frame / 24.0)["players"])
        for frame in range(73)
    ]
    absent_runs = []
    start = None
    for index, value in enumerate(visible + [True]):
        if not value and start is None:
            start = index
        elif value and start is not None:
            absent_runs.append(index - start)
            start = None
    assert absent_runs
    assert min(absent_runs) > 1
