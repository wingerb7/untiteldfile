from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from src.domain.models import Event, NormalizedPossession, PlayerSnapshot, Position, TacticalFinding
from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.patterns.positional import PositionalPatternConfig, detect_cutback_candidates, detect_positional_patterns
from src.intelligence.reasoning.rank_findings import rank_findings
from src.source_selection import PINNED_REVISION, SourceSelectionError, select_source_documents
from src.tactical_episodes import build_tactical_episodes
from src.tactical_episodes.eligibility import evaluate_candidates, select_episodes
from src.tactical_episodes.engine import PATTERN_TO_EPISODE_TYPE
from src.tactical_episodes.models import TacticalEpisode

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Synthetic-fixture helpers
# ---------------------------------------------------------------------------


def _pos(x: float, y: float) -> Position:
    return Position(x, y)


def _snapshot(tracking_id: str, x: float, y: float, is_teammate: bool = True, is_goalkeeper: bool = False) -> PlayerSnapshot:
    return PlayerSnapshot(tracking_id, "attack" if is_teammate else "defense", _pos(x, y), is_teammate, is_goalkeeper)


def _event(
    event_id: str,
    event_type: str,
    start: Position | None,
    end: Position | None,
    player_id: str | None,
    recipient_id: str | None = None,
    timestamp: float = 0.0,
    freeze_frame: list[PlayerSnapshot] | None = None,
) -> Event:
    return Event(event_id, event_type, timestamp, 1, "attack", player_id, start, end, recipient_id, None, freeze_frame or [], {})


def _possession(events: list[Event]) -> NormalizedPossession:
    return NormalizedPossession(1, "attack", "defense", events, 0.0, float(len(events)), "test", "synthetic")


def _finding(
    pattern_type: str,
    event_id: str,
    confidence: float = 0.8,
    feature_values: dict | None = None,
    actors: list[str] | None = None,
    receivers: list[str] | None = None,
) -> TacticalFinding:
    return TacticalFinding(
        finding_id=f"finding_{pattern_type}_{event_id}",
        pattern_type=pattern_type,
        event_id=event_id,
        confidence=confidence,
        evidence={"pattern": pattern_type, "feature_values": feature_values or {}},
        explanation_key=pattern_type,
        limitations=[],
        actors=actors or [],
        receivers=receivers or [],
    )


def _evaluate_one(possession: NormalizedPossession, finding: TacticalFinding, shot_event: Event | None = None):
    event_index = {event.event_id: idx for idx, event in enumerate(possession.events)}
    return evaluate_candidates(possession, [finding], PATTERN_TO_EPISODE_TYPE, event_index, shot_event)[0]


# ---------------------------------------------------------------------------
# Real-fixture datasets, built fresh through the public pipeline each run
# (mirrors tests/test_tactical_episodes.py's fixtures).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def depay_dataset():
    p = load_normalized_possession(ROOT / "data" / "depay_goal.json")
    findings = rank_findings(p, [*detect_line_breaking_passes(p, LineBreakConfig()), *detect_positional_patterns(p, PositionalPatternConfig())])
    return p, build_tactical_episodes(p, findings)


@pytest.fixture(scope="module")
def locatelli_dataset():
    p = load_normalized_possession(ROOT / "data" / "second_goal.json")
    findings = rank_findings(p, [*detect_line_breaking_passes(p, LineBreakConfig()), *detect_positional_patterns(p, PositionalPatternConfig())])
    return p, build_tactical_episodes(p, findings)


# ---------------------------------------------------------------------------
# 1-2: SWITCH_OF_PLAY semantic invariant
# ---------------------------------------------------------------------------


def test_switch_of_play_with_changed_side_false_is_ineligible():
    event = _event("e1", "Pass", _pos(20, 40), _pos(20, 70), "p1", "p2")
    possession = _possession([event])
    finding = _finding("switch_of_play", "e1", confidence=1.0, feature_values={"changed_side": False, "lateral_change": 30.0})
    evaluation = _evaluate_one(possession, finding)
    assert evaluation.semantic_valid is False
    assert any("SWITCH_OF_PLAY_NO_SIDE_CHANGE" in reason for reason in evaluation.semantic_validity_reasons)


def test_valid_changed_side_switch_remains_semantically_eligible():
    event = _event("e1", "Pass", _pos(20, 20), _pos(20, 60), "p1", "p2")
    possession = _possession([event])
    finding = _finding("switch_of_play", "e1", confidence=1.0, feature_values={"changed_side": True, "lateral_change": 40.0})
    evaluation = _evaluate_one(possession, finding)
    assert evaluation.semantic_valid is True
    assert evaluation.semantic_validity_reasons == []


# ---------------------------------------------------------------------------
# 3: Defensive-third goalkeeper circulation must not outrank a causally
#    grounded scoring episode, even at much lower raw confidence.
# ---------------------------------------------------------------------------


def test_goalkeeper_circulation_does_not_outrank_causally_grounded_scoring_episode():
    gk_event = _event(
        "e1", "Pass", _pos(20, 30), _pos(10, 40), "p1", "gk1",
        freeze_frame=[_snapshot("gk1", 10, 40, is_teammate=True, is_goalkeeper=True)],
    )
    cutback_event = _event("e2", "Pass", _pos(108, 68), _pos(105, 44), "p3", "p4", timestamp=10.0)
    shot = _event("e3", "Shot", _pos(105, 44), _pos(120, 40), "p4", timestamp=11.0)
    possession = _possession([gk_event, cutback_event, shot])

    isolation_finding = _finding("free_man_creation", "e1", confidence=1.0, actors=["p1"], receivers=["gk1"])
    cutback_finding = _finding(
        "cutback_candidate", "e2", confidence=0.6,
        feature_values={"backward_x": 3.0, "from_wide_zone": True, "target_central": True},
        actors=["p3"], receivers=["p4"],
    )

    dataset = build_tactical_episodes(possession, [isolation_finding, cutback_finding])
    types = [episode.episode_type for episode in dataset.episodes]
    assert "ISOLATION" not in types
    assert "CUTBACK" in types

    isolation_eval = next(c for c in dataset.candidate_evaluations if c.episode_type == "ISOLATION")
    assert isolation_eval.causal_relevant is False
    assert any("GOALKEEPER_ANCHORED" in reason for reason in isolation_eval.disqualification_reasons)


# ---------------------------------------------------------------------------
# 4: BOX_ARRIVAL must be able to outrank an unrelated higher-confidence
#    candidate that carries no causal relevance to the terminal shot.
# ---------------------------------------------------------------------------


def test_box_arrival_outranks_unrelated_higher_confidence_candidate():
    unrelated_event = _event("e1", "Pass", _pos(20, 20), _pos(25, 25), "p1", "p2")
    arrival_event = _event("e2", "Carry", _pos(90, 30), _pos(110, 40), "p3", timestamp=10.0)
    shot = _event("e3", "Shot", _pos(110, 40), _pos(120, 40), "p3", timestamp=11.0)
    possession = _possession([unrelated_event, arrival_event, shot])

    unrelated_finding = _finding("free_man_creation", "e1", confidence=1.0, actors=["p1"], receivers=["p2"])
    box_arrival_finding = _finding("box_arrival", "e2", confidence=0.75, actors=["p3"])

    dataset = build_tactical_episodes(possession, [unrelated_finding, box_arrival_finding])
    types = [episode.episode_type for episode in dataset.episodes]
    assert types == ["BUILDUP", "BOX_ARRIVAL", "FINISH"]

    unrelated_eval = next(c for c in dataset.candidate_evaluations if c.episode_type == "ISOLATION")
    assert unrelated_eval.causal_relevant is False
    assert unrelated_eval.detection_confidence > next(c for c in dataset.candidate_evaluations if c.episode_type == "BOX_ARRIVAL").detection_confidence


# ---------------------------------------------------------------------------
# 5: CUTBACK requires appropriate attacking context (grounded near goal),
#    not merely the raw wide-to-central-and-backward geometry.
# ---------------------------------------------------------------------------


def test_cutback_requires_appropriate_attacking_context():
    defensive_third_event = _event("e1", "Pass", _pos(30, 65), _pos(20, 40), "p1", "p2")
    possession = _possession([defensive_third_event])
    finding = _finding(
        "cutback_candidate", "e1", confidence=0.9,
        feature_values={"backward_x": 10.0, "from_wide_zone": True, "target_central": True},
    )
    evaluation = _evaluate_one(possession, finding)
    assert evaluation.semantic_valid is False
    assert any("CUTBACK_NOT_GROUNDED_IN_ATTACKING_THIRD" in reason for reason in evaluation.semantic_validity_reasons)

    final_third_event = _event("e1", "Pass", _pos(108, 68), _pos(105, 44), "p1", "p2")
    possession2 = _possession([final_third_event])
    finding2 = _finding(
        "cutback_candidate", "e1", confidence=0.64,
        feature_values={"backward_x": 3.8, "from_wide_zone": True, "target_central": True},
    )
    evaluation2 = _evaluate_one(possession2, finding2)
    assert evaluation2.semantic_valid is True


# ---------------------------------------------------------------------------
# 6: OFF_BALL_RUN requires supported movement and causal/narrative relevance.
# ---------------------------------------------------------------------------


def test_off_ball_run_requires_supported_movement():
    first_involvement = _event("e0", "Pass", _pos(30, 30), _pos(35, 32), "other", "p1", timestamp=0.0)
    reappearance = _event("e1", "Pass", _pos(50, 50), _pos(40, 34), "x", "p1", timestamp=20.0)
    possession = _possession([first_involvement, reappearance])
    finding = _finding(
        "late_support", "e1", confidence=1.0,
        feature_values={"events_since_first_involvement": 12, "first_involvement_event_id": "e0"},
    )
    evaluation = _evaluate_one(possession, finding)
    assert evaluation.semantic_valid is False
    assert any("OFF_BALL_RUN_NO_SUPPORTED_MOVEMENT" in reason for reason in evaluation.semantic_validity_reasons)


def test_off_ball_run_redundant_with_box_entry_is_ineligible():
    first_involvement = _event("e0", "Pass", _pos(30, 30), _pos(35, 32), "other", "p1", timestamp=0.0)
    reappearance = _event("e1", "Pass", _pos(90, 30), _pos(110, 40), "x", "p1", timestamp=20.0)
    possession = _possession([first_involvement, reappearance])
    finding = _finding(
        "late_support", "e1", confidence=1.0,
        feature_values={"events_since_first_involvement": 12, "first_involvement_event_id": "e0"},
    )
    evaluation = _evaluate_one(possession, finding)
    assert evaluation.semantic_valid is False
    assert any("OFF_BALL_RUN_REDUNDANT_WITH_BOX_ENTRY" in reason for reason in evaluation.semantic_validity_reasons)


# ---------------------------------------------------------------------------
# 7: Redundant candidates on the identical anchor event are deterministically
#    resolved to a single survivor, never both selected.
# ---------------------------------------------------------------------------


def test_redundant_same_event_candidates_are_deterministically_resolved():
    event = _event("e1", "Pass", _pos(108, 68), _pos(105, 44), "p1", "p2")
    shot = _event("e2", "Shot", _pos(105, 44), _pos(120, 40), "p2", timestamp=1.0)
    possession = _possession([event, shot])
    event_index = {"e1": 0, "e2": 1}

    cutback = _finding("cutback_candidate", "e1", confidence=0.64, feature_values={"backward_x": 3.8, "from_wide_zone": True, "target_central": True})
    box_arrival = _finding("box_arrival", "e1", confidence=0.9)

    evaluations = evaluate_candidates(possession, [cutback, box_arrival], PATTERN_TO_EPISODE_TYPE, event_index, shot)
    selected, all_evaluations = select_episodes(evaluations, event_index)

    assert len(selected) == 1
    assert selected[0].episode_type == "CUTBACK"
    box_arrival_eval = next(e for e in all_evaluations if e.episode_type == "BOX_ARRIVAL")
    assert box_arrival_eval.eligibility == "REJECTED"
    assert any("REDUNDANT_SAME_EVENT" in reason for reason in box_arrival_eval.disqualification_reasons)


# ---------------------------------------------------------------------------
# 8-12, 14-15: real-fixture regression coverage
# ---------------------------------------------------------------------------


def test_selector_may_return_fewer_than_max_finding_episodes(depay_dataset, locatelli_dataset):
    from src.tactical_episodes.engine import MAX_FINDING_EPISODES

    for _, dataset in (depay_dataset, locatelli_dataset):
        middle = [e for e in dataset.episodes if e.episode_type not in ("BUILDUP", "FINISH")]
        assert 0 < len(middle) < MAX_FINDING_EPISODES


def test_final_selected_episodes_are_chronological(depay_dataset, locatelli_dataset):
    for p, dataset in (depay_dataset, locatelli_dataset):
        index = {event.event_id: idx for idx, event in enumerate(p.events)}
        starts = [index[episode.start_event_id] for episode in dataset.episodes]
        assert starts == sorted(starts)


def test_finish_is_preserved_when_valid(depay_dataset, locatelli_dataset):
    for _, dataset in (depay_dataset, locatelli_dataset):
        assert dataset.episodes[-1].episode_type == "FINISH"
        assert dataset.episodes[-1].eligibility_verdict == "STRUCTURAL"


def test_depay_produces_audited_corrected_sequence(depay_dataset):
    _, dataset = depay_dataset
    assert [e.episode_type for e in dataset.episodes] == ["BUILDUP", "CUTBACK", "FINISH"]
    switch_candidates = [c for c in dataset.candidate_evaluations if c.episode_type == "SWITCH_OF_PLAY"]
    assert switch_candidates and all(c.eligibility != "SELECTED" for c in switch_candidates)
    false_side_change = [
        c for c in switch_candidates if any("SWITCH_OF_PLAY_NO_SIDE_CHANGE" in r for r in c.semantic_validity_reasons)
    ]
    assert false_side_change
    assert not any(c.episode_type == "OFF_BALL_RUN" and c.eligibility == "SELECTED" for c in dataset.candidate_evaluations)
    assert not any(c.episode_type == "ISOLATION" and c.eligibility == "SELECTED" for c in dataset.candidate_evaluations)


def test_locatelli_produces_audited_corrected_sequence(locatelli_dataset):
    _, dataset = locatelli_dataset
    assert [e.episode_type for e in dataset.episodes] == ["BUILDUP", "BOX_ARRIVAL", "FINISH"]


def test_di_maria_remains_rejected_upstream():
    open_data = ROOT / "data" / "open-data" / "data"
    match_id, possession_id = 3869685, 52
    request = {
        "source_dataset": "statsbomb-open-data",
        "source_revision": PINNED_REVISION,
        "match_id": match_id,
        "possession_id": possession_id,
    }
    import json

    events = json.loads((open_data / f"events/{match_id}.json").read_text())
    frames = json.loads((open_data / f"three-sixty/{match_id}.json").read_text())
    with pytest.raises(SourceSelectionError) as exc_info:
        select_source_documents(events, frames, request)
    assert str(exc_info.value) == "SRC_EVENT_INDEX_INVALID"


def test_candidate_audit_serialization_is_deterministic(depay_dataset):
    p, dataset = depay_dataset
    findings = rank_findings(p, [*detect_line_breaking_passes(p, LineBreakConfig()), *detect_positional_patterns(p, PositionalPatternConfig())])
    rebuilt = build_tactical_episodes(p, findings)
    first = [asdict(c) for c in dataset.candidate_evaluations]
    second = [asdict(c) for c in rebuilt.candidate_evaluations]
    assert first == second


def test_existing_valid_detector_outputs_remain_unchanged_before_evaluation():
    p = load_normalized_possession(ROOT / "data" / "depay_goal.json")
    findings = detect_cutback_candidates(p, PositionalPatternConfig())
    real_cutback = next(f for f in findings if abs(f.confidence - 0.64) < 1e-6)
    assert real_cutback.evidence["feature_values"]["backward_x"] == pytest.approx(3.8, abs=0.05)
    assert real_cutback.evidence["feature_values"]["from_wide_zone"] is True
    assert real_cutback.evidence["feature_values"]["target_central"] is True


# ---------------------------------------------------------------------------
# 16: backward-compatible rendering/caption interface -- old-style
# construction still works, additive fields carry sensible defaults, and
# asdict() still exposes every pre-existing key.
# ---------------------------------------------------------------------------


def test_tactical_episode_additive_fields_are_backward_compatible():
    episode = TacticalEpisode(
        episode_id="episode:x",
        episode_type="BUILDUP",
        start_event_id="e1",
        end_event_id="e2",
        participating_action_ids=["e1", "e2"],
        primary_actor_ids=["100"],
        relevant_defender_ids=[],
        tactical_question="q",
        cause="c",
        created_advantage="a",
        decisive_action="d",
        evidence={},
        confidence=1.0,
    )
    data = asdict(episode)
    pre_existing_keys = {
        "episode_id", "episode_type", "start_event_id", "end_event_id", "participating_action_ids",
        "primary_actor_ids", "relevant_defender_ids", "tactical_question", "cause", "created_advantage",
        "decisive_action", "evidence", "confidence", "limitations",
    }
    assert pre_existing_keys.issubset(data.keys())
    assert episode.eligibility_verdict == "STRUCTURAL"
    assert episode.selection_reasons == []
    assert episode.zone_context == {}
    assert episode.identity_resolution == {}
