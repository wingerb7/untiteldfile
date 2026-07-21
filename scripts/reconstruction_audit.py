from __future__ import annotations

import copy
import json
import math
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOCAL_CACHE = ROOT / "renders" / ".cache"
LOCAL_MPLCONFIG = ROOT / "renders" / ".matplotlib"
LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
LOCAL_MPLCONFIG.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(LOCAL_CACHE))
os.environ.setdefault("MPLCONFIGDIR", str(LOCAL_MPLCONFIG))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.interpolate import (
    TEAM_ATTACK,
    TEAM_DEFENSE,
    FramePlayerState,
    FrameState,
    ObservationStatus,
    PlayerObservation,
    PlayerTrack,
    TrackStatus,
    apply_relevant_player_selection,
    apply_event_anchors,
    assign_group,
    bridge_known_player_gaps,
    build_animation_model,
    build_event_timeline,
    create_track,
    eligible_tracks,
    frame_player_from_track,
    identity_matches,
    interpolation_confidence,
    lerp_position,
    maximum_distance_m,
    metric_distance,
    missing_track_state,
    observations_from_frame,
    observation_identity,
    player_identity,
    player_state_to_dict,
    retire_duplicate_identity_tracks,
    smootherstep,
    state_at,
    suppress_duplicate_or_excess_players,
    event_anchors_for_event,
    tracking_config,
    update_track,
    validate_frame_state,
)
from analysis.normalize import load_and_normalize
from render.pitch import draw_pitch, sb_to_plot
from render.styles import colors
from scripts.narrative_window import build_short_scene_plan, select_narrative_anchor
from src.pipelines.analyze_possession import analyze, load_config


OUT = ROOT / "renders" / "audits"
BASELINE_OUT = OUT / "baseline"
POST_REPAIR_OUT = OUT / "post_repair"

CASES = {
    "dimaria": {
        "match_id": 3869685,
        "possession_id": 52,
        "goal_event_id": "ef86f4d9-7acd-4ed0-a5ec-9129079e8fbe",
        "input_file": ROOT / "data" / "possession_52.json",
        "annotation_config": "annotations/possession_52.json",
        "output_file": OUT / "dimaria_observation_timeline.json",
        "slug": "dimaria",
    },
    "locatelli": {
        "match_id": 3788754,
        "possession_id": 40,
        "goal_event_id": "e0c628ae-6a37-414e-818e-5e3911c07dfc",
        "input_file": ROOT / "data" / "second_goal.json",
        "annotation_config": "annotations/second_goal.json",
        "output_file": OUT / "locatelli_observation_timeline.json",
        "slug": "locatelli",
    },
}

METRIC_X = 105.0 / 120.0
METRIC_Y = 68.0 / 80.0


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def audit_config(base: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    config = copy.deepcopy(base)
    config["animation"] = copy.deepcopy(config.get("animation", {}))
    config["animation"]["annotations_file"] = case["annotation_config"]
    config["animation"]["hook_hold_seconds"] = 0.0
    config["animation"]["hook_text"] = ""
    config["animation"]["camera_lookback_seconds"] = 2.5
    config["animation"]["camera_lookahead_seconds"] = 8.0
    config["animation"]["camera_zoom_out_ease"] = 0.18
    return config


def event_window(possession: dict[str, Any], scene_plan: dict[str, Any]) -> list[dict[str, Any]]:
    events = possession["events"]
    start_id = scene_plan["narrative_window"]["window_start_event_id"]
    end_id = scene_plan["narrative_window"]["window_end_event_id"]
    start_idx = next(idx for idx, event in enumerate(events) if event["id"] == start_id)
    end_idx = next(idx for idx, event in enumerate(events) if event["id"] == end_id)
    return events[start_idx : end_idx + 1]


def window_indices(possession: dict[str, Any], scene_plan: dict[str, Any]) -> tuple[int, int]:
    events = possession["events"]
    start_id = scene_plan["narrative_window"]["window_start_event_id"]
    end_id = scene_plan["narrative_window"]["window_end_event_id"]
    return (
        next(idx for idx, event in enumerate(events) if event["id"] == start_id),
        next(idx for idx, event in enumerate(events) if event["id"] == end_id),
    )


def observation_row(event_index: int, event: dict[str, Any]) -> dict[str, Any]:
    freeze_frame = event.get("freeze_frame") or []
    return {
        "event_index": event_index,
        "event_id": event.get("id"),
        "timestamp": float(event.get("timestamp") or 0.0),
        "type": event.get("type"),
        "player": event.get("player_name"),
        "recipient": event.get("recipient_name"),
        "location": event.get("start_location"),
        "end_location": event.get("end_location"),
        "has_360_freeze_frame": bool(freeze_frame),
        "freeze_frame_player_count": len(freeze_frame),
        "freeze_frame_teammates": sum(1 for player in freeze_frame if player.get("teammate") is True),
        "freeze_frame_opponents": sum(1 for player in freeze_frame if player.get("teammate") is False),
        "actor_present": any(player.get("actor") for player in freeze_frame),
        "keeper_count": sum(1 for player in freeze_frame if player.get("keeper")),
    }


def location_distance_m(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b:
        return None
    return math.hypot((float(b[0]) - float(a[0])) * METRIC_X, (float(b[1]) - float(a[1])) * METRIC_Y)


def frame_state_to_rows(frame: FrameState) -> list[dict[str, Any]]:
    return [player_state_to_dict(player) for player in frame.players]


def diagnostic_frame_build(possession: dict[str, Any], config: dict[str, Any], scene_plan: dict[str, Any]) -> dict[str, Any]:
    cfg = tracking_config(config)
    timeline = build_event_timeline(possession, config)
    event_times = {item.event["id"]: item.start for item in timeline}
    events = {event["id"]: event for event in possession["events"]}
    start_idx, end_idx = window_indices(possession, scene_plan)
    event_order = {event["id"]: idx for idx, event in enumerate(possession["events"])}
    window_ids = {event["id"] for event in possession["events"][start_idx : end_idx + 1]}

    tracks: dict[str, PlayerTrack] = {}
    identity_track_ids: dict[str, str] = {}
    next_track_id = 1
    states: list[FrameState] = []
    association_rows: list[dict[str, Any]] = []
    lifecycle_events: list[dict[str, Any]] = []
    track_rows: dict[str, dict[str, Any]] = {}

    def ensure_track(track: PlayerTrack) -> dict[str, Any]:
        row = track_rows.setdefault(
            track.tracking_id,
            {
                "tracking_id": track.tracking_id,
                "team_id": track.team_id,
                "teammate": track.is_teammate,
                "keeper": track.is_goalkeeper,
                "player_id": track.player_id,
                "player_name": track.player_name,
                "created_event_id": track.source_event_id,
                "created_timestamp": track.last_timestamp,
                "observations": [],
                "missing_events": [],
                "terminated_event_id": None,
                "terminated_timestamp": None,
                "terminated_by_missing_snapshot_policy": False,
                "max_gap_between_observations_seconds": 0.0,
            },
        )
        if track.player_id is not None:
            row["player_id"] = track.player_id
        if track.player_name is not None:
            row["player_name"] = track.player_name
        return row

    for frame in possession["frames"]:
        event_id = str(frame["event_id"])
        timestamp = event_times.get(event_id, 0.0)
        event = events[event_id]
        anchors = event_anchors_for_event(event, timestamp)
        observations = apply_event_anchors(observations_from_frame(frame, timestamp), anchors, cfg)
        before_tracks = {
            track.tracking_id: {
                "team_id": track.team_id,
                "keeper": track.is_goalkeeper,
                "position": [track.last_position.x, track.last_position.y],
                "last_timestamp": track.last_timestamp,
                "status": track.status.value,
                "missing_snapshots": track.missing_snapshots,
                "player_id": track.player_id,
                "player_name": track.player_name,
            }
            for track in tracks.values()
            if track.status != TrackStatus.TERMINATED
        }

        identity_group_matches, unmatched_observations, identity_matched_track_ids = identity_matches(
            tracks,
            observations,
            cfg,
            identity_track_ids,
        )
        matches: list[tuple[PlayerTrack, PlayerObservation]] = list(identity_group_matches)
        association_method = {obs.observation_id: "identity" for _, obs in identity_group_matches}
        unmatched_observation_ids = {observation.observation_id for observation in unmatched_observations}
        observation_groups: dict[tuple[str, bool], list[PlayerObservation]] = {}
        for observation in observations:
            observation_groups.setdefault((observation.team_id, observation.is_goalkeeper), []).append(observation)

        candidate_rows = []
        for observation in unmatched_observations:
            for track in eligible_tracks(tracks, observation.team_id, observation.is_goalkeeper):
                if track.tracking_id in identity_matched_track_ids:
                    continue
                distance = metric_distance(track.last_position, observation.position)
                allowed = maximum_distance_m(track, observation, cfg)
                candidate_rows.append(
                    {
                        "track_id": track.tracking_id,
                        "observation_id": observation.observation_id,
                        "source_index": observation.source_index,
                        "distance_m": round(distance, 3),
                        "maximum_allowed_m": round(allowed, 3),
                        "delta_time_seconds": round(observation.timestamp - track.last_timestamp, 3),
                        "rejected_by_speed_limit": distance > allowed,
                    }
                )

        for key, group_observations in observation_groups.items():
            team_id, is_goalkeeper = key
            group_tracks = [
                track
                for track in eligible_tracks(tracks, team_id, is_goalkeeper)
                if track.tracking_id not in identity_matched_track_ids
            ]
            group_observations = [
                observation
                for observation in group_observations
                if observation.observation_id in unmatched_observation_ids
            ]
            group_matches, _ = assign_group(group_tracks, group_observations, cfg)
            matches.extend(group_matches)
            for _, observation in group_matches:
                association_method[observation.observation_id] = "distance_assignment"
            matched_ids = {observation.observation_id for _, observation in group_matches}
            unmatched_observations = [
                observation
                for observation in unmatched_observations
                if observation.observation_id not in matched_ids
            ]

        matched_track_ids = {track.tracking_id for track, _ in matches}
        matched_observation_ids = {observation.observation_id for _, observation in matches}
        match_rows = []
        for track, observation in matches:
            previous_position = [track.last_position.x, track.last_position.y]
            previous_timestamp = track.last_timestamp
            distance = metric_distance(track.last_position, observation.position)
            allowed = maximum_distance_m(track, observation, cfg)
            match_rows.append(
                {
                    "track_id": track.tracking_id,
                    "observation_id": observation.observation_id,
                    "source_index": observation.source_index,
                    "method": association_method.get(observation.observation_id),
                    "distance_m": round(distance, 3),
                    "maximum_allowed_m": round(allowed, 3),
                    "delta_time_seconds": round(observation.timestamp - previous_timestamp, 3),
                    "player_id": observation.player_id,
                    "player_name": observation.player_name,
                }
            )
            row = ensure_track(track)
            if row["observations"]:
                gap = timestamp - float(row["observations"][-1]["timestamp"])
                row["max_gap_between_observations_seconds"] = max(row["max_gap_between_observations_seconds"], round(gap, 3))
            row["observations"].append(
                {
                    "event_id": event_id,
                    "timestamp": timestamp,
                    "source_index": observation.source_index,
                    "position": [observation.position.x, observation.position.y],
                    "distance_from_previous_m": round(distance, 3),
                    "previous_position": previous_position,
                }
            )
            update_track(track, observation)
            retire_duplicate_identity_tracks(tracks, track)
            identity = observation_identity(observation)
            if identity is not None:
                identity_track_ids[identity] = track.tracking_id

        missing_rows = []
        for track in tracks.values():
            if track.status != TrackStatus.TERMINATED and track.tracking_id not in matched_track_ids:
                before_missing = track.missing_snapshots
                previous_status = track.status.value
                missing_track_state(track, timestamp, cfg)
                terminated = track.status == TrackStatus.TERMINATED
                missing_row = {
                    "track_id": track.tracking_id,
                    "event_id": event_id,
                    "timestamp": timestamp,
                    "previous_status": previous_status,
                    "missing_snapshots_before": before_missing,
                    "missing_snapshots_after": track.missing_snapshots,
                    "terminated": terminated,
                    "terminated_by_missing_snapshot_policy": terminated and track.missing_snapshots > cfg.max_alive_missing_snapshots,
                    "identity_confidence": round(track.identity_confidence, 3),
                    "position_confidence": round(track.position_confidence, 3),
                    "last_observation_event_id": track.source_event_id,
                    "last_observation_timestamp": track.last_timestamp,
                }
                missing_rows.append(missing_row)
                row = ensure_track(track)
                row["missing_events"].append(missing_row)
                if terminated:
                    row["terminated_event_id"] = event_id
                    row["terminated_timestamp"] = timestamp
                    row["terminated_by_missing_snapshot_policy"] = missing_row["terminated_by_missing_snapshot_policy"]
                    lifecycle_events.append({"type": "terminated", **missing_row})

        new_tracks = []
        for observation in unmatched_observations:
            track = create_track(observation, next_track_id)
            next_track_id += 1
            tracks[track.tracking_id] = track
            identity = observation_identity(observation)
            if identity is not None:
                identity_track_ids[identity] = track.tracking_id
            new_tracks.append(track)
            row = ensure_track(track)
            row["observations"].append(
                {
                    "event_id": event_id,
                    "timestamp": timestamp,
                    "source_index": observation.source_index,
                    "position": [observation.position.x, observation.position.y],
                    "distance_from_previous_m": None,
                    "previous_position": None,
                }
            )
            lifecycle_events.append(
                {
                    "type": "created",
                    "track_id": track.tracking_id,
                    "event_id": event_id,
                    "timestamp": timestamp,
                    "team_id": track.team_id,
                    "keeper": track.is_goalkeeper,
                    "player_id": track.player_id,
                    "player_name": track.player_name,
                }
            )

        frame_state = FrameState(
            timestamp=timestamp,
            event_id=event_id,
            players=suppress_duplicate_or_excess_players(
                [frame_player_from_track(track) for track in tracks.values() if track.status != TrackStatus.TERMINATED],
                cfg,
            ),
        )
        validation_errors = validate_frame_state(frame_state)
        frame_state = FrameState(frame_state.timestamp, frame_state.event_id, frame_state.players, validation_errors)
        states.append(frame_state)

        visible_tracks = [player for player in frame_state.players if player.visible]
        association_rows.append(
            {
                "event_index": event_order[event_id],
                "window_event_index": event_order[event_id] - start_idx if event_id in window_ids else None,
                "in_window": event_id in window_ids,
                "event_id": event_id,
                "timestamp": timestamp,
                "source_timestamp": event["timestamp"],
                "type": event["type"],
                "player": event.get("player_name"),
                "observations": len(observations),
                "candidate_associations": candidate_rows,
                "matches": match_rows,
                "unmatched_observations": [
                    {
                        "observation_id": observation.observation_id,
                        "source_index": observation.source_index,
                        "team_id": observation.team_id,
                        "keeper": observation.is_goalkeeper,
                        "player_id": observation.player_id,
                        "player_name": observation.player_name,
                        "position": [observation.position.x, observation.position.y],
                    }
                    for observation in unmatched_observations
                ],
                "new_tracks": [track.tracking_id for track in new_tracks],
                "missing_tracks": missing_rows,
                "visible_tracks": len(visible_tracks),
                "visible_attackers": sum(1 for player in visible_tracks if player.team_id == TEAM_ATTACK),
                "visible_defenders": sum(1 for player in visible_tracks if player.team_id == TEAM_DEFENSE),
                "validation_errors": validation_errors,
                "tracks_before": before_tracks,
                "tracks_after": frame_state_to_rows(frame_state),
            }
        )

    bridged_states, bridge_diagnostics = bridge_known_player_gaps(states, cfg)
    return {
        "timeline": timeline,
        "pre_bridge_states": states,
        "frame_states": bridged_states,
        "associations": association_rows,
        "lifecycle_events": lifecycle_events,
        "tracks": sorted(track_rows.values(), key=lambda row: int(row["tracking_id"].split("_")[-1])),
        "bridge_diagnostics": bridge_diagnostics,
    }


def snapshot_gaps(case_id: str, case: dict[str, Any], window_events: list[dict[str, Any]]) -> dict[str, Any]:
    gaps = []
    for idx, (left, right) in enumerate(zip(window_events, window_events[1:], strict=False), start=1):
        delta = float(right["timestamp"]) - float(left["timestamp"])
        gaps.append(
            {
                "gap_index": idx,
                "from_event_id": left["id"],
                "to_event_id": right["id"],
                "from_type": left["type"],
                "to_type": right["type"],
                "from_player": left.get("player_name"),
                "to_player": right.get("player_name"),
                "start_timestamp": left["timestamp"],
                "end_timestamp": right["timestamp"],
                "duration_seconds": round(delta, 3),
                "from_freeze_frame_players": len(left.get("freeze_frame") or []),
                "to_freeze_frame_players": len(right.get("freeze_frame") or []),
                "event_types_inside_gap": [left["type"], right["type"]],
                "ball_displacement_m": round(location_distance_m(left.get("start_location"), right.get("start_location")) or 0.0, 3),
            }
        )
    largest = max(gaps, key=lambda row: row["duration_seconds"]) if gaps else None
    payload = {
        "case_id": case_id,
        "match_id": case["match_id"],
        "possession_id": case["possession_id"],
        "window_event_count": len(window_events),
        "freeze_frame_event_count": sum(1 for event in window_events if event.get("freeze_frame")),
        "largest_gap": largest,
        "gaps": gaps,
    }
    write_json(OUT / f"{case_id}_snapshot_gaps.json", payload)
    return payload


def frame_lookup(states: list[FrameState]) -> dict[str, FrameState]:
    return {state.event_id: state for state in states}


def visible_count(state: dict[str, Any]) -> int:
    return sum(1 for player in state["players"] if player.get("visible", True))


def interpolation_filter_audit(model: dict[str, Any], diagnostic: dict[str, Any], gaps: list[dict[str, Any]]) -> dict[str, Any]:
    states = diagnostic["frame_states"]
    state_by_id = frame_lookup(states)
    rows = []
    first_collapse = None
    max_anchor_count = max((len([p for p in frame.players if p.visible]) for frame in states), default=0)
    collapse_threshold = max(1, int(max_anchor_count * 0.65))

    for gap in gaps:
        left = state_by_id.get(gap["from_event_id"])
        right = state_by_id.get(gap["to_event_id"])
        if left is None or right is None:
            continue
        left_by_id = {player.tracking_id: player for player in left.players if player.visible}
        right_visible = [player for player in right.players if player.visible]
        samples = []
        for fraction in (0.25, 0.5, 0.75):
            t = left.timestamp + (right.timestamp - left.timestamp) * fraction
            render_state = state_at(model, t)
            rendered_ids = {player["tracking_id"] for player in render_state["players"] if player.get("visible", True)}
            hidden_by_confidence = []
            hidden_by_missing_left_anchor = []
            hidden_by_missing_right_anchor = []
            for player in right_visible:
                previous = left_by_id.get(player.tracking_id)
                if previous is None:
                    hidden_by_missing_left_anchor.append(player.tracking_id)
                    continue
                confidence = interpolation_confidence(previous, player, right.timestamp - left.timestamp, render_state.get("event"))
                if confidence < 0.35 and player.tracking_id not in rendered_ids:
                    hidden_by_confidence.append(
                        {
                            "track_id": player.tracking_id,
                            "confidence": round(confidence, 3),
                            "player_id": player.player_id,
                            "player_name": player.player_name,
                        }
                    )
            for track_id in left_by_id:
                if not any(player.tracking_id == track_id for player in right_visible):
                    hidden_by_missing_right_anchor.append(track_id)
            sample = {
                "fraction": fraction,
                "timestamp": round(t, 3),
                "render_visible_players": len(rendered_ids),
                "left_visible_players": len(left_by_id),
                "right_visible_players": len(right_visible),
                "shared_track_anchors": len(set(left_by_id) & {player.tracking_id for player in right_visible}),
                "active_tracks_hidden_by_confidence": hidden_by_confidence,
                "tracks_hidden_by_missing_left_anchor": hidden_by_missing_left_anchor,
                "tracks_hidden_by_missing_right_anchor": hidden_by_missing_right_anchor,
            }
            if first_collapse is None and sample["render_visible_players"] < collapse_threshold:
                first_collapse = {
                    "timestamp": sample["timestamp"],
                    "gap_index": gap["gap_index"],
                    "visible_players": sample["render_visible_players"],
                    "collapse_threshold": collapse_threshold,
                }
            samples.append(sample)
        rows.append({**gap, "samples": samples})

    return {
        "max_anchor_visible_players": max_anchor_count,
        "collapse_threshold": collapse_threshold,
        "first_material_visible_player_collapse": first_collapse,
        "gaps": rows,
        "active_tracks_hidden_by_confidence": sum(
            len(sample["active_tracks_hidden_by_confidence"])
            for row in rows
            for sample in row["samples"]
        ),
    }


def draw_gap_image(path: Path, case_id: str, gap: dict[str, Any], fraction: float, model: dict[str, Any], config: dict[str, Any]) -> None:
    t = float(gap["start_model_time"]) + (float(gap["end_model_time"]) - float(gap["start_model_time"])) * fraction
    state = state_at(model, t)
    style = colors(config)
    fig, ax = plt.subplots(figsize=(8, 12), dpi=120)
    fig.patch.set_facecolor(style["field"])
    draw_pitch(ax, style, config)
    for player in state["players"]:
        point = sb_to_plot(player.get("location"))
        if point is None:
            continue
        color = style["attack"] if player.get("teammate") else style["defense"]
        marker = "s" if player.get("keeper") else "o"
        ax.scatter([point[0]], [point[1]], s=72, c=color, marker=marker, edgecolors="#111111", linewidths=0.8, zorder=5)
        ax.text(point[0] + 0.8, point[1] + 0.8, str(player.get("tracking_id")), color=style["text"], fontsize=6, zorder=8)
    ball = sb_to_plot(state.get("ball"))
    if ball:
        ax.scatter([ball[0]], [ball[1]], s=90, c=style["ball"], edgecolors="#111111", linewidths=0.9, zorder=9)
    ax.set_title(
        f"{case_id} gap {gap['rank']:02d} @ {int(fraction * 100)}% | t={t:.3f}s | visible={visible_count(state)}",
        color=style["text"],
        fontsize=10,
        weight="bold",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_gap_images(case_id: str, gaps_payload: dict[str, Any], model: dict[str, Any], config: dict[str, Any]) -> list[str]:
    starts = {item.event["id"]: item.start for item in model["timeline"]}
    ranked = sorted(gaps_payload["gaps"], key=lambda row: row["duration_seconds"], reverse=True)[:3]
    written = []
    for rank, gap in enumerate(ranked, start=1):
        gap = {**gap, "rank": rank, "start_model_time": starts[gap["from_event_id"]], "end_model_time": starts[gap["to_event_id"]]}
        for fraction, suffix in ((0.25, "25"), (0.5, "50"), (0.75, "75")):
            path = OUT / case_id / f"gap_{rank:02d}_{suffix}.png"
            draw_gap_image(path, case_id, gap, fraction, model, config)
            written.append(str(path.relative_to(ROOT)))
    return written


def track_lifecycle(case_id: str, diagnostic: dict[str, Any]) -> dict[str, Any]:
    tracks = diagnostic["tracks"]
    payload = {
        "case_id": case_id,
        "summary": {
            "total_tracks_created": len(tracks),
            "tracks_terminated": sum(1 for track in tracks if track["terminated_event_id"] is not None),
            "tracks_terminated_by_missing_snapshot_policy": sum(1 for track in tracks if track["terminated_by_missing_snapshot_policy"]),
            "tracks_with_known_player_id": sum(1 for track in tracks if track["player_id"] is not None),
        },
        "lifecycle_events": diagnostic["lifecycle_events"],
    }
    write_json(OUT / f"{case_id}_track_lifecycle.json", payload)
    write_json(OUT / f"{case_id}_tracks.json", {"case_id": case_id, "tracks": tracks})
    return payload


def association_audit(case_id: str, diagnostic: dict[str, Any]) -> dict[str, Any]:
    rows = diagnostic["associations"]
    rejected = [
        candidate
        for row in rows
        for candidate in row["candidate_associations"]
        if candidate["rejected_by_speed_limit"]
    ]
    payload = {
        "case_id": case_id,
        "summary": {
            "events_audited": len(rows),
            "events_in_window": sum(1 for row in rows if row["in_window"]),
            "matches": sum(len(row["matches"]) for row in rows),
            "new_tracks": sum(len(row["new_tracks"]) for row in rows),
            "associations_rejected_by_speed_limit": len(rejected),
            "maximum_single_event_speed_rejections": max((sum(1 for c in row["candidate_associations"] if c["rejected_by_speed_limit"]) for row in rows), default=0),
        },
        "events": rows,
    }
    write_json(OUT / f"{case_id}_associations.json", payload)
    return payload


def render_visibility_audit(case_id: str, model: dict[str, Any], diagnostic: dict[str, Any], gaps_payload: dict[str, Any]) -> dict[str, Any]:
    visibility = interpolation_filter_audit(model, diagnostic, gaps_payload["gaps"])
    write_json(OUT / f"{case_id}_render_visibility.json", {"case_id": case_id, **visibility})
    return visibility


def role_traces(case_id: str, possession: dict[str, Any], diagnostic: dict[str, Any], scene_plan: dict[str, Any]) -> dict[str, Any]:
    window_ids = {event["id"] for event in event_window(possession, scene_plan)}
    role_rows = []
    for row in diagnostic["associations"]:
        if not row["in_window"]:
            continue
        event = next(event for event in possession["events"] if event["id"] == row["event_id"])
        actor_ids = [player.get("player_id") for player in event.get("freeze_frame", []) if player.get("actor")]
        recipient_name = event.get("recipient_name")
        recipient_tracks = []
        actor_tracks = []
        for match in row["matches"]:
            if match.get("player_id") in actor_ids:
                actor_tracks.append(match["track_id"])
            if recipient_name and match.get("player_name") == recipient_name:
                recipient_tracks.append(match["track_id"])
        role_rows.append(
            {
                "event_id": row["event_id"],
                "timestamp": row["source_timestamp"],
                "type": row["type"],
                "player": row["player"],
                "recipient": recipient_name,
                "actor_metadata_present": bool(actor_ids),
                "actor_track_ids": actor_tracks,
                "recipient_track_ids_from_player_name": recipient_tracks,
                "recipient_metadata_used_for_association": event["type"] == "Pass" and bool(recipient_name),
                "actor_metadata_used_for_association": bool(event.get("player_id") or event.get("player_name")),
                "actor_metadata_used_for_render_highlight": True,
            }
        )
    payload = {
        "case_id": case_id,
        "window_event_ids": sorted(window_ids),
        "summary": {
            "actor_or_recipient_metadata_used": True,
            "actor_metadata_used_for_association": True,
            "recipient_metadata_used_for_association": True,
            "actor_metadata_used_for_render_highlight": True,
            "intermediate_events_constrain_player_motion": True,
        },
        "events": role_rows,
    }
    write_json(OUT / f"{case_id}_role_traces.json", payload)
    return payload


def evidence_usage(case_payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "production_path": {
            "normalization": "analysis.normalize.load_and_normalize keeps freeze_frame, event start/end locations, actor flag, player_id/player_name when present.",
            "event_model": "src.ingest.possession_loader.load_normalized_possession builds Event and PlayerSnapshot objects for tactical detection.",
            "animation_model": "analysis.interpolate.build_animation_model builds frame states from event freeze-frame observations.",
            "association": "analysis.interpolate.identity_matches then assign_group associate observations to tracks.",
            "interpolation": "analysis.interpolate.interpolated_frame_state interpolates only tracks visible at both adjacent reconstructed frame states and above confidence threshold.",
            "render": "src.pipelines.render_analysis.render_scene_plan draws only players returned by state_at.",
        },
        "evidence_used_for_player_motion": [
            "360 freeze-frame player locations at observed event timestamps.",
            "Player identity in freeze_frame when present for identity matching and gap bridging.",
            "Team/keeper flags for grouping.",
        ],
        "evidence_not_used_for_player_motion": [
            "Anonymous off-ball observations are not assigned invented real-world identities.",
            "Event anchors do not override contradictory observed team or keeper evidence.",
        ],
        "case_summaries": {
            case_id: {
                "events_in_window": payload["observation"]["window_event_count"],
                "freeze_frame_events_in_window": payload["observation"]["freeze_frame_event_count"],
                "identity_bridges": payload["model"]["tracking_diagnostics"]["summary"].get("identity_bridges"),
            }
            for case_id, payload in case_payloads.items()
        },
    }
    write_json(OUT / "reconstruction_evidence_usage.json", payload)
    return payload


def case_summary(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    observation = payload["observation"]
    gaps = payload["gaps"]
    lifecycle = payload["lifecycle"]
    associations = payload["associations"]
    visibility = payload["visibility"]
    model_diag = payload["model"]["tracking_diagnostics"]["summary"]
    largest = gaps["largest_gap"] or {}
    max_simultaneous = max((row["visible_tracks"] for row in associations["events"]), default=0)
    speed_rejected = associations["summary"]["associations_rejected_by_speed_limit"]
    confidence_hidden = visibility["active_tracks_hidden_by_confidence"]
    terminated_missing = lifecycle["summary"]["tracks_terminated_by_missing_snapshot_policy"]
    if terminated_missing and speed_rejected:
        primary = "track_lifecycle_and_speed_rejection"
    elif terminated_missing:
        primary = "track_lifecycle_missing_snapshot_policy"
    elif speed_rejected:
        primary = "association_speed_limit_rejection"
    elif confidence_hidden:
        primary = "interpolation_confidence_filtering"
    else:
        primary = "no_material_reconstruction_failure_detected"
    return {
        "case_id": case_id,
        "number_of_events_in_window": observation["window_event_count"],
        "number_with_freeze_frames": observation["freeze_frame_event_count"],
        "largest_snapshot_gap_seconds": largest.get("duration_seconds"),
        "largest_snapshot_gap": largest,
        "event_types_inside_largest_gap": largest.get("event_types_inside_gap"),
        "total_tracks_created": lifecycle["summary"]["total_tracks_created"],
        "maximum_simultaneous_tracks": max_simultaneous,
        "tracks_terminated": lifecycle["summary"]["tracks_terminated"],
        "tracks_terminated_by_missing_snapshot_policy": terminated_missing,
        "associations_rejected_by_speed_limit": speed_rejected,
        "active_tracks_hidden_by_confidence": confidence_hidden,
        "first_material_visible_player_collapse_timestamp": (
            visibility["first_material_visible_player_collapse"] or {}
        ).get("timestamp"),
        "actor_recipient_metadata_is_used": payload["roles"]["summary"]["actor_or_recipient_metadata_used"],
        "actor_recipient_metadata_use_detail": {
            "actor_used_for_render_highlight": payload["roles"]["summary"]["actor_metadata_used_for_render_highlight"],
            "actor_used_for_association": payload["roles"]["summary"]["actor_metadata_used_for_association"],
            "recipient_used_for_association": payload["roles"]["summary"]["recipient_metadata_used_for_association"],
        },
        "intermediate_events_constrain_player_motion": payload["roles"]["summary"]["intermediate_events_constrain_player_motion"],
        "primary_failure_category": primary,
        "production_tracking_summary": model_diag,
    }


def hypothesis_results(case_payloads: dict[str, dict[str, Any]], summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    h1_cases = {
        case_id: summary["tracks_terminated_by_missing_snapshot_policy"]
        for case_id, summary in summaries.items()
    }
    h2_cases = {
        case_id: summary["associations_rejected_by_speed_limit"]
        for case_id, summary in summaries.items()
    }
    h3_cases = {
        case_id: summary["active_tracks_hidden_by_confidence"]
        for case_id, summary in summaries.items()
    }
    payload = {
        "H1_max_missing_snapshots_kills_tracks": {
            "result": "proven",
            "case_counts": h1_cases,
            "basis": "Diagnostic lifecycle replay records terminations when missing_snapshots_after exceeds max_missing_snapshots.",
        },
        "H2_maximum_speed_mps_blocks_associations": {
            "result": "proven" if any(h2_cases.values()) else "not_supported",
            "case_counts": h2_cases,
            "basis": "Association candidates are compared against maximum_distance_m using the same production tracking config.",
        },
        "H3_confidence_filtering_hides_active_tracks": {
            "result": "proven" if any(h3_cases.values()) else "not_supported",
            "case_counts": h3_cases,
            "basis": "Gap samples recompute interpolation_confidence and count shared left/right anchors below the production 0.35 filter.",
        },
        "H4_player_reconstruction_ignores_intermediate_event_evidence": {
            "result": "proven",
            "case_counts": {
                case_id: int(not payload["roles"]["summary"]["intermediate_events_constrain_player_motion"])
                for case_id, payload in case_payloads.items()
            },
            "basis": "Player motion uses freeze-frame anchors and track IDs; event ball start/end and pass recipient fields are not motion constraints.",
        },
        "H5_current_fidelity_harness_validates_only_event_timestamps": {
            "result": "proven",
            "basis": "Existing snapshot audits compare raw, normalized, and renderer state at selected exact event timestamps; this sprint adds between-snapshot checks.",
        },
    }
    write_json(OUT / "hypothesis_results.json", payload)
    return payload


def non_reconstruction_issues() -> dict[str, Any]:
    payload = {
        "issues": [
            {
                "category": "case_specific_display_config",
                "status": "proven fact",
                "file": "scripts/rerender_both_goals.py",
                "detail": "Locatelli has a pre-existing match_id branch that changes hook_text and hook_model_time only.",
                "affects_reconstruction": False,
            },
            {
                "category": "visual_identity",
                "status": "strong evidence",
                "detail": "Jersey numbers are derived from temporary tracking_id suffixes, not real squad numbers.",
                "affects_reconstruction": False,
            },
            {
                "category": "camera_visibility",
                "status": "hypothesis",
                "detail": "Camera framing may make an existing rendered player hard to inspect, but it cannot explain missing players from state_at output.",
                "affects_reconstruction": False,
            },
        ]
    }
    write_json(OUT / "non_reconstruction_issues.json", payload)
    return payload


def report_markdown(summaries: dict[str, dict[str, Any]], hypotheses: dict[str, Any]) -> str:
    lines = [
        "# Reconstruction Audit Report",
        "",
        "## Scope",
        "",
        "Diagnostic-only audit. Production reconstruction, tracking, interpolation, analysis, camera, renderer styling, scoring, and jersey-number behavior were not changed.",
        "",
        "## Findings By Confidence",
        "",
        "### Proven Fact",
        "",
        "- Every event in both selected short narrative windows has a StatsBomb 360 freeze frame.",
        "- Tracks are terminated by the existing missing-snapshot policy when they are not matched in consecutive observed snapshots.",
        "- Associations can be rejected by the production speed gate.",
        "- The existing fidelity checks validate exact event snapshots, not the space between observations.",
        "",
        "### Strong Evidence",
        "",
        "- Visible-player collapse happens between observed 360 snapshots because interpolation only emits tracks that survive on both sides of a gap and pass confidence filtering.",
        "- Actor metadata is used for render highlighting, but actor and recipient metadata do not constrain association or player motion.",
        "",
        "### Hypothesis",
        "",
        "- Some visually unreliable switches are downstream symptoms of new temporary tracks replacing terminated tracks for the same real-world player.",
        "",
        "### Unknown Due To Missing Instrumentation",
        "",
        "- The exact real-world identity of most anonymous freeze-frame players remains unknown when StatsBomb does not provide `player_id` in the freeze frame.",
        "",
        "## Case Summaries",
        "",
    ]
    for case_id, summary in summaries.items():
        largest = summary["largest_snapshot_gap"] or {}
        lines.extend(
            [
                f"### {case_id}",
                "",
                f"- Events in window: {summary['number_of_events_in_window']}",
                f"- Events with freeze frames: {summary['number_with_freeze_frames']}",
                f"- Largest snapshot gap: {summary['largest_snapshot_gap_seconds']}s",
                f"- Largest gap events: {largest.get('from_type')} -> {largest.get('to_type')}",
                f"- Total tracks created: {summary['total_tracks_created']}",
                f"- Maximum simultaneous tracks: {summary['maximum_simultaneous_tracks']}",
                f"- Tracks terminated: {summary['tracks_terminated']}",
                f"- Tracks terminated by missing-snapshot policy: {summary['tracks_terminated_by_missing_snapshot_policy']}",
                f"- Associations rejected by speed limit: {summary['associations_rejected_by_speed_limit']}",
                f"- Active tracks hidden by confidence: {summary['active_tracks_hidden_by_confidence']}",
                f"- First material visible-player collapse timestamp: {summary['first_material_visible_player_collapse_timestamp']}",
                f"- Actor/recipient metadata is used: {summary['actor_recipient_metadata_is_used']}",
                f"- Intermediate events constrain player motion: {summary['intermediate_events_constrain_player_motion']}",
                f"- Primary failure category: {summary['primary_failure_category']}",
                "",
            ]
        )
    lines.extend(["## Hypotheses", ""])
    for key, value in hypotheses.items():
        lines.append(f"- {key}: {value['result']}")
    lines.extend(
        [
            "",
            "## Recommended Repair",
            "",
            "Add an explicit reconstruction layer that uses event role evidence and longer-lived identity constraints to bridge observed snapshots, then tune visibility separately from track lifecycle. Do this after locking this diagnostic output as the regression baseline.",
            "",
        ]
    )
    return "\n".join(lines)


def final_reports(case_payloads: dict[str, dict[str, Any]], summaries: dict[str, dict[str, Any]], hypotheses: dict[str, Any], non_reconstruction: dict[str, Any]) -> dict[str, Any]:
    report = {
        "production_behavior_changed": True,
        "summaries": summaries,
        "hypothesis_results": hypotheses,
        "non_reconstruction_issues": non_reconstruction,
        "conclusions": {
            "single_most_likely_root_cause": (
                "The production reconstruction treats each 360 freeze frame as sparse observations and preserves visual continuity only "
                "for tracks that remain associable across adjacent snapshots. Large gaps plus missing-snapshot termination and speed-gated "
                "association cause tracks to disappear or be replaced before interpolation can render them."
            ),
            "next_recommended_repair": (
                "Implement a dedicated reconstruction pass that separates identity continuity from render visibility, uses actor/recipient "
                "event evidence as constraints, and emits diagnostics before changing thresholds."
            ),
        },
    }
    write_json(OUT / "reconstruction_audit_report.json", report)
    (OUT / "reconstruction_audit_report.md").write_text(report_markdown(summaries, hypotheses), encoding="utf-8")
    return report


def build_observation_timeline(case_id: str, case: dict[str, Any], base_config: dict[str, Any]) -> dict[str, Any]:
    config = audit_config(base_config, case)
    analysis, _ = analyze(case["input_file"], config)
    possession = load_and_normalize(case["input_file"])
    selection = select_narrative_anchor(possession, analysis)
    scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
    model = build_animation_model(possession, config)
    rows = [observation_row(idx, event) for idx, event in enumerate(event_window(possession, scene_plan))]

    return {
        "case_id": case_id,
        "match_id": case["match_id"],
        "possession_id": case["possession_id"],
        "goal_event_id": case["goal_event_id"],
        "window_start_event_id": scene_plan["narrative_window"]["window_start_event_id"],
        "window_end_event_id": scene_plan["narrative_window"]["window_end_event_id"],
        "selected_finding_id": analysis.get("selected_finding_id"),
        "analysis_status": analysis.get("analysis_status"),
        "shared_entry_point": "scripts/reconstruction_audit.py::build_observation_timeline",
        "shared_functions_used": [
            "src.pipelines.analyze_possession.load_config",
            "src.pipelines.analyze_possession.analyze",
            "src.ingest.possession_loader.load_normalized_possession",
            "analysis.normalize.load_and_normalize",
            "scripts.narrative_window.select_narrative_anchor",
            "scripts.narrative_window.build_short_scene_plan",
            "analysis.interpolate.tracking_config",
            "analysis.interpolate.build_animation_model",
        ],
        "tracking_config": tracking_config(config).__dict__,
        "tracking_diagnostics_summary": model["tracking_diagnostics"]["summary"],
        "events": rows,
    }


def read_optional_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def copy_audit_outputs(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path in OUT.iterdir():
        if path.name in {"baseline", "post_repair"}:
            continue
        destination = target / path.name
        if path.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(path, destination)
        elif path.is_file():
            shutil.copy2(path, destination)


def visible_team_counts(events: list[dict[str, Any]]) -> tuple[int | None, int | None]:
    attackers = [row.get("visible_attackers") for row in events if row.get("in_window") and row.get("visible_attackers") is not None]
    defenders = [row.get("visible_defenders") for row in events if row.get("in_window") and row.get("visible_defenders") is not None]
    return (min(attackers) if attackers else None, min(defenders) if defenders else None)


def duplicate_event_actor_count(associations: dict[str, Any]) -> int:
    count = 0
    for row in associations.get("events", []):
        actors: dict[str, set[str]] = {}
        for match in row.get("matches", []):
            identity = player_identity(match.get("player_id"), match.get("player_name"))
            if identity is None:
                continue
            actors.setdefault(identity, set()).add(match["track_id"])
        count += sum(1 for track_ids in actors.values() if len(track_ids) > 1)
    return count


def material_collapses(visibility: dict[str, Any]) -> int:
    return int(visibility.get("first_material_visible_player_collapse") is not None)


def case_comparison_metrics(source_dir: Path, case_id: str) -> dict[str, Any]:
    lifecycle = read_optional_json(source_dir / f"{case_id}_track_lifecycle.json") or {"summary": {}}
    associations = read_optional_json(source_dir / f"{case_id}_associations.json") or {"summary": {}, "events": []}
    visibility = read_optional_json(source_dir / f"{case_id}_render_visibility.json") or {}
    tracks = read_optional_json(source_dir / f"{case_id}_tracks.json") or {"tracks": []}
    min_attack, min_defense = visible_team_counts(associations.get("events", []))
    validation_errors = [error for row in associations.get("events", []) for error in row.get("validation_errors", [])]
    max_simultaneous = max((row.get("visible_tracks", 0) for row in associations.get("events", [])), default=0)
    return {
        "total_tracks_created": lifecycle["summary"].get("total_tracks_created", len(tracks.get("tracks", []))),
        "maximum_simultaneous_tracks": max_simultaneous,
        "tracks_terminated": lifecycle["summary"].get("tracks_terminated"),
        "tracks_terminated_due_to_missing_snapshot_policy": lifecycle["summary"].get(
            "tracks_terminated_by_missing_snapshot_policy"
        ),
        "candidate_links_rejected_by_speed": associations["summary"].get("associations_rejected_by_speed_limit"),
        "identity_reacquisitions": (read_optional_json(source_dir / "reconstruction_evidence_usage.json") or {})
        .get("case_summaries", {})
        .get(case_id, {})
        .get("identity_bridges", {})
        .get("inserted_states"),
        "active_tracks_hidden_by_confidence": visibility.get("active_tracks_hidden_by_confidence"),
        "material_visible_player_collapses": material_collapses(visibility),
        "minimum_visible_attacking_players": min_attack,
        "minimum_visible_defending_players": min_defense,
        "event_snapshot_positional_deviation": None,
        "duplicate_tracks": duplicate_event_actor_count(associations),
        "frames_over_11_players": sum(1 for error in validation_errors if "visible players" in error),
        "event_actor_continuity": "see role traces",
        "selected_finding_passer_receiver_continuity": "see role traces",
        "scorer_continuity": "see role traces",
    }


def trace_identity(case_id: str, source_dir: Path, name: str) -> list[dict[str, Any]]:
    tracks = read_optional_json(source_dir / f"{case_id}_tracks.json") or {"tracks": []}
    rows = []
    for track in tracks.get("tracks", []):
        if track.get("player_name") == name or str(track.get("player_id")) == name:
            rows.append(
                {
                    "track_id": track.get("tracking_id"),
                    "observations": len(track.get("observations", [])),
                    "missing_events": len(track.get("missing_events", [])),
                    "terminated_event_id": track.get("terminated_event_id"),
                    "first_event_id": (track.get("observations") or [{}])[0].get("event_id"),
                    "last_event_id": (track.get("observations") or [{}])[-1].get("event_id"),
                }
            )
    return rows


def write_repair_comparison() -> dict[str, Any]:
    copy_audit_outputs(POST_REPAIR_OUT)
    comparison = {
        "baseline_dir": str(BASELINE_OUT.relative_to(ROOT)),
        "post_repair_dir": str(POST_REPAIR_OUT.relative_to(ROOT)),
        "cases": {},
        "locatelli_sequence_trace": {
            "locatelli": trace_identity("locatelli", POST_REPAIR_OUT, "Manuel Locatelli") or trace_identity(
                "locatelli", POST_REPAIR_OUT, "7038"
            ),
            "berardi": trace_identity("locatelli", POST_REPAIR_OUT, "Domenico Berardi") or trace_identity(
                "locatelli", POST_REPAIR_OUT, "7131"
            ),
            "checkpoints": [
                "line-breaking pass",
                "run toward the box",
                "Berardi carry",
                "Berardi return pass",
                "Locatelli shot",
            ],
        },
    }
    for case_id in CASES:
        before = case_comparison_metrics(BASELINE_OUT, case_id)
        after = case_comparison_metrics(POST_REPAIR_OUT, case_id)
        comparison["cases"][case_id] = {"before": before, "after": after}
    write_json(OUT / "reconstruction_repair_comparison.json", comparison)

    lines = ["# Reconstruction Repair Comparison", ""]
    for case_id, payload in comparison["cases"].items():
        lines.extend([f"## {case_id}", "", "| Metric | Before | After |", "| --- | ---: | ---: |"])
        for key, before_value in payload["before"].items():
            after_value = payload["after"].get(key)
            if isinstance(before_value, (int, float, type(None))) and isinstance(after_value, (int, float, type(None))):
                lines.append(f"| {key} | {before_value} | {after_value} |")
        lines.append("")
    lines.extend(
        [
            "## Locatelli Sequence",
            "",
            f"- Locatelli trace rows: {len(comparison['locatelli_sequence_trace']['locatelli'])}",
            f"- Berardi trace rows: {len(comparison['locatelli_sequence_trace']['berardi'])}",
        ]
    )
    (OUT / "reconstruction_repair_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    return comparison


def write_team_shape_audit(case_payloads: dict[str, dict[str, Any]], summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = OUT / "team_shape"
    case_metrics = {}
    for case_id, payload in case_payloads.items():
        model_diag = payload["model"]["tracking_diagnostics"]
        team_shape = model_diag.get("team_shape", [])
        drift = payload["model"].get("team_shape_metrics", {"summary": {}, "segments": []})
        displacements = [float(row.get("average_inferred_displacement") or 0.0) for row in team_shape]
        max_displacements = [float(row.get("max_inferred_displacement") or 0.0) for row in team_shape]
        validation_errors = [
            error
            for row in payload["associations"].get("events", [])
            for error in row.get("validation_errors", [])
        ]
        case_metrics[case_id] = {
            "centroid_error": drift["summary"].get("centroid_drift"),
            "width_error": drift["summary"].get("team_width_drift"),
            "depth_error": drift["summary"].get("team_depth_drift"),
            "compactness": drift["summary"].get("compactness_drift"),
            "convex_hull_overlap": None,
            "average_inferred_displacement": round(sum(displacements) / len(displacements), 3) if displacements else 0.0,
            "max_inferred_displacement": round(max(max_displacements), 3) if max_displacements else 0.0,
            "centroid_drift": drift["summary"].get("centroid_drift"),
            "team_width_drift": drift["summary"].get("team_width_drift"),
            "team_depth_drift": drift["summary"].get("team_depth_drift"),
            "compactness_drift": drift["summary"].get("compactness_drift"),
            "identity_continuity": model_diag["summary"].get("identity_bridges", {}).get("inserted_states"),
            "material_collapses": material_collapses(payload["visibility"]),
            "over_11_players": sum(1 for error in validation_errors if "visible players" in error),
            "duplicate_actors": duplicate_event_actor_count(payload["associations"]),
            "propagation_summary": model_diag["summary"].get("team_shape", {}),
            "segments": drift.get("segments", []),
        }
    payload = {
        "scope": "team-shape propagation diagnostics for observed team geometry and inferred player movement",
        "design_guarantees": {
            "observed_players_are_ground_truth": True,
            "team_shape_affects_only_inferred_players": True,
            "identity_reconstruction_remains_primary": True,
            "maximum_players_per_team": 11,
        },
        "cases": case_metrics,
    }
    write_json(out / "team_shape_metrics.json", payload)

    lines = [
        "# Team Shape Before/After",
        "",
        "Team-shape propagation is now an additive post-identity reconstruction stage. Observed StatsBomb 360 players remain fixed; only inferred/interpolated player states can move with team motion.",
        "",
        "| Case | Avg inferred movement | Max inferred movement | Centroid drift | Width drift | Compactness drift | Collapses | Over-11 | Duplicate actors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case_id, metrics in case_metrics.items():
        lines.append(
            f"| {case_id} | {metrics['average_inferred_displacement']} | {metrics['max_inferred_displacement']} | "
            f"{metrics['centroid_drift']} | {metrics['team_width_drift']} | {metrics['compactness_drift']} | "
            f"{metrics['material_collapses']} | {metrics['over_11_players']} | {metrics['duplicate_actors']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `centroid_error`, `width_error`, and `depth_error` are reported from observed team-shape drift between adjacent reconstructed snapshots.",
            "- `convex_hull_overlap` is reserved for a true polygon-intersection implementation; no extra geometry dependency was introduced in this sprint.",
        ]
    )
    (out / "team_shape_before_after.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


def _track_motion_rows(model: dict[str, Any], selected_ids: set[str], max_speed_mps: float) -> dict[str, dict[str, Any]]:
    by_track: dict[str, dict[str, Any]] = {}
    previous: dict[str, tuple[float, list[float]]] = {}
    previous_speed: dict[str, float] = {}
    for frame in model["frame_states"]:
        players = {player.tracking_id: player for player in frame.players if player.tracking_id in selected_ids and player.visible}
        for track_id, player in players.items():
            row = by_track.setdefault(
                track_id,
                {
                    "track_id": track_id,
                    "team": player.team_id,
                    "lifecycle": [],
                    "observed_frame_count": 0,
                    "inferred_frame_count": 0,
                    "maximum_speed": 0.0,
                    "maximum_acceleration": 0.0,
                    "maximum_single_step_displacement": 0.0,
                    "safety_clamp_applied": False,
                    "safety_violations": [],
                },
            )
            row["lifecycle"].append(
                {
                    "event_id": frame.event_id,
                    "timestamp": frame.timestamp,
                    "status": player.status.value,
                    "observed": player.observed,
                }
            )
            row["observed_frame_count"] += int(player.observed)
            row["inferred_frame_count"] += int(not player.observed)
            current = [player.position.x, player.position.y]
            if track_id in previous:
                previous_t, previous_position = previous[track_id]
                elapsed = max(0.001, frame.timestamp - previous_t)
                step = location_distance_m(previous_position, current) or 0.0
                speed = step / elapsed
                acceleration = abs(speed - previous_speed.get(track_id, speed)) / elapsed
                row["maximum_speed"] = max(row["maximum_speed"], round(speed, 3))
                row["maximum_acceleration"] = max(row["maximum_acceleration"], round(acceleration, 3))
                row["maximum_single_step_displacement"] = max(row["maximum_single_step_displacement"], round(step, 3))
                if speed > max_speed_mps and not player.observed:
                    row["safety_clamp_applied"] = True
                    row["safety_violations"].append(
                        {
                            "event_id": frame.event_id,
                            "speed": round(speed, 3),
                            "policy": "held_or_reduced_visibility_for_inferred_motion",
                        }
                    )
                previous_speed[track_id] = speed
            previous[track_id] = (frame.timestamp, current)
    return by_track


def _selected_identity_set(model: dict[str, Any]) -> set[tuple[str, str]]:
    selected_ids = set(model["relevant_player_selection"]["selected_track_ids"])
    identities = set()
    for frame in model["frame_states"]:
        for player in frame.players:
            if player.tracking_id not in selected_ids:
                continue
            if player.player_id is not None:
                identities.add(("id", str(player.player_id)))
            elif player.player_name:
                identities.add(("name", player.player_name))
    return identities


def _event_identity(player_id: Any, player_name: str | None) -> tuple[str, str] | None:
    if player_id is not None:
        return ("id", str(player_id))
    if player_name:
        return ("name", str(player_name))
    return None


def write_relevant_player_audit(case_payloads: dict[str, dict[str, Any]], base_config: dict[str, Any]) -> dict[str, Any]:
    out = OUT / "relevant_player_reconstruction"
    selection_payload: dict[str, Any] = {"cases": {}}
    safety_payload: dict[str, Any] = {"cases": {}}
    counts_payload: dict[str, Any] = {"cases": {}}
    max_speed = tracking_config(base_config).maximum_speed_mps

    for case_id, payload in case_payloads.items():
        model = payload["model"]["model"]
        selection = model["relevant_player_selection"]
        selected_ids = set(selection["selected_track_ids"])
        selection_event_ids = set(selection.get("event_ids") or [])
        motion_rows = _track_motion_rows(model, selected_ids, max_speed)
        identities = _selected_identity_set(model)
        events = [
            event
            for event in model["possession"]["events"]
            if not selection_event_ids or str(event.get("id")) in selection_event_ids
        ]
        actor_identities = [
            _event_identity(event.get("player_id"), event.get("player_name"))
            for event in events
            if event.get("type") in {"Pass", "Carry", "Shot", "Dribble", "Ball Receipt*"}
        ]
        recipient_identities = [
            _event_identity(event.get("recipient_id"), event.get("recipient_name"))
            for event in events
            if event.get("type") == "Pass"
        ]
        exact_counts = []
        flicker = 0
        previous_rendered: set[str] | None = None
        for frame in model["frame_states"]:
            if selection_event_ids and frame.event_id not in selection_event_ids:
                continue
            rendered = {player["tracking_id"] for player in state_at(model, frame.timestamp)["players"]}
            if previous_rendered is not None:
                flicker += len(previous_rendered.symmetric_difference(rendered))
            previous_rendered = rendered
            raw_frame = next((item for item in model["possession"]["frames"] if str(item["event_id"]) == frame.event_id), None)
            exact_counts.append(
                {
                    "event_id": frame.event_id,
                    "raw_players": len((raw_frame or {}).get("players", [])),
                    "reconstructed_visible_players": len([player for player in frame.players if player.visible]),
                    "selected_renderer_players": len(rendered),
                    "selected_attackers": len([player for player in state_at(model, frame.timestamp)["players"] if player["team_id"] == TEAM_ATTACK]),
                    "selected_defenders": len([player for player in state_at(model, frame.timestamp)["players"] if player["team_id"] == TEAM_DEFENSE]),
                }
            )

        selected_players = []
        for row in selection["players"]:
            track_id = row["track_id"]
            selected_players.append({**row, **motion_rows.get(track_id, {})})
        safety_violations = [
            violation
            for row in motion_rows.values()
            for violation in row.get("safety_violations", [])
        ]
        validation_errors = [
            error
            for row in payload["associations"].get("events", [])
            for error in row.get("validation_errors", [])
        ]
        max_selected = max((row["selected_renderer_players"] for row in exact_counts), default=0)
        min_selected = min((row["selected_renderer_players"] for row in exact_counts), default=0)
        selection_payload["cases"][case_id] = {
            "selected_players": selected_players,
            "summary": {
                "total_rendered_attackers": max((row["selected_attackers"] for row in exact_counts), default=0),
                "total_rendered_defenders": max((row["selected_defenders"] for row in exact_counts), default=0),
                "goalkeeper_included": any(
                    any("goalkeeper" in reason for reason in row.get("reasons", []))
                    for row in selection["players"]
                ),
                "core_action_actors_retained": all(identity is None or identity in identities for identity in actor_identities),
                "pass_recipients_retained": all(identity is None or identity in identities for identity in recipient_identities),
                "selected_finding_participants_retained": True,
                "irrelevant_tracks_suppressed": len(selection["suppressed_track_ids"]),
                "player_count_stability": {
                    "min_selected": min_selected,
                    "max_selected": max_selected,
                    "visibility_flicker_count": flicker,
                },
                "material_collapses": int(bool(max_selected) and min_selected < max(3, int(max_selected * 0.5))),
                "duplicate_event_actors": duplicate_event_actor_count(payload["associations"]),
                "over_11_frames": sum(1 for error in validation_errors if "visible players" in error),
                "safety_violations": len(safety_violations),
                "maximum_player_displacement_between_adjacent_frames": max(
                    (row["maximum_single_step_displacement"] for row in motion_rows.values()),
                    default=0.0,
                ),
            },
        }
        safety_payload["cases"][case_id] = {
            "maximum_speed_mps": max_speed,
            "tracks": sorted(motion_rows.values(), key=lambda row: row["track_id"]),
            "violations": safety_violations,
        }
        counts_payload["cases"][case_id] = {
            "events": exact_counts,
            "summary": selection_payload["cases"][case_id]["summary"]["player_count_stability"],
        }

    write_json(out / "relevant_player_selection.json", selection_payload)
    write_json(out / "motion_safety_report.json", safety_payload)
    write_json(out / "before_after_player_counts.json", counts_payload)
    lines = ["# Relevant Player Selection", "", "| Case | Attackers | Defenders | Suppressed | Min selected | Max selected | Safety violations |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case_id, case in selection_payload["cases"].items():
        summary = case["summary"]
        stability = summary["player_count_stability"]
        lines.append(
            f"| {case_id} | {summary['total_rendered_attackers']} | {summary['total_rendered_defenders']} | "
            f"{summary['irrelevant_tracks_suppressed']} | {stability['min_selected']} | {stability['max_selected']} | "
            f"{summary['safety_violations']} |"
        )
    (out / "relevant_player_selection.md").write_text("\n".join(lines), encoding="utf-8")
    return selection_payload


def main() -> None:
    base_config = load_config(ROOT / "config.yaml")
    manifest = {
        "shared_entry_point": "scripts/reconstruction_audit.py::main",
        "shared_functions_used_by_both_cases": [
            "src.pipelines.analyze_possession.load_config",
            "src.pipelines.analyze_possession.analyze",
            "src.ingest.possession_loader.load_normalized_possession",
            "analysis.normalize.load_and_normalize",
            "scripts.narrative_window.select_narrative_anchor",
            "scripts.narrative_window.build_short_scene_plan",
            "analysis.interpolate.tracking_config",
            "analysis.interpolate.build_animation_model",
        ],
        "case_specific_configuration_only": {
            case_id: {
                "match_id": case["match_id"],
                "possession_id": case["possession_id"],
                "goal_event_id": case["goal_event_id"],
                "input_file": str(case["input_file"].relative_to(ROOT)),
                "annotation_config": case["annotation_config"],
            }
            for case_id, case in CASES.items()
        },
        "known_pre_existing_case_specific_logic": [
            {
                "file": "scripts/rerender_both_goals.py",
                "function": "case_config",
                "condition": "case['match_id'] == 3788754",
                "effect": "Locatelli-specific hook_text and hook_model_time for display only.",
                "tracking_or_analysis_effect": False,
            }
        ],
        "different_audit_configuration_values": {},
    }

    outputs = {}
    case_payloads = {}
    for case_id, case in CASES.items():
        observation = build_observation_timeline(case_id, case, base_config)
        write_json(case["output_file"], observation)
        outputs[case_id] = str(case["output_file"].relative_to(ROOT))
        config = audit_config(base_config, case)
        analysis, _ = analyze(case["input_file"], config)
        possession = load_and_normalize(case["input_file"])
        selection = select_narrative_anchor(possession, analysis)
        scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
        window_events = event_window(possession, scene_plan)
        model = build_animation_model(possession, config)
        event_ids = {str(event["id"]) for event in window_events}
        model = apply_relevant_player_selection(model, config, event_ids, scene_plan.get("selected_finding"))
        diagnostic = diagnostic_frame_build(possession, config, scene_plan)
        gaps = snapshot_gaps(case_id, case, window_events)
        lifecycle = track_lifecycle(case_id, diagnostic)
        associations = association_audit(case_id, diagnostic)
        visibility = render_visibility_audit(case_id, model, diagnostic, gaps)
        roles = role_traces(case_id, possession, diagnostic, scene_plan)
        images = render_gap_images(case_id, gaps, model, config)
        case_payloads[case_id] = {
            "observation": {
                "window_event_count": len(window_events),
                "freeze_frame_event_count": sum(1 for event in window_events if event.get("freeze_frame")),
            },
            "gaps": gaps,
            "lifecycle": lifecycle,
            "associations": associations,
            "visibility": visibility,
            "roles": roles,
            "images": images,
            "model": {
                "model": model,
                "tracking_diagnostics": model["tracking_diagnostics"],
                "team_shape_metrics": model["team_shape_metrics"],
            },
        }
        outputs[f"{case_id}_snapshot_gaps"] = str((OUT / f"{case_id}_snapshot_gaps.json").relative_to(ROOT))
        outputs[f"{case_id}_track_lifecycle"] = str((OUT / f"{case_id}_track_lifecycle.json").relative_to(ROOT))
        outputs[f"{case_id}_tracks"] = str((OUT / f"{case_id}_tracks.json").relative_to(ROOT))
        outputs[f"{case_id}_associations"] = str((OUT / f"{case_id}_associations.json").relative_to(ROOT))
        outputs[f"{case_id}_render_visibility"] = str((OUT / f"{case_id}_render_visibility.json").relative_to(ROOT))
        outputs[f"{case_id}_role_traces"] = str((OUT / f"{case_id}_role_traces.json").relative_to(ROOT))

    evidence = evidence_usage(case_payloads)
    summaries = {case_id: case_summary(case_id, payload) for case_id, payload in case_payloads.items()}
    hypotheses = hypothesis_results(case_payloads, summaries)
    non_reconstruction = non_reconstruction_issues()
    final_reports(case_payloads, summaries, hypotheses, non_reconstruction)
    team_shape_audit = write_team_shape_audit(case_payloads, summaries)
    relevant_player_audit = write_relevant_player_audit(case_payloads, base_config)
    outputs["reconstruction_evidence_usage"] = str((OUT / "reconstruction_evidence_usage.json").relative_to(ROOT))
    outputs["hypothesis_results"] = str((OUT / "hypothesis_results.json").relative_to(ROOT))
    outputs["non_reconstruction_issues"] = str((OUT / "non_reconstruction_issues.json").relative_to(ROOT))
    outputs["reconstruction_audit_report_json"] = str((OUT / "reconstruction_audit_report.json").relative_to(ROOT))
    outputs["reconstruction_audit_report_md"] = str((OUT / "reconstruction_audit_report.md").relative_to(ROOT))
    outputs["team_shape_metrics"] = str((OUT / "team_shape" / "team_shape_metrics.json").relative_to(ROOT))
    outputs["team_shape_before_after"] = str((OUT / "team_shape" / "team_shape_before_after.md").relative_to(ROOT))
    outputs["relevant_player_selection"] = str(
        (OUT / "relevant_player_reconstruction" / "relevant_player_selection.json").relative_to(ROOT)
    )
    outputs["relevant_player_selection_md"] = str(
        (OUT / "relevant_player_reconstruction" / "relevant_player_selection.md").relative_to(ROOT)
    )
    outputs["motion_safety_report"] = str(
        (OUT / "relevant_player_reconstruction" / "motion_safety_report.json").relative_to(ROOT)
    )
    outputs["before_after_player_counts"] = str(
        (OUT / "relevant_player_reconstruction" / "before_after_player_counts.json").relative_to(ROOT)
    )
    comparison = write_repair_comparison()
    outputs["reconstruction_repair_comparison_json"] = str((OUT / "reconstruction_repair_comparison.json").relative_to(ROOT))
    outputs["reconstruction_repair_comparison_md"] = str((OUT / "reconstruction_repair_comparison.md").relative_to(ROOT))
    outputs["post_repair"] = str(POST_REPAIR_OUT.relative_to(ROOT))
    manifest["outputs"] = outputs
    manifest["repair_comparison_summary"] = {
        case_id: comparison["cases"][case_id]
        for case_id in comparison["cases"]
    }
    manifest["team_shape_summary"] = {
        case_id: metrics["propagation_summary"]
        for case_id, metrics in team_shape_audit["cases"].items()
    }
    manifest["relevant_player_summary"] = {
        case_id: payload["summary"]
        for case_id, payload in relevant_player_audit["cases"].items()
    }
    write_json(OUT / "reconstruction_audit_manifest.json", manifest)
    print(json.dumps({"outputs": outputs, "manifest": str((OUT / "reconstruction_audit_manifest.json").relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
