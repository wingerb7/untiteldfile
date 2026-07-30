from __future__ import annotations

from pathlib import Path

from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.patterns.positional import PositionalPatternConfig, detect_positional_patterns
from src.intelligence.reasoning.rank_findings import rank_findings
from src.scene_direction import ALL_OVERLAY_TYPES, build_scene_direction
from src.tactical_episodes import build_tactical_episodes
from src.tactical_relevance import classify_episode_players

ROOT = Path(__file__).resolve().parents[1]


def _directions_for(path: Path):
    possession = load_normalized_possession(path)
    findings = rank_findings(
        possession,
        [*detect_line_breaking_passes(possession, LineBreakConfig()), *detect_positional_patterns(possession, PositionalPatternConfig())],
    )
    dataset = build_tactical_episodes(possession, findings)
    directions = []
    for episode in dataset.episodes:
        records = classify_episode_players(possession, episode)
        directions.append(build_scene_direction(possession, episode, records))
    return directions


def test_every_scene_has_exactly_one_primary_message() -> None:
    for direction in _directions_for(ROOT / "data" / "depay_goal.json"):
        assert direction.primary_message
        assert direction.caption_intent
        assert direction.visual_budget["captions"] == 1


def test_visual_budget_cannot_be_exceeded() -> None:
    for direction in _directions_for(ROOT / "data" / "second_goal.json"):
        assert direction.visual_budget["primary_overlays"] in (0, 1)
        assert direction.visual_budget["secondary_overlays"] in (0, 1)
        chosen = [overlay for overlay in (direction.primary_overlay, direction.secondary_overlay) if overlay]
        assert len(chosen) <= 2
        assert len(chosen) == len(set(chosen))  # never the same overlay type twice


def test_forbidden_overlays_complement_the_chosen_ones() -> None:
    for direction in _directions_for(ROOT / "data" / "depay_goal.json"):
        chosen = {overlay for overlay in (direction.primary_overlay, direction.secondary_overlay) if overlay}
        assert chosen.isdisjoint(direction.forbidden_overlays)
        assert chosen | set(direction.forbidden_overlays) == set(ALL_OVERLAY_TYPES)


def test_visible_and_hidden_players_never_overlap() -> None:
    for direction in _directions_for(ROOT / "data" / "second_goal.json"):
        assert set(direction.visible_players).isdisjoint(direction.hidden_players)


def test_highlighted_players_are_a_subset_of_visible_players() -> None:
    for direction in _directions_for(ROOT / "data" / "depay_goal.json"):
        assert set(direction.highlighted_players).issubset(direction.visible_players)
