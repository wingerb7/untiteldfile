from __future__ import annotations

from dataclasses import dataclass, replace
from math import atan2, cos, hypot, isfinite, pi, sin
from typing import Any

import numpy as np

from src.domain.models import Position


PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0
TEAM_ATTACK = "attacking_team"
TEAM_DEFENSE = "defending_team"
INFERRED_STATUSES = {"PREDICTED_OR_HELD", "MISSING_BUT_ALIVE", "INTERPOLATED"}


@dataclass(frozen=True)
class Polygon:
    points: tuple[tuple[float, float], ...]

    @property
    def area(self) -> float:
        if len(self.points) < 3:
            return 0.0
        total = 0.0
        for left, right in zip(self.points, self.points[1:] + self.points[:1], strict=False):
            total += left[0] * right[1] - right[0] * left[1]
        return abs(total) * 0.5


@dataclass(frozen=True)
class TeamShapeState:
    centroid: np.ndarray
    width: float
    depth: float
    orientation: float
    convex_hull: Polygon
    compactness: float
    observed_count: int
    confidence: float


@dataclass(frozen=True)
class TeamMotionEstimate:
    previous: TeamShapeState
    current: TeamShapeState
    translation: np.ndarray
    orientation_delta: float
    width_delta: float
    depth_delta: float
    width_ratio: float
    depth_ratio: float
    confidence: float


@dataclass(frozen=True)
class TeamShapeDiagnostics:
    frames: list[dict[str, Any]]
    summary: dict[str, Any]


def _status_value(player: Any) -> str:
    value = getattr(player, "status", "")
    return str(getattr(value, "value", value))


def _xy(player: Any) -> tuple[float, float]:
    position = getattr(player, "position")
    return float(position.x), float(position.y)


def _convex_hull(points: np.ndarray) -> Polygon:
    unique = sorted({(float(x), float(y)) for x, y in points})
    if len(unique) <= 1:
        return Polygon(tuple(unique))

    def cross(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return Polygon(tuple(lower[:-1] + upper[:-1]))


def _angle_delta(left: float, right: float) -> float:
    delta = right - left
    while delta > pi:
        delta -= 2.0 * pi
    while delta < -pi:
        delta += 2.0 * pi
    return delta


def _rotate(vector: np.ndarray, angle: float) -> np.ndarray:
    return np.array([vector[0] * cos(angle) - vector[1] * sin(angle), vector[0] * sin(angle) + vector[1] * cos(angle)])


def _clamp_position(position: np.ndarray) -> Position:
    return Position(float(np.clip(position[0], 0.0, PITCH_LENGTH)), float(np.clip(position[1], 0.0, PITCH_WIDTH)))


def _team_players(frame: Any, team_id: str, observed_only: bool = False) -> list[Any]:
    players = [
        player
        for player in getattr(frame, "players", [])
        if getattr(player, "team_id", None) == team_id and getattr(player, "visible", True)
    ]
    if observed_only:
        players = [player for player in players if getattr(player, "observed", False)]
    return players


def _observed_by_track(frame: Any, team_id: str) -> dict[str, Any]:
    return {
        player.tracking_id: player
        for player in _team_players(frame, team_id)
        if getattr(player, "observed", False)
    }


def _overlap_translation(previous_frame: Any, current_frame: Any, team_id: str) -> tuple[np.ndarray | None, float]:
    previous = _observed_by_track(previous_frame, team_id)
    current = _observed_by_track(current_frame, team_id)
    shared = sorted(set(previous) & set(current))
    if len(shared) < 2:
        return None, 0.0
    deltas = [np.array(_xy(current[track_id])) - np.array(_xy(previous[track_id])) for track_id in shared]
    translation = np.mean(np.array(deltas, dtype=float), axis=0)
    distance = float(np.linalg.norm(translation))
    distance_confidence = 1.0 - float(np.clip(distance / 35.0, 0.0, 0.8))
    count_confidence = float(np.clip(len(shared) / 5.0, 0.0, 1.0))
    return translation, count_confidence * distance_confidence


def calculate_team_shape(players: list[Any]) -> TeamShapeState | None:
    observed = [player for player in players if getattr(player, "observed", False) and getattr(player, "visible", True)]
    outfield = [player for player in observed if not getattr(player, "is_goalkeeper", False)]
    shape_players = outfield if len(outfield) >= 3 else observed
    if len(shape_players) < 2:
        return None

    points = np.array([_xy(player) for player in shape_players], dtype=float)
    centroid = points.mean(axis=0)
    centered = points - centroid
    if len(points) >= 3 and np.any(centered):
        covariance = np.cov(centered, rowvar=False)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        principal = eigenvectors[:, int(np.argmax(eigenvalues))]
    else:
        principal = np.array([1.0, 0.0])
    if principal[0] < 0 or (abs(float(principal[0])) <= 1e-9 and principal[1] < 0):
        principal = -principal
    orientation = atan2(float(principal[1]), float(principal[0]))
    forward = np.array([cos(orientation), sin(orientation)])
    lateral = np.array([-sin(orientation), cos(orientation)])
    projected_depth = centered @ forward
    projected_width = centered @ lateral
    depth = float(projected_depth.max() - projected_depth.min()) if len(projected_depth) else 0.0
    width = float(projected_width.max() - projected_width.min()) if len(projected_width) else 0.0
    hull = _convex_hull(points)
    envelope = max(width * depth, 1.0)
    compactness = float(np.clip(1.0 - hull.area / envelope, 0.0, 1.0))
    confidence = float(np.clip((len(shape_players) - 1) / 5.0, 0.0, 1.0))
    return TeamShapeState(
        centroid=centroid,
        width=max(width, 0.001),
        depth=max(depth, 0.001),
        orientation=orientation,
        convex_hull=hull,
        compactness=compactness,
        observed_count=len(shape_players),
        confidence=confidence,
    )


def estimate_team_motion(previous: TeamShapeState | None, current: TeamShapeState | None) -> TeamMotionEstimate | None:
    if previous is None or current is None:
        return None
    width_ratio = float(np.clip(current.width / max(previous.width, 0.001), 0.75, 1.25))
    depth_ratio = float(np.clip(current.depth / max(previous.depth, 0.001), 0.75, 1.25))
    translation = current.centroid - previous.centroid
    distance = float(np.linalg.norm(translation))
    distance_confidence = 1.0 - float(np.clip(distance / 35.0, 0.0, 0.8))
    confidence = float(np.clip(min(previous.confidence, current.confidence) * distance_confidence, 0.0, 1.0))
    return TeamMotionEstimate(
        previous=previous,
        current=current,
        translation=translation,
        orientation_delta=_angle_delta(previous.orientation, current.orientation),
        width_delta=current.width - previous.width,
        depth_delta=current.depth - previous.depth,
        width_ratio=width_ratio,
        depth_ratio=depth_ratio,
        confidence=confidence,
    )


def _ball_adjustment(team_id: str, ball: list[float] | None, shape: TeamShapeState) -> tuple[np.ndarray, float]:
    if not ball or len(ball) < 2:
        return np.zeros(2), 1.0
    ball_xy = np.array([float(ball[0]), float(ball[1])])
    if not np.all(np.isfinite(ball_xy)):
        return np.zeros(2), 1.0
    vector = ball_xy - shape.centroid
    distance = max(float(np.linalg.norm(vector)), 0.001)
    direction = vector / distance
    if team_id == TEAM_DEFENSE and ball_xy[0] >= PITCH_LENGTH * 0.66:
        return direction * min(4.0, distance * 0.12), 0.92
    if team_id == TEAM_ATTACK and ball_xy[0] >= PITCH_LENGTH * 0.66:
        return direction * min(2.0, distance * 0.08), 0.96
    if team_id == TEAM_DEFENSE and ball_xy[0] <= PITCH_LENGTH * 0.33:
        return direction * min(2.0, distance * 0.06), 0.96
    return np.zeros(2), 1.0


def propagate_team_shape(
    frames: list[Any],
    *,
    balls_by_event_id: dict[str, list[float] | None] | None = None,
    minimum_motion_confidence: float = 0.35,
) -> tuple[list[Any], TeamShapeDiagnostics]:
    if not frames:
        return frames, TeamShapeDiagnostics([], {"frames_changed": 0})

    balls_by_event_id = balls_by_event_id or {}
    shape_by_frame: list[dict[str, TeamShapeState | None]] = []
    for frame in frames:
        shape_by_frame.append(
            {
                TEAM_ATTACK: calculate_team_shape(_team_players(frame, TEAM_ATTACK, observed_only=True)),
                TEAM_DEFENSE: calculate_team_shape(_team_players(frame, TEAM_DEFENSE, observed_only=True)),
            }
        )

    output = [frames[0]]
    diagnostics: list[dict[str, Any]] = []
    total_changed = 0
    displacements: list[float] = []
    low_confidence_stops = 0

    for idx in range(1, len(frames)):
        frame = frames[idx]
        previous_frame = output[idx - 1]
        previous_previous_frame = output[idx - 2] if idx >= 2 else None
        next_players = []
        frame_changed = 0
        frame_displacements: list[float] = []
        teams: dict[str, Any] = {}
        previous_players = {
            player.tracking_id: player
            for player in getattr(previous_frame, "players", [])
            if getattr(player, "visible", True)
        }
        previous_previous_players = (
            {
                player.tracking_id: player
                for player in getattr(previous_previous_frame, "players", [])
                if getattr(player, "visible", True)
            }
            if previous_previous_frame is not None
            else {}
        )

        for team_id in (TEAM_ATTACK, TEAM_DEFENSE):
            motion = estimate_team_motion(shape_by_frame[idx - 1][team_id], shape_by_frame[idx][team_id])
            overlap_translation, overlap_confidence = _overlap_translation(previous_frame, frame, team_id)
            effective_translation = overlap_translation if overlap_translation is not None else (None if motion is None else motion.translation)
            effective_confidence = max(overlap_confidence, 0.0 if motion is None else motion.confidence)
            teams[team_id] = {
                "observed_count": None if shape_by_frame[idx][team_id] is None else shape_by_frame[idx][team_id].observed_count,
                "motion_confidence": None if motion is None else round(effective_confidence, 3),
                "translation": None if effective_translation is None else [round(float(effective_translation[0]), 3), round(float(effective_translation[1]), 3)],
                "width": None if shape_by_frame[idx][team_id] is None else round(shape_by_frame[idx][team_id].width, 3),
                "depth": None if shape_by_frame[idx][team_id] is None else round(shape_by_frame[idx][team_id].depth, 3),
                "compactness": None if shape_by_frame[idx][team_id] is None else round(shape_by_frame[idx][team_id].compactness, 3),
            }

        for player in getattr(frame, "players", []):
            status = _status_value(player)
            if getattr(player, "observed", False) or status not in INFERRED_STATUSES:
                next_players.append(player)
                continue
            previous_player = previous_players.get(player.tracking_id)
            if previous_player is None:
                next_players.append(player)
                continue
            motion = estimate_team_motion(shape_by_frame[idx - 1][player.team_id], shape_by_frame[idx][player.team_id])
            overlap_translation, overlap_confidence = _overlap_translation(previous_frame, frame, player.team_id)
            effective_confidence = max(overlap_confidence, 0.0 if motion is None else motion.confidence)
            if motion is None or effective_confidence < minimum_motion_confidence:
                low_confidence_stops += 1
                next_players.append(player)
                continue

            translation = overlap_translation if overlap_translation is not None else motion.translation
            centroid = motion.previous.centroid + translation
            width_ratio = 1.0 if motion.current.observed_count < motion.previous.observed_count else motion.width_ratio
            depth_ratio = 1.0 if motion.current.observed_count < motion.previous.observed_count else motion.depth_ratio
            offset = np.array(_xy(previous_player)) - motion.previous.centroid
            offset = _rotate(offset, motion.orientation_delta)
            offset[0] *= depth_ratio
            offset[1] *= width_ratio
            ball_shift, width_factor = _ball_adjustment(player.team_id, balls_by_event_id.get(str(frame.event_id)), motion.current)
            adjusted_offset = np.array([offset[0], offset[1] * width_factor])
            previous_previous = previous_previous_players.get(player.tracking_id)
            inertia = np.zeros(2)
            if previous_previous is not None:
                inertia = (np.array(_xy(previous_player)) - np.array(_xy(previous_previous))) * 0.12
                if not np.all(np.isfinite(inertia)):
                    inertia = np.zeros(2)
            candidate = centroid + adjusted_offset + ball_shift + inertia
            if not np.all(np.isfinite(candidate)):
                next_players.append(player)
                continue

            old_xy = np.array(_xy(player))
            displacement = float(np.linalg.norm(candidate - old_xy))
            individual_confidence = float(getattr(player, "confidence", 0.0))
            team_confidence = float(motion.current.confidence)
            blended_confidence = float(np.clip(individual_confidence * 0.6 + team_confidence * 0.3 + effective_confidence * 0.1, 0.0, 1.0))
            updated = replace(
                player,
                position=_clamp_position(candidate),
                confidence=blended_confidence,
                position_confidence=blended_confidence,
                alpha=max(0.28, min(0.72, blended_confidence)),
                individual_confidence=individual_confidence,
                team_confidence=team_confidence,
                motion_confidence=float(effective_confidence),
            )
            next_players.append(updated)
            frame_changed += 1
            total_changed += 1
            frame_displacements.append(displacement)
            displacements.append(displacement)

        if frame_changed:
            output.append(replace(frame, players=next_players))
        else:
            output.append(frame)
        diagnostics.append(
            {
                "event_id": str(frame.event_id),
                "timestamp": float(frame.timestamp),
                "players_adjusted": frame_changed,
                "average_inferred_displacement": (
                    round(sum(frame_displacements) / len(frame_displacements), 3) if frame_displacements else 0.0
                ),
                "max_inferred_displacement": round(max(frame_displacements), 3) if frame_displacements else 0.0,
                "teams": teams,
            }
        )

    summary = {
        "frames_evaluated": max(0, len(frames) - 1),
        "frames_changed": sum(1 for row in diagnostics if row["players_adjusted"]),
        "players_adjusted": total_changed,
        "low_confidence_stops": low_confidence_stops,
        "average_inferred_displacement": round(sum(displacements) / len(displacements), 3) if displacements else 0.0,
        "max_inferred_displacement": round(max(displacements), 3) if displacements else 0.0,
    }
    return output, TeamShapeDiagnostics(diagnostics, summary)


def team_shape_drift_metrics(frames: list[Any]) -> dict[str, Any]:
    rows = []
    centroid_drifts: list[float] = []
    width_drifts: list[float] = []
    depth_drifts: list[float] = []
    compactness_drifts: list[float] = []
    for left, right in zip(frames, frames[1:], strict=False):
        for team_id in (TEAM_ATTACK, TEAM_DEFENSE):
            left_shape = calculate_team_shape(_team_players(left, team_id, observed_only=True))
            right_shape = calculate_team_shape(_team_players(right, team_id, observed_only=True))
            motion = estimate_team_motion(left_shape, right_shape)
            if motion is None:
                continue
            centroid_drift = float(np.linalg.norm(motion.translation))
            centroid_drifts.append(centroid_drift)
            width_drifts.append(abs(motion.width_delta))
            depth_drifts.append(abs(motion.depth_delta))
            compactness_drifts.append(abs(right_shape.compactness - left_shape.compactness))
            rows.append(
                {
                    "from_event_id": str(left.event_id),
                    "to_event_id": str(right.event_id),
                    "team_id": team_id,
                    "centroid_drift": round(centroid_drift, 3),
                    "team_width_drift": round(abs(motion.width_delta), 3),
                    "team_depth_drift": round(abs(motion.depth_delta), 3),
                    "compactness_drift": round(abs(right_shape.compactness - left_shape.compactness), 3),
                    "convex_hull_overlap": None,
                    "motion_confidence": round(motion.confidence, 3),
                }
            )

    def average(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None

    return {
        "summary": {
            "centroid_drift": average(centroid_drifts),
            "team_width_drift": average(width_drifts),
            "team_depth_drift": average(depth_drifts),
            "compactness_drift": average(compactness_drifts),
        },
        "segments": rows,
    }
