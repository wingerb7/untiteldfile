from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.models import Event, NormalizedPossession, PlayerSnapshot, Position
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.patterns.positional import PositionalPatternConfig, detect_positional_patterns
from src.intelligence.reasoning.rank_findings import rank_findings
from src.ingest.possession_loader import load_normalized_possession
from src.tactical_episodes import EPISODE_TYPES, TacticalEpisodeError, build_tactical_episodes
from src.tactical_episodes.geometry import is_in_box, is_in_half_space, nearest_defender

ROOT = Path(__file__).resolve().parents[1]

# Algorithmic source files that must generalize across any possession: no fixture-,
# player-, or match-specific literals are allowed here (mirrors the existing
# test_narrative_window_code_has_no_possession_specific_hardcoding convention).
GENERIC_SOURCE_FILES = (
    ROOT / "src" / "tactical_episodes" / "engine.py",
    ROOT / "src" / "tactical_episodes" / "geometry.py",
    ROOT / "src" / "tactical_relevance" / "engine.py",
    ROOT / "src" / "scene_direction" / "engine.py",
    ROOT / "src" / "tactical_story" / "episodic_scene_plan.py",
)
FORBIDDEN_LITERALS = (
    "Depay", "Locatelli", "Memphis", "Manuel", "Netherlands", "Argentina", "Switzerland",
    "3869117", "3788754", "3869685",
    "2988", "7038", "3669", "7173",
)


def defender(x: float, y: float, keeper: bool = False, tracking_id: str | None = None) -> PlayerSnapshot:
    return PlayerSnapshot(tracking_id or f"d{x}-{y}", "defense", Position(x, y), False, keeper)


def attacker(x: float, y: float, tracking_id: str | None = None) -> PlayerSnapshot:
    return PlayerSnapshot(tracking_id or f"a{x}-{y}", "attack", Position(x, y), True, False)


def pass_event(event_id, start, end, defenders, teammates=None, timestamp=0.0, player_id="passer", recipient_id="receiver") -> Event:
    return Event(event_id, "Pass", timestamp, 1, "attack", player_id, start, end, recipient_id, None, [*(teammates or []), *defenders], {})


def carry_event(event_id, start, end, timestamp, player_id) -> Event:
    return Event(event_id, "Carry", timestamp, 1, "attack", player_id, start, end, None, None, [], {})


def shot_event(event_id, start, timestamp, player_id, defenders=None) -> Event:
    return Event(event_id, "Shot", timestamp, 1, "attack", player_id, start, Position(120, 40), None, None, defenders or [], {"xg": 0.3})


def possession(events: list[Event]) -> NormalizedPossession:
    return NormalizedPossession(1, "attack", "defense", events, 0.0, 1.0, "test", "1")


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


def test_geometry_helpers_are_pure_and_generic() -> None:
    assert is_in_box(Position(115, 40))
    assert not is_in_box(Position(60, 40))
    assert is_in_half_space(Position(60, 25))
    assert not is_in_half_space(Position(60, 40))
    defenders = [defender(10, 10), defender(14, 10)]
    nearest = nearest_defender(Position(10, 12), defenders)
    assert nearest is not None and nearest.tracking_id == defenders[0].tracking_id
    assert nearest_defender(Position(0, 0), []) is None


def test_events_do_not_convert_one_to_one_into_episodes(depay_dataset) -> None:
    p, dataset = depay_dataset
    assert len(dataset.episodes) < len(p.events)
    total_actions = sum(len(episode.participating_action_ids) for episode in dataset.episodes)
    assert total_actions == len(p.events)  # every event is accounted for, none dropped silently


def test_at_least_one_episode_groups_multiple_actions(depay_dataset, locatelli_dataset) -> None:
    for _, dataset in (depay_dataset, locatelli_dataset):
        assert any(len(episode.participating_action_ids) > 1 for episode in dataset.episodes)


def test_episode_types_are_within_the_generic_catalog(depay_dataset, locatelli_dataset) -> None:
    for _, dataset in (depay_dataset, locatelli_dataset):
        for episode in dataset.episodes:
            assert episode.episode_type in EPISODE_TYPES


def test_not_every_possession_requires_every_type(depay_dataset, locatelli_dataset) -> None:
    _, depay = depay_dataset
    _, locatelli = locatelli_dataset
    depay_types = {episode.episode_type for episode in depay.episodes}
    locatelli_types = {episode.episode_type for episode in locatelli.episodes}
    assert depay_types < set(EPISODE_TYPES)
    assert locatelli_types < set(EPISODE_TYPES)


def test_finish_episode_present_when_a_shot_exists(depay_dataset, locatelli_dataset) -> None:
    for _, dataset in (depay_dataset, locatelli_dataset):
        assert dataset.episodes[-1].episode_type == "FINISH"


def test_episodes_are_contiguous_and_non_overlapping(depay_dataset) -> None:
    p, dataset = depay_dataset
    index = {event.event_id: idx for idx, event in enumerate(p.events)}
    expected_next = 0
    for episode in dataset.episodes:
        start_idx = index[episode.start_event_id]
        end_idx = index[episode.end_event_id]
        assert start_idx == expected_next
        assert end_idx >= start_idx
        expected_next = end_idx + 1
    assert expected_next == len(p.events)


def test_no_more_than_max_finding_episodes_between_buildup_and_finish(depay_dataset, locatelli_dataset) -> None:
    from src.tactical_episodes.engine import MAX_FINDING_EPISODES

    for _, dataset in (depay_dataset, locatelli_dataset):
        middle = [e for e in dataset.episodes if e.episode_type not in ("BUILDUP", "FINISH")]
        assert len(middle) <= MAX_FINDING_EPISODES


def test_raises_on_empty_possession() -> None:
    with pytest.raises(TacticalEpisodeError):
        build_tactical_episodes(possession([]), [])


def test_line_break_synthetic_possession_produces_line_break_and_finish_episodes() -> None:
    defenders = [defender(70, 40), defender(75, 42)]
    events = [
        pass_event("e1", Position(20, 40), Position(40, 40), [], timestamp=0.0, player_id="p1", recipient_id="p2"),
        pass_event(
            "e2", Position(40, 40), Position(90, 40), defenders, timestamp=2.0, player_id="p2", recipient_id="p3"
        ),
        shot_event("e3", Position(105, 40), 4.0, "p3"),
    ]
    p = possession(events)
    findings = rank_findings(p, [*detect_line_breaking_passes(p, LineBreakConfig(minimum_confidence=0.0)), *detect_positional_patterns(p, PositionalPatternConfig())])
    dataset = build_tactical_episodes(p, findings)
    types = [episode.episode_type for episode in dataset.episodes]
    assert "FINISH" in types
    assert len(dataset.episodes) >= 2


@pytest.mark.parametrize("path", GENERIC_SOURCE_FILES)
def test_generic_engine_code_has_no_fixture_specific_hardcoding(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for literal in FORBIDDEN_LITERALS:
        assert literal not in text, f"{path.name} must not hardcode {literal!r}"
