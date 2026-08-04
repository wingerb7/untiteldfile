from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "renders/.matplotlib"))

import yaml

from render.reconstruction import render_reconstruction
from src.reconstruction import build_window_reconstruction, load_statsbomb_match, reconstruction_state_at
from src.world_model import build_world_model_from_reconstruction

BASE = ROOT / "data/open-data/data"
CASES = [
    {"slug": "locatelli_pass", "match_id": 3788754, "event_id": "ff68f0b9-0fc4-4f72-bce7-fb6a4f54a605", "kind": "pass"},
    {"slug": "locatelli_carry", "match_id": 3788754, "event_id": "f79c20a4-f70f-4ef3-b4f3-d6e0a2d7fafe", "kind": "carry"},
    {"slug": "depay_pass", "match_id": 3869117, "event_id": "cd4e2356-a699-4aff-8f50-21b532223687", "kind": "pass"},
    {"slug": "depay_carry", "match_id": 3869117, "event_id": "87a2348f-3097-4ac8-a7b4-2929c60b6f79", "kind": "carry"},
    {"slug": "di_maria_rejection", "match_id": 3869685, "event_id": "9afa860b-47cd-4be3-84cc-9f0846027721", "kind": "source-validation-rejection"},
    {"slug": "period_boundary_rejection", "match_id": 3869117, "event_id": "5566d71a-983c-4f30-9ddb-85d7b8815ba1", "sequence_end_event_id": "69073b1f-9c3f-4657-8207-0309e1fb16c4", "kind": "period-boundary-rejection"},
]


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def metric_distance(a: list[float], b: list[float]) -> float:
    from math import dist
    return dist((a[0] * 105 / 120, a[1] * 68 / 80), (b[0] * 105 / 120, b[1] * 68 / 80))


def audit(reconstruction: dict[str, Any], fps: int, support_seconds: float) -> dict[str, Any]:
    count = max(1, int(reconstruction["duration"] * fps) + 1)
    spans: dict[str, list[float]] = defaultdict(list)
    observations: dict[str, list[float]] = defaultdict(list)
    anonymous = set()
    for keyframe in reconstruction["keyframes"]:
        for player in keyframe["players"]:
            spans[player["tracking_id"]].append(keyframe["timestamp"])
            if player["interpolation_state"] == "OBSERVED":
                observations[player["tracking_id"]].append(keyframe["timestamp"])
            if player["identity"]["player_id"] is None:
                anonymous.add(player["tracking_id"])
    states = Counter()
    last_visible = {}
    disappearances = reappearances = jumps = 0
    max_speed = longest_interp = longest_gap = 0.0
    last_position: dict[str, tuple[float, list[float]]] = {}
    last_ball = None
    max_ball_speed = 0.0
    ball_transitions = 0
    rows = []
    for frame_index in range(count):
        timestamp = min(reconstruction["duration"], frame_index / fps)
        state = reconstruction_state_at(reconstruction, timestamp)
        visible = {player["tracking_id"]: player for player in state["players"]}
        frame_tracks = []
        for track_id, times in spans.items():
            if timestamp < min(times) or timestamp > max(times):
                continue
            player = visible.get(track_id)
            source_supported = any(abs(timestamp - observed) <= support_seconds for observed in observations[track_id])
            truth = "OBSERVED_SOURCE_SUPPORT" if source_supported else player["interpolation_state"] if player else "UNKNOWN"
            states[truth] += 1
            is_visible = player is not None
            if track_id in last_visible and last_visible[track_id] and not is_visible: disappearances += 1
            if track_id in last_visible and not last_visible[track_id] and is_visible: reappearances += 1
            last_visible[track_id] = is_visible
            if player:
                age = player.get("interpolation_duration")
                if age is not None: longest_interp = max(longest_interp, age)
                if track_id in last_position:
                    prior_time, prior = last_position[track_id]
                    elapsed = timestamp - prior_time
                    distance = metric_distance(prior, player["location"])
                    speed = distance / elapsed if elapsed else 0.0
                    max_speed = max(max_speed, speed)
                    jumps += int(distance > 12.0)
                last_position[track_id] = (timestamp, player["location"])
            frame_tracks.append({"track_id": track_id, "state": truth, "visible": is_visible, "position": player.get("location") if player else None, "provenance": player.get("provenance") if player else [], "source_supported": source_supported})
        if state["ball"] is None:
            last_ball = None
        elif last_ball is not None:
            prior_time, prior = last_ball
            speed = metric_distance(prior, state["ball"]) / max(1e-9, timestamp - prior_time)
            max_ball_speed = max(max_ball_speed, speed)
            ball_transitions += int(speed > 45.0)
            last_ball = (timestamp, state["ball"])
        else:
            last_ball = (timestamp, state["ball"])
        rows.append({"frame_index": frame_index, "timestamp": timestamp, "period": state.get("period"), "event_id": state.get("event_id"), "ball": {"position": state.get("ball"), "state": state.get("ball_state"), "source": state.get("ball_source")}, "tracks": frame_tracks})
    for values in observations.values():
        longest_gap = max(longest_gap, max((b - a for a, b in zip(values, values[1:])), default=0.0))
    total = sum(states.values()) or 1
    lifecycle_events = [event for track in reconstruction["track_lifecycles"] for event in track["events"]]
    return {
        "metrics": {
            "duration_seconds": reconstruction["duration"], "rendered_frames": count,
            "selected_events": len(reconstruction["events"]), "source_360_frame_count": len(reconstruction["keyframes"]),
            "active_track_count": len(spans), "anonymous_track_count": len(anonymous),
            "track_creations": sum(event["state"] == "CREATED" for event in lifecycle_events),
            "track_retirements": sum(event["state"] == "RETIRED" for event in lifecycle_events),
            "track_reactivations": sum(event["state"].startswith("ACTIVE") for track in reconstruction["track_lifecycles"] for event in track["events"][2:]),
            "observed_source_support_percentage": 100 * states["OBSERVED_SOURCE_SUPPORT"] / total,
            "interpolated_percentage": 100 * states["INTERPOLATED"] / total,
            "unknown_percentage": 100 * states["UNKNOWN"] / total,
            "longest_interpolation_seconds": longest_interp, "longest_association_gap_seconds": longest_gap,
            "disappearances": disappearances, "reappearances": reappearances,
            "implausible_player_jumps": jumps, "maximum_player_speed_mps": max_speed,
            "implausible_ball_transitions": ball_transitions, "maximum_ball_speed_mps": max_ball_speed,
        },
        "frames": rows,
    }


def decoded_hashes(video: Path, directory: Path) -> list[str]:
    directory.mkdir()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-vsync", "0", str(directory / "frame_%04d.png")], check=True)
    return [hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(directory.glob("*.png"))]


def sheet(video: Path, output: Path) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-vf", "select='not(mod(n,8))',scale=270:-1,tile=4x3", "-frames:v", "1", str(output)], check=True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fps", type=int, default=8)
    args = parser.parse_args()
    if args.output.exists(): raise SystemExit("refusing to overwrite immutable validation output")
    args.output.mkdir(parents=True)
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config["animation"].update({"fps": args.fps, "width": 540, "height": 900})
    manifest = {"schema_id": "tip.event_window_validation", "cases": []}
    for case in CASES:
        directory = args.output / case["slug"]; directory.mkdir()
        match = load_statsbomb_match(BASE / f"events/{case['match_id']}.json", BASE / f"three-sixty/{case['match_id']}.json", match_id=case["match_id"])
        kwargs = {"event_id": case["event_id"], "sequence_end_event_id": case.get("sequence_end_event_id"), "pre_roll_seconds": 0.75, "post_roll_seconds": 2.0, "config": config}
        first = build_window_reconstruction(match, **kwargs)
        second = build_window_reconstruction(deepcopy(match), **kwargs)
        dump(directory / "selection.json", first["selection"])
        deterministic = {"selection_equal": first["selection"] == second["selection"], "reconstruction_equal": first["reconstruction"] == second["reconstruction"]}
        item = {"case": case, "selection": first["selection"], "determinism": deterministic}
        reconstruction = first["reconstruction"]
        if reconstruction is not None and str(first["selection"]["admission"]).startswith("ACCEPTED"):
            dump(directory / "reconstruction.json", reconstruction)
            result_a = audit(reconstruction, args.fps, config.get("reconstruction_window", {}).get("observed_support_seconds", 0.125))
            result_b = audit(second["reconstruction"], args.fps, config.get("reconstruction_window", {}).get("observed_support_seconds", 0.125))
            deterministic["audit_equal"] = result_a == result_b
            world_source = deepcopy(reconstruction); world = build_world_model_from_reconstruction(world_source)
            result_a["world_boundary"] = {"input_unchanged": world_source == reconstruction, "unknown_factual_positions": sum(player["position"] is not None for frame in world["frames"] for player in frame["players"] if player["state"] == "UNKNOWN")}
            raw=directory/"raw.mp4"; ghost=directory/"uncertainty.mp4"; qa=directory/"visual_qa.mp4"; rerun=directory/"raw_rerun.mp4"
            render_reconstruction(reconstruction,config,raw)
            render_reconstruction(reconstruction,config,ghost,uncertainty_presentation=True)
            render_reconstruction(reconstruction,config,qa,visual_qa=True,uncertainty_presentation=True)
            render_reconstruction(second["reconstruction"],config,rerun)
            hashes_a=decoded_hashes(raw,directory/"decoded_a");hashes_b=decoded_hashes(rerun,directory/"decoded_b")
            deterministic["decoded_frames_equal"] = hashes_a == hashes_b
            deterministic["decoded_frame_hash"] = hashlib.sha256("".join(hashes_a).encode()).hexdigest()
            sheet(qa,directory/"contact_sheet.png")
            result_a["admission"] = first["selection"]["admission"];result_a["admission_reasons"] = first["selection"]["reasons"]
            dump(directory/"audit.json",result_a);item["metrics"] = result_a["metrics"]
        else:
            dump(directory / "audit.json", {"admission": first["selection"]["admission"], "admission_reasons": first["selection"]["reasons"], "rendered": False})
        manifest["cases"].append(item)
    baseline_path=ROOT/"audit/reconstruction_validation/validation_20260802_d/manifest.json"
    manifest["baseline"] = json.loads(baseline_path.read_text()) if baseline_path.exists() else None
    dump(args.output/"manifest.json",manifest)


if __name__ == "__main__": main()
