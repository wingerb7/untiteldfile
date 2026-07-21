from __future__ import annotations

from dataclasses import asdict, dataclass

from src.domain.models import Event, NormalizedPossession, PlayerSnapshot, TacticalFinding
from src.intelligence.features.circulation import ball_circulation_speed
from src.intelligence.features.geometry import PITCH_WIDTH, ball_side, opposite_side, players_on_side
from src.intelligence.features.overloads import estimate_local_overload
from src.intelligence.features.passing_lanes import estimate_passing_lane
from src.intelligence.features.receiver import estimate_receiver_freedom
from src.intelligence.features.support import count_support_options
from src.intelligence.features.width import estimate_width


@dataclass(frozen=True)
class PositionalPatternConfig:
    minimum_confidence: float = 0.55
    overload_radius: float = 12.0
    support_radius: float = 28.0
    switch_minimum_lateral_change: float = 32.0
    late_support_window_events: int = 4
    cutback_minimum_backward_x: float = 3.0


def _attackers(event: Event) -> list[PlayerSnapshot]:
    return [player for player in event.freeze_frame if player.is_teammate and not player.is_goalkeeper]


def _defenders(event: Event) -> list[PlayerSnapshot]:
    return [player for player in event.freeze_frame if not player.is_teammate and not player.is_goalkeeper]


def _pass_events(possession: NormalizedPossession) -> list[Event]:
    return [event for event in possession.events if event.event_type == "Pass" and not event.outcome]


def _ids(*values: str | None) -> list[str]:
    return [value for value in values if value]


def _make_finding(
    pattern_type: str,
    event: Event,
    confidence: float,
    evidence: dict,
    players: list[str],
    receivers: list[str] | None = None,
    enabled_by: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> TacticalFinding:
    return TacticalFinding(
        finding_id=f"finding_{pattern_type}_{event.event_id}",
        pattern_type=pattern_type,
        event_id=event.event_id,
        confidence=round(max(0.0, min(1.0, confidence)), 3),
        evidence=evidence,
        explanation_key=pattern_type,
        limitations=[],
        players_involved=players,
        feature_values=evidence.get("feature_values", {}),
        actors=[event.player_id] if event.player_id else [],
        receivers=receivers or ([event.recipient_id] if event.recipient_id else []),
        created_space_for=receivers or ([event.recipient_id] if event.recipient_id else []),
        enabled_by=enabled_by or [],
        depends_on=depends_on or [],
    )


def detect_width_creation(possession: NormalizedPossession, config: PositionalPatternConfig) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    for event in _pass_events(possession):
        if not event.end_position:
            continue
        attackers = _attackers(event)
        defenders = _defenders(event)
        width = estimate_width(event.end_position, attackers)
        support_options = count_support_options(
            event.start_position or event.end_position,
            attackers,
            defenders,
            maximum_distance=config.support_radius,
        )
        confidence = 0.45 * width.width_ratio + 0.35 * float(width.is_wide) + 0.20 * float(width.is_isolated_wide_player)
        if confidence < config.minimum_confidence:
            continue
        evidence = {
            "pattern": "width_creation",
            "feature_values": {
                "distance_to_touchline": width.distance_to_touchline,
                "team_width": width.team_width,
                "width_ratio": width.width_ratio,
                "isolated_wide_player": width.is_isolated_wide_player,
                "support_options": support_options,
            },
            "diagnostics": asdict(width),
        }
        findings.append(_make_finding("width_creation", event, confidence, evidence, _ids(event.player_id, event.recipient_id)))
    return findings


def detect_switches_of_play(possession: NormalizedPossession, config: PositionalPatternConfig) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    previous_pass: Event | None = None
    for event in _pass_events(possession):
        if not event.start_position or not event.end_position:
            previous_pass = event
            continue
        lateral_change = abs(event.end_position.y - event.start_position.y)
        changed_side = ball_side(event.start_position) != ball_side(event.end_position)
        speed = ball_circulation_speed(previous_pass, event)
        confidence = min(1.0, lateral_change / max(1.0, config.switch_minimum_lateral_change))
        if changed_side:
            confidence = min(1.0, confidence + 0.25)
        if confidence < config.minimum_confidence:
            previous_pass = event
            continue
        evidence = {
            "pattern": "switch_of_play",
            "feature_values": {
                "lateral_change": round(lateral_change, 3),
                "changed_side": changed_side,
                "ball_circulation_speed": speed,
            },
        }
        findings.append(
            _make_finding(
                "switch_of_play",
                event,
                confidence,
                evidence,
                _ids(event.player_id, event.recipient_id),
                depends_on=[previous_pass.event_id] if previous_pass else [],
            )
        )
        previous_pass = event
    return findings


def detect_third_man_combinations(possession: NormalizedPossession, config: PositionalPatternConfig) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    passes = _pass_events(possession)
    for first, second, third in zip(passes, passes[1:], passes[2:]):
        players = _ids(first.player_id, first.recipient_id, second.player_id, second.recipient_id, third.player_id, third.recipient_id)
        unique_players = set(players)
        if len(unique_players) < 3:
            continue
        if third.recipient_id and third.recipient_id == first.recipient_id:
            continue
        elapsed = third.timestamp - first.timestamp
        if elapsed < 0 or elapsed > 12.0:
            continue
        confidence = 0.65 if elapsed <= 8.0 else 0.55
        evidence = {
            "pattern": "third_man_combination",
            "feature_values": {
                "sequence_event_ids": [first.event_id, second.event_id, third.event_id],
                "unique_players": len(unique_players),
                "elapsed_seconds": round(elapsed, 3),
            },
        }
        findings.append(
            _make_finding(
                "third_man_combination",
                third,
                confidence,
                evidence,
                sorted(unique_players),
                depends_on=[first.event_id, second.event_id],
            )
        )
    return findings


def detect_free_man_creation(possession: NormalizedPossession, config: PositionalPatternConfig) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    for event in _pass_events(possession):
        if not event.start_position or not event.end_position:
            continue
        defenders = _defenders(event)
        lane = estimate_passing_lane(event.start_position, event.end_position, defenders)
        freedom = estimate_receiver_freedom(event.end_position, defenders, lane)
        if not freedom.is_free:
            continue
        confidence = 0.5 * freedom.freedom + 0.5 * lane.openness
        evidence = {
            "pattern": "free_man_creation",
            "feature_values": {
                "receiver_freedom": freedom.freedom,
                "nearest_defender_distance": freedom.nearest_defender_distance,
                "lane_openness": lane.openness,
                "defenders_in_lane": lane.defenders_in_lane,
            },
            "diagnostics": {"lane": asdict(lane), "receiver": asdict(freedom)},
        }
        findings.append(_make_finding("free_man_creation", event, confidence, evidence, _ids(event.player_id, event.recipient_id)))
    return findings


def detect_cutback_candidates(possession: NormalizedPossession, config: PositionalPatternConfig) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    for event in _pass_events(possession):
        if not event.start_position or not event.end_position:
            continue
        backward = event.start_position.x - event.end_position.x
        from_wide_zone = abs(event.start_position.y - PITCH_WIDTH / 2) >= 22.0
        target_central = abs(event.end_position.y - PITCH_WIDTH / 2) <= 16.0
        if backward < config.cutback_minimum_backward_x or not from_wide_zone or not target_central:
            continue
        confidence = min(1.0, 0.45 + backward / 20.0)
        evidence = {
            "pattern": "cutback_candidate",
            "feature_values": {
                "backward_x": round(backward, 3),
                "from_wide_zone": from_wide_zone,
                "target_central": target_central,
            },
        }
        findings.append(_make_finding("cutback_candidate", event, confidence, evidence, _ids(event.player_id, event.recipient_id)))
    return findings


def detect_late_support(possession: NormalizedPossession, config: PositionalPatternConfig) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    seen: dict[str, int] = {}
    for idx, event in enumerate(possession.events):
        if event.player_id:
            seen.setdefault(event.player_id, idx)
        if event.event_type != "Pass" or event.outcome or not event.recipient_id:
            continue
        first_seen = seen.get(event.recipient_id)
        if first_seen is None:
            seen[event.recipient_id] = idx
            continue
        if idx - first_seen <= config.late_support_window_events:
            continue
        confidence = min(1.0, 0.45 + (idx - first_seen) / 20.0)
        if confidence < config.minimum_confidence:
            continue
        evidence = {
            "pattern": "late_support",
            "feature_values": {
                "events_since_first_involvement": idx - first_seen,
                "first_involvement_event_id": possession.events[first_seen].event_id,
            },
        }
        findings.append(
            _make_finding(
                "late_support",
                event,
                confidence,
                evidence,
                _ids(event.player_id, event.recipient_id),
                depends_on=[possession.events[first_seen].event_id],
            )
        )
    return findings


def detect_ball_side_overloads(possession: NormalizedPossession, config: PositionalPatternConfig) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    for event in _pass_events(possession):
        if not event.start_position:
            continue
        attackers = _attackers(event)
        defenders = _defenders(event)
        overload = estimate_local_overload(event.start_position, attackers, defenders, radius=config.overload_radius)
        side = ball_side(event.start_position)
        ball_side_attackers = len(players_on_side(attackers, side))
        ball_side_defenders = len(players_on_side(defenders, side))
        weak_side_defenders = len(players_on_side(defenders, opposite_side(side)))
        if not overload.has_overload and ball_side_attackers <= ball_side_defenders:
            continue
        confidence = min(1.0, 0.45 + max(overload.margin, ball_side_attackers - ball_side_defenders) / 4.0)
        if confidence < config.minimum_confidence:
            continue
        evidence = {
            "pattern": "ball_side_overload",
            "feature_values": {
                "local_attackers": overload.attackers,
                "local_defenders": overload.defenders,
                "local_margin": overload.margin,
                "ball_side_attackers": ball_side_attackers,
                "ball_side_defenders": ball_side_defenders,
                "weak_side_defenders": weak_side_defenders,
            },
            "diagnostics": asdict(overload),
        }
        findings.append(_make_finding("ball_side_overload", event, confidence, evidence, _ids(event.player_id, event.recipient_id)))
    return findings


def detect_positional_patterns(
    possession: NormalizedPossession,
    config: PositionalPatternConfig | None = None,
) -> list[TacticalFinding]:
    resolved = config or PositionalPatternConfig()
    detectors = [
        detect_width_creation,
        detect_switches_of_play,
        detect_third_man_combinations,
        detect_free_man_creation,
        detect_cutback_candidates,
        detect_late_support,
        detect_ball_side_overloads,
    ]
    findings: list[TacticalFinding] = []
    for detector in detectors:
        findings.extend(detector(possession, resolved))
    return findings
