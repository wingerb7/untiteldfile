from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
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
import numpy as np
import yaml
from matplotlib.animation import FFMpegWriter
from matplotlib.patches import Circle

from analysis.interpolate import build_animation_model, state_at
from analysis.normalize import load_and_normalize
from render.animation import actor_player, coordinates, split_players
from render.pitch import draw_pitch, sb_to_plot
from render.styles import colors
from src.render.annotations import draw_annotations, load_annotations
from src.render.overlays import clear_overlays, create_overlay_artists, execute_instruction


def load_config(path: Path = Path("config.yaml")) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def event_start_times(model: dict[str, Any]) -> dict[str, float]:
    return {item.event["id"]: item.start for item in model["timeline"]}


def scene_event_time(scene: dict[str, Any], starts: dict[str, float], by_id: dict[str, Any], key: str = "at_event_id") -> float | None:
    event_id = scene.get(key)
    if scene.get("at_event_boundary") == "end":
        item = by_id.get(event_id)
        return item.end if item else None
    return starts.get(event_id)


def scene_segments(scene_plan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    starts = event_start_times(model)
    by_id = {item.event["id"]: item for item in model["timeline"]}
    segments: list[dict[str, Any]] = []
    output_cursor = 0.0

    for scene in scene_plan.get("scenes", []):
        scene_type = scene.get("type")
        if scene_type == "play":
            start_event_id = scene.get("from_event_id")
            end_event_id = scene.get("to_event_id")
            model_start = starts.get(start_event_id, 0.0)
            end_item = by_id.get(end_event_id)
            model_end = end_item.end if end_item else model["duration"]
            if model_end <= model_start:
                continue
            speed = max(0.1, float(scene.get("playback_speed") or 1.0))
            duration = (model_end - model_start) / speed
            segments.append(
                {
                    "type": "play",
                    "output_start": output_cursor,
                    "output_end": output_cursor + duration,
                    "model_start": model_start,
                    "model_end": model_end,
                    "playback_speed": speed,
                    "scene": scene,
                }
            )
            output_cursor += duration
            continue

        if scene_type == "tactical_pause":
            model_time = scene_event_time(scene, starts, by_id)
            if model_time is None:
                continue
            duration = max(0.0, float(scene.get("duration_seconds") or 0.0))
            segments.append(
                {
                    "type": "tactical_pause",
                    "output_start": output_cursor,
                    "output_end": output_cursor + duration,
                    "model_time": model_time,
                    "event_id": scene.get("at_event_id"),
                    "instructions": scene.get("instructions", []),
                    "scene": scene,
                }
            )
            output_cursor += duration
            continue

        if scene_type == "hold":
            model_time = scene_event_time(scene, starts, by_id) or model["duration"]
            duration = max(0.0, float(scene.get("duration_seconds") or 0.0))
            segments.append(
                {
                    "type": "hold",
                    "output_start": output_cursor,
                    "output_end": output_cursor + duration,
                    "model_time": model_time,
                    "event_id": scene.get("at_event_id"),
                    "instructions": scene.get("instructions", []),
                    "scene": scene,
                }
            )
            output_cursor += duration

    if segments:
        return segments

    duration = model["duration"]
    return [
        {
            "type": "play",
            "output_start": 0.0,
            "output_end": duration,
            "model_start": 0.0,
            "model_end": duration,
            "playback_speed": 1.0,
            "scene": {},
        }
    ]


def pause_windows(scene_plan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    return [segment for segment in scene_segments(scene_plan, model) if segment["type"] == "tactical_pause"]


def map_output_time(t: float, segments: list[dict[str, Any]]) -> tuple[float, dict[str, Any] | None]:
    if not segments:
        return max(0.0, t), None
    for segment in segments:
        if segment["output_start"] <= t <= segment["output_end"]:
            if segment["type"] == "play":
                elapsed = t - segment["output_start"]
                return min(segment["model_end"], segment["model_start"] + elapsed * segment["playback_speed"]), None
            return segment["model_time"], segment
    last = segments[-1]
    if last["type"] == "play":
        return last["model_end"], None
    return last["model_time"], last


def map_render_time(t: float, segments: list[dict[str, Any]], hook_hold: float, hook_model_time: float) -> tuple[float, dict[str, Any] | None, bool]:
    if t < hook_hold:
        return hook_model_time, None, True
    model_t, active_pause = map_output_time(t - hook_hold, segments)
    return model_t, active_pause, False


def jersey_number(player: dict[str, Any]) -> str:
    track_id = str(player.get("tracking_id") or player.get("track_id") or "0")
    suffix = track_id.rsplit("_", 1)[-1]
    if suffix.isdigit():
        return str(((int(suffix) - 1) % 99) + 1)
    return "?"


def player_label(player: dict[str, Any], event: dict[str, Any]) -> str | None:
    if player.get("actor") and event.get("player_name"):
        parts = str(event["player_name"]).split()
        return parts[-1] if parts else None
    return None


def debug_edge(player: dict[str, Any], default_edge: str) -> str:
    status = str(player.get("status") or "")
    if status == "OBSERVED":
        return "#31D158"
    if status == "INTERPOLATED":
        return "#FF9F0A"
    if status == "UNKNOWN":
        return "#9CA3AF"
    return default_edge


def draw_player_disc(ax: Any, player: dict[str, Any], event: dict[str, Any], color: str, edge: str, text_color: str, debug: bool = False) -> list[Any]:
    point = sb_to_plot(player.get("location"))
    if point is None:
        return []
    artists: list[Any] = []
    outline = debug_edge(player, edge) if debug else edge
    disc = Circle(point, radius=1.85, facecolor=color, edgecolor=outline, linewidth=2.0 if debug else 1.15, zorder=10)
    ax.add_patch(disc)
    artists.append(disc)
    artists.append(
        ax.text(
            point[0],
            point[1],
            jersey_number(player),
            ha="center",
            va="center",
            color=text_color,
            fontsize=7.5,
            weight="bold",
            zorder=11,
        )
    )
    label = player_label(player, event)
    if label:
        artists.append(
            ax.text(
                point[0],
                point[1] - 3.6,
                label,
                ha="center",
                va="top",
                color=text_color,
                fontsize=7.2,
                weight="bold",
                zorder=12,
                bbox={"boxstyle": "round,pad=0.16", "facecolor": "#121912", "edgecolor": edge, "linewidth": 0.5, "alpha": 0.72},
            )
        )
    if debug:
        artists.append(
            ax.text(
                point[0] + 2.1,
                point[1] + 1.9,
                f"{float(player.get('confidence', 0.0)):.2f}",
                ha="left",
                va="center",
                color=outline,
                fontsize=7,
                weight="bold",
                zorder=13,
            )
        )
    return artists


def update_trail_history(history: dict[str, list[tuple[float, tuple[float, float]]]], players: list[dict[str, Any]], model_t: float) -> None:
    for player in players:
        point = sb_to_plot(player.get("location"))
        if point is None:
            continue
        track_id = str(player.get("tracking_id") or player.get("track_id"))
        history.setdefault(track_id, []).append((model_t, point))
        history[track_id] = [(time, old_point) for time, old_point in history[track_id] if 0.0 <= model_t - time <= 0.40]


def draw_motion_trails(ax: Any, history: dict[str, list[tuple[float, tuple[float, float]]]], players: list[dict[str, Any]], style: dict[str, str], model_t: float) -> list[Any]:
    artists: list[Any] = []
    for player in players:
        track_id = str(player.get("tracking_id") or player.get("track_id"))
        points = history.get(track_id, [])
        if len(points) < 2:
            continue
        color = style["attack"] if player.get("teammate") else style["defense"]
        for idx in range(len(points) - 1):
            left_t, left = points[idx]
            _, right = points[idx + 1]
            age = max(0.0, model_t - left_t)
            alpha = max(0.0, 0.34 * (1.0 - age / 0.40))
            line = ax.plot([left[0], right[0]], [left[1], right[1]], color=color, linewidth=2.2, alpha=alpha, zorder=7)[0]
            artists.append(line)
    return artists


def draw_players(ax: Any, state: dict[str, Any], style: dict[str, str], trail_history: dict[str, list[tuple[float, tuple[float, float]]]], debug: bool = False) -> list[Any]:
    event = state.get("event") or {}
    players = state["players"]
    update_trail_history(trail_history, players, float(state["time"]))
    artists = draw_motion_trails(ax, trail_history, players, style, float(state["time"]))
    attackers, defenders = split_players(players)
    edge = style.get("player_edge", "#172017")
    for player in defenders:
        artists.extend(draw_player_disc(ax, player, event, style["defense"], edge, style["text"], debug))
    for player in attackers:
        artists.extend(draw_player_disc(ax, player, event, style["attack"], edge, "#071018", debug))
    return artists


def active_annotation_points(annotations: list[dict[str, Any]], t: float) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for annotation in annotations:
        if not (float(annotation.get("t_start", 0.0)) <= t <= float(annotation.get("t_end", 0.0))):
            continue
        if "x" in annotation and "y" in annotation:
            point = sb_to_plot([annotation.get("x"), annotation.get("y")])
            if point:
                points.append(point)
        for key in ("from", "to"):
            point = sb_to_plot(annotation.get(key))
            if point:
                points.append(point)
        for point_value in annotation.get("path", []) + annotation.get("polygon", []):
            point = sb_to_plot(point_value)
            if point:
                points.append(point)
    return points


def nearby_event_points(timeline: list[Any], t: float, lookback_seconds: float, lookahead_seconds: float) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    if lookback_seconds <= 0.0 and lookahead_seconds <= 0.0:
        return points
    window_start = t - max(0.0, lookback_seconds)
    window_end = t + max(0.0, lookahead_seconds)
    for item in timeline:
        if item.end < window_start or item.start > window_end:
            continue
        event = item.event
        for location in (event.get("start_location"), event.get("end_location")):
            point = sb_to_plot(location)
            if point:
                points.append(point)
    return points


def apply_camera(
    ax: Any,
    state: dict[str, Any],
    annotations: list[dict[str, Any]],
    camera: dict[str, float],
    style_config: dict[str, Any],
    timeline: list[Any] | None = None,
) -> None:
    ball_point = sb_to_plot(state.get("ball"))
    event = state.get("event") or {}
    points = [ball_point, sb_to_plot(event.get("start_location")), sb_to_plot(event.get("end_location"))]
    for player in state["players"]:
        point = sb_to_plot(player.get("location"))
        if point is None:
            continue
        if ball_point is None or np.hypot(point[0] - ball_point[0], point[1] - ball_point[1]) <= 34.0 or player.get("actor"):
            points.append(point)
    points.extend(active_annotation_points(annotations, float(state["time"])))
    points.extend(
        nearby_event_points(
            timeline or [],
            float(state["time"]),
            float(style_config.get("camera_lookback_seconds", 0.0)),
            float(style_config.get("camera_lookahead_seconds", 0.0)),
        )
    )
    points = [point for point in points if point is not None]
    if not points:
        return
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    margin = float(style_config.get("camera_margin", 13.0))
    aspect = 0.606
    width_needed = max(xs) - min(xs) + margin * 2.0
    height_needed = max(ys) - min(ys) + margin * 2.0
    height = max(height_needed, width_needed / aspect, 46.0)
    height = min(height, 124.0)
    width = height * aspect
    center_x = (min(xs) + max(xs)) / 2.0
    center_y = (min(ys) + max(ys)) / 2.0
    if width < 80.0:
        center_x = min(80.0 - width / 2.0, max(width / 2.0, center_x))
    else:
        center_x = 40.0
    if height < 120.0:
        center_y = min(120.0 - height / 2.0, max(height / 2.0, center_y))
    else:
        center_y = 60.0
    target_height = height
    if target_height > camera["height"]:
        ease = float(style_config.get("camera_zoom_out_ease", style_config.get("camera_ease", 0.08)))
    else:
        ease = float(style_config.get("camera_ease", 0.08))
    camera["x"] += (center_x - camera["x"]) * ease
    camera["y"] += (center_y - camera["y"]) * ease
    camera["height"] += (target_height - camera["height"]) * ease
    width = camera["height"] * aspect
    ax.set_xlim(max(-3.0, camera["x"] - width / 2.0), min(83.0, camera["x"] + width / 2.0))
    ax.set_ylim(max(-3.0, camera["y"] - camera["height"] / 2.0), min(123.0, camera["y"] + camera["height"] / 2.0))


def write_tracking_diagnostics(model: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(model["tracking_diagnostics"], indent=2, ensure_ascii=True), encoding="utf-8")


def render_debug_frame(model: dict[str, Any], config: dict[str, Any], t: float, output_path: Path) -> None:
    style = colors(config)
    width = int(config.get("animation", {}).get("width", 1080))
    height = int(config.get("animation", {}).get("height", 1920))
    dpi = 100
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor(style["field"])
    ax = fig.add_axes([0.08, 0.12, 0.84, 0.78])
    draw_pitch(ax, style, config)
    state = state_at(model, t)
    attackers, defenders = split_players(state["players"])
    for players, color in ((defenders, style["defense"]), (attackers, style["attack"])):
        xs, ys = coordinates(players)
        ax.scatter(xs, ys, s=90, c=color, edgecolors=style["actor_edge"], linewidths=0.8, zorder=5)
        for player in players:
            point = sb_to_plot(player.get("location"))
            if point is None:
                continue
            label = f"{player['tracking_id']} {player['team_id'].replace('_team', '')} {'obs' if player.get('observed') else 'interp'}"
            ax.text(point[0] + 0.9, point[1] + 0.9, label, color=style["text"], fontsize=8, zorder=9)
    ball_point = sb_to_plot(state["ball"])
    if ball_point:
        ax.scatter([ball_point[0]], [ball_point[1]], s=80, c=style["ball"], edgecolors=style["actor_edge"], linewidths=0.9, zorder=8)
    fig.text(0.5, 0.955, f"Tracking check | t={t:.2f}s", ha="center", va="top", color=style["text"], fontsize=24, weight="bold")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_tracking_check_frames(model: dict[str, Any], config: dict[str, Any], windows: list[dict[str, Any]]) -> list[Path]:
    pause_time = windows[0]["model_time"] if windows else model["duration"] * 0.35
    times = [
        model["frame_states"][0].timestamp if model["frame_states"] else 0.0,
        pause_time,
        model["duration"] * 0.62,
        max(0.0, model["duration"] - 0.25),
    ]
    paths = [ROOT / "renders" / f"tracking_check_{idx:02d}.png" for idx in range(1, 5)]
    for t, path in zip(times, paths, strict=True):
        render_debug_frame(model, config, t, path)
    return paths


def render_scene_plan(possession: dict[str, Any], scene_plan: dict[str, Any], config: dict[str, Any], output_path: Path, frames_dir: Path | None = None, frame_range: tuple[int, int] | None = None) -> dict[str, Any]:
    animation_config = config["animation"]
    fps = int(scene_plan.get("format", {}).get("fps") or animation_config.get("fps", 30))
    width = int(scene_plan.get("format", {}).get("width") or animation_config.get("width", 1080))
    height = int(scene_plan.get("format", {}).get("height") or animation_config.get("height", 1920))
    hook_hold = max(0.0, float(animation_config.get("hook_hold_seconds", 0.0)))
    hook_text_value = str(animation_config.get("hook_text") or "")
    hook_model_time = max(0.0, float(animation_config.get("hook_model_time", 0.0)))
    debug_mode = bool(animation_config.get("debug", False))
    dpi = 100
    style = colors(config)
    model = build_animation_model(possession, config)
    annotations_file = animation_config.get("annotations_file")
    annotations_path = ROOT / annotations_file if annotations_file else None
    annotations = load_annotations(annotations_path)
    segments = scene_segments(scene_plan, model)
    duration = hook_hold + (segments[-1]["output_end"] if segments else model["duration"])
    event_by_id = {event["id"]: event for event in possession["events"]}

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor(style["field"])
    ax = fig.add_axes([0.08, 0.12, 0.84, 0.78])
    draw_pitch(ax, style, config)
    top_text = fig.text(0.5, 0.955, "", ha="center", va="top", color=style["text"], fontsize=27, weight="bold")
    fig.text(0.5, 0.925, possession.get("match_label") or "", ha="center", va="top", color=style["muted_text"], fontsize=14)
    event_text = fig.text(0.5, 0.075, "", ha="center", va="bottom", color=style["text"], fontsize=18, weight="bold")
    detail_text = fig.text(0.5, 0.05, "", ha="center", va="bottom", color=style["muted_text"], fontsize=13)
    timeline_line = fig.add_axes([0.18, 0.035, 0.64, 0.008])
    timeline_line.set_facecolor(style["muted_text"])
    timeline_line.set_xlim(0, duration)
    timeline_line.set_ylim(0, 1)
    timeline_line.axis("off")
    progress_bar = timeline_line.axvspan(0, 0, color=style["ball"], ymin=0, ymax=1)

    xg_text = fig.text(0.5, 0.89, "", ha="center", va="top", color=style["ball"], fontsize=16, weight="bold")
    overlay_artists = create_overlay_artists(ax, fig, style)
    total_frames = max(1, int(duration * fps))
    dynamic_artists: list[Any] = []
    trail_history: dict[str, list[tuple[float, tuple[float, float]]]] = {}
    camera = {"x": 40.0, "y": 60.0, "height": 90.0, "last_model_t": -1.0}

    def clear_dynamic_artists() -> None:
        while dynamic_artists:
            artist = dynamic_artists.pop()
            try:
                artist.remove()
            except ValueError:
                pass

    def update(frame_idx: int) -> list[Any]:
        nonlocal progress_bar
        output_t = min(duration, frame_idx / fps)
        model_t, active_pause, is_hook = map_render_time(output_t, segments, hook_hold, hook_model_time)
        state = state_at(model, model_t)
        if model_t < camera["last_model_t"]:
            trail_history.clear()
        camera["last_model_t"] = model_t
        clear_dynamic_artists()
        apply_camera(ax, state, annotations, camera, animation_config, model["timeline"])
        event = state["event"] or {}
        start = sb_to_plot(event.get("start_location"))
        ball_point = sb_to_plot(state["ball"])
        if event.get("type") in {"Pass", "Shot"} and start and ball_point:
            line = ax.plot(
                [start[0], ball_point[0]],
                [start[1], ball_point[1]],
                color=style["ball"],
                linewidth=2.0,
                alpha=0.72 if event.get("type") == "Shot" else 0.42,
                zorder=8,
            )[0]
            dynamic_artists.append(line)

        dynamic_artists.extend(draw_annotations(ax, annotations, model_t, style))
        dynamic_artists.extend(draw_players(ax, state, style, trail_history, debug_mode))

        actor = actor_player(state["players"])
        actor_point = sb_to_plot(actor.get("location")) if actor else None
        if actor_point:
            actor_ring = Circle(actor_point, radius=3.0, facecolor="none", edgecolor=style["actor_edge"], linewidth=2.2, zorder=19)
            ax.add_patch(actor_ring)
            dynamic_artists.append(actor_ring)
        if ball_point:
            ball = Circle(ball_point, radius=1.25, facecolor=style["ball"], edgecolor=style.get("player_edge", "#111111"), linewidth=1.0, zorder=25)
            ax.add_patch(ball)
            dynamic_artists.append(ball)

        event_text.set_text(f"{event.get('type', '')}  |  {event.get('player_name') or ''}".strip())
        if is_hook and hook_text_value:
            top_text.set_text(hook_text_value)
            top_text.set_alpha(1.0)
        else:
            top_text.set_text("")
            top_text.set_alpha(0.0)
        if event.get("type") == "Shot" and event.get("xg") is not None:
            xg_text.set_text(f"xG {float(event['xg']):.3f}")
            detail_text.set_text(f"xG {float(event['xg']):.3f}")
        else:
            xg_text.set_text("")
            detail_text.set_text(f"{possession.get('team') or 'Attack'} reconstruction from StatsBomb 360")

        clear_overlays(overlay_artists)
        if active_pause:
            pause_event = event_by_id.get(active_pause["event_id"], event)
            for instruction in active_pause["instructions"]:
                execute_instruction(instruction, pause_event, overlay_artists)

        progress_bar.remove()
        progress_bar = timeline_line.axvspan(0, output_t, color=style["ball"], ymin=0, ymax=1)
        return [
            *dynamic_artists,
            top_text,
            event_text,
            detail_text,
            xg_text,
            progress_bar,
            *overlay_artists.values(),
        ]

    if frames_dir is not None:
        frames_dir.mkdir(parents=True, exist_ok=True)
        (frames_dir / "TOTAL").write_text(str(total_frames))
        lo, hi = frame_range or (0, total_frames)
        for frame_idx in range(lo, min(hi, total_frames)):
            update(frame_idx)
            fig.savefig(frames_dir / f"f{frame_idx:05d}.png", dpi=dpi, facecolor=fig.get_facecolor())
        plt.close(fig)
        return model
    writer = FFMpegWriter(fps=fps, metadata={"title": f"Annotated possession {possession.get('possession_id', '')}"}, bitrate=4500)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with writer.saving(fig, str(output_path), dpi):
        for frame_idx in range(total_frames):
            update(frame_idx)
            writer.grab_frame()
    plt.close(fig)
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--scene-plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", default=Path("config.yaml"), type=Path)
    args = parser.parse_args()

    config = load_config(args.config)
    possession = load_and_normalize(args.input)
    scene_plan = json.loads(args.scene_plan.read_text(encoding="utf-8"))
    model = render_scene_plan(possession, scene_plan, config, args.output)
    diagnostics_path = args.output.with_name(f"{args.output.stem}_tracking_diagnostics.json")
    write_tracking_diagnostics(model, diagnostics_path)
    render_tracking_check_frames(model, config, pause_windows(scene_plan, model))
    print(f"Wrote {args.output}")
    print(f"Wrote {diagnostics_path}")


if __name__ == "__main__":
    main()
