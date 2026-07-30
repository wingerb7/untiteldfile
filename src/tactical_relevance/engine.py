from __future__ import annotations

from src.domain.models import Event, NormalizedPossession, PlayerSnapshot
from src.intelligence.features.geometry import distance
from src.tactical_episodes.geometry import nearest_defender
from src.tactical_episodes.models import TacticalEpisode

from .models import PlayerRelevance

MANDATORY = "MANDATORY"
DEFENSIVE_CONTEXT = "DEFENSIVE_CONTEXT"
STRUCTURAL_CONTEXT = "STRUCTURAL_CONTEXT"

# Never render every player: this caps how many DEFENSIVE_CONTEXT + STRUCTURAL_CONTEXT
# players are added on top of the mandatory participants for a single episode.
MAXIMUM_CONTEXT_PLAYERS = 4

_MANDATORY_ROLE_BY_EPISODE_TYPE: dict[str, str] = {
    "FINISH": "shooter",
    "OFF_BALL_RUN": "decisive runner arriving late",
    "CUTBACK": "decisive runner receiving the cutback",
    "BOX_ARRIVAL": "decisive runner entering the box",
}


def _events_in_span(possession: NormalizedPossession, episode: TacticalEpisode) -> list[Event]:
    by_id = {event.event_id: event for event in possession.events}
    return [by_id[event_id] for event_id in episode.participating_action_ids if event_id in by_id]


def _attackers(event: Event) -> list[PlayerSnapshot]:
    return [player for player in event.freeze_frame if player.is_teammate and not player.is_goalkeeper]


def _defenders(event: Event) -> list[PlayerSnapshot]:
    return [player for player in event.freeze_frame if not player.is_teammate and not player.is_goalkeeper]


def _defending_goalkeeper(event: Event) -> PlayerSnapshot | None:
    return next((player for player in event.freeze_frame if not player.is_teammate and player.is_goalkeeper), None)


def _distance_score(value: float, scale: float = 20.0) -> float:
    return round(max(0.0, min(1.0, 1.0 - value / scale)), 3)


def classify_episode_players(possession: NormalizedPossession, episode: TacticalEpisode) -> list[PlayerRelevance]:
    """Classify which players matter for this episode and why.

    Never returns every player on the pitch: mandatory participants come straight from
    the episode's own actors; defensive/structural context is capped and only added
    when the geometry at the episode's anchor event actually supports it.
    """
    span = _events_in_span(possession, episode)
    if not span:
        return []
    anchor_event = span[-1]
    records: list[PlayerRelevance] = []
    seen_player_ids: set[str] = set()

    decisive_role = _MANDATORY_ROLE_BY_EPISODE_TYPE.get(episode.episode_type)
    for player_id in episode.primary_actor_ids:
        if player_id in seen_player_ids:
            continue
        if decisive_role and player_id == anchor_event.player_id:
            reason = decisive_role
        elif player_id == anchor_event.player_id:
            reason = "ball carrier / passer initiating this episode"
        elif player_id == anchor_event.recipient_id:
            reason = "receiver of the decisive action in this episode"
        else:
            reason = "participant in the action sequence forming this episode"
        records.append(
            PlayerRelevance(
                player_id=player_id,
                category=MANDATORY,
                reason=reason,
                episode_id=episode.episode_id,
                relevance_score=1.0,
                evidence={"episode_type": episode.episode_type, "anchor_event_id": anchor_event.event_id},
                confidence=episode.confidence,
            )
        )
        seen_player_ids.add(player_id)

    context_budget = MAXIMUM_CONTEXT_PLAYERS
    defenders = _defenders(anchor_event)

    if defenders and context_budget > 0:
        pressing_position = anchor_event.start_position
        if pressing_position is not None:
            presser = nearest_defender(pressing_position, defenders)
            if presser is not None:
                gap = distance(pressing_position, presser.position)
                records.append(
                    PlayerRelevance(
                        player_id=presser.tracking_id,
                        category=DEFENSIVE_CONTEXT,
                        reason="nearest pressing defender at the start of this episode",
                        episode_id=episode.episode_id,
                        relevance_score=_distance_score(gap),
                        evidence={"distance_m": round(gap, 3)},
                        confidence=episode.confidence,
                    )
                )
                context_budget -= 1

    if defenders and context_budget > 0:
        lane_position = anchor_event.end_position or anchor_event.start_position
        if lane_position is not None:
            lane_defender = nearest_defender(lane_position, defenders)
            if lane_defender is not None and lane_defender.tracking_id not in {r.player_id for r in records}:
                gap = distance(lane_position, lane_defender.position)
                reason = (
                    "defender defining the last defensive line"
                    if episode.episode_type == "LINE_BREAK"
                    else "defender controlling the passing lane / closest to the receiver"
                )
                records.append(
                    PlayerRelevance(
                        player_id=lane_defender.tracking_id,
                        category=DEFENSIVE_CONTEXT,
                        reason=reason,
                        episode_id=episode.episode_id,
                        relevance_score=_distance_score(gap),
                        evidence={"distance_m": round(gap, 3)},
                        confidence=episode.confidence,
                    )
                )
                context_budget -= 1

    if episode.episode_type in ("FINISH", "BOX_ARRIVAL") and context_budget > 0:
        goalkeeper = _defending_goalkeeper(anchor_event)
        if goalkeeper is not None:
            records.append(
                PlayerRelevance(
                    player_id=goalkeeper.tracking_id,
                    category=DEFENSIVE_CONTEXT,
                    reason="goalkeeper facing the shot",
                    episode_id=episode.episode_id,
                    relevance_score=0.9,
                    evidence={},
                    confidence=episode.confidence,
                )
            )
            context_budget -= 1

    if context_budget > 0:
        attackers = [player for player in _attackers(anchor_event) if player.tracking_id not in seen_player_ids]
        candidate, reason_text = None, None
        if attackers and episode.episode_type == "WIDE_PROGRESSION":
            candidate = max(attackers, key=lambda player: abs(player.position.y - 40.0))
            reason_text = "player creating width"
        elif attackers and episode.episode_type == "SWITCH_OF_PLAY":
            candidate = max(attackers, key=lambda player: abs(player.position.y - 40.0))
            reason_text = "player occupying the far side before the switch"
        elif attackers and episode.episode_type in ("OVERLOAD", "THIRD_MAN_COMBINATION"):
            candidate = attackers[0]
            reason_text = (
                "player creating the overload" if episode.episode_type == "OVERLOAD" else "supporting runner in the combination"
            )
        if candidate is not None and reason_text is not None:
            records.append(
                PlayerRelevance(
                    player_id=candidate.tracking_id,
                    category=STRUCTURAL_CONTEXT,
                    reason=reason_text,
                    episode_id=episode.episode_id,
                    relevance_score=0.6,
                    evidence={"position": [round(candidate.position.x, 2), round(candidate.position.y, 2)]},
                    confidence=episode.confidence,
                )
            )
            context_budget -= 1

    return records
