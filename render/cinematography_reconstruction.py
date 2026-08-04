from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
from matplotlib.colors import to_rgba
import numpy as np

from render.pitch import PITCH_LENGTH, PITCH_WIDTH, draw_pitch, sb_to_plot
from src.cinematography import source_time_at
from src.reconstruction import reconstruction_state_at, validate_reconstruction


def _lerp_point(a: list[float] | None, b: list[float] | None, amount: float) -> list[float] | None:
    if a is None:
        return b
    if b is None:
        return a
    return [float(a[i]) + (float(b[i]) - float(a[i])) * amount for i in (0, 1)]


def _active_beat(plan: dict[str, Any], source_time: float) -> dict[str, Any]:
    active = [
        beat for beat in plan["beats"]
        if float(beat["source_start"]) <= source_time + 1e-9 <= float(beat["source_end"])
    ]
    # Overlap is intentional: receipt can share a timestamp with carry or shot.
    # Perceptual boundary beats must win briefly so the handoff is actually seen.
    priority = {"OUTCOME_HOLD": 60, "RECEIPT": 50, "ESTABLISH": 40, "SHOT": 30, "CARRY": 20, "PASS_HANDOFF": 10}
    if active:
        return max(active, key=lambda beat: priority[beat["kind"]])
    completed = [beat for beat in plan["beats"] if float(beat["source_start"]) <= source_time + 1e-9]
    return completed[-1] if completed else plan["beats"][0]


def _focus(beat: dict[str, Any], source_time: float) -> tuple[list[float] | None, list[float] | None, float]:
    start, end = float(beat["source_start"]), float(beat["source_end"])
    amount = min(1.0, max(0.0, (source_time - start) / max(0.001, end - start)))
    primary, secondary = beat.get("primary_location"), beat.get("secondary_location")
    if beat["kind"] == "PASS_HANDOFF":
        # The receiver becomes available before arrival; this is the visual handoff.
        handoff = min(1.0, max(0.0, (amount - 0.28) / 0.55))
        return _lerp_point(primary, secondary, handoff), secondary, handoff
    if beat["kind"] in {"CARRY", "SHOT"}:
        return _lerp_point(primary, secondary, amount), primary, amount
    return primary, secondary, 1.0


def _nearest_teammate(players: list[dict[str, Any]], location: list[float] | None) -> str | None:
    if location is None:
        return None
    candidates = [player for player in players if player.get("teammate") and player.get("location")]
    if not candidates:
        return None
    closest = min(candidates, key=lambda player: (float(player["location"][0]) - location[0]) ** 2 + (float(player["location"][1]) - location[1]) ** 2)
    distance = ((float(closest["location"][0]) - location[0]) ** 2 + (float(closest["location"][1]) - location[1]) ** 2) ** 0.5
    return str(closest["tracking_id"]) if distance <= 8.0 else None


def render_cinematography_reconstruction(
    reconstruction: dict[str, Any], plan: dict[str, Any], output_path: str | Path, *,
    fps: int = 30, width: int = 1920, height: int = 1080,
) -> None:
    """Execute the benchmark shot plan without changing reconstructed state."""
    validate_reconstruction(reconstruction)
    if plan.get("reconstruction_sha256") != reconstruction.get("sha256"):
        raise ValueError("CINEMATOGRAPHY_RECONSTRUCTION_DIGEST_MISMATCH")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = float(plan["timing"]["presentation_duration"])
    frame_count = max(1, int(round(duration * fps)) + 1)
    dpi = 120
    style = {"field": "#123D2B", "field_stripe": "#1B5138", "pitch_lines": "#E9F1E9"}
    figure = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    figure.patch.set_facecolor("#091E16")
    axis = figure.add_axes([0.0, 0.0, 1.0, 1.0])
    draw_pitch(axis, style, {"brand": {"pitch": {"stripe_count": 12}}})
    axis.set_facecolor(style["field"])

    shadow = axis.scatter([], [], s=285, c="#07130E", alpha=.32, linewidths=0, zorder=4)
    attack = axis.scatter([], [], s=210, c="#F36C21", edgecolors="#F7FAF7", linewidths=2.0, zorder=6)
    defense = axis.scatter([], [], s=198, c="#76B7E5", edgecolors="#F7FAF7", linewidths=1.8, zorder=5)
    focus_ring = axis.scatter([], [], s=420, facecolors="none", edgecolors="#FFF2C2", linewidths=3.0, alpha=.0, zorder=8)
    incoming_ring = axis.scatter([], [], s=350, facecolors="none", edgecolors="#FFF2C2", linewidths=2.0, alpha=.0, zorder=7)
    ball_halo = axis.scatter([], [], s=330, c="#FFFFFF", alpha=.24, linewidths=0, zorder=9)
    ball = axis.scatter([], [], s=112, c="#FFFFFF", edgecolors="#111A15", linewidths=2.5, zorder=10)

    camera_x: float | None = None
    camera_y: float | None = None

    def point_array(players: list[dict[str, Any]], offset: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
        points = [sb_to_plot(player["location"]) for player in players if player.get("location")]
        return np.asarray([(p[0] + offset[0], p[1] + offset[1]) for p in points], dtype=float) if points else np.empty((0, 2))

    def update(frame_index: int) -> None:
        nonlocal camera_x, camera_y
        presentation_time = min(duration, frame_index / fps)
        source_time = source_time_at(plan, presentation_time, float(reconstruction["duration"]))
        state = reconstruction_state_at(reconstruction, source_time)
        beat = _active_beat(plan, source_time)
        focus_location, incoming_location, handoff = _focus(beat, source_time)
        players = state["players"]
        teammates = [player for player in players if player.get("teammate")]
        opponents = [player for player in players if not player.get("teammate")]
        primary_track = _nearest_teammate(players, focus_location)
        incoming_track = _nearest_teammate(players, incoming_location)

        shadow.set_offsets(point_array(players, (.45, -.55)))
        attack.set_offsets(point_array(teammates))
        defense.set_offsets(point_array(opponents))
        attack.set_facecolors([
            to_rgba("#FF8B45" if str(player["tracking_id"]) == primary_track else "#F36C21", 1.0 if str(player["tracking_id"]) in {primary_track, incoming_track} else .72)
            for player in teammates
        ] or [to_rgba("#F36C21", 1.0)])
        defense.set_facecolors([to_rgba("#76B7E5", .68) for _ in opponents] or [to_rgba("#76B7E5", .68)])

        primary_player = next((player for player in players if str(player["tracking_id"]) == primary_track), None)
        incoming_player = next((player for player in players if str(player["tracking_id"]) == incoming_track and incoming_track != primary_track), None)
        focus_ring.set_offsets(point_array([primary_player] if primary_player else []))
        focus_ring.set_alpha(.55 if primary_player else 0.0)
        incoming_ring.set_offsets(point_array([incoming_player] if incoming_player else []))
        incoming_ring.set_alpha((.18 + .32 * handoff) if incoming_player and beat["kind"] == "PASS_HANDOFF" else 0.0)

        ball_point = sb_to_plot(state.get("ball"))
        ball_offsets = np.asarray([ball_point], dtype=float) if ball_point else np.empty((0, 2))
        ball.set_offsets(ball_offsets)
        ball_halo.set_offsets(ball_offsets)
        crowded = 0
        if state.get("ball"):
            crowded = sum(1 for player in players if player.get("location") and ((player["location"][0] - state["ball"][0]) ** 2 + (player["location"][1] - state["ball"][1]) ** 2) ** .5 < 5.0)
        ball_halo.set_sizes([390 if crowded >= 2 else 300])
        ball_halo.set_alpha(.34 if crowded >= 2 else .20)

        target = sb_to_plot(focus_location) or ball_point or (PITCH_WIDTH / 2, PITCH_LENGTH - 18)
        # Goal remains compositional context for shots; pass handoffs lead toward
        # the verified receiver. Continuous easing avoids cuts in this slice.
        if beat["kind"] == "SHOT":
            target = ((target[0] + 40.0) / 2.0, (target[1] + 120.0) / 2.0)
        camera_x = target[0] if camera_x is None else camera_x + .065 * (target[0] - camera_x)
        camera_y = target[1] if camera_y is None else camera_y + .065 * (target[1] - camera_y)
        view_width = 72.0 if beat["kind"] in {"ESTABLISH", "PASS_HANDOFF"} else 62.0
        view_height = view_width * 9.0 / 16.0
        low_x = max(-3.0, min(PITCH_WIDTH + 3.0 - view_width, camera_x - view_width / 2))
        low_y = max(-2.5, min(PITCH_LENGTH + 2.5 - view_height, camera_y - view_height / 2))
        axis.set_xlim(low_x, low_x + view_width)
        axis.set_ylim(low_y, low_y + view_height)
        axis.set_aspect("equal", adjustable="box")

    writer = FFMpegWriter(fps=fps, codec="libx264", bitrate=10000, metadata={"title": "Benchmark cinematography vertical slice"}, extra_args=["-pix_fmt", "yuv420p", "-preset", "slow", "-crf", "17"])
    with writer.saving(figure, str(output_path), dpi):
        for frame_index in range(frame_count):
            update(frame_index)
            writer.grab_frame(facecolor=figure.get_facecolor())
    plt.close(figure)
