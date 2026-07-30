from __future__ import annotations

"""Deterministic eligibility and ranking layer between tactical-pattern
detection (`src/intelligence/patterns`) and final episode selection
(`build_tactical_episodes`).

Raw per-pattern detection confidence answers only one question: how strongly
does the source evidence support the existence of this geometric pattern? It
says nothing about whether the pattern's own definition is actually satisfied
(semantic validity), whether the action it describes contributed to the
scoring outcome (causal relevance), or whether selecting it alongside other
candidates would add non-redundant explanatory value (narrative utility).
This module computes all four, independently, for every candidate -- then
ranks and selects using that fuller picture instead of confidence alone.

Nothing here is fixture-, player-, or match-specific: every threshold is a
generic pitch-zone or evidence-shape constant that applies identically to any
possession.
"""

from dataclasses import replace
from typing import Any

from src.domain.enums import AttackingDirection
from src.domain.models import Event, NormalizedPossession, TacticalFinding
from src.intelligence.features.progression import calculate_goal_distance_reduction

from .geometry import is_in_box
from .models import CandidateEvaluation

_ATTACKING_DIRECTION = AttackingDirection.LEFT_TO_RIGHT.value

# Standard equal-thirds split of a 120m-long pitch. This is *context* attached
# to every candidate (zone_context), and is only used as a hard gate inside
# the specific per-type invariants below that call for it (ISOLATION, CUTBACK)
# -- it is never applied as a blanket "defensive third = invalid" rule across
# all episode types.
DEFENSIVE_THIRD_X = 40.0
FINAL_THIRD_X = 100.0

# An OFF_BALL_RUN must cover more net goal-distance than this to count as a
# supported run rather than incidental positional drift during circulation.
OFF_BALL_RUN_MIN_ADVANCE_M = 10.0

# Episode types whose *own* evidence describes only the destination zone of
# the anchor action (where the ball ended up), never the geometry/mechanism
# that put it there. When such a type collides with another type on the exact
# same anchor event, the mechanism-describing type is the more informative,
# less redundant label for that single action. Within this zone-only tier,
# BOX_ARRIVAL is a strictly stronger (smaller, more goal-adjacent) zone claim
# than HALF_SPACE_ENTRY, so it wins zone-only-vs-zone-only collisions too.
_ZONE_ONLY_SPECIFICITY = {"HALF_SPACE_ENTRY": 0, "BOX_ARRIVAL": 1}

# Mechanism types whose own evidence is a direct geometric description of the
# terminal anchor action itself (not a network/history property of *earlier*
# actions, the way THIRD_MAN_COMBINATION or OFF_BALL_RUN are). When one of
# these coincides with a zone signal on the same event, it is the most
# informative available label for that action.
_TERMINAL_MECHANISM_TYPES = {"CUTBACK", "LINE_BREAK"}

MAX_FINDING_EPISODES_DEFAULT = 4


def _type_specificity(episode_type: str) -> int:
    if episode_type in _ZONE_ONLY_SPECIFICITY:
        return _ZONE_ONLY_SPECIFICITY[episode_type]
    if episode_type in _TERMINAL_MECHANISM_TYPES:
        return 3
    return 2


def goalkeeper_ids(possession: NormalizedPossession) -> frozenset[str]:
    """Every player_id ever observed acting with `keeper: true` in this
    possession's own freeze-frame data (see src/ingest/possession_loader.py).
    Purely structural -- no player names or ids are hardcoded anywhere."""
    ids: set[str] = set()
    for event in possession.events:
        for snapshot in event.freeze_frame:
            if snapshot.is_goalkeeper and snapshot.tracking_id and not snapshot.tracking_id.startswith("recon:"):
                ids.add(snapshot.tracking_id)
    return frozenset(ids)


def _zone_label(x: float | None) -> str | None:
    if x is None:
        return None
    if x < DEFENSIVE_THIRD_X:
        return "DEFENSIVE_THIRD"
    if x < FINAL_THIRD_X:
        return "MIDDLE_THIRD"
    return "FINAL_THIRD"


def _position_list(position: Any | None) -> list[float] | None:
    return None if position is None else [round(position.x, 3), round(position.y, 3)]


def build_zone_context(anchor_event: Event) -> dict[str, Any]:
    start, end = anchor_event.start_position, anchor_event.end_position
    reduction = None
    if start is not None and end is not None:
        reduction = round(calculate_goal_distance_reduction(start, end, _ATTACKING_DIRECTION), 3)
    end_in_box = bool(end is not None and is_in_box(end))
    start_in_box = bool(start is not None and is_in_box(start))
    return {
        "start_position": _position_list(start),
        "end_position": _position_list(end),
        "start_zone": _zone_label(start.x if start else None),
        "end_zone": _zone_label(end.x if end else None),
        "goal_distance_reduction": reduction,
        "end_in_box": end_in_box,
        # A *transition* into the box (arrival), not merely "ends in the box"
        # -- an action that starts and ends inside the box (e.g. a short
        # combination pass in the six-yard area) is not a box "arrival".
        "box_transition": bool(end_in_box and not start_in_box),
    }


def _semantic_validity(
    episode_type: str,
    finding: TacticalFinding,
    anchor_event: Event,
    keeper_ids: frozenset[str],
    event_index: dict[str, int],
    possession: NormalizedPossession,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if episode_type == "SWITCH_OF_PLAY":
        changed_side = finding.evidence.get("feature_values", {}).get("changed_side")
        if changed_side is not True:
            reasons.append(
                f"SWITCH_OF_PLAY_NO_SIDE_CHANGE: evidence.feature_values.changed_side={changed_side!r}, "
                "not True -- a large lateral pass that stays on the same side of the pitch is progression, "
                "not a switch of the point of attack"
            )
        elif anchor_event.start_position is not None and is_in_box(anchor_event.start_position):
            reasons.append(
                "SWITCH_OF_PLAY_STARTS_INSIDE_BOX: the pass already begins inside the attacking box; "
                "redistributing the ball within a settled attacking position does not switch the point of attack"
            )

    elif episode_type == "CUTBACK":
        end = anchor_event.end_position
        if end is None or end.x < FINAL_THIRD_X:
            reasons.append(
                f"CUTBACK_NOT_GROUNDED_IN_ATTACKING_THIRD: end position {_position_list(end)} is not within "
                f"the final third (x>={FINAL_THIRD_X}); a backward pass into a central area only creates a "
                "clearer scoring angle when that area is near the opponent's goal"
            )

    elif episode_type == "ISOLATION":
        if anchor_event.recipient_id in keeper_ids or anchor_event.player_id in keeper_ids:
            reasons.append(
                "ISOLATION_ANCHORED_ON_GOALKEEPER: the receiving player is a goalkeeper, not an attacker "
                "being isolated -- nobody pressing a keeper's outlet pass is not a tactical mismatch"
            )
        end = anchor_event.end_position
        if end is not None and end.x < DEFENSIVE_THIRD_X:
            reasons.append(
                f"ISOLATION_ROUTINE_DEFENSIVE_THIRD_CIRCULATION: receiving position x={end.x} is within the "
                f"defensive third (x<{DEFENSIVE_THIRD_X}); absence of pressure here is routine possession "
                "retention, not a tactically consequential isolation"
            )

    elif episode_type == "OFF_BALL_RUN":
        end = anchor_event.end_position
        if end is not None and is_in_box(end):
            reasons.append(
                "OFF_BALL_RUN_REDUNDANT_WITH_BOX_ENTRY: this reception already qualifies as a box entry and "
                "is better explained by that more specific label than by the receiving player's history"
            )
        else:
            feature_values = finding.evidence.get("feature_values", {})
            first_id = feature_values.get("first_involvement_event_id")
            first_idx = event_index.get(first_id)
            player_id = anchor_event.recipient_id
            if first_idx is None or player_id is None or end is None:
                reasons.append("OFF_BALL_RUN_MISSING_EVIDENCE: cannot locate the first-involvement event or receiving position")
            else:
                first_event = possession.events[first_idx]
                origin = first_event.end_position if first_event.recipient_id == player_id else first_event.start_position
                if origin is None:
                    reasons.append("OFF_BALL_RUN_MISSING_EVIDENCE: first-involvement position unavailable")
                else:
                    reduction = calculate_goal_distance_reduction(origin, end, _ATTACKING_DIRECTION)
                    if reduction <= OFF_BALL_RUN_MIN_ADVANCE_M:
                        reasons.append(
                            f"OFF_BALL_RUN_NO_SUPPORTED_MOVEMENT: net goal-distance change {reduction:.1f}m "
                            f"does not clear the {OFF_BALL_RUN_MIN_ADVANCE_M}m materiality bar for a "
                            "purposeful attacking run"
                        )

    return (len(reasons) == 0), reasons


def _direct_chain_to_shot(anchor_event: Event, shot_event: Event, possession: NormalizedPossession, event_index: dict[str, int]) -> bool:
    """True when the same single player carries this action uninterrupted
    through to the shot: no other player touches the ball in between, and
    that same player takes the shot. A generic, deterministic proxy for
    "player-action continuation" given no true action-graph edges exist for
    this legacy possession pipeline (see ROOT_CAUSE_REPORT.md)."""
    continuator = anchor_event.recipient_id or anchor_event.player_id
    if not continuator or shot_event.player_id != continuator:
        return False
    anchor_idx = event_index[anchor_event.event_id]
    shot_idx = event_index[shot_event.event_id]
    for idx in range(anchor_idx + 1, shot_idx):
        event = possession.events[idx]
        if continuator not in (event.player_id, event.recipient_id):
            return False
    return True


def _causal_relevance(
    finding: TacticalFinding,
    anchor_event: Event,
    zone_context: dict[str, Any],
    shot_event: Event | None,
    keeper_ids: frozenset[str],
    possession: NormalizedPossession,
    event_index: dict[str, int],
) -> tuple[bool, int, list[str]]:
    """Generic, type-agnostic materiality gate: does this action connect to
    the terminal outcome through something stronger than "it happened
    somewhere during a possession that ended in a shot"? Uses only structure
    already present in the domain model (zone geometry, TacticalFinding's own
    created_space_for semantic link, and player-action continuation) -- it
    never invents a causal edge that isn't backed by that structure."""
    if anchor_event.recipient_id in keeper_ids or anchor_event.player_id in keeper_ids:
        return False, 0, [
            "GOALKEEPER_ANCHORED_NO_DOWNSTREAM_CONSEQUENCE: the decisive participant in this action is a "
            "goalkeeper; a keeper receiving the ball has no demonstrated downstream tactical consequence"
        ]
    if zone_context["box_transition"]:
        return True, 2, [
            "BOX_TRANSITION: this action carries the ball from outside the penalty area to inside it, "
            "immediate proximity to goal"
        ]
    if shot_event is not None and _direct_chain_to_shot(anchor_event, shot_event, possession, event_index):
        return True, 1, [
            "UNBROKEN_POSSESSION_CHAIN_TO_SHOT: the same player carries this action uninterrupted through to the shot "
            "(player-action continuation), with no other player touching the ball in between"
        ]
    return False, 0, [
        "NO_SUPPORTED_CAUSAL_LINK_TO_TERMINAL_OUTCOME: no box entry or unbroken possession chain connects this "
        "action to the shot; a shared participant identity alone (without an unbroken chain) is not evidence of "
        "causal contribution -- it is undifferentiated circulation"
    ]


def _ranking_key(evaluation: CandidateEvaluation, event_idx: int) -> tuple[float, ...]:
    return (
        1.0 if (evaluation.semantic_valid and evaluation.causal_relevant) else 0.0,
        float(evaluation.causal_relevance_tier),
        float(_type_specificity(evaluation.episode_type)),
        float(evaluation.detection_confidence),
        float(-event_idx),
    )


def evaluate_candidates(
    possession: NormalizedPossession,
    candidate_findings: list[TacticalFinding],
    pattern_to_episode_type: dict[str, str],
    event_index: dict[str, int],
    shot_event: Event | None,
) -> list[CandidateEvaluation]:
    """Independently evaluate every candidate finding. Order and content do
    not depend on any other candidate -- collision/redundancy resolution
    happens afterward in `select_episodes`."""
    keeper_ids = goalkeeper_ids(possession)
    evaluations: list[CandidateEvaluation] = []
    for finding in candidate_findings:
        episode_type = pattern_to_episode_type[finding.pattern_type]
        anchor_event = possession.events[event_index[finding.event_id]]
        zone_context = build_zone_context(anchor_event)
        semantic_valid, semantic_reasons = _semantic_validity(episode_type, finding, anchor_event, keeper_ids, event_index, possession)
        causal_relevant, causal_tier, causal_reasons = _causal_relevance(
            finding, anchor_event, zone_context, shot_event, keeper_ids, possession, event_index
        )
        eligible = semantic_valid and causal_relevant
        disqualification_reasons: list[str] = []
        if not semantic_valid:
            disqualification_reasons.extend(semantic_reasons)
        if not causal_relevant:
            disqualification_reasons.extend(causal_reasons)
        evaluation = CandidateEvaluation(
            finding_id=finding.finding_id,
            episode_type=episode_type,
            event_id=finding.event_id,
            detection_confidence=finding.confidence,
            semantic_valid=semantic_valid,
            semantic_validity_reasons=semantic_reasons,
            causal_relevant=causal_relevant,
            causal_relevance_tier=causal_tier,
            causal_relevance_reasons=causal_reasons,
            narrative_utility_score=float(causal_tier),
            redundancy_reasons=[],
            zone_context=zone_context,
            eligibility=("ELIGIBLE_UNSELECTED" if eligible else "REJECTED"),
            disqualification_reasons=disqualification_reasons,
            ranking_key=(),
            provenance={
                "finding_id": finding.finding_id,
                "event_id": finding.event_id,
                "pattern_type": finding.pattern_type,
                "evidence": finding.evidence,
                "players_involved": list(finding.players_involved),
                "created_space_for": list(finding.created_space_for),
                "depends_on": list(finding.depends_on),
            },
        )
        evaluation = replace(evaluation, ranking_key=_ranking_key(evaluation, event_index[finding.event_id]))
        evaluations.append(evaluation)
    return evaluations


def select_episodes(
    evaluations: list[CandidateEvaluation],
    event_index: dict[str, int],
    max_finding_episodes: int = MAX_FINDING_EPISODES_DEFAULT,
) -> tuple[list[CandidateEvaluation], list[CandidateEvaluation]]:
    """Resolve same-event collisions, same-type duplicates, and the episode
    cap using each candidate's ranking_key (causal relevance and semantic
    validity dominate; raw detection confidence is only a late tiebreaker).

    Returns (selected, all_evaluations) where `all_evaluations` is the full
    input list with `eligibility`/`disqualification_reasons`/
    `redundancy_reasons` updated to reflect the final outcome -- every
    candidate remains present and auditable, none are silently dropped.
    """
    by_id = {evaluation.finding_id: evaluation for evaluation in evaluations}
    gate_passed = [e for e in evaluations if e.eligibility == "ELIGIBLE_UNSELECTED"]

    # 1. Same-anchor-event collisions: multiple types describing the identical
    #    action are redundant; keep only the highest-ranked one.
    by_event: dict[str, list[CandidateEvaluation]] = {}
    for evaluation in gate_passed:
        by_event.setdefault(evaluation.event_id, []).append(evaluation)
    survivors: list[CandidateEvaluation] = []
    for event_id, group in by_event.items():
        if len(group) == 1:
            survivors.append(group[0])
            continue
        ordered_group = sorted(group, key=lambda e: e.ranking_key, reverse=True)
        winner, losers = ordered_group[0], ordered_group[1:]
        survivors.append(winner)
        for loser in losers:
            by_id[loser.finding_id] = replace(
                loser,
                eligibility="REJECTED",
                redundancy_reasons=[
                    f"REJECTED_REDUNDANT_SAME_EVENT: {winner.episode_type} describes the identical anchor "
                    "action more specifically/relevantly than this candidate's type"
                ],
                disqualification_reasons=[
                    *loser.disqualification_reasons,
                    f"REJECTED_REDUNDANT_SAME_EVENT: outranked by {winner.episode_type} on the same anchor event",
                ],
            )

    # 2. Same-type duplicates: keep the single highest-ranked candidate per
    #    episode type across the whole possession.
    by_type: dict[str, list[CandidateEvaluation]] = {}
    for evaluation in survivors:
        by_type.setdefault(evaluation.episode_type, []).append(evaluation)
    type_representatives: list[CandidateEvaluation] = []
    for episode_type, group in by_type.items():
        ordered_group = sorted(group, key=lambda e: e.ranking_key, reverse=True)
        winner, losers = ordered_group[0], ordered_group[1:]
        type_representatives.append(winner)
        for loser in losers:
            by_id[loser.finding_id] = replace(
                loser,
                eligibility="REJECTED",
                disqualification_reasons=[
                    *loser.disqualification_reasons,
                    f"REJECTED_LOWER_RANKED_SAME_TYPE: episode type {episode_type!r} already represented by "
                    "a higher-ranked candidate elsewhere in this possession",
                ],
            )

    # 3. Chronological order, then the episode cap -- applied only after
    #    eligibility and ranking, never before.
    type_representatives.sort(key=lambda e: event_index[e.event_id])
    if len(type_representatives) > max_finding_episodes:
        ranked = sorted(type_representatives, key=lambda e: e.ranking_key, reverse=True)
        kept_ids = {e.finding_id for e in ranked[:max_finding_episodes]}
        dropped = [e for e in type_representatives if e.finding_id not in kept_ids]
        type_representatives = [e for e in type_representatives if e.finding_id in kept_ids]
        for dropped_eval in dropped:
            by_id[dropped_eval.finding_id] = replace(
                dropped_eval,
                eligibility="REJECTED",
                disqualification_reasons=[
                    *dropped_eval.disqualification_reasons,
                    "REJECTED_EPISODE_CAP: exceeds MAX_FINDING_EPISODES after eligibility and ranking were applied",
                ],
            )

    for evaluation in type_representatives:
        by_id[evaluation.finding_id] = replace(evaluation, eligibility="SELECTED")

    selected = sorted(type_representatives, key=lambda e: event_index[e.event_id])
    selected = [by_id[e.finding_id] for e in selected]
    all_evaluations = [by_id[e.finding_id] for e in evaluations]
    return selected, all_evaluations
