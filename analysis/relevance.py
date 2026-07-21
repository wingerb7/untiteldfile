from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from typing import Any


TEAM_ATTACK = "attacking_team"
TEAM_DEFENSE = "defending_team"
METRIC_X = 105.0 / 120.0
METRIC_Y = 68.0 / 80.0


@dataclass(frozen=True)
class RelevanceConfig:
    minimum_attackers: int = 3
    target_attackers: int = 5
    maximum_attackers: int = 6
    minimum_defenders: int = 3
    target_defenders: int = 5
    maximum_defenders: int = 6
    maximum_total_outfield_players: int = 10
    nearby_distance_m: float = 14.0
    pressure_distance_m: float = 8.0


@dataclass(frozen=True)
class RelevantPlayerSelection:
    selected_track_ids: set[str]
    reasons_by_track: dict[str, list[str]]
    scores_by_track: dict[str, float]
    attacking_track_ids: set[str]
    defending_track_ids: set[str]
    event_anchors_by_track: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    suppressed_track_ids: set[str] = field(default_factory=set)
    mandatory_track_ids: set[str] = field(default_factory=set)
    context_track_ids: set[str] = field(default_factory=set)
    optional_track_ids: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_track_ids": sorted(self.selected_track_ids),
            "attacking_track_ids": sorted(self.attacking_track_ids),
            "defending_track_ids": sorted(self.defending_track_ids),
            "suppressed_track_ids": sorted(self.suppressed_track_ids),
            "mandatory_track_ids": sorted(self.mandatory_track_ids),
            "context_track_ids": sorted(self.context_track_ids),
            "optional_track_ids": sorted(self.optional_track_ids),
            "warnings": list(self.warnings),
            "players": [
                {
                    "track_id": track_id,
                    "score": round(self.scores_by_track.get(track_id, 0.0), 3),
                    "reasons": self.reasons_by_track.get(track_id, []),
                    "event_anchors": self.event_anchors_by_track.get(track_id, []),
                }
                for track_id in sorted(self.selected_track_ids)
            ],
        }


def relevance_config(config: dict[str, Any]) -> RelevanceConfig:
    values = config.get("relevance", {})
    return RelevanceConfig(
        minimum_attackers=int(values.get("minimum_attackers", RelevanceConfig.minimum_attackers)),
        target_attackers=int(values.get("target_attackers", RelevanceConfig.target_attackers)),
        maximum_attackers=int(values.get("maximum_attackers", RelevanceConfig.maximum_attackers)),
        minimum_defenders=int(values.get("minimum_defenders", RelevanceConfig.minimum_defenders)),
        target_defenders=int(values.get("target_defenders", RelevanceConfig.target_defenders)),
        maximum_defenders=int(values.get("maximum_defenders", RelevanceConfig.maximum_defenders)),
        maximum_total_outfield_players=int(
            values.get("maximum_total_outfield_players", RelevanceConfig.maximum_total_outfield_players)
        ),
        nearby_distance_m=float(values.get("nearby_distance_m", RelevanceConfig.nearby_distance_m)),
        pressure_distance_m=float(values.get("pressure_distance_m", RelevanceConfig.pressure_distance_m)),
    )


def _identity(player_id: Any, player_name: str | None = None) -> tuple[str, str] | None:
    if player_id is not None:
        return "id", str(player_id)
    if player_name:
        return "name", str(player_name)
    return None


def _player_identity(player: Any) -> tuple[str, str] | None:
    return _identity(getattr(player, "player_id", None), getattr(player, "player_name", None))


def _distance(a: Any, location: list[float] | None) -> float:
    if not location or len(location) < 2:
        return 1_000_000.0
    return hypot((float(a.position.x) - float(location[0])) * METRIC_X, (float(a.position.y) - float(location[1])) * METRIC_Y)


def _add(
    track_id: str,
    amount: float,
    reason: str,
    scores: dict[str, float],
    reasons: dict[str, list[str]],
) -> None:
    scores[track_id] = scores.get(track_id, 0.0) + amount
    reasons.setdefault(track_id, [])
    if reason not in reasons[track_id]:
        reasons[track_id].append(reason)


def _event_frame(frame_states: list[Any], event_id: str) -> Any | None:
    return next((frame for frame in frame_states if str(frame.event_id) == str(event_id)), None)


def _players(frame: Any | None, team_id: str | None = None) -> list[Any]:
    if frame is None:
        return []
    players = [player for player in frame.players if getattr(player, "visible", True)]
    if team_id is not None:
        players = [player for player in players if player.team_id == team_id]
    return players


def _all_tracks(frame_states: list[Any]) -> dict[str, Any]:
    tracks: dict[str, Any] = {}
    for frame in frame_states:
        for player in frame.players:
            tracks.setdefault(player.tracking_id, player)
    return tracks


def _tracks_by_identity(frame_states: list[Any]) -> dict[tuple[str, str], set[str]]:
    by_identity: dict[tuple[str, str], set[str]] = {}
    for frame in frame_states:
        for player in frame.players:
            identity = _player_identity(player)
            if identity is not None:
                by_identity.setdefault(identity, set()).add(player.tracking_id)
    return by_identity


def _event_anchor_ids(event: dict[str, Any]) -> list[tuple[tuple[str, str] | None, str, float]]:
    event_type = str(event.get("type") or "")
    anchors = []
    actor = _identity(event.get("player_id"), event.get("player_name"))
    if actor is not None and event_type in {"Pass", "Carry", "Shot", "Dribble", "Ball Receipt*"}:
        anchors.append((actor, f"{event_type.lower()}_actor", 10.0))
    recipient = _identity(event.get("recipient_id"), event.get("recipient_name"))
    if recipient is not None and event_type == "Pass":
        anchors.append((recipient, "pass_recipient", 9.5))
    return anchors


def _score_event_participants(
    possession: dict[str, Any],
    frame_states: list[Any],
    scores: dict[str, float],
    reasons: dict[str, list[str]],
    anchors: dict[str, list[dict[str, Any]]],
) -> None:
    by_identity = _tracks_by_identity(frame_states)
    for event in possession.get("events", []):
        for identity, reason, score in _event_anchor_ids(event):
            if identity is None:
                continue
            for track_id in by_identity.get(identity, set()):
                _add(track_id, score, reason, scores, reasons)
                anchors.setdefault(track_id, []).append(
                    {"event_id": event.get("id"), "event_type": event.get("type"), "role": reason}
                )


def _score_selected_finding(
    selected_finding: dict[str, Any] | None,
    frame_states: list[Any],
    scores: dict[str, float],
    reasons: dict[str, list[str]],
) -> None:
    if not selected_finding:
        return
    by_identity = _tracks_by_identity(frame_states)
    for key, reason in (("player_id", "selected_finding_actor"), ("recipient_id", "selected_finding_recipient")):
        identity = _identity(selected_finding.get(key), selected_finding.get(key.replace("_id", "_name")))
        if identity is None:
            continue
        for track_id in by_identity.get(identity, set()):
            _add(track_id, 11.0, reason, scores, reasons)


def _score_context(
    possession: dict[str, Any],
    frame_states: list[Any],
    config: RelevanceConfig,
    scores: dict[str, float],
    reasons: dict[str, list[str]],
) -> None:
    for event in possession.get("events", []):
        frame = _event_frame(frame_states, str(event.get("id")))
        if frame is None:
            continue
        start = event.get("start_location")
        end = event.get("end_location") or start
        attackers = _players(frame, TEAM_ATTACK)
        defenders = _players(frame, TEAM_DEFENSE)

        nearby_attackers = sorted(
            (player for player in attackers if not getattr(player, "actor", False)),
            key=lambda player: min(_distance(player, start), _distance(player, end)),
        )[:3]
        for player in nearby_attackers:
            if min(_distance(player, start), _distance(player, end)) <= config.nearby_distance_m:
                _add(player.tracking_id, 2.0, "nearby_support_player", scores, reasons)

        for location, reason in ((start, "nearest_presser"), (end, "nearest_defender_to_receiver")):
            if not location or not defenders:
                continue
            defender = min(defenders, key=lambda player: _distance(player, location))
            _add(defender.tracking_id, 4.0, reason, scores, reasons)
            if _distance(defender, location) <= config.pressure_distance_m:
                _add(defender.tracking_id, 2.0, "pressure_on_ball_or_receiver", scores, reasons)

        if defenders:
            line_candidates = sorted(defenders, key=lambda player: abs(player.position.x - (end or start or [60.0, 40.0])[0]))[:4]
            for player in sorted(line_candidates, key=lambda player: player.position.y)[:2]:
                _add(player.tracking_id, 2.5, "defensive_line_context", scores, reasons)
            for player in sorted(line_candidates, key=lambda player: player.position.y)[-2:]:
                _add(player.tracking_id, 2.5, "defensive_line_context", scores, reasons)

        if event.get("type") == "Shot":
            keepers = [player for player in defenders if getattr(player, "is_goalkeeper", False)]
            for keeper in keepers[:1]:
                _add(keeper.tracking_id, 8.0, "shot_goalkeeper_context", scores, reasons)


def _apply_limits(
    tracks: dict[str, Any],
    scores: dict[str, float],
    reasons: dict[str, list[str]],
    config: RelevanceConfig,
) -> tuple[set[str], set[str], set[str], set[str], list[str]]:
    core_reasons = {
        "pass_actor",
        "carry_actor",
        "shot_actor",
        "dribble_actor",
        "ball receipt*_actor",
        "pass_recipient",
        "selected_finding_actor",
        "selected_finding_recipient",
    }
    required_context_reasons = {
        "nearest_presser",
        "nearest_defender_to_receiver",
        "pressure_on_ball_or_receiver",
        "defensive_line_context",
        "shot_goalkeeper_context",
    }

    mandatory = {
        track_id
        for track_id, track_reasons in reasons.items()
        if any(reason in core_reasons or reason.endswith("_actor") for reason in track_reasons)
    }
    context = {
        track_id
        for track_id, track_reasons in reasons.items()
        if track_id not in mandatory and any(reason in required_context_reasons for reason in track_reasons)
    }
    optional = {
        track_id
        for track_id in scores
        if track_id not in mandatory and track_id not in context and scores.get(track_id, 0.0) > 0.0
    }
    warnings: list[str] = []

    selected: set[str] = set(mandatory)

    def team_count(team_id: str) -> int:
        return sum(1 for track_id in selected if tracks[track_id].team_id == team_id)

    def outfield_count() -> int:
        return sum(1 for track_id in selected if not getattr(tracks[track_id], "is_goalkeeper", False))

    for team_id, maximum in ((TEAM_ATTACK, config.maximum_attackers), (TEAM_DEFENSE, config.maximum_defenders)):
        count = team_count(team_id)
        if count > maximum:
            warnings.append(f"mandatory_{team_id}_limit_exceeded:{count}>{maximum}")
    mandatory_outfield = outfield_count()
    if mandatory_outfield > config.maximum_total_outfield_players:
        warnings.append(f"mandatory_outfield_limit_exceeded:{mandatory_outfield}>{config.maximum_total_outfield_players}")

    def can_add(track_id: str) -> bool:
        player = tracks[track_id]
        team_max = config.maximum_attackers if player.team_id == TEAM_ATTACK else config.maximum_defenders
        if team_count(player.team_id) >= team_max:
            return False
        if not getattr(player, "is_goalkeeper", False) and outfield_count() >= config.maximum_total_outfield_players:
            return False
        return True

    def fill(candidates: set[str]) -> None:
        for track_id in sorted(candidates, key=lambda item: (-scores.get(item, 0.0), item)):
            if track_id in selected:
                continue
            if can_add(track_id):
                selected.add(track_id)

    fill(context)
    fill(optional)
    return selected, mandatory, context, optional, warnings


def select_relevant_players(
    possession: dict[str, Any],
    frame_states: list[Any],
    config: RelevanceConfig | None = None,
    selected_finding: dict[str, Any] | None = None,
) -> RelevantPlayerSelection:
    config = config or RelevanceConfig()
    scores: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}
    anchors: dict[str, list[dict[str, Any]]] = {}
    tracks = _all_tracks(frame_states)
    _score_event_participants(possession, frame_states, scores, reasons, anchors)
    _score_selected_finding(selected_finding, frame_states, scores, reasons)
    _score_context(possession, frame_states, config, scores, reasons)
    selected, mandatory, context, optional, warnings = _apply_limits(tracks, scores, reasons, config)
    attack = {track_id for track_id in selected if tracks[track_id].team_id == TEAM_ATTACK}
    defense = {track_id for track_id in selected if tracks[track_id].team_id == TEAM_DEFENSE}
    return RelevantPlayerSelection(
        selected_track_ids=selected,
        reasons_by_track={track_id: reasons.get(track_id, []) for track_id in selected},
        scores_by_track={track_id: scores.get(track_id, 0.0) for track_id in selected},
        attacking_track_ids=attack,
        defending_track_ids=defense,
        event_anchors_by_track={track_id: anchors.get(track_id, []) for track_id in selected},
        suppressed_track_ids=set(tracks) - selected,
        mandatory_track_ids=mandatory,
        context_track_ids=context & selected,
        optional_track_ids=optional & selected,
        warnings=warnings,
    )
