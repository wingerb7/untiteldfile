from __future__ import annotations

from src.domain.models import Event, NormalizedPossession, PlayerSnapshot, Position
from src.intelligence.features.defensive_lines import estimate_line_break
from src.intelligence.features.pressure import count_defenders_within_radius, nearest_defender_distance
from src.intelligence.features.progression import calculate_forward_progress, calculate_goal_distance_reduction
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.reasoning.rank_findings import rank_findings
from src.intelligence.scene_builder import build_scene_plan


def defender(x: float, y: float, keeper: bool = False) -> PlayerSnapshot:
    return PlayerSnapshot(f"d{x}-{y}", "defense", Position(x, y), False, keeper)


def pass_event(event_id: str, start: Position, end: Position, defenders: list[PlayerSnapshot]) -> Event:
    return Event(event_id, "Pass", 0.0, 52, "attack", "passer", start, end, None, None, defenders, {})


def possession(events: list[Event]) -> NormalizedPossession:
    return NormalizedPossession(52, "attack", "defense", events, 0.0, 1.0, "test", "match")


def test_forward_progress_and_goal_distance_reduction() -> None:
    assert calculate_forward_progress(Position(20, 40), Position(35, 40), "left_to_right") == 15
    assert calculate_forward_progress(Position(35, 40), Position(20, 40), "right_to_left") == 15
    assert calculate_goal_distance_reduction(Position(20, 40), Position(35, 40), "left_to_right") == 15


def test_pressure_features() -> None:
    defenders = [defender(10, 10), defender(14, 10), defender(30, 30)]
    assert count_defenders_within_radius(Position(10, 12), defenders, 5) == 2
    assert nearest_defender_distance(Position(10, 12), defenders) == 2


def test_defensive_line_crossed() -> None:
    defenders = [defender(50, 25), defender(51, 40), defender(52, 55), defender(70, 40)]
    evidence = estimate_line_break(Position(40, 40), Position(65, 40), defenders, "left_to_right")
    assert evidence.sufficient_data is True
    assert evidence.line_broken is True
    assert evidence.defenders_bypassed == 3


def test_defensive_line_not_crossed() -> None:
    defenders = [defender(50, 25), defender(51, 40), defender(52, 55)]
    evidence = estimate_line_break(Position(40, 40), Position(48, 40), defenders, "left_to_right")
    assert evidence.sufficient_data is True
    assert evidence.line_broken is False


def test_defensive_line_insufficient_data() -> None:
    evidence = estimate_line_break(Position(40, 40), Position(65, 40), [defender(50, 40)], "left_to_right")
    assert evidence.sufficient_data is False
    assert evidence.reason == "insufficient_defenders"


def test_line_break_detection_and_confidence_bounds() -> None:
    event = pass_event(
        "event_1",
        Position(40, 40),
        Position(65, 40),
        [defender(50, 25), defender(51, 40), defender(52, 55), defender(70, 40)],
    )
    findings = detect_line_breaking_passes(possession([event]), LineBreakConfig())
    assert len(findings) == 1
    assert 0.0 <= findings[0].confidence <= 1.0
    assert findings[0].evidence["line_crossed"] is True


def test_progressive_pass_without_line_crossing_is_not_finding() -> None:
    event = pass_event("event_1", Position(40, 40), Position(65, 40), [defender(70, 25), defender(71, 40)])
    assert detect_line_breaking_passes(possession([event]), LineBreakConfig()) == []


def test_scene_plan_generation() -> None:
    event = pass_event(
        "event_1",
        Position(40, 40),
        Position(65, 40),
        [defender(50, 25), defender(51, 40), defender(52, 55)],
    )
    finding = detect_line_breaking_passes(possession([event]), LineBreakConfig())[0]
    plan = build_scene_plan(possession([event]), finding, "Caption")
    assert plan["selected_finding_id"] == finding.finding_id
    assert plan["scenes"][1]["type"] == "tactical_pause"
    assert any(item["type"] == "draw_defensive_line" for item in plan["scenes"][1]["instructions"])


def test_no_reliable_analysis_selection() -> None:
    event = pass_event("event_1", Position(40, 40), Position(47, 40), [defender(50, 25), defender(51, 40)])
    findings = rank_findings(possession([event]), detect_line_breaking_passes(possession([event]), LineBreakConfig()))
    selected = next((finding for finding in findings if finding.confidence >= LineBreakConfig().minimum_confidence), None)
    assert selected is None
