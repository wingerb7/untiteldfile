from __future__ import annotations

from src.domain.models import Event, NormalizedPossession, PlayerSnapshot, Position
from src.intelligence.features.overloads import estimate_local_overload
from src.intelligence.features.passing_lanes import estimate_passing_lane
from src.intelligence.features.receiver import estimate_receiver_freedom
from src.intelligence.features.width import estimate_width
from src.intelligence.features.defensive_lines import estimate_line_break
from src.intelligence.features.pressure import count_defenders_within_radius, nearest_defender_distance
from src.intelligence.features.progression import calculate_forward_progress, calculate_goal_distance_reduction
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.patterns.positional import PositionalPatternConfig, detect_positional_patterns
from src.intelligence.reasoning.build_causal_chain import build_causal_chain
from src.intelligence.reasoning.rank_findings import rank_findings
from src.intelligence.scene_builder import build_scene_plan


def defender(x: float, y: float, keeper: bool = False) -> PlayerSnapshot:
    return PlayerSnapshot(f"d{x}-{y}", "defense", Position(x, y), False, keeper)


def attacker(x: float, y: float, tracking_id: str | None = None) -> PlayerSnapshot:
    return PlayerSnapshot(tracking_id or f"a{x}-{y}", "attack", Position(x, y), True, False)


def pass_event(
    event_id: str,
    start: Position,
    end: Position,
    defenders: list[PlayerSnapshot],
    teammates: list[PlayerSnapshot] | None = None,
    timestamp: float = 0.0,
    player_id: str = "passer",
    recipient_id: str | None = "receiver",
) -> Event:
    return Event(
        event_id,
        "Pass",
        timestamp,
        52,
        "attack",
        player_id,
        start,
        end,
        recipient_id,
        None,
        [*(teammates or []), *defenders],
        {},
    )


def carry_event(
    event_id: str,
    start: Position,
    end: Position,
    timestamp: float,
    player_id: str,
) -> Event:
    return Event(event_id, "Carry", timestamp, 52, "attack", player_id, start, end, None, None, [], {})


def shot_event(event_id: str, start: Position, timestamp: float, player_id: str) -> Event:
    return Event(event_id, "Shot", timestamp, 52, "attack", player_id, start, Position(120, 40), None, None, [], {"xg": 0.4})


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


def test_generic_spatial_features_are_deterministic() -> None:
    teammates = [attacker(40, 5, "wide"), attacker(42, 38), attacker(50, 72)]
    defenders = [defender(55, 40), defender(70, 40)]
    width = estimate_width(Position(40, 5), teammates)
    lane = estimate_passing_lane(Position(40, 5), Position(70, 40), defenders)
    freedom = estimate_receiver_freedom(Position(70, 40), defenders, lane)
    overload = estimate_local_overload(Position(42, 38), teammates, defenders, radius=34)
    assert width.is_wide is True
    assert width.team_width == 67
    assert lane.defenders_in_lane >= 1
    assert 0.0 <= freedom.freedom <= 1.0
    assert overload.attackers == 2


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
    assert findings[0].actors == ["passer"]
    assert findings[0].receivers == ["receiver"]


def test_progressive_pass_without_line_crossing_is_not_finding() -> None:
    event = pass_event("event_1", Position(40, 40), Position(65, 40), [defender(70, 25), defender(71, 40)])
    assert detect_line_breaking_passes(possession([event]), LineBreakConfig()) == []


def test_positional_patterns_emit_graph_ready_findings() -> None:
    teammates = [attacker(40, 6, "wide"), attacker(48, 38, "central"), attacker(50, 74, "weak")]
    defenders = [defender(62, 40), defender(70, 45)]
    event = pass_event(
        "event_width",
        Position(35, 38),
        Position(40, 6),
        defenders,
        teammates=teammates,
        player_id="central",
        recipient_id="wide",
    )
    findings = detect_positional_patterns(possession([event]), PositionalPatternConfig(minimum_confidence=0.5))
    width = next(finding for finding in findings if finding.pattern_type == "width_creation")
    free_man = next(finding for finding in findings if finding.pattern_type == "free_man_creation")
    assert width.players_involved == ["central", "wide"]
    assert width.created_space_for == ["wide"]
    assert "team_width" in width.feature_values
    assert free_man.receivers == ["wide"]


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


def test_causal_chain_links_progressive_pass_wide_carry_return_and_finish() -> None:
    line_break = pass_event(
        "line_break",
        Position(46, 40),
        Position(74, 78),
        [defender(50, 25), defender(51, 40), defender(52, 55)],
        timestamp=1.0,
        player_id="original_passer",
        recipient_id="wide_receiver",
    )
    carry = carry_event("wide_carry", Position(74, 78), Position(116, 56), 4.0, "wide_receiver")
    return_pass = pass_event(
        "return",
        Position(116, 56),
        Position(114, 40),
        [defender(110, 42), defender(112, 50), defender(118, 38)],
        timestamp=10.0,
        player_id="wide_receiver",
        recipient_id="original_passer",
    )
    shot = shot_event("shot", Position(115, 40), 10.5, "original_passer")
    poss = possession([line_break, carry, return_pass, shot])
    finding = detect_line_breaking_passes(poss, LineBreakConfig())[0]

    chain = build_causal_chain(poss, [finding], finding)

    assert chain is not None
    assert [step.step_type for step in chain.steps] == ["line_break", "wide_carry", "return_pass", "finish"]
    assert chain.evidence["relations"]["passer_becomes_later_receiver"] is True
    assert chain.evidence["relations"]["shot_by_original_passer"] is True
    assert "continued run" in chain.steps[2].caption


def test_no_reliable_analysis_selection() -> None:
    event = pass_event("event_1", Position(40, 40), Position(47, 40), [defender(50, 25), defender(51, 40)])
    findings = rank_findings(possession([event]), detect_line_breaking_passes(possession([event]), LineBreakConfig()))
    selected = next((finding for finding in findings if finding.confidence >= LineBreakConfig().minimum_confidence), None)
    assert selected is None
