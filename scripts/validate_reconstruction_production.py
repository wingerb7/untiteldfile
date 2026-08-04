from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "renders/.matplotlib"))

from typing import Any

import yaml
from matplotlib.path import Path as PolygonPath

from render.reconstruction import render_reconstruction
from src.reconstruction import build_reconstruction, load_statsbomb_match, reconstruction_state_at
from src.world_model import build_world_model_from_reconstruction


BASE = ROOT / "data/open-data/data"
PLAYER_JUMP_THRESHOLD_M = 12.0
PLAYER_SPEED_THRESHOLD_MPS = 12.0
BALL_SPEED_THRESHOLD_MPS = 45.0
ACCELERATION_THRESHOLD_MPS2 = 15.0

CASES = [
    {"slug": "locatelli_p40", "match_id": 3788754, "possession_id": 40, "description": "Locatelli; long 7.808 s source-observation gap and anonymous 360 identities"},
    {"slug": "depay_p20", "match_id": 3869117, "possession_id": 20, "description": "Depay; 6.069 s gap and dense anonymous 360 snapshots"},
    {"slug": "di_maria_p52", "match_id": 3869685, "possession_id": 52, "description": "Existing StatsBomb 360 fixture; short attacking sequence"},
    {"slug": "period_boundary_3869117", "match_id": 3869117, "boundary": True, "description": "Last three position events of period 1 and first three of period 2"},
]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def seconds(value: str) -> float:
    hours, minutes, sec = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(sec)


def selected_event_ids(events_path: Path, case: dict[str, Any]) -> tuple[set[str], dict[str, Any]]:
    raw = json.loads(events_path.read_text(encoding="utf-8"))
    positioned = [event for event in raw if isinstance(event.get("location"), list)]
    if case.get("boundary"):
        p1 = [event for event in positioned if event.get("period") == 1][-3:]
        p2 = [event for event in positioned if event.get("period") == 2][:3]
        chosen = p1 + p2
    else:
        chosen = [event for event in positioned if event.get("possession") == case["possession_id"]]
    return {str(event["id"]) for event in chosen}, {
        "periods": sorted({event.get("period") for event in chosen}),
        "source_time_range": [chosen[0]["timestamp"], chosen[-1]["timestamp"]],
        "source_event_indices": [chosen[0]["index"], chosen[-1]["index"]],
        "source_event_count": len(chosen),
    }


def load_case(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    match_id = case["match_id"]
    events_path = BASE / f"events/{match_id}.json"
    frames_path = BASE / f"three-sixty/{match_id}.json"
    ids, coverage = selected_event_ids(events_path, case)
    match = load_statsbomb_match(events_path, frames_path, match_id=match_id)
    match["events"] = [event for event in match["events"] if event["id"] in ids]
    match["frames"] = [frame for frame in match["frames"] if frame["event_id"] in ids]
    match["start_time"] = match["events"][0]["timestamp"]
    match["end_time"] = max(event["timestamp"] + event["duration"] for event in match["events"])
    match["match_label"] = case["slug"]
    return match, coverage


def metric_distance(left: list[float], right: list[float]) -> float:
    return math.dist((left[0] * 105 / 120, left[1] * 68 / 80), (right[0] * 105 / 120, right[1] * 68 / 80))


def inside_visible_area(position: list[float], area: Any) -> bool:
    if not isinstance(area, list) or len(area) < 8 or len(area) % 2:
        return True
    polygon = [(float(area[index]), float(area[index + 1])) for index in range(0, len(area), 2)]
    return bool(PolygonPath(polygon).contains_point((position[0], position[1]), radius=1e-9))


def decoded_frame_hashes(video: Path, directory: Path) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    pattern = directory / "frame_%05d.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-vsync", "0", str(pattern)], check=True)
    return [hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(directory.glob("frame_*.png"))]


def contact_sheet(video: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-i", str(video), "-vf",
        "select='not(mod(n,20))',scale=270:-1,tile=4x3", "-frames:v", "1", str(output),
    ], check=True)


def audit_reconstruction(reconstruction: dict[str, Any], fps: int) -> dict[str, Any]:
    frame_count = max(1, int(reconstruction["duration"] * fps) + 1)
    tracks: dict[str, dict[str, Any]] = {}
    track_presence: dict[str, list[float]] = defaultdict(list)
    for keyframe in reconstruction["keyframes"]:
        for player in keyframe["players"]:
            tracks.setdefault(player["tracking_id"], player)
            track_presence[player["tracking_id"]].append(float(keyframe["timestamp"]))
    rows = []
    counts: Counter[str] = Counter()
    outside_area = untraceable = 0
    identity_changes = []
    duplicate_identity = []
    previous_identity: dict[str, Any] = {}
    last_visible: dict[str, bool] = {}
    disappearances = reappearances = 0
    previous_position: dict[str, tuple[float, list[float]]] = {}
    previous_speed: dict[str, tuple[float, float]] = {}
    jumps = []
    ball_jumps = []
    accelerations = []
    max_player_speed = 0.0
    max_acceleration = 0.0
    max_ball_speed = 0.0
    previous_ball: tuple[float, list[float], str] | None = None
    unknown_runs: dict[str, float] = {}
    longest_unknown = 0.0
    longest_interpolation = 0.0
    state_samples = {}
    for frame_index in range(frame_count):
        timestamp = min(float(reconstruction["duration"]), frame_index / fps)
        state = reconstruction_state_at(reconstruction, timestamp)
        visible_by_track = {player["tracking_id"]: player for player in state["players"]}
        frame_rows = []
        active_authenticated: dict[str, str] = {}
        for track_id, exemplar in sorted(tracks.items()):
            first, last = min(track_presence[track_id]), max(track_presence[track_id])
            if timestamp < first or timestamp > last:
                continue
            player = visible_by_track.get(track_id)
            reconstruction_state = player["interpolation_state"] if player else "UNKNOWN"
            counts[reconstruction_state] += 1
            visible = player is not None
            identity = (player or exemplar).get("identity") or {}
            pid = identity.get("player_id")
            prior = previous_identity.setdefault(track_id, pid)
            if prior is not None and pid is not None and str(prior) != str(pid):
                identity_changes.append({"timestamp": timestamp, "track_id": track_id, "from": prior, "to": pid, "provenance": (player or exemplar).get("provenance")})
            if visible and pid is not None:
                key = str(pid)
                if key in active_authenticated and active_authenticated[key] != track_id:
                    duplicate_identity.append({"timestamp": timestamp, "player_id": pid, "tracks": [active_authenticated[key], track_id]})
                active_authenticated[key] = track_id
            if track_id in last_visible and last_visible[track_id] and not visible:
                disappearances += 1
            if track_id in last_visible and not last_visible[track_id] and visible:
                reappearances += 1
            last_visible[track_id] = visible
            if reconstruction_state == "UNKNOWN":
                unknown_runs.setdefault(track_id, timestamp)
                longest_unknown = max(longest_unknown, timestamp - unknown_runs[track_id])
            else:
                unknown_runs.pop(track_id, None)
            position = player.get("location") if player else None
            interpolation_duration = player.get("interpolation_duration", 0.0) if player else None
            if interpolation_duration is not None:
                longest_interpolation = max(longest_interpolation, float(interpolation_duration))
            if visible and position:
                if not inside_visible_area(position, state.get("visible_area")):
                    outside_area += 1
                if not player.get("provenance"):
                    untraceable += 1
                if track_id in previous_position:
                    previous_time, previous = previous_position[track_id]
                    elapsed = timestamp - previous_time
                    distance = metric_distance(previous, position)
                    speed = distance / elapsed if elapsed > 0 else 0.0
                    max_player_speed = max(max_player_speed, speed)
                    if distance > PLAYER_JUMP_THRESHOLD_M:
                        jumps.append({"timestamp": timestamp, "track_id": track_id, "distance_m": distance, "elapsed_seconds": elapsed, "speed_mps": speed, "provenance": player.get("provenance")})
                    if track_id in previous_speed:
                        speed_time, prior_speed = previous_speed[track_id]
                        acceleration = abs(speed - prior_speed) / max(1e-9, timestamp - speed_time)
                        max_acceleration = max(max_acceleration, acceleration)
                        if acceleration > ACCELERATION_THRESHOLD_MPS2:
                            accelerations.append({"timestamp": timestamp, "track_id": track_id, "acceleration_mps2": acceleration})
                    previous_speed[track_id] = (timestamp, speed)
                previous_position[track_id] = (timestamp, position)
            provenance = (player or exemplar).get("provenance", [])
            source = (player or exemplar).get("source", {})
            frame_rows.append({
                "timestamp": timestamp, "period": state.get("period"), "identity": identity,
                "track_id": track_id, "position": position, "visibility": visible,
                "reconstruction_state": reconstruction_state,
                "confidence": player.get("confidence") if player else 0.0,
                "provenance": provenance, "last_observed_timestamp": (player or exemplar).get("last_observed_timestamp"),
                "interpolation_duration": interpolation_duration,
                "unknown_reason": None if player else "NO_SUPPORTED_POSITION_AT_TIMESTAMP",
                "source_event_id": source.get("event_id"),
                "source_360_frame_id": source.get("event_id") if source.get("kind") == "STATSBOMB_360_OBSERVATION" else None,
            })
        ball_position = state.get("ball")
        if ball_position is not None and previous_ball is not None:
            prior_time, prior_position, prior_event = previous_ball
            elapsed = timestamp - prior_time
            speed = metric_distance(prior_position, ball_position) / elapsed if elapsed > 0 else 0.0
            max_ball_speed = max(max_ball_speed, speed)
            if speed > BALL_SPEED_THRESHOLD_MPS and prior_event == state.get("event_id"):
                ball_jumps.append({"timestamp": timestamp, "object": "ball", "speed_mps": speed, "reason": "BALL_JUMP_WITHOUT_NEW_EVENT", "event_id": state.get("event_id")})
        if ball_position is not None:
            previous_ball = (timestamp, ball_position, state.get("event_id"))
        rows.append({"frame_index": frame_index, "timestamp": timestamp, "period": state.get("period"), "event_id": state.get("event_id"), "ball": {"position": ball_position, "state": state.get("ball_state"), "source": state.get("ball_source")}, "tracks": frame_rows})
        if frame_index in {0, frame_count // 2, frame_count - 1}:
            state_samples[str(frame_index)] = state
    total = sum(counts.values()) or 1
    findings = {
        "identity_changes": identity_changes,
        "duplicate_authenticated_identity": duplicate_identity,
        "position_jumps": jumps,
        "unsupported_ball_jumps": ball_jumps,
        "unrealistic_accelerations": accelerations,
        "frozen_tracks": [],
        "substitution_validation": "NOT_APPLICABLE_NO_LINEUP_OR_SUBSTITUTION_METADATA_IN_SELECTED_INPUT",
    }
    metrics = {
        "total_duration_seconds": reconstruction["duration"], "rendered_frames": frame_count,
        "distinct_player_tracks": len(tracks),
        "observed_percentage": 100 * counts["OBSERVED"] / total,
        "interpolated_percentage": 100 * counts["INTERPOLATED"] / total,
        "unknown_percentage": 100 * counts["UNKNOWN"] / total,
        "longest_interpolation_seconds": longest_interpolation,
        "longest_unknown_seconds": longest_unknown,
        "identity_changes": len(identity_changes), "player_disappearances": disappearances,
        "player_reappearances": reappearances, "position_jumps_above_threshold": len(jumps),
        "unsupported_ball_jumps": len(ball_jumps),
        "maximum_player_speed_mps": max_player_speed, "maximum_player_acceleration_mps2": max_acceleration,
        "maximum_ball_speed_mps": max_ball_speed, "player_frames_outside_visible_area": outside_area,
        "source_untraceable_visible_objects": untraceable,
    }
    return {"schema_id": "tip.reconstruction_validation_audit", "thresholds": {"player_jump_m": PLAYER_JUMP_THRESHOLD_M, "player_speed_mps": PLAYER_SPEED_THRESHOLD_MPS, "ball_speed_mps": BALL_SPEED_THRESHOLD_MPS, "acceleration_mps2": ACCELERATION_THRESHOLD_MPS2}, "metrics": metrics, "findings": findings, "selected_state_samples": state_samples, "frames": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=8)
    parser.add_argument("--skip-video", action="store_true")
    args = parser.parse_args()
    output = args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing audit directory: {output}")
    output.mkdir(parents=True)
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    config["animation"].update({"fps": args.fps, "width": 540, "height": 900})
    manifest = {"schema_id": "tip.reconstruction_validation_manifest", "fps": args.fps, "cases": []}
    for case in CASES:
        case_dir = output / case["slug"]
        case_dir.mkdir()
        match, coverage = load_case(case)
        first = build_reconstruction(match, config)
        second = build_reconstruction(deepcopy(match), config)
        write_json(case_dir / "reconstruction.json", first)
        audit_first = audit_reconstruction(first, args.fps)
        audit_second = audit_reconstruction(second, args.fps)
        deterministic = {
            "canonical_sha256_equal": first["sha256"] == second["sha256"],
            "first_sha256": first["sha256"], "second_sha256": second["sha256"],
            "frame_count_equal": audit_first["metrics"]["rendered_frames"] == audit_second["metrics"]["rendered_frames"],
            "audit_json_equal": audit_first == audit_second,
            "selected_states_equal": audit_first["selected_state_samples"] == audit_second["selected_state_samples"],
        }
        world_input = deepcopy(first)
        world = build_world_model_from_reconstruction(world_input)
        boundary = {"input_not_mutated": world_input == first, "unknown_positions_factual": sum(1 for frame in world["frames"] for player in frame["players"] if player["state"] == "UNKNOWN" and player["position"] is not None), "world_reconstruction_sha256": world["reconstruction_sha256"], "tactical_components_required": False, "renderer_ghost_positions_in_world": 0}
        if not args.skip_video:
            raw = case_dir / "raw.mp4"
            raw_rerun = case_dir / "raw_rerun.mp4"
            qa = case_dir / "visual_qa.mp4"
            render_reconstruction(first, config, raw, visual_qa=False)
            render_reconstruction(first, config, qa, visual_qa=True)
            render_reconstruction(second, config, raw_rerun, visual_qa=False)
            first_hashes = decoded_frame_hashes(raw, case_dir / "decoded_raw")
            second_hashes = decoded_frame_hashes(raw_rerun, case_dir / "decoded_rerun")
            deterministic["decoded_frame_hashes_equal"] = first_hashes == second_hashes
            deterministic["decoded_frame_count"] = len(first_hashes)
            deterministic["decoded_frame_hashes_sha256"] = hashlib.sha256("".join(first_hashes).encode()).hexdigest()
            contact_sheet(qa, case_dir / "contact_sheet.png")
        audit_first["fixture"] = {**case, **coverage}
        audit_first["determinism"] = deterministic
        audit_first["world_model_boundary"] = boundary
        write_json(case_dir / "audit.json", audit_first)
        manifest["cases"].append({"slug": case["slug"], "fixture": audit_first["fixture"], "reconstruction_sha256": first["sha256"], "metrics": audit_first["metrics"], "determinism": deterministic, "world_model_boundary": boundary})
    write_json(output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
