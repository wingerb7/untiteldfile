from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.domain.models import ActionChain, Event, NarrativeStep, NormalizedPossession, TacticalFinding

WIDE_Y_DISTANCE = 22.0
FINAL_THIRD_X = 100.0
RETURN_PASS_MAX_SECONDS = 12.0


def _event_name(event: Event, role: str) -> str:
    if role == "actor":
        return str(event.source_metadata.get("player_name") or event.player_id or "The passer")
    if role == "receiver":
        return str(event.source_metadata.get("recipient_name") or event.recipient_id or "the receiver")
    return "the player"


def _is_wide(position: Any | None) -> bool:
    return bool(position and abs(float(position.y) - 40.0) >= WIDE_Y_DISTANCE)


def _is_final_third(position: Any | None) -> bool:
    return bool(position and float(position.x) >= FINAL_THIRD_X)


def _find_event(possession: NormalizedPossession, event_id: str) -> Event | None:
    return next((event for event in possession.events if event.event_id == event_id), None)


def _event_index(possession: NormalizedPossession, event_id: str) -> int | None:
    for idx, event in enumerate(possession.events):
        if event.event_id == event_id:
            return idx
    return None


def _shot_event(possession: NormalizedPossession) -> tuple[int, Event] | None:
    for idx, event in enumerate(possession.events):
        if event.event_type == "Shot":
            return idx, event
    return None


def _player_involved(event: Event, player_id: str | None) -> bool:
    return bool(player_id and (event.player_id == player_id or event.recipient_id == player_id))


def _next_event(events: list[Event], start_idx: int, predicate: Any) -> tuple[int, Event] | None:
    for idx in range(start_idx + 1, len(events)):
        event = events[idx]
        if predicate(event):
            return idx, event
    return None


def _build_step(
    step_id: str,
    step_type: str,
    event: Event,
    actor_id: str | None,
    receiver_id: str | None,
    caption: str,
    evidence: dict[str, Any],
) -> NarrativeStep:
    return NarrativeStep(
        step_id=step_id,
        step_type=step_type,
        event_id=event.event_id,
        actor_id=actor_id,
        receiver_id=receiver_id,
        caption=caption,
        evidence=evidence,
    )


def build_causal_chain(
    possession: NormalizedPossession,
    findings: list[TacticalFinding],
    selected: TacticalFinding | None,
) -> ActionChain | None:
    if selected is None:
        return None
    selected_event = _find_event(possession, selected.event_id)
    shot_pair = _shot_event(possession)
    selected_idx = _event_index(possession, selected.event_id)
    if selected_event is None or shot_pair is None or selected_idx is None:
        return None

    shot_idx, shot = shot_pair
    if selected_idx >= shot_idx or selected_event.event_type != "Pass":
        return None

    passer_id = selected_event.player_id
    receiver_id = selected_event.recipient_id
    passer = _event_name(selected_event, "actor")
    receiver = _event_name(selected_event, "receiver")
    between = possession.events[selected_idx: shot_idx + 1]
    steps: list[NarrativeStep] = []

    steps.append(
        _build_step(
            "step_1",
            "line_break",
            selected_event,
            passer_id,
            receiver_id,
            f"{passer} breaks the line to {receiver}.",
            {
                "finding_id": selected.finding_id,
                "pattern_type": selected.pattern_type,
                "defenders_bypassed": selected.evidence.get("defenders_bypassed"),
                "forward_progress": selected.evidence.get("forward_progress"),
            },
        )
    )

    wide_carry_pair = _next_event(
        possession.events[: shot_idx + 1],
        selected_idx,
        lambda event: event.event_type == "Carry"
        and event.player_id == receiver_id
        and (_is_wide(event.end_position or event.start_position) or _is_final_third(event.end_position)),
    )
    if wide_carry_pair:
        _, carry = wide_carry_pair
        steps.append(
            _build_step(
                f"step_{len(steps) + 1}",
                "wide_carry",
                carry,
                receiver_id,
                None,
                f"{receiver} carries into the wide channel.",
                {
                    "carry_start": None
                    if carry.start_position is None
                    else {"x": carry.start_position.x, "y": carry.start_position.y},
                    "carry_end": None if carry.end_position is None else {"x": carry.end_position.x, "y": carry.end_position.y},
                },
            )
        )

    return_pass_pair = _next_event(
        possession.events[: shot_idx + 1],
        selected_idx,
        lambda event: event.event_type == "Pass"
        and event.player_id == receiver_id
        and event.recipient_id == passer_id
        and float(event.timestamp - selected_event.timestamp) <= RETURN_PASS_MAX_SECONDS,
    )
    if passer_id and return_pass_pair:
        _, return_pass = return_pass_pair
        steps.append(
            _build_step(
                f"step_{len(steps) + 1}",
                "return_pass",
                return_pass,
                receiver_id,
                passer_id,
                f"The return pass finds {passer}'s continued run.",
                {
                    "same_player_passes_then_receives": True,
                    "seconds_after_initial_pass": round(return_pass.timestamp - selected_event.timestamp, 3),
                    "from_wide_zone": _is_wide(return_pass.start_position),
                    "toward_central_zone": bool(
                        return_pass.end_position and abs(float(return_pass.end_position.y) - 40.0) < WIDE_Y_DISTANCE
                    ),
                },
            )
        )

    if passer_id and shot.player_id == passer_id:
        steps.append(
            _build_step(
                f"step_{len(steps) + 1}",
                "finish",
                shot,
                passer_id,
                None,
                f"{passer} finishes the move he started.",
                {
                    "shot_by_original_passer": True,
                    "xg": shot.source_metadata.get("xg"),
                },
            )
        )

    continuation_detected = bool(passer_id and any(_player_involved(event, passer_id) for event in between[1:]))
    score = 0.35 + 0.15 * len(steps)
    if continuation_detected:
        score += 0.2
    if wide_carry_pair:
        score += 0.15
    if return_pass_pair:
        score += 0.2
    score = round(min(1.0, score), 3)

    return ActionChain(
        chain_id=f"chain_{selected.finding_id}",
        primary_finding_id=selected.finding_id,
        start_event_id=selected_event.event_id,
        end_event_id=shot.event_id,
        score=score,
        steps=steps,
        evidence={
            "relations": {
                "passer_becomes_later_receiver": bool(return_pass_pair),
                "receiver_wide_carry_after_progressive_pass": bool(wide_carry_pair),
                "shot_by_original_passer": bool(passer_id and shot.player_id == passer_id),
                "continuation_detected": continuation_detected,
            },
            "supporting_finding_ids": [finding.finding_id for finding in findings if finding.event_id in {step.event_id for step in steps}],
        },
    )


def action_chain_to_dict(chain: ActionChain | None) -> dict[str, Any] | None:
    return None if chain is None else asdict(chain)


def _position_from_dict(value: list[float] | None) -> Any | None:
    if not value or len(value) < 2:
        return None
    from src.domain.models import Position

    return Position(float(value[0]), float(value[1]))


def _event_from_dict(raw: dict[str, Any], possession_id: int) -> Event:
    return Event(
        event_id=str(raw.get("id")),
        event_type=str(raw.get("type") or "Unknown"),
        timestamp=float(raw.get("timestamp") or 0.0),
        possession_id=possession_id,
        team_id=None if raw.get("team_id") is None else str(raw.get("team_id")),
        player_id=None if raw.get("player_id") is None else str(raw.get("player_id")),
        start_position=_position_from_dict(raw.get("start_location")),
        end_position=_position_from_dict(raw.get("end_location")),
        recipient_id=None if raw.get("recipient_id") is None else str(raw.get("recipient_id")),
        outcome=raw.get("outcome"),
        freeze_frame=[],
        source_metadata={
            "index": raw.get("index"),
            "player_name": raw.get("player_name"),
            "recipient_name": raw.get("recipient_name"),
            "xg": raw.get("xg"),
        },
    )


def _finding_from_dict(raw: dict[str, Any]) -> TacticalFinding:
    return TacticalFinding(
        finding_id=str(raw.get("finding_id")),
        pattern_type=str(raw.get("pattern_type")),
        event_id=str(raw.get("event_id")),
        confidence=float(raw.get("confidence") or 0.0),
        evidence=dict(raw.get("evidence") or {}),
        explanation_key=str(raw.get("explanation_key") or raw.get("pattern_type") or ""),
        limitations=list(raw.get("limitations") or []),
        players_involved=[str(value) for value in raw.get("players_involved") or []],
        feature_values=dict(raw.get("feature_values") or {}),
        actors=[str(value) for value in raw.get("actors") or []],
        receivers=[str(value) for value in raw.get("receivers") or []],
        created_space_for=[str(value) for value in raw.get("created_space_for") or []],
        enabled_by=[str(value) for value in raw.get("enabled_by") or []],
        depends_on=[str(value) for value in raw.get("depends_on") or []],
    )


def build_causal_chain_from_payload(possession: dict[str, Any], analysis: dict[str, Any]) -> ActionChain | None:
    possession_id = int(possession.get("possession_id") or 0)
    domain_possession = NormalizedPossession(
        possession_id=possession_id,
        attacking_team_id=None,
        defending_team_id=None,
        events=[_event_from_dict(event, possession_id) for event in possession.get("events", [])],
        start_timestamp=float(possession.get("start_time") or 0.0),
        end_timestamp=float(possession.get("end_time") or 0.0),
        source_name=str(possession.get("source") or "StatsBomb"),
        source_match_id=None if possession.get("match_id") is None else str(possession.get("match_id")),
    )
    findings = [_finding_from_dict(finding) for finding in analysis.get("findings", [])]
    selected_id = analysis.get("selected_finding_id")
    selected = next((finding for finding in findings if finding.finding_id == selected_id), None)
    return build_causal_chain(domain_possession, findings, selected)
