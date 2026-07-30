from __future__ import annotations

from pathlib import Path

from src.domain.models import Event, NormalizedPossession, PlayerSnapshot, Position
from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.patterns.positional import PositionalPatternConfig, detect_positional_patterns
from src.intelligence.reasoning.rank_findings import rank_findings
from src.tactical_episodes import build_tactical_episodes
from src.tactical_relevance import DEFENSIVE_CONTEXT, MANDATORY, MAXIMUM_CONTEXT_PLAYERS, STRUCTURAL_CONTEXT, classify_episode_players

ROOT = Path(__file__).resolve().parents[1]


def _episodes_for(path: Path) -> tuple[NormalizedPossession, list]:
    p = load_normalized_possession(path)
    findings = rank_findings(p, [*detect_line_breaking_passes(p, LineBreakConfig()), *detect_positional_patterns(p, PositionalPatternConfig())])
    return p, build_tactical_episodes(p, findings).episodes


def test_every_record_has_required_fields_populated() -> None:
    possession, episodes = _episodes_for(ROOT / "data" / "depay_goal.json")
    for episode in episodes:
        for record in classify_episode_players(possession, episode):
            assert record.player_id
            assert record.category in (MANDATORY, DEFENSIVE_CONTEXT, STRUCTURAL_CONTEXT)
            assert record.reason
            assert record.episode_id == episode.episode_id
            assert 0.0 <= record.relevance_score <= 1.0
            assert isinstance(record.evidence, dict)
            assert 0.0 <= record.confidence <= 1.0


def test_never_renders_every_player_on_the_pitch() -> None:
    possession, episodes = _episodes_for(ROOT / "data" / "depay_goal.json")
    events_by_id = {event.event_id: event for event in possession.events}
    for episode in episodes:
        records = classify_episode_players(possession, episode)
        anchor = events_by_id[episode.participating_action_ids[-1]]
        on_pitch = len(anchor.freeze_frame)
        assert len(records) <= MAXIMUM_CONTEXT_PLAYERS + 5  # mandatory (small) + bounded context
        if on_pitch > 4:
            assert len(records) < on_pitch  # some opponents are always omittable


def test_relevant_defenders_remain_selected_when_they_define_the_problem() -> None:
    defenders = [PlayerSnapshot("near", "defense", Position(41, 40), False, False), PlayerSnapshot("far", "defense", Position(5, 5), False, False)]
    events = [
        Event("e1", "Pass", 0.0, 1, "attack", "passer", Position(20, 40), Position(40, 40), "receiver", None, defenders, {}),
        Event("e2", "Shot", 1.0, 1, "attack", "receiver", Position(105, 40), Position(120, 40), None, None, defenders, {"xg": 0.3}),
    ]
    possession = NormalizedPossession(1, "attack", "defense", events, 0.0, 1.0, "test", "1")
    findings = rank_findings(possession, [*detect_line_breaking_passes(possession, LineBreakConfig()), *detect_positional_patterns(possession, PositionalPatternConfig())])
    dataset = build_tactical_episodes(possession, findings)
    episode = next(e for e in dataset.episodes if "e1" in e.participating_action_ids)
    records = classify_episode_players(possession, episode)
    defensive_ids = {record.player_id for record in records if record.category == DEFENSIVE_CONTEXT}
    assert "near" in defensive_ids
    assert "far" not in defensive_ids  # the nearby defender defines the problem, the distant one doesn't


def test_unrelated_opponents_may_be_omitted_for_locatelli() -> None:
    possession, episodes = _episodes_for(ROOT / "data" / "second_goal.json")
    events_by_id = {event.event_id: event for event in possession.events}
    omitted_somewhere = False
    for episode in episodes:
        records = classify_episode_players(possession, episode)
        anchor = events_by_id[episode.participating_action_ids[-1]]
        opponents_on_pitch = {p.tracking_id for p in anchor.freeze_frame if not p.is_teammate}
        selected_opponents = {r.player_id for r in records if r.category != MANDATORY}
        if opponents_on_pitch - selected_opponents:
            omitted_somewhere = True
    assert omitted_somewhere
