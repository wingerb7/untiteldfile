from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Any

from src.domain.enums import AttackingDirection
from src.domain.models import Event, NormalizedPossession, PlayerSnapshot, TacticalFinding
from src.identity_bridge import resolve_identity
from src.intelligence.features.geometry import distance
from src.intelligence.features.progression import calculate_forward_progress

from .eligibility import evaluate_candidates, select_episodes
from .errors import TacticalEpisodeError
from .geometry import PRESS_DISTANCE_M, is_in_box, is_in_half_space, nearest_defender
from .models import TacticalEpisode, TacticalEpisodeDataset

# Left-to-right attacking goal, matching the pitch convention used throughout
# this pipeline (src/intelligence/features/progression.py::GOAL_X).
ATTACKING_GOAL_X = 120.0

EPISODE_TYPES = (
    "BUILDUP",
    "PRESS_ESCAPE",
    "LINE_BREAK",
    "THIRD_MAN_COMBINATION",
    "WIDE_PROGRESSION",
    "OVERLOAD",
    "ISOLATION",
    "SWITCH_OF_PLAY",
    "HALF_SPACE_ENTRY",
    "OFF_BALL_RUN",
    "CUTBACK",
    "BOX_ARRIVAL",
    "FINISH",
)

# Maximum number of finding-derived episodes between BUILDUP and FINISH, so a
# possession is always explained by a small number of ideas, never one per event.
MAX_FINDING_EPISODES = 4

PATTERN_TO_EPISODE_TYPE = {
    "line_breaking_pass": "LINE_BREAK",
    "width_creation": "WIDE_PROGRESSION",
    "switch_of_play": "SWITCH_OF_PLAY",
    "third_man_combination": "THIRD_MAN_COMBINATION",
    "free_man_creation": "ISOLATION",
    "cutback_candidate": "CUTBACK",
    "late_support": "OFF_BALL_RUN",
    "ball_side_overload": "OVERLOAD",
    "press_escape": "PRESS_ESCAPE",
    "half_space_entry": "HALF_SPACE_ENTRY",
    "box_arrival": "BOX_ARRIVAL",
}

_TEMPLATES: dict[str, dict[str, str]] = {
    "BUILDUP": {
        "tactical_question": "How does the team progress the ball before the decisive sequence begins?",
        "cause": "Patient circulation probes the opponent's shape without yet breaking it.",
        "created_advantage": "Sets the platform for the sequence that follows.",
        "decisive_action": "Circulation before the first identified tactical opportunity.",
    },
    "PRESS_ESCAPE": {
        "tactical_question": "How does the player under pressure keep the move alive?",
        "cause": "An opponent closes down the ball carrier before the action is played.",
        "created_advantage": "Escaping the press keeps possession advancing instead of being turned over.",
        "decisive_action": "The pass or carry away from the nearest presser.",
    },
    "LINE_BREAK": {
        "tactical_question": "How does the pass get in behind the defensive line?",
        "cause": "A pass is played through or beyond a line of defenders.",
        "created_advantage": "Bypasses defenders and reduces the distance to goal.",
        "decisive_action": "The line-breaking pass.",
    },
    "THIRD_MAN_COMBINATION": {
        "tactical_question": "How does a third player unlock the defense?",
        "cause": "A short exchange draws defenders before the ball reaches an unmarked third player.",
        "created_advantage": "The third player receives in the space the first two actions created.",
        "decisive_action": "The third-man combination.",
    },
    "WIDE_PROGRESSION": {
        "tactical_question": "How does width stretch the defense?",
        "cause": "An attacker occupies a wide area with few nearby defenders.",
        "created_advantage": "Stretches the defensive shape and opens space centrally.",
        "decisive_action": "The pass into the wide attacker.",
    },
    "OVERLOAD": {
        "tactical_question": "How does the team gain a numbers advantage?",
        "cause": "More attackers than defenders operate in the same area of the pitch.",
        "created_advantage": "The extra attacker cannot be marked, forcing a defensive choice.",
        "decisive_action": "The pass exploiting the local numbers advantage.",
    },
    "ISOLATION": {
        "tactical_question": "How does the receiver find time and space on the ball?",
        "cause": "The receiver is found with no defender positioned to immediately close them down.",
        "created_advantage": "Time on the ball to progress the attack unopposed.",
        "decisive_action": "The pass into the free player.",
    },
    "SWITCH_OF_PLAY": {
        "tactical_question": "How does switching sides unbalance the defense?",
        "cause": "The ball is moved quickly from one side of the pitch to the other.",
        "created_advantage": "Defenders must shift across the pitch before they can press again.",
        "decisive_action": "The switch of play.",
    },
    "HALF_SPACE_ENTRY": {
        "tactical_question": "How does the attack enter the dangerous half-space?",
        "cause": "The ball is moved into the channel between the widest and most central defenders.",
        "created_advantage": "Access to a shooting or cutback angle a purely wide or central position lacks.",
        "decisive_action": "The entry into the half-space.",
    },
    "OFF_BALL_RUN": {
        "tactical_question": "How does a supporting run reappear at the right moment?",
        "cause": "A player already involved earlier reappears further forward without the ball.",
        "created_advantage": "Provides a fresh passing option the defense has to re-track.",
        "decisive_action": "The pass to the player arriving late.",
    },
    "CUTBACK": {
        "tactical_question": "How does the cutback create a clearer scoring angle?",
        "cause": "The ball is played backward from a wide advanced position into a central area.",
        "created_advantage": "Creates a more central, lower-angle opportunity than continuing forward.",
        "decisive_action": "The cutback pass.",
    },
    "BOX_ARRIVAL": {
        "tactical_question": "How does the ball reach the penalty area?",
        "cause": "The ball or ball carrier enters the penalty box.",
        "created_advantage": "Immediate proximity to goal increases the chance of a shot.",
        "decisive_action": "The action that brings the ball into the box.",
    },
    "FINISH": {
        "tactical_question": "How does the scorer become available to finish?",
        "cause": "The build-up concludes with a shot.",
        "created_advantage": "Converts the created space and time into an attempt on goal.",
        "decisive_action": "The shot.",
    },
}

_RECONSTRUCTED_DEFENDER_LIMITATION = (
    "relevant_defender_ids reference reconstructed per-event freeze-frame snapshots; "
    "opposing player identity is not persistent across events in this source data."
)


def _identifier(*parts: str) -> str:
    return f"episode:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:16]}"


def _defenders(event: Event) -> list[PlayerSnapshot]:
    return [player for player in event.freeze_frame if not player.is_teammate and not player.is_goalkeeper]


def _detect_press_escape(possession: NormalizedPossession) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    for event in possession.events:
        if event.event_type not in ("Pass", "Carry") or not event.start_position or not event.end_position:
            continue
        presser = nearest_defender(event.start_position, _defenders(event))
        if presser is None:
            continue
        press_distance = distance(event.start_position, presser.position)
        if press_distance > PRESS_DISTANCE_M:
            continue
        progress = calculate_forward_progress(event.start_position, event.end_position, AttackingDirection.LEFT_TO_RIGHT.value)
        if progress <= 3.0:
            continue
        confidence = round(
            min(1.0, 0.5 + (PRESS_DISTANCE_M - press_distance) / PRESS_DISTANCE_M * 0.3 + min(progress, 15.0) / 15.0 * 0.2),
            3,
        )
        findings.append(
            TacticalFinding(
                finding_id=f"finding_press_escape_{event.event_id}",
                pattern_type="press_escape",
                event_id=event.event_id,
                confidence=confidence,
                evidence={
                    "pattern": "press_escape",
                    "feature_values": {"press_distance_m": round(press_distance, 3), "forward_progress": round(progress, 3)},
                },
                explanation_key="press_escape",
                limitations=[],
                players_involved=[p for p in (event.player_id, event.recipient_id) if p],
                actors=[event.player_id] if event.player_id else [],
                receivers=[event.recipient_id] if event.recipient_id else [],
            )
        )
    return findings


def _detect_half_space_entry(possession: NormalizedPossession) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    for event in possession.events:
        if event.event_type not in ("Pass", "Carry") or not event.end_position:
            continue
        if not is_in_half_space(event.end_position):
            continue
        if event.start_position and is_in_half_space(event.start_position):
            continue
        nearest = nearest_defender(event.end_position, _defenders(event))
        nearest_distance = distance(event.end_position, nearest.position) if nearest else None
        confidence = 0.55 if nearest_distance is None else round(min(1.0, 0.4 + min(nearest_distance, 10.0) / 10.0 * 0.4), 3)
        findings.append(
            TacticalFinding(
                finding_id=f"finding_half_space_entry_{event.event_id}",
                pattern_type="half_space_entry",
                event_id=event.event_id,
                confidence=confidence,
                evidence={
                    "pattern": "half_space_entry",
                    "feature_values": {"nearest_defender_distance": None if nearest_distance is None else round(nearest_distance, 3)},
                },
                explanation_key="half_space_entry",
                limitations=[],
                players_involved=[p for p in (event.player_id, event.recipient_id) if p],
                actors=[event.player_id] if event.player_id else [],
                receivers=[event.recipient_id] if event.recipient_id else [],
            )
        )
    return findings


def _detect_box_arrival(possession: NormalizedPossession) -> list[TacticalFinding]:
    findings: list[TacticalFinding] = []
    for event in possession.events:
        if event.event_type not in ("Pass", "Carry", "Ball Receipt*") or not event.end_position:
            continue
        if not is_in_box(event.end_position):
            continue
        if event.start_position and is_in_box(event.start_position):
            continue
        findings.append(
            TacticalFinding(
                finding_id=f"finding_box_arrival_{event.event_id}",
                pattern_type="box_arrival",
                event_id=event.event_id,
                confidence=0.75,
                evidence={"pattern": "box_arrival", "feature_values": {}},
                explanation_key="box_arrival",
                limitations=[],
                players_involved=[p for p in (event.player_id, event.recipient_id) if p],
                actors=[event.player_id] if event.player_id else [],
                receivers=[event.recipient_id] if event.recipient_id else [],
            )
        )
    return findings


def _identity_resolution_map(player_ids: list[str]) -> dict[str, str]:
    return {player_id: resolve_identity(player_id).state.value for player_id in player_ids}


def _build_episode(
    episode_type: str,
    start_event_id: str,
    end_event_id: str,
    participating_action_ids: list[str],
    primary_actor_ids: list[str],
    relevant_defender_ids: list[str],
    evidence: dict[str, Any],
    confidence: float,
    eligibility_verdict: str = "STRUCTURAL",
    selection_reasons: list[str] | None = None,
    zone_context: dict[str, Any] | None = None,
) -> TacticalEpisode:
    template = _TEMPLATES[episode_type]
    return TacticalEpisode(
        episode_id=_identifier(episode_type, start_event_id, end_event_id),
        episode_type=episode_type,
        start_event_id=start_event_id,
        end_event_id=end_event_id,
        participating_action_ids=participating_action_ids,
        primary_actor_ids=primary_actor_ids,
        relevant_defender_ids=relevant_defender_ids,
        tactical_question=template["tactical_question"],
        cause=template["cause"],
        created_advantage=template["created_advantage"],
        decisive_action=template["decisive_action"],
        evidence=evidence,
        confidence=round(float(confidence), 3),
        limitations=[_RECONSTRUCTED_DEFENDER_LIMITATION] if relevant_defender_ids else [],
        eligibility_verdict=eligibility_verdict,
        selection_reasons=selection_reasons or [],
        zone_context=zone_context or {},
        identity_resolution=_identity_resolution_map([*primary_actor_ids, *relevant_defender_ids]),
    )


def _run_production_validators(
    possession: NormalizedPossession,
    episodes: list[TacticalEpisode],
) -> list[Any]:
    """Wire the deterministic validators in src.tactical_validation into the
    real selection flow (not just the audit script): every dataset this
    engine produces is checked against its own final episodes with the exact
    same PASS/WARN/FAIL logic the semantic audit used. Validators only read
    the already-built episodes/events; they never mutate evidence or
    fabricate anything."""
    from src.tactical_validation import (
        build_position_index,
        validate_episode_forward_progress,
        validate_evidence_within_interval,
        validate_low_confidence_retention,
        validate_no_duplicate_decisive_action,
        validate_supported_episode_type,
        validate_switch_of_play_changes_channel,
        validate_temporal_order,
    )

    episode_dicts = [asdict(episode) for episode in episodes]
    raw_events = []
    for idx, event in enumerate(possession.events):
        raw: dict[str, Any] = {"id": event.event_id, "type": event.event_type, "timestamp": event.timestamp, "index": idx}
        end = None if event.end_position is None else [event.end_position.x, event.end_position.y]
        if event.event_type == "Pass":
            raw["pass_end_location"] = end
        elif event.event_type == "Carry":
            raw["carry_end_location"] = end
        elif event.event_type == "Shot":
            raw["shot_end_location"] = end
        raw["location"] = None if event.start_position is None else [event.start_position.x, event.start_position.y]
        raw_events.append(raw)
    order = {raw["id"]: position for position, raw in enumerate(raw_events)}

    results: list[Any] = []
    results += validate_temporal_order(episode_dicts, order)
    results += validate_evidence_within_interval(episode_dicts, order)
    results += validate_no_duplicate_decisive_action(episode_dicts)
    results += validate_supported_episode_type(episode_dicts)
    results += validate_switch_of_play_changes_channel(episode_dicts)
    results += validate_episode_forward_progress(episode_dicts, build_position_index(raw_events), ATTACKING_GOAL_X)
    results += validate_low_confidence_retention(episode_dicts)
    return results


def build_tactical_episodes(
    possession: NormalizedPossession,
    findings: list[TacticalFinding],
    match_id: str | None = None,
) -> TacticalEpisodeDataset:
    """Segment a possession into a small, deterministic set of causal tactical episodes.

    `findings` should be the output of the existing generic pattern detectors
    (`detect_line_breaking_passes` + `detect_positional_patterns`); this function adds
    three more generic geometric detectors (press escape, half-space entry, box arrival)
    and groups everything into episodes, never one episode per event.
    """
    if not possession.events:
        raise TacticalEpisodeError("TACTICAL_EPISODE_EMPTY_POSSESSION")

    event_index = {event.event_id: idx for idx, event in enumerate(possession.events)}
    candidate_findings = [
        finding
        for finding in (
            list(findings) + _detect_press_escape(possession) + _detect_half_space_entry(possession) + _detect_box_arrival(possession)
        )
        if finding.pattern_type in PATTERN_TO_EPISODE_TYPE and finding.event_id in event_index
    ]

    shot_event = next((event for event in possession.events if event.event_type == "Shot"), None)
    candidate_findings = [finding for finding in candidate_findings if shot_event is None or finding.event_id != shot_event.event_id]
    findings_by_id = {finding.finding_id: finding for finding in candidate_findings}

    # Deterministic eligibility/ranking layer: distinguishes detection
    # confidence from semantic validity, causal relevance to the terminal
    # shot, and narrative/redundancy value (see eligibility.py). Every
    # candidate remains present and auditable in candidate_evaluations below,
    # whether selected, eligible-but-outranked, or rejected.
    evaluations = evaluate_candidates(possession, candidate_findings, PATTERN_TO_EPISODE_TYPE, event_index, shot_event)
    selected, candidate_evaluations = select_episodes(evaluations, event_index, MAX_FINDING_EPISODES)
    ordered = [findings_by_id[evaluation.finding_id] for evaluation in selected]
    selection_by_finding_id = {evaluation.finding_id: evaluation for evaluation in selected}

    episodes: list[TacticalEpisode] = []
    cursor = 0

    def _span(end_idx: int) -> tuple[str, str, list[str]]:
        nonlocal cursor
        start_idx = min(cursor, end_idx)
        action_ids = [possession.events[i].event_id for i in range(start_idx, end_idx + 1)]
        cursor = end_idx + 1
        return possession.events[start_idx].event_id, possession.events[end_idx].event_id, action_ids

    if ordered:
        first_anchor_idx = event_index[ordered[0].event_id]
        if first_anchor_idx > cursor:
            start_id, end_id, action_ids = _span(first_anchor_idx - 1)
            # A wider eligibility/causal-relevance gate now lets BUILDUP legitimately
            # absorb a much longer circulation phase than before (that is the fix).
            # Its primary_actor_ids should still describe "who has the ball as this
            # phase hands off", not the full historical roster of a possibly
            # dozens-of-events-long span, so scenes never render every participant.
            handoff_event = possession.events[event_index[end_id]]
            actor_ids = sorted({p for p in (handoff_event.player_id, handoff_event.recipient_id) if p})
            episodes.append(_build_episode("BUILDUP", start_id, end_id, action_ids, actor_ids, [], {"event_count": len(action_ids)}, 1.0))

    for finding in ordered:
        anchor_idx = event_index[finding.event_id]
        start_id, end_id, action_ids = _span(anchor_idx)
        episode_type = PATTERN_TO_EPISODE_TYPE[finding.pattern_type]
        primary_actor_ids = sorted(set(finding.actors) | set(finding.receivers))
        anchor_event = possession.events[anchor_idx]
        relevant_position = anchor_event.end_position or anchor_event.start_position
        relevant_defender_ids: list[str] = []
        if relevant_position is not None:
            nearest = nearest_defender(relevant_position, _defenders(anchor_event))
            if nearest is not None:
                relevant_defender_ids = [nearest.tracking_id]
        evaluation = selection_by_finding_id[finding.finding_id]
        episodes.append(
            _build_episode(
                episode_type,
                start_id,
                end_id,
                action_ids,
                primary_actor_ids,
                relevant_defender_ids,
                finding.evidence,
                finding.confidence,
                eligibility_verdict=evaluation.eligibility,
                selection_reasons=[*evaluation.causal_relevance_reasons, *evaluation.semantic_validity_reasons],
                zone_context=evaluation.zone_context,
            )
        )

    if shot_event is not None:
        shot_idx = event_index[shot_event.event_id]
        start_idx = min(cursor, shot_idx)
        action_ids = [possession.events[i].event_id for i in range(start_idx, shot_idx + 1)]
        cursor = shot_idx + 1
        primary_actor_ids = [shot_event.player_id] if shot_event.player_id else []
        relevant_defender_ids = []
        if shot_event.start_position is not None:
            nearest = nearest_defender(shot_event.start_position, _defenders(shot_event))
            if nearest is not None:
                relevant_defender_ids = [nearest.tracking_id]
        episodes.append(
            _build_episode(
                "FINISH",
                possession.events[start_idx].event_id,
                shot_event.event_id,
                action_ids,
                primary_actor_ids,
                relevant_defender_ids,
                {"pattern": "finish"},
                1.0,
            )
        )

    if not episodes:
        raise TacticalEpisodeError("TACTICAL_EPISODE_NONE_DETECTED")

    return TacticalEpisodeDataset(
        match_id=match_id or (possession.source_match_id or ""),
        possession_id=possession.possession_id,
        episodes=episodes,
        candidate_evaluations=candidate_evaluations,
        validator_results=_run_production_validators(possession, episodes),
    )
