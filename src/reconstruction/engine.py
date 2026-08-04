from __future__ import annotations

import json
import math
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Any

from analysis.interpolate import (
    ObservationStatus,
    HOLD_REASON_CODES,
    build_event_timeline,
    build_frame_states,
    interpolation_hold_diagnostics,
    player_state_to_dict,
    total_animation_seconds,
    tracking_config,
)
from analysis.normalize import timestamp_to_seconds
from src.reconstruction.windows import SUPPORTED_ACTIONS, materialize_window, select_reconstruction_window, window_config


RECONSTRUCTION_MEDIA_TYPE = "application/vnd.tip.reconstructed-match+json"
SCHEMA_ID = "tip.reconstructed_match"
CONTRACT_VERSION = "1.0.0"


class ReconstructionError(ValueError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _file_hash(path: Path | None) -> str | None:
    return sha256(path.read_bytes()).hexdigest() if path is not None else None


def _name(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("name")
    return value if isinstance(value, str) else None


def _id(value: Any) -> Any:
    return value.get("id") if isinstance(value, dict) else value


def _end_location(event: dict[str, Any]) -> list[float] | None:
    event_type = _name(event.get("type"))
    child = {"Pass": "pass", "Carry": "carry", "Shot": "shot"}.get(event_type)
    value = event.get(child, {}).get("end_location") if child else None
    return list(value[:2]) if isinstance(value, list) and len(value) >= 2 else None


def _lineup_catalog(lineups: Any) -> list[dict[str, Any]]:
    result = []
    for team in lineups if isinstance(lineups, list) else []:
        team_id = _id(team.get("team_id") or team.get("team"))
        team_name = team.get("team_name") or _name(team.get("team"))
        for item in team.get("lineup", []):
            player = item.get("player", item)
            pid = _id(player.get("player_id") or player)
            name = player.get("player_name") or _name(player)
            if pid is not None:
                result.append({"player_id": pid, "player_name": name, "team_id": team_id, "team_name": team_name})
    return sorted(result, key=lambda row: (str(row["team_id"]), str(row["player_id"])))


def load_statsbomb_match(
    events_path: str | Path,
    three_sixty_path: str | Path | None = None,
    lineups_path: str | Path | None = None,
    matches_path: str | Path | None = None,
    *,
    match_id: int | str | None = None,
) -> dict[str, Any]:
    """Load StatsBomb JSON without requiring tactical/possession selection."""
    ep = Path(events_path)
    fp = Path(three_sixty_path) if three_sixty_path else None
    lp = Path(lineups_path) if lineups_path else None
    mp = Path(matches_path) if matches_path else None
    events = json.loads(ep.read_text(encoding="utf-8"))
    frames = json.loads(fp.read_text(encoding="utf-8")) if fp else []
    lineups = json.loads(lp.read_text(encoding="utf-8")) if lp else []
    matches = json.loads(mp.read_text(encoding="utf-8")) if mp else []
    if not isinstance(events, list) or not isinstance(frames, list):
        raise ReconstructionError("StatsBomb events and 360 roots must be arrays")

    frame_by_event = {str(row.get("event_uuid")): row for row in frames if row.get("event_uuid")}
    ordered_events = sorted(events, key=lambda row: int(row.get("index", 0)))
    previous_source_key = None
    source_validation_errors = []
    for raw in ordered_events:
        source_key = (int(raw.get("period") or 1), str(raw.get("timestamp") or ""))
        if previous_source_key is not None and source_key < previous_source_key:
            source_validation_errors.append("SOURCE_EVENT_INDEX_TIME_ORDER_INVALID")
            break
        previous_source_key = source_key
    highest_period = max((int(row.get("period") or 1) for row in ordered_events), default=1)
    period_starts: dict[int, float] = {}
    cumulative = 0.0
    for period in range(1, highest_period + 1):
        period_starts[period] = cumulative
        period_events = [row for row in ordered_events if int(row.get("period") or 1) == period]
        observed_span = max(
            (timestamp_to_seconds(row.get("timestamp")) + max(0.0, float(row.get("duration") or 0.0)) for row in period_events),
            default=0.0,
        )
        cumulative += max(45.0 * 60.0 if period < 3 else 15.0 * 60.0, observed_span)

    normalized_events = []
    normalized_frames = []
    for source_index, raw in enumerate(ordered_events):
        location = raw.get("location")
        if not isinstance(location, list) or len(location) < 2:
            continue
        event_id = str(raw.get("id"))
        period = int(raw.get("period") or 1)
        timestamp = period_starts[period] + timestamp_to_seconds(raw.get("timestamp"))
        event_type = _name(raw.get("type")) or "Unknown"
        actor = raw.get("player") or {}
        team = raw.get("team") or {}
        recipient = raw.get("pass", {}).get("recipient", {}) if isinstance(raw.get("pass"), dict) else {}
        frame = frame_by_event.get(event_id, {})
        players = []
        for observation_index, observation in enumerate(frame.get("freeze_frame", [])):
            observed_actor = bool(observation.get("actor"))
            players.append({
                "location": observation.get("location"),
                "teammate": bool(observation.get("teammate")),
                "keeper": bool(observation.get("keeper")),
                "actor": observed_actor,
                # StatsBomb 360 identifies only the event actor. Unknown is kept unknown.
                "player_id": _id(actor) if observed_actor else None,
                "player_name": _name(actor) if observed_actor else None,
                "team_id": _id(team) if observed_actor else None,
                "source_index": observation_index,
            })
        normalized_events.append({
            "id": event_id,
            "index": int(raw.get("index", source_index)),
            "period": period,
            "timestamp": timestamp,
            "duration": max(0.0, float(raw.get("duration") or 0.0)),
            "type": event_type,
            "player_id": _id(actor),
            "player_name": _name(actor),
            "team_id": _id(team),
            "team_name": _name(team),
            "start_location": [float(location[0]), float(location[1])],
            "end_location": _end_location(raw),
            "recipient_id": _id(recipient),
            "recipient_name": _name(recipient),
            "visible_area": frame.get("visible_area"),
            "source_event_index": int(raw.get("index", source_index)),
            "outcome": _name((raw.get("pass") or {}).get("outcome")) if event_type == "Pass" else _name((raw.get("shot") or {}).get("outcome")) if event_type == "Shot" else None,
        })
        normalized_frames.append({"event_id": event_id, "event_index": source_index, "timestamp": timestamp, "players": players})

    if not normalized_events:
        raise ReconstructionError("no position-bearing StatsBomb events")
    inferred_match_id = match_id if match_id is not None else ep.stem
    metadata = next((row for row in matches if str(row.get("match_id")) == str(inferred_match_id)), None)
    start = normalized_events[0]["timestamp"]
    return {
        "match_id": inferred_match_id,
        "match_label": str((metadata or {}).get("match_date") or inferred_match_id),
        "start_time": start,
        "end_time": max(row["timestamp"] + row["duration"] for row in normalized_events),
        "events": normalized_events,
        "frames": normalized_frames,
        "lineups": _lineup_catalog(lineups),
        "source_documents": {
            "events": {"path": str(ep), "sha256": _file_hash(ep)},
            "three_sixty": {"path": str(fp) if fp else None, "sha256": _file_hash(fp)},
            "lineups": {"path": str(lp) if lp else None, "sha256": _file_hash(lp)},
            "matches": {"path": str(mp) if mp else None, "sha256": _file_hash(mp)},
        },
        "source_validation_errors": source_validation_errors,
    }


def _source_for_player(player: Any) -> dict[str, Any]:
    if player.observation_id:
        return {
            "kind": "STATSBOMB_360_OBSERVATION",
            "event_id": player.source_event_id,
            "observation_id": player.observation_id,
            "source_index": player.source_index,
        }
    return {"kind": "NO_POSITION_SOURCE", "event_id": player.source_event_id}


def _keyframe(frame: Any, event: dict[str, Any] | None) -> dict[str, Any]:
    players = []
    for player in sorted(frame.players, key=lambda item: item.tracking_id):
        status = player.status.value
        supported = status in {ObservationStatus.OBSERVED.value, ObservationStatus.INTERPOLATED.value}
        players.append({
            **player_state_to_dict(player),
            "location": player_state_to_dict(player)["location"] if supported else None,
            "last_known_position": player_state_to_dict(player)["location"] if not supported and player.last_observed_timestamp is not None else None,
            "identity": {"player_id": player.player_id, "player_name": player.player_name},
            "interpolation_state": status if supported else ObservationStatus.UNKNOWN.value,
            "visible": bool(player.visible and supported),
            "source": _source_for_player(player),
            "provenance": [_source_for_player(player)],
            "unknown_reason": None if supported else "NO_SUPPORTED_POSITION_AT_TIMESTAMP",
            "lifecycle": "ACTIVE_OBSERVED" if status == "OBSERVED" else "ACTIVE_INTERPOLATED" if status == "INTERPOLATED" else "SUSPENDED",
        })
    return {
        "timestamp": float(frame.timestamp),
        "event_id": frame.event_id,
        "period": (event or {}).get("period"),
        "players": players,
        "visible_area": (event or {}).get("visible_area"),
    }


def build_reconstruction(match: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build immutable-by-convention keyframes; no recognition or relevance is invoked."""
    config = dict(config or {})
    animation = dict(config.get("animation", {}))
    animation.update({"start_hold_seconds": 0.0, "end_hold_seconds": 0.0, "playback_speed": 1.0})
    tracking = dict(config.get("tracking", {}))
    tracking["enable_team_shape_propagation"] = False
    window_policy = window_config(config)
    tracking["maximum_speed_mps"] = window_policy.maximum_player_speed_mps
    tracking["identity_max_gap_seconds"] = window_policy.maximum_authenticated_association_gap_seconds
    tracking["max_anonymous_association_gap_seconds"] = window_policy.maximum_anonymous_association_gap_seconds
    tracking["maximum_association_displacement_m"] = window_policy.maximum_player_displacement_m
    tracking["strict_association_speed_gate"] = True
    reconstruction_config = {**config, "animation": animation, "tracking": tracking}
    timeline = build_event_timeline(match, reconstruction_config)
    resolved_tracking = tracking_config(reconstruction_config)
    frame_states, diagnostics = build_frame_states(match, timeline, resolved_tracking)
    diagnostics["interpolation_holds"] = interpolation_hold_diagnostics(
        frame_states,
        {str(event.get("id")): event for event in match.get("events", [])},
        diagnostics.get("association_conflicts", []),
    )
    diagnostics["hold_reason_codes"] = list(HOLD_REASON_CODES)
    event_by_id = {str(event["id"]): event for event in match["events"]}
    keyframes = [_keyframe(frame, event_by_id.get(frame.event_id)) for frame in frame_states]
    occurrences: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for frame_index, keyframe in enumerate(keyframes):
        for player in keyframe["players"]:
            occurrences.setdefault(player["tracking_id"], []).append((frame_index, player))
    track_lifecycles = []
    for track_id, items in sorted(occurrences.items()):
        first_index, first_player = items[0]
        last_index, _ = items[-1]
        events = [{"state": "CREATED", "timestamp": keyframes[first_index]["timestamp"]}]
        previous = None
        for frame_index, player in items:
            if player["lifecycle"] != previous:
                events.append({"state": player["lifecycle"], "timestamp": keyframes[frame_index]["timestamp"]})
                previous = player["lifecycle"]
        events.append({"state": "RETIRED", "timestamp": keyframes[last_index]["timestamp"]})
        track_lifecycles.append({"tracking_id": track_id, "authenticated_player_id": first_player["identity"]["player_id"], "anonymous": first_player["identity"]["player_id"] is None, "events": events})
    source_start = float(match["events"][0]["timestamp"])
    event_sources = [{
        "event_id": str(event["id"]),
        "source_event_index": event.get("source_event_index", event.get("index")),
        "timestamp": float(event["timestamp"]) - source_start,
        "source_timestamp": float(event["timestamp"]),
        "period": event.get("period"),
        "ball_start": event.get("start_location"),
        "ball_end": event.get("end_location"),
        "action": SUPPORTED_ACTIONS.get(str(event.get("type"))),
        "duration_seconds": float(event.get("duration") or 0.0),
        "outcome": event.get("outcome"),
    } for event in match["events"]]
    payload = {
        "schema_id": SCHEMA_ID,
        "contract_version": CONTRACT_VERSION,
        "media_type": RECONSTRUCTION_MEDIA_TYPE,
        "match_id": match.get("match_id"),
        "match_label": match.get("match_label"),
        "coordinate_system": "STATSBOMB_120x80",
        "start_timestamp": source_start,
        "duration": float(total_animation_seconds(timeline, reconstruction_config)),
        "events": event_sources,
        "lineups": match.get("lineups", []),
        "keyframes": keyframes,
        "track_lifecycles": track_lifecycles,
        "source_documents": match.get("source_documents", {}),
        "diagnostics": diagnostics,
        "policy": {
            "authoritative_states": ["OBSERVED", "INTERPOLATED", "UNKNOWN"],
            "unsupported_position_state": "UNKNOWN",
            "team_shape_propagation": False,
            "relevance_filtering": False,
            "tactical_input": False,
            "maximum_interpolation_seconds": window_config(config).maximum_interpolation_seconds,
            "maximum_player_speed_mps": window_config(config).maximum_player_speed_mps,
        },
        "window_selection": match.get("reconstruction_window"),
    }
    payload["sha256"] = sha256(_canonical_bytes(payload)).hexdigest()
    return validate_reconstruction(payload)


def build_window_reconstruction(
    match: dict[str, Any],
    *,
    event_id: str | None = None,
    event_index: int | None = None,
    sequence_end_event_id: str | None = None,
    pre_roll_seconds: float = 1.0,
    post_roll_seconds: float = 1.0,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selection = select_reconstruction_window(match, event_id=event_id, event_index=event_index, sequence_end_event_id=sequence_end_event_id, pre_roll_seconds=pre_roll_seconds, post_roll_seconds=post_roll_seconds, config=config)
    if not str(selection["admission"]).startswith("ACCEPTED"):
        return {"selection": selection, "reconstruction": None}
    reconstruction = build_reconstruction(materialize_window(match, selection), config)
    quality = reconstruction_quality(reconstruction, config)
    selection = {**selection, **quality}
    reconstruction["window_selection"] = selection
    # The admission result is part of the canonical artifact, so rebind its digest.
    reconstruction.pop("sha256", None)
    reconstruction["sha256"] = sha256(_canonical_bytes(reconstruction)).hexdigest()
    validate_reconstruction(reconstruction)
    return {"selection": selection, "reconstruction": reconstruction}


def reconstruction_quality(reconstruction: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = window_config(config)
    spans: dict[str,list[float]] = {}
    for frame in reconstruction["keyframes"]:
        for player in frame["players"]:
            spans.setdefault(player["tracking_id"],[]).append(float(frame["timestamp"]))
    sampled_unknown=sampled_total=0
    sampled_maximum_speed=0.0
    previous_sample:dict[str,tuple[float,list[float]]]={}
    sample_count=max(1,int(float(reconstruction["duration"])*resolved.quality_sample_hz)+1)
    for index in range(sample_count):
        timestamp=min(float(reconstruction["duration"]),index/resolved.quality_sample_hz)
        sampled_players=reconstruction_state_at(reconstruction,timestamp)["players"]
        visible={player["tracking_id"] for player in sampled_players}
        for player in sampled_players:
            track_id=player["tracking_id"]
            if track_id in previous_sample:
                previous_time,previous_position=previous_sample[track_id]
                elapsed=timestamp-previous_time
                if elapsed>0:
                    distance=math.dist((previous_position[0]*105/120,previous_position[1]*68/80),(player["location"][0]*105/120,player["location"][1]*68/80))
                    sampled_maximum_speed=max(sampled_maximum_speed,distance/elapsed)
            previous_sample[track_id]=(timestamp,player["location"])
        for track_id,times in spans.items():
            if min(times)<=timestamp<=max(times):
                sampled_total+=1;sampled_unknown+=int(track_id not in visible)
    unknown=100.0*sampled_unknown/max(1,sampled_total)
    distinct = {player["tracking_id"] for frame in reconstruction["keyframes"] for player in frame["players"]}
    maximum_visible = max((sum(player["visible"] for player in frame["players"]) for frame in reconstruction["keyframes"]), default=0)
    fragmentation = len(distinct) / max(1, maximum_visible)
    reasons = []
    selection_duration = float((reconstruction.get("window_selection") or {}).get("duration_seconds", reconstruction.get("duration", 0.0)))
    if unknown > resolved.unknown_rejection_percentage:
        reasons.append(f"UNKNOWN_PERCENTAGE_{unknown:.3f}_EXCEEDS_{resolved.unknown_rejection_percentage:.3f}")
    if fragmentation > resolved.maximum_track_fragmentation_ratio:
        reasons.append(f"TRACK_FRAGMENTATION_RATIO_{fragmentation:.3f}_EXCEEDS_{resolved.maximum_track_fragmentation_ratio:.3f}")
    if sampled_maximum_speed > resolved.maximum_player_speed_mps + 1e-9:
        reasons.append(f"PLAYER_SPEED_{sampled_maximum_speed:.3f}_EXCEEDS_{resolved.maximum_player_speed_mps:.3f}")
    if reasons and any(reason.startswith("TRACK_FRAGMENTATION") for reason in reasons):
        admission = "REJECTED_IDENTITY_FRAGMENTATION"
    elif reasons:
        admission = "REJECTED_INSUFFICIENT_OBSERVATION"
    elif unknown > 25.0 or selection_duration < resolved.target_min_seconds:
        admission = "ACCEPTED_WITH_LIMITATIONS"
        reasons = ([f"UNKNOWN_PERCENTAGE_{unknown:.3f}"] if unknown > 25.0 else []) + ([f"WINDOW_DURATION_{selection_duration:.3f}s_BELOW_TARGET_{resolved.target_min_seconds:.3f}s"] if selection_duration < resolved.target_min_seconds else [])
    else:
        admission = "ACCEPTED"
    return {"admission": admission, "reasons": reasons, "quality_estimates": {"unknown_percentage_sampled": unknown, "quality_sample_hz": resolved.quality_sample_hz, "distinct_track_count": len(distinct), "maximum_visible_players": maximum_visible, "track_fragmentation_ratio": fragmentation, "maximum_player_speed_mps": sampled_maximum_speed}}


def validate_reconstruction(reconstruction: dict[str, Any]) -> dict[str, Any]:
    if reconstruction.get("schema_id") != SCHEMA_ID or reconstruction.get("contract_version") != CONTRACT_VERSION:
        raise ReconstructionError("invalid reconstruction contract")
    digest_payload = {key: value for key, value in reconstruction.items() if key != "sha256"}
    if reconstruction.get("sha256") != sha256(_canonical_bytes(digest_payload)).hexdigest():
        raise ReconstructionError("reconstruction digest mismatch")
    previous = -float("inf")
    identities: dict[str, str] = {}
    for frame in reconstruction.get("keyframes", []):
        timestamp = frame.get("timestamp")
        if not isinstance(timestamp, (int, float)) or not isfinite(timestamp) or timestamp < previous:
            raise ReconstructionError("non-monotonic reconstruction timestamp")
        previous = timestamp
        seen = set()
        for player in frame.get("players", []):
            track = player.get("tracking_id")
            if not track or track in seen:
                raise ReconstructionError("duplicate or missing tracking identity")
            seen.add(track)
            state = player.get("interpolation_state")
            if state not in {"OBSERVED", "INTERPOLATED", "UNKNOWN"}:
                raise ReconstructionError("invalid interpolation state")
            if player.get("visible") and (state == "UNKNOWN" or not player.get("provenance")):
                raise ReconstructionError("visible player lacks positional evidence")
            pid = (player.get("identity") or {}).get("player_id")
            if pid is not None:
                prior = identities.setdefault(track, str(pid))
                if prior != str(pid):
                    raise ReconstructionError("identity changed within track")
    return reconstruction


def _lerp(a: float, b: float, amount: float) -> float:
    return a + (b - a) * amount


def reconstruction_state_at(reconstruction: dict[str, Any], timestamp: float) -> dict[str, Any]:
    """Return a deterministic, pauseable state at any reconstruction timestamp."""
    frames = reconstruction["keyframes"]
    if not frames:
        return {"timestamp": timestamp, "players": [], "ball": None, "visible_area": None}
    left = max((frame for frame in frames if frame["timestamp"] <= timestamp), default=frames[0], key=lambda row: row["timestamp"])
    right = min((frame for frame in frames if frame["timestamp"] >= timestamp), default=frames[-1], key=lambda row: row["timestamp"])
    if left is right or right["timestamp"] <= left["timestamp"]:
        players = [dict(player) for player in left["players"] if player.get("visible")]
    elif left.get("period") != right.get("period"):
        players = []
    else:
        amount = (timestamp - left["timestamp"]) / (right["timestamp"] - left["timestamp"])
        span = right["timestamp"] - left["timestamp"]
        maximum_span = float(reconstruction.get("policy", {}).get("maximum_interpolation_seconds", 3.0))
        maximum_speed = float(reconstruction.get("policy", {}).get("maximum_player_speed_mps", 9.5))
        right_by_track = {player["tracking_id"]: player for player in right["players"]}
        players = []
        for player in left["players"]:
            other = right_by_track.get(player["tracking_id"])
            if not player.get("visible") or not other or not other.get("visible"):
                continue
            if span > maximum_span:
                continue
            distance_m = math.dist((float(player["location"][0]) * 105 / 120, float(player["location"][1]) * 68 / 80), (float(other["location"][0]) * 105 / 120, float(other["location"][1]) * 68 / 80))
            if distance_m / span > maximum_speed:
                continue
            location = [_lerp(float(player["location"][i]), float(other["location"][i]), amount) for i in (0, 1)]
            confidence = min(float(player["confidence"]), float(other["confidence"]))
            sources = [*player["provenance"], *[source for source in other["provenance"] if source not in player["provenance"]]]
            last_observed = player.get("last_observed_timestamp")
            players.append({**player, "location": location, "observed": False, "status": "INTERPOLATED", "interpolation_state": "INTERPOLATED", "confidence": confidence, "position_confidence": confidence, "last_observed_timestamp": last_observed, "interpolation_duration": max(0.0, timestamp - last_observed) if last_observed is not None else None, "provenance": sources})

    event = max((event for event in reconstruction["events"] if event["timestamp"] <= timestamp), default=reconstruction["events"][0], key=lambda row: row["timestamp"])
    ball = None
    ball_state = "UNKNOWN"
    elapsed = timestamp - float(event["timestamp"])
    action = event.get("action")
    declared_duration = float(event.get("duration_seconds") or 0.0)
    duration = declared_duration if declared_duration > 0 else 0.6 if action == "SHOT" else 0.0
    if abs(elapsed) <= 1e-9 and event.get("ball_start") is not None:
        ball, ball_state = event["ball_start"], "OBSERVED"
    elif action in {"PASS", "CARRY", "SHOT"} and event.get("ball_start") is not None and event.get("ball_end") is not None and duration > 0 and 0 < elapsed <= duration:
        amount = min(1.0, elapsed / duration)
        ball = [_lerp(float(event["ball_start"][i]), float(event["ball_end"][i]), amount) for i in (0, 1)]
        ball_state = "INTERPOLATED" if amount < 1.0 else "OBSERVED"
    elif action == "BALL_RECEIPT" and event.get("ball_start") is not None and 0 <= elapsed <= 0.125:
        ball, ball_state = event["ball_start"], "OBSERVED"
    return {"timestamp": float(timestamp), "period": event.get("period"), "event_id": event["event_id"], "players": players, "ball": ball, "ball_state": ball_state, "ball_source": {"event_id": event["event_id"], "source_event_index": event.get("source_event_index")}, "visible_area": left.get("visible_area")}
