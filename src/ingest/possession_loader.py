from __future__ import annotations

from pathlib import Path

from analysis.normalize import load_and_normalize

from src.domain.models import Event, NormalizedPossession, PlayerSnapshot, Position


RECONSTRUCTED_ID_LIMITATION = (
    "Freeze-frame player identities are reconstructed using deterministic temporary tracking IDs; "
    "they are not guaranteed real-world player identities."
)


def _position(value: list[float] | None) -> Position | None:
    if not value or len(value) < 2:
        return None
    return Position(float(value[0]), float(value[1]))


def _snapshot(player: dict, event_id: str, idx: int) -> PlayerSnapshot:
    raw_player_id = player.get("player_id")
    tracking_id = str(raw_player_id) if raw_player_id is not None else f"recon:{event_id}:{idx}"
    team_id = str(player.get("team_id") or ("attack" if player.get("teammate") else "defense"))
    return PlayerSnapshot(
        tracking_id=tracking_id,
        team_id=team_id,
        position=_position(player["location"]) or Position(0.0, 0.0),
        is_teammate=bool(player.get("teammate")),
        is_goalkeeper=bool(player.get("keeper")),
        source_metadata={
            "source_index": player.get("source_index", idx),
            "actor": bool(player.get("actor")),
            "player_name": player.get("player_name"),
            "reconstructed_tracking_id": raw_player_id is None,
        },
    )


def load_normalized_possession(path: str | Path) -> NormalizedPossession:
    payload = load_and_normalize(path)
    possession_id = int(payload.get("possession_id") or 0)
    events: list[Event] = []
    for raw in payload.get("events", []):
        event_id = str(raw.get("id") or raw.get("index"))
        freeze_frame = [_snapshot(player, event_id, idx) for idx, player in enumerate(raw.get("freeze_frame", []))]
        events.append(
            Event(
                event_id=event_id,
                event_type=str(raw.get("type") or "Unknown"),
                timestamp=float(raw.get("timestamp") or 0.0),
                possession_id=possession_id,
                team_id=str(raw.get("team_id") or raw.get("team_name") or "") or None,
                player_id=str(raw.get("player_id") or raw.get("player_name") or "") or None,
                start_position=_position(raw.get("start_location")),
                end_position=_position(raw.get("end_location")),
                recipient_id=str(raw.get("recipient_id") or raw.get("recipient_name") or "") or None,
                outcome=raw.get("outcome"),
                freeze_frame=freeze_frame,
                source_metadata={
                    "index": raw.get("index"),
                    "player_name": raw.get("player_name"),
                    "recipient_name": raw.get("recipient_name"),
                    "xg": raw.get("xg"),
                    "visible_area": raw.get("visible_area"),
                },
            )
        )

    return NormalizedPossession(
        possession_id=possession_id,
        attacking_team_id=str(payload.get("team") or "") or None,
        defending_team_id=None,
        events=events,
        start_timestamp=float(payload.get("start_time") or 0.0),
        end_timestamp=float(payload.get("end_time") or 0.0),
        source_name=str(payload.get("source") or "StatsBomb"),
        source_match_id=str(payload.get("match_id") or "") or None,
        limitations=[RECONSTRUCTED_ID_LIMITATION],
    )
