from __future__ import annotations

import json
from pathlib import Path

from src.tactical_validation import (
    ValidationOutcome,
    build_position_index,
    run_all_episode_validators,
    validate_actor_visibility,
    validate_caption_timing,
    validate_causal_transition,
    validate_defender_visibility_when_required,
    validate_evidence_within_interval,
    validate_identity_resolution,
    validate_no_duplicate_decisive_action,
    validate_supported_episode_type,
    validate_switch_of_play_changes_channel,
    validate_temporal_order,
)

ROOT = Path(__file__).resolve().parents[1]

FAIL, WARN, PASS = ValidationOutcome.FAIL, ValidationOutcome.WARN, ValidationOutcome.PASS


def _episode(**overrides):
    base = {
        "episode_id": "episode:a",
        "episode_type": "BUILDUP",
        "start_event_id": "e1",
        "end_event_id": "e2",
        "participating_action_ids": ["e1", "e2"],
        "primary_actor_ids": ["100"],
        "relevant_defender_ids": [],
        "evidence": {},
        "confidence": 1.0,
        "limitations": [],
    }
    base.update(overrides)
    return base


def _direction(episode_id="episode:a", visible=("100",)):
    return {
        "episode_id": episode_id,
        "visible_players": list(visible),
        "highlighted_players": list(visible),
        "hidden_players": [],
    }


# ---------------------------------------------------------------------------
# Real-fixture regression coverage: these lock in the two objective defects
# found in the semantic audit so they cannot silently regress or be "fixed"
# by accident without the test suite noticing.
# ---------------------------------------------------------------------------


def test_depay_switch_of_play_episode_fails_channel_check():
    episodes = json.loads((ROOT / "renders/tactical_episodes/depay/tactical_episodes.json").read_text())["episodes"]
    results = validate_switch_of_play_changes_channel(episodes)
    switch_results = [r for r in results if r.subject_id == "episode:f3ac99e003eee69e"]
    assert switch_results and switch_results[0].outcome == FAIL


def test_locatelli_switch_of_play_episode_passes_channel_check():
    episodes = json.loads((ROOT / "renders/tactical_episodes/locatelli/tactical_episodes.json").read_text())["episodes"]
    results = validate_switch_of_play_changes_channel(episodes)
    assert all(r.outcome == PASS for r in results)


def test_depay_isolation_and_cutback_show_no_net_progress_toward_goal():
    episodes = json.loads((ROOT / "renders/tactical_episodes/depay/tactical_episodes.json").read_text())["episodes"]
    raw_events = json.loads((ROOT / "data/depay_goal.json").read_text())["events"]
    positions = build_position_index(raw_events)
    from src.tactical_validation.validators import validate_episode_forward_progress

    results = validate_episode_forward_progress(episodes, positions, attacking_goal_x=120.0)
    by_id = {r.subject_id: r for r in results}
    assert by_id["episode:283efcb45602010a"].outcome == WARN  # ISOLATION
    assert by_id["episode:e869ff80d404c7d9"].outcome == WARN  # CUTBACK


def test_all_real_fixture_identities_are_either_authenticated_or_disclosed_observation_only():
    for fixture in ("depay", "locatelli"):
        episodes = json.loads((ROOT / f"renders/tactical_episodes/{fixture}/tactical_episodes.json").read_text())["episodes"]
        directions = json.loads((ROOT / f"renders/tactical_episodes/{fixture}/scene_directions.json").read_text())["directions"]
        directions_by_id = {d["episode_id"]: d for d in directions}
        for episode in episodes:
            direction = directions_by_id[episode["episode_id"]]
            results = validate_identity_resolution(episode, direction)
            assert all(r.outcome != FAIL for r in results), f"{fixture} {episode['episode_id']} has an unresolved/ambiguous identity"


def test_real_fixtures_have_no_temporal_or_interval_violations():
    for fixture, source in (("depay", "data/depay_goal.json"), ("locatelli", "data/second_goal.json")):
        episodes = json.loads((ROOT / f"renders/tactical_episodes/{fixture}/tactical_episodes.json").read_text())["episodes"]
        raw_events = json.loads((ROOT / source).read_text())["events"]
        order = {event["id"]: i for i, event in enumerate(raw_events)}
        assert all(r.outcome == PASS for r in validate_temporal_order(episodes, order))
        assert all(r.outcome == PASS for r in validate_evidence_within_interval(episodes, order))
        assert all(r.outcome == PASS for r in validate_no_duplicate_decisive_action(episodes))
        assert all(r.outcome == PASS for r in validate_supported_episode_type(episodes))


def test_run_all_episode_validators_is_deterministic():
    episodes = json.loads((ROOT / "renders/tactical_episodes/depay/tactical_episodes.json").read_text())["episodes"]
    directions = json.loads((ROOT / "renders/tactical_episodes/depay/scene_directions.json").read_text())["directions"]
    directions_by_id = {d["episode_id"]: d for d in directions}
    raw_events = json.loads((ROOT / "data/depay_goal.json").read_text())["events"]
    first = run_all_episode_validators(episodes, directions_by_id, raw_events, attacking_goal_x=120.0)
    second = run_all_episode_validators(episodes, directions_by_id, raw_events, attacking_goal_x=120.0)
    assert [(r.check, r.subject_id, r.outcome) for r in first] == [(r.check, r.subject_id, r.outcome) for r in second]


# ---------------------------------------------------------------------------
# Synthetic-fixture unit coverage for each validator's decision boundary.
# ---------------------------------------------------------------------------


def test_temporal_order_flags_overlap():
    episodes = [
        _episode(episode_id="episode:a", start_event_id="e1", end_event_id="e3"),
        _episode(episode_id="episode:b", start_event_id="e2", end_event_id="e4"),
    ]
    order = {"e1": 0, "e2": 1, "e3": 2, "e4": 3}
    results = validate_temporal_order(episodes, order)
    assert any(r.subject_id == "episode:b" and r.outcome == FAIL for r in results)


def test_temporal_order_passes_when_sequential():
    episodes = [
        _episode(episode_id="episode:a", start_event_id="e1", end_event_id="e2"),
        _episode(episode_id="episode:b", start_event_id="e3", end_event_id="e4"),
    ]
    order = {"e1": 0, "e2": 1, "e3": 2, "e4": 3}
    results = validate_temporal_order(episodes, order)
    assert all(r.outcome == PASS for r in results)


def test_evidence_within_interval_flags_evidence_outside_declared_span():
    episode = _episode(participating_action_ids=["e1", "e2", "e5"])
    order = {"e1": 0, "e2": 1, "e5": 4}
    results = validate_evidence_within_interval([episode], order)
    assert results[0].outcome == FAIL
    assert "e5" in results[0].evidence["outside_ids"]


def test_no_duplicate_decisive_action_flags_shared_end_event():
    episodes = [
        _episode(episode_id="episode:a", end_event_id="shared"),
        _episode(episode_id="episode:b", end_event_id="shared"),
    ]
    results = validate_no_duplicate_decisive_action(episodes)
    assert results[1].outcome == FAIL


def test_supported_episode_type_flags_unknown_type():
    episode = _episode(episode_type="INVENTED_TYPE")
    results = validate_supported_episode_type([episode])
    assert results[0].outcome == FAIL


def test_switch_of_play_fails_when_changed_side_is_false():
    episode = _episode(episode_type="SWITCH_OF_PLAY", evidence={"feature_values": {"changed_side": False}})
    results = validate_switch_of_play_changes_channel([episode])
    assert results[0].outcome == FAIL


def test_switch_of_play_passes_when_changed_side_is_true():
    episode = _episode(episode_type="SWITCH_OF_PLAY", evidence={"feature_values": {"changed_side": True}})
    results = validate_switch_of_play_changes_channel([episode])
    assert results[0].outcome == PASS


def test_actor_visibility_fails_when_actor_not_visible():
    episode = _episode(primary_actor_ids=["100", "200"])
    direction = _direction(visible=("100",))
    result = validate_actor_visibility(episode, direction)
    assert result.outcome == FAIL


def test_defender_visibility_required_for_isolation_but_not_buildup():
    episode = _episode(episode_type="ISOLATION", relevant_defender_ids=["recon:e1:0"])
    direction = _direction(visible=("100",))
    assert validate_defender_visibility_when_required(episode, direction).outcome == FAIL

    buildup = _episode(episode_type="BUILDUP", relevant_defender_ids=[])
    assert validate_defender_visibility_when_required(buildup, direction).outcome == PASS


def test_caption_timing_fails_when_lead_exceeds_duration():
    result = validate_caption_timing("episode:a", duration_seconds=1.0, lead_seconds=2.0)
    assert result.outcome == FAIL


def test_caption_timing_passes_when_lead_fits():
    result = validate_caption_timing("episode:a", duration_seconds=2.0, lead_seconds=0.5)
    assert result.outcome == PASS


def test_causal_transition_fails_on_chronology_only_evidence():
    edge = {
        "source_episode_id": "episode:a",
        "target_episode_id": "episode:b",
        "relation": "ENABLES",
        "supporting_evidence": {"adjacent": True},
        "confidence": 0.9,
    }
    result = validate_causal_transition(edge)
    assert result.outcome == FAIL


def test_causal_transition_passes_with_independent_evidence():
    edge = {
        "source_episode_id": "episode:a",
        "target_episode_id": "episode:b",
        "relation": "OPENS",
        "supporting_evidence": {"defender_displacement_m": 12.4},
        "confidence": 0.8,
    }
    result = validate_causal_transition(edge)
    assert result.outcome == PASS
