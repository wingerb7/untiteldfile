from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isinf

from src.domain.enums import AttackingDirection
from src.domain.models import Event, NormalizedPossession, PlayerSnapshot
from src.intelligence.features.defensive_lines import estimate_line_break
from src.intelligence.features.progression import calculate_forward_progress, calculate_goal_distance_reduction
from src.intelligence.features.space import calculate_receiver_space


@dataclass(frozen=True)
class LineBreakConfig:
    attacking_direction: str = AttackingDirection.LEFT_TO_RIGHT.value
    minimum_forward_progress: float = 8.0
    minimum_goal_distance_reduction: float = 8.0
    minimum_defenders_bypassed: int = 2
    maximum_receiver_pressure_distance: float = 8.0
    minimum_confidence: float = 0.60


@dataclass(frozen=True)
class TacticalFinding:
    finding_id: str
    pattern_type: str
    event_id: str
    confidence: float
    evidence: dict
    explanation_key: str
    limitations: list[str]


def _defenders(event: Event) -> list[PlayerSnapshot]:
    return [player for player in event.freeze_frame if not player.is_teammate]


def _score(event: Event, config: LineBreakConfig) -> tuple[float, dict, list[str]]:
    limitations: list[str] = []
    if not event.start_position or not event.end_position:
        return 0.0, {"reason": "missing_pass_locations"}, limitations

    defenders = _defenders(event)
    line = estimate_line_break(event.start_position, event.end_position, defenders, config.attacking_direction)
    forward_progress = calculate_forward_progress(event.start_position, event.end_position, config.attacking_direction)
    goal_distance_reduction = calculate_goal_distance_reduction(event.start_position, event.end_position, config.attacking_direction)
    receiver_space = calculate_receiver_space(event.end_position, defenders)
    if not line.sufficient_data:
        limitations.append("Freeze-frame data is too sparse to estimate a defensive line reliably.")

    line_component = 1.0 if line.line_broken else 0.0
    bypass_component = min(1.0, line.defenders_bypassed / max(1, config.minimum_defenders_bypassed + 1))
    progression_component = min(1.0, max(0.0, forward_progress / max(0.1, config.minimum_forward_progress * 1.5)))
    receiver_component = 1.0 if line.end_side == "behind_line" else 0.0
    data_quality_component = 1.0 if line.sufficient_data else 0.0
    confidence = (
        0.30 * line_component
        + 0.25 * bypass_component
        + 0.20 * progression_component
        + 0.15 * receiver_component
        + 0.10 * data_quality_component
    )
    evidence = {
        "forward_progress": round(forward_progress, 3),
        "goal_distance_reduction": round(goal_distance_reduction, 3),
        "defenders_bypassed": line.defenders_bypassed,
        "receiver_space": None if isinf(receiver_space) else round(receiver_space, 3),
        "receiver_pressure_within_threshold": False
        if isinf(receiver_space)
        else receiver_space <= config.maximum_receiver_pressure_distance,
        "defensive_line_x": None if line.line_x is None else round(line.line_x, 3),
        "line_crossed": line.line_broken,
        "defensive_line": asdict(line),
        "confidence_components": {
            "line_crossed": line_component,
            "defenders_bypassed": round(bypass_component, 3),
            "progression": round(progression_component, 3),
            "receiver_position": receiver_component,
            "data_quality": data_quality_component,
        },
    }
    return round(max(0.0, min(1.0, confidence)), 3), evidence, limitations


def detect_line_breaking_passes(possession: NormalizedPossession, config: LineBreakConfig) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    for event in possession.events:
        if event.event_type != "Pass" or event.outcome:
            continue
        confidence, evidence, limitations = _score(event, config)
        if evidence.get("forward_progress", 0.0) < config.minimum_forward_progress:
            continue
        if evidence.get("goal_distance_reduction", 0.0) < config.minimum_goal_distance_reduction:
            continue
        if not evidence.get("line_crossed"):
            continue
        if evidence.get("defenders_bypassed", 0) < config.minimum_defenders_bypassed:
            continue
        findings.append(
            TacticalFinding(
                finding_id=f"finding_linebreak_{event.event_id}",
                pattern_type="line_breaking_pass",
                event_id=event.event_id,
                confidence=confidence,
                evidence=evidence,
                explanation_key="line_breaking_pass",
                limitations=limitations,
            )
        )
    return findings
