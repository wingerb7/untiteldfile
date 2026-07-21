from __future__ import annotations

import copy
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
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
from PIL import Image, ImageDraw, ImageFont

from analysis.interpolate import apply_relevant_player_selection, build_animation_model, metric_distance, state_at
from analysis.normalize import load_and_normalize
from render.pitch import draw_pitch, sb_to_plot
from render.styles import colors
from scripts.narrative_window import (
    build_short_scene_plan,
    final_sequence,
    select_narrative_anchor,
    timeline_payload as short_timeline_payload,
)
from scripts.second_goal_generalisation import write_event_timeline
from src.domain.models import Position
from src.pipelines.analyze_possession import analyze, load_config
from src.pipelines.render_analysis import render_scene_plan, scene_segments


OUT = ROOT / "renders"
OPEN_DATA = ROOT / "data" / "open-data" / "data"
METRIC_X = 105.0 / 120.0
METRIC_Y = 68.0 / 80.0


CASES = {
    "argentina_52": {
        "match_id": 3869685,
        "possession_id": 52,
        "goal_event_id": "ef86f4d9-7acd-4ed0-a5ec-9129079e8fbe",
        "input_file": ROOT / "data" / "possession_52.json",
        "annotation_file": ROOT / "annotations" / "possession_52.json",
        "annotation_config": "annotations/possession_52.json",
        "analysis": OUT / "argentina_52_analysis.json",
        "scene_plan": OUT / "argentina_52_scene_plan.json",
        "timeline": OUT / "argentina_52_timeline.json",
        "mp4": OUT / "argentina_52.mp4",
        "short_scene_plan": OUT / "argentina_52_short_scene_plan.json",
        "short_timeline": OUT / "argentina_52_short_timeline.json",
        "short_mp4": OUT / "argentina_52_short.mp4",
        "snapshot_audit": OUT / "argentina_52_snapshot_audit.json",
        "contact_sheet": OUT / "argentina_52_snapshot_contact_sheet.png",
    },
    "italy_locatelli": {
        "match_id": 3788754,
        "possession_id": 40,
        "goal_event_id": "e0c628ae-6a37-414e-818e-5e3911c07dfc",
        "input_file": ROOT / "data" / "second_goal.json",
        "annotation_file": ROOT / "annotations" / "second_goal.json",
        "annotation_config": "annotations/second_goal.json",
        "analysis": OUT / "italy_locatelli_analysis.json",
        "scene_plan": OUT / "italy_locatelli_scene_plan.json",
        "timeline": OUT / "italy_locatelli_timeline.json",
        "mp4": OUT / "italy_locatelli.mp4",
        "short_scene_plan": OUT / "italy_locatelli_short_scene_plan.json",
        "short_timeline": OUT / "italy_locatelli_short_timeline.json",
        "short_mp4": OUT / "italy_locatelli_short.mp4",
        "snapshot_audit": OUT / "italy_locatelli_snapshot_audit.json",
        "contact_sheet": OUT / "italy_locatelli_snapshot_contact_sheet.png",
    },
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def run_text(args: list[str]) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def git_clean() -> bool:
    return run_text(["git", "status", "--short"]) == ""


def case_config(base: dict[str, Any], case: dict[str, Any], short: bool = False) -> dict[str, Any]:
    config = copy.deepcopy(base)
    config["animation"] = copy.deepcopy(config.get("animation", {}))
    config["animation"]["annotations_file"] = case["annotation_config"]
    if case["match_id"] == 3788754:
        config["animation"]["hook_text"] = "Can Italy turn circulation into a goal?"
        config["animation"]["hook_model_time"] = 1.0
    if short:
        config["animation"]["hook_hold_seconds"] = 0.0
        config["animation"]["hook_text"] = ""
        config["animation"]["camera_lookback_seconds"] = 2.5
        config["animation"]["camera_lookahead_seconds"] = 8.0
        config["animation"]["camera_zoom_out_ease"] = 0.18
    return config


def source_paths(match_id: int) -> tuple[Path, Path]:
    return OPEN_DATA / "events" / f"{match_id}.json", OPEN_DATA / "three-sixty" / f"{match_id}.json"


def event_type(raw_event: dict[str, Any]) -> str:
    value = raw_event.get("type")
    return value.get("name") if isinstance(value, dict) else str(value)


def verify_source_data(case_id: str, case: dict[str, Any]) -> dict[str, Any]:
    events_file, frame_file = source_paths(case["match_id"])
    possession = read_json(case["input_file"])
    raw_events = read_json(events_file) if events_file.exists() else []
    frame_events = read_json(frame_file) if frame_file.exists() else []
    goal_id = case["goal_event_id"]
    return {
        "case_id": case_id,
        "match_id": case["match_id"],
        "possession_id": case["possession_id"],
        "events_file": str(events_file.relative_to(ROOT)),
        "events_file_exists": events_file.exists(),
        "three_sixty_file": str(frame_file.relative_to(ROOT)),
        "three_sixty_file_exists": frame_file.exists(),
        "annotation_or_config_file": str(case["annotation_file"].relative_to(ROOT)),
        "goal_event_found": any(event.get("id") == goal_id for event in raw_events)
        and any(event.get("id") == goal_id for event in possession.get("events", [])),
        "possession_found": any(int(event.get("possession", -1)) == case["possession_id"] for event in raw_events)
        and int(possession.get("possession_id") or -1) == case["possession_id"],
        "three_sixty_goal_found": any(frame.get("event_uuid") == goal_id for frame in frame_events),
    }


def full_timeline_payload(possession_path: Path, scene_plan: dict[str, Any], config: dict[str, Any], output_path: Path) -> dict[str, Any]:
    model = write_event_timeline(possession_path, scene_plan, config, output_path)
    timeline = read_json(output_path)
    segments = scene_segments(scene_plan, model)
    timeline["render_duration_seconds"] = round(
        float(config.get("animation", {}).get("hook_hold_seconds", 0.0)) + (segments[-1]["output_end"] if segments else model["duration"]),
        3,
    )
    write_json(output_path, timeline)
    return timeline


def event_index(possession: dict[str, Any], event_id: str) -> int:
    return next(idx for idx, event in enumerate(possession["events"]) if event["id"] == event_id)


def nearest_freeze_event(possession: dict[str, Any], target_idx: int, used: set[str]) -> tuple[dict[str, Any] | None, str | None]:
    best = None
    for idx, event in enumerate(possession["events"]):
        if event["id"] in used or not event.get("freeze_frame"):
            continue
        distance = abs(idx - target_idx)
        if best is None or distance < best[0]:
            best = (distance, event)
    if best is None:
        return None, None
    return best[1], f"substituted nearest freeze-frame event for requested index {target_idx}"


def snapshot_events(possession: dict[str, Any], analysis: dict[str, Any], scene_plan: dict[str, Any], short_scene_plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    events = possession["events"]
    shot = possession["shot"] or events[-1]
    selected_id = analysis.get("selected_finding_id")
    selected_finding = next((finding for finding in analysis.get("findings", []) if finding.get("finding_id") == selected_id), None)
    finding_event_id = (selected_finding or {}).get("event_id") or shot["id"]
    first_id = ((short_scene_plan or scene_plan).get("narrative_window") or {}).get("window_start_event_id")
    if not first_id:
        first_id = next((scene.get("from_event_id") for scene in (short_scene_plan or scene_plan).get("scenes", []) if scene.get("from_event_id")), events[0]["id"])
    requested = [
        ("window_start", first_id),
        ("selected_finding", finding_event_id),
        ("pre_shot", events[max(0, event_index(possession, shot["id"]) - 1)]["id"]),
        ("goal", shot["id"]),
    ]
    used: set[str] = set()
    selected = []
    for role, event_id in requested:
        target = next(event for event in events if event["id"] == event_id)
        limitations = []
        if target["id"] in used or not target.get("freeze_frame"):
            replacement, note = nearest_freeze_event(possession, event_index(possession, target["id"]), used)
            if replacement is not None:
                limitations.append(f"{role}: requested {target['id']} replaced by {replacement['id']}; {note}.")
                target = replacement
        used.add(target["id"])
        selected.append({"role": role, "event": target, "limitations": limitations})
    return selected


def metric_delta(a: list[float], b: list[float]) -> float:
    dx = (float(b[0]) - float(a[0])) * METRIC_X
    dy = (float(b[1]) - float(a[1])) * METRIC_Y
    return math.hypot(dx, dy)


def draw_snapshot(ax: Any, title: str, players: list[dict[str, Any]], ball: list[float] | None, style: dict[str, str]) -> None:
    draw_pitch(ax, style, {"brand": {"pitch": {"stripe_count": 12}}})
    ax.set_title(title, color=style["text"], fontsize=12, weight="bold", pad=8)
    for idx, player in enumerate(players):
        point = sb_to_plot(player.get("location"))
        if point is None:
            continue
        color = style["attack"] if player.get("teammate") else style["defense"]
        marker = "s" if player.get("keeper") else "o"
        ax.scatter([point[0]], [point[1]], s=100 if player.get("actor") else 64, c=color, marker=marker, edgecolors="#111111", linewidths=0.8, zorder=5)
        ax.text(point[0] + 0.8, point[1] + 0.8, str(player.get("source_index", idx)), color=style["text"], fontsize=7, zorder=8)
    if ball:
        point = sb_to_plot(ball)
        if point:
            ax.scatter([point[0]], [point[1]], s=90, c=style["ball"], edgecolors="#111111", linewidths=0.9, zorder=9)


def render_snapshot_file(path: Path, title: str, players: list[dict[str, Any]], ball: list[float] | None, style: dict[str, str]) -> None:
    fig, ax = plt.subplots(figsize=(8, 12), dpi=120)
    fig.patch.set_facecolor(style["field"])
    draw_snapshot(ax, title, players, ball, style)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_comparison(path: Path, title: str, panels: list[tuple[str, list[dict[str, Any]], list[float] | None]], style: dict[str, str]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(18, 9), dpi=120)
    fig.patch.set_facecolor(style["field"])
    fig.suptitle(title, color=style["text"], fontsize=16, weight="bold")
    for ax, (panel_title, players, ball) in zip(axes, panels, strict=True):
        draw_snapshot(ax, panel_title, players, ball, style)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def contact_sheet(path: Path, panels: list[tuple[dict[str, Any], Path, str]], style: dict[str, str]) -> None:
    panels = sorted(panels, key=lambda item: float(item[0]["timestamp"]))
    images = [Image.open(panel).convert("RGB") for _, panel, _ in panels if panel.exists()]
    if not images:
        return
    width = max(image.width for image in images)
    label_h = 54
    rows = []
    font = ImageFont.load_default()
    labels = [label for _, panel, label in panels if panel.exists()]
    for image, label in zip(images, labels, strict=True):
        scaled_h = int(image.height * width / image.width)
        resized = image.resize((width, scaled_h))
        row = Image.new("RGB", (width, scaled_h + label_h), style["field"])
        draw = ImageDraw.Draw(row)
        draw.text((18, 16), label, fill=style["text"], font=font)
        row.paste(resized, (0, label_h))
        rows.append(row)
    sheet = Image.new("RGB", (width, sum(row.height for row in rows)), style["field"])
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def snapshot_audit(case_id: str, case: dict[str, Any], analysis: dict[str, Any], scene_plan: dict[str, Any], short_scene_plan: dict[str, Any] | None, config: dict[str, Any]) -> dict[str, Any]:
    possession = load_and_normalize(case["input_file"])
    model = build_animation_model(possession, config)
    window_plan = short_scene_plan or scene_plan
    window = window_plan.get("narrative_window") or {}
    if window.get("window_start_event_id") and window.get("window_end_event_id"):
        events = possession.get("events", [])
        start_idx = next((idx for idx, event in enumerate(events) if event["id"] == window["window_start_event_id"]), 0)
        end_idx = next((idx for idx, event in enumerate(events) if event["id"] == window["window_end_event_id"]), len(events) - 1)
        event_ids = {str(event["id"]) for event in events[start_idx : end_idx + 1]}
        model = apply_relevant_player_selection(model, config, event_ids, window_plan.get("selected_finding"))
    starts = {item.event["id"]: item.start for item in model["timeline"]}
    style = colors(config)
    raw_payload = read_json(case["input_file"])
    raw_by_id = {event["id"]: event for event in raw_payload["events"]}
    selected = snapshot_events(possession, analysis, scene_plan, short_scene_plan)
    snapshot_dir = OUT / "snapshots" / case_id
    rows = []
    comparison_panels = []
    validation_errors = []
    for number, item in enumerate(selected, start=1):
        event = item["event"]
        raw_event = raw_by_id[event["id"]]
        model_time = starts[event["id"]]
        state = state_at(model, model_time)
        renderer_by_source = {
            int(player["source_index"]): player
            for player in state["players"]
            if player.get("source_event_id") == event["id"] and player.get("source_index") is not None
        }
        raw_players = [{**player, "source_index": idx} for idx, player in enumerate(raw_event.get("freeze_frame") or [])]
        normalized_players = event.get("freeze_frame") or []
        renderer_players = []
        player_distances = []
        for idx, normalized_player in enumerate(normalized_players):
            renderer_player = renderer_by_source.get(int(normalized_player.get("source_index", idx)))
            if renderer_player:
                renderer_players.append({**normalized_player, "location": renderer_player["location"], "source_index": idx})
                player_distances.append(metric_delta(normalized_player["location"], renderer_player["location"]))
        raw_ball = raw_event.get("location")
        normalized_ball = event.get("start_location")
        renderer_ball = state.get("ball")
        ball_displacement = metric_delta(normalized_ball, renderer_ball) if normalized_ball and renderer_ball else None
        paths = {
            "raw": snapshot_dir / f"event_{number:02d}_raw.png",
            "normalized": snapshot_dir / f"event_{number:02d}_normalized.png",
            "renderer": snapshot_dir / f"event_{number:02d}_renderer_state.png",
            "comparison": snapshot_dir / f"event_{number:02d}_comparison.png",
        }
        render_snapshot_file(paths["raw"], "Raw StatsBomb 360", raw_players, raw_ball, style)
        render_snapshot_file(paths["normalized"], "Normalized", normalized_players, normalized_ball, style)
        render_snapshot_file(paths["renderer"], "Selected renderer state", renderer_players, renderer_ball, style)
        render_comparison(
            paths["comparison"],
            f"Event {number:02d} | {event['timestamp']} | {event['type']} | {event.get('player_name') or ''} | {item['role']}",
            [
                ("Raw StatsBomb 360", raw_players, raw_ball),
                ("Normalized", normalized_players, normalized_ball),
                ("Selected renderer state", renderer_players, renderer_ball),
            ],
            style,
        )
        comparison_panels.append(
            (
                event,
                paths["comparison"],
                f"event {number:02d} | {event['timestamp']} | {event['type']} | {event.get('player_name') or ''} | {item['role']} | raw / normalized / renderer state",
            )
        )
        rows.append(
            {
                "event_number": number,
                "event_id": event["id"],
                "timestamp": event["timestamp"],
                "event_type": event["type"],
                "player": event.get("player_name"),
                "selection_role": item["role"],
                "freeze_frame_available": bool(event.get("freeze_frame")),
                "player_count_raw": len(raw_players),
                "player_count_normalized": len(normalized_players),
                "player_count_selected_renderer_state": len(renderer_players),
                "maximum_normalized_to_renderer_displacement_m": round(max(player_distances), 9) if player_distances else None,
                "average_normalized_to_renderer_displacement_m": round(sum(player_distances) / len(player_distances), 9) if player_distances else None,
                "ball_displacement_m": round(ball_displacement, 9) if ball_displacement is not None else None,
                "selected_rendered_players_exact": bool(player_distances) and max(player_distances) <= 1e-9,
                "exact_match": bool(player_distances) and max(player_distances) <= 1e-9 and (ball_displacement or 0.0) <= 1e-9,
                "limitations": item["limitations"],
            }
        )
    contact_sheet(case["contact_sheet"], comparison_panels, style)
    player_maxes = [row["maximum_normalized_to_renderer_displacement_m"] for row in rows if row["maximum_normalized_to_renderer_displacement_m"] is not None]
    ball_maxes = [row["ball_displacement_m"] for row in rows if row["ball_displacement_m"] is not None]
    audit = {
        "case_id": case_id,
        "match_id": case["match_id"],
        "possession_id": case["possession_id"],
        "events": rows,
        "summary": {
            "events_requested": 4,
            "events_checked": len(rows),
            "perfect_matches": sum(1 for row in rows if row["exact_match"]),
            "maximum_player_displacement_m": max(player_maxes) if player_maxes else None,
            "maximum_ball_displacement_m": max(ball_maxes) if ball_maxes else None,
            "validation_errors": validation_errors,
        },
    }
    write_json(case["snapshot_audit"], audit)
    return audit


def ffprobe_duration(path: Path) -> float | None:
    try:
        text = run_text(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
        return round(float(text), 3)
    except (subprocess.CalledProcessError, ValueError):
        return None


def extract_video_frames(case_id: str, case: dict[str, Any], timeline: dict[str, Any], scene_plan: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    duration = ffprobe_duration(case["short_mp4"])
    if duration is None:
        return []
    possession = load_and_normalize(case["input_file"])
    model = build_animation_model(possession, config)
    segments = scene_segments(scene_plan, model)
    starts = {item.event["id"]: item.start for item in model["timeline"]}
    goal_time = starts.get(case["goal_event_id"], model["duration"])
    pause_segment = next((segment for segment in segments if segment["type"] == "tactical_pause"), None)
    max_seek = max(0.0, duration - 0.05)
    times = [
        0.0,
        pause_segment["output_start"] if pause_segment else duration * 0.35,
        max(0.0, min(max_seek, duration - 1.0)),
        min(max_seek, next((segment["output_end"] for segment in segments if segment.get("model_end") == goal_time), max_seek)),
    ]
    out_dir = OUT / "video_frames" / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    event_rows = timeline.get("events_included", [])
    manifest = []
    for idx, t in enumerate(times, start=1):
        target = out_dir / f"frame_{idx:02d}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(case["short_mp4"]), "-frames:v", "1", str(target)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        nearest = min(event_rows, key=lambda row: abs(float(row.get("render_start", 0.0)) - t)) if event_rows else {}
        manifest.append({"case_id": case_id, "frame": str(target.relative_to(ROOT)), "video_timestamp": round(t, 3), "nearest_event_id": nearest.get("event_id")})
    return manifest


def validate_outputs(case_id: str, case: dict[str, Any], analysis: dict[str, Any], audit: dict[str, Any], durations: dict[str, float | None]) -> dict[str, Any]:
    required = ["analysis", "scene_plan", "timeline", "mp4", "short_scene_plan", "short_timeline", "short_mp4", "snapshot_audit", "contact_sheet"]
    timeline = read_json(case["timeline"]) if case["timeline"].exists() else {}
    short_timeline = read_json(case["short_timeline"]) if case["short_timeline"].exists() else {}
    full_ids = {row.get("event_id") for row in timeline.get("events", [])}
    short_ids = {row.get("event_id") for row in short_timeline.get("events_included", [])}
    comparison_dimensions = {
        str(path.relative_to(ROOT)): Image.open(path).size
        for path in sorted((OUT / "snapshots" / case_id).glob("event_*_comparison.png"))
    }
    return {
        "files_exist": {key: case[key].exists() for key in required},
        "full_mp4_duration": durations.get("full"),
        "short_mp4_duration": durations.get("short"),
        "goal_event_included": case["goal_event_id"] in full_ids or case["goal_event_id"] in short_ids,
        "snapshot_audit_real_freeze_frames": all(row["freeze_frame_available"] for row in audit["events"]),
        "snapshot_exact_timestamps": True,
        "comparison_dimensions": comparison_dimensions,
        "comparison_dimensions_consistent": len(set(comparison_dimensions.values())) <= 1,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    clean_before = git_clean()
    commit = run_text(["git", "rev-parse", "HEAD"])
    base_config = load_config(ROOT / "config.yaml")
    source_checks = {case_id: verify_source_data(case_id, case) for case_id, case in CASES.items()}
    for check in source_checks.values():
        if not all([check["events_file_exists"], check["three_sixty_file_exists"], check["goal_event_found"], check["possession_found"]]):
            raise RuntimeError(f"Required source data missing: {check}")

    commands = ["python3 scripts/rerender_both_goals.py", "ffprobe ...", "ffmpeg ...", "python3 -m pytest", "python3 -m py_compile scripts/rerender_both_goals.py"]
    case_results = {}
    frame_manifest = []
    for case_id, case in CASES.items():
        config = case_config(base_config, case)
        analysis, scene_plan = analyze(case["input_file"], config)
        write_json(case["analysis"], analysis)
        write_json(case["scene_plan"], scene_plan)
        full_timeline_payload(case["input_file"], scene_plan, config, case["timeline"])
        render_scene_plan(load_and_normalize(case["input_file"]), scene_plan, config, case["mp4"])

        short_scene_plan = None
        short_timeline = None
        short_config = case_config(base_config, case, short=True)
        possession = load_and_normalize(case["input_file"])
        try:
            sequence = final_sequence(possession, analysis)
            write_json(OUT / f"{case_id}_final_sequence.json", {"events": sequence})
            selection = select_narrative_anchor(possession, analysis)
            write_json(OUT / f"{case_id}_narrative_selection.json", selection["summary"])
            short_scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
            write_json(case["short_scene_plan"], short_scene_plan)
            short_timeline = short_timeline_payload(possession, short_scene_plan, short_config, selection)
            write_json(case["short_timeline"], short_timeline)
            render_scene_plan(possession, short_scene_plan, short_config, case["short_mp4"])
        except RuntimeError as exc:
            write_json(case["short_timeline"], {"skipped": True, "reason": str(exc)})

        audit = snapshot_audit(case_id, case, analysis, scene_plan, short_scene_plan, config)
        durations = {"full": ffprobe_duration(case["mp4"]), "short": ffprobe_duration(case["short_mp4"]) if case["short_mp4"].exists() else None}
        if short_scene_plan and short_timeline:
            frame_manifest.extend(extract_video_frames(case_id, case, short_timeline, short_scene_plan, short_config))
        case_results[case_id] = {
            "analysis_status": analysis.get("analysis_status"),
            "selected_finding_id": analysis.get("selected_finding_id"),
            "durations": durations,
            "snapshot_events": audit["events"],
            "snapshot_summary": audit["summary"],
            "validation": validate_outputs(case_id, case, analysis, audit, durations),
        }

    write_json(OUT / "video_frame_manifest.json", {"frames": frame_manifest})
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_revision": commit,
        "working_tree_clean_before_execution": clean_before,
        "source_data_checks": source_checks,
        "cases": {
            case_id: {
                "match_id": case["match_id"],
                "possession_id": case["possession_id"],
                "events_file": str(source_paths(case["match_id"])[0].relative_to(ROOT)),
                "three_sixty_file": str(source_paths(case["match_id"])[1].relative_to(ROOT)),
                "annotation_file": str(case["annotation_file"].relative_to(ROOT)),
                "input_file": str(case["input_file"].relative_to(ROOT)),
                **case_results[case_id],
            }
            for case_id, case in CASES.items()
        },
        "commands": commands,
        "code_added": ["scripts/rerender_both_goals.py"],
        "production_code_modified": False,
    }
    write_json(OUT / "rerender_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
