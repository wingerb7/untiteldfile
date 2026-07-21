from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.domain.models import PlayerIdentityHook, SocialPacingProfile, SocialTacticalBeat, SocialVideoPlan


PACING_PROFILES = {
    "fast": SocialPacingProfile("fast", 1.0, 0.25, 0.8, 0.9, 1.4, 0.35, 0.6, 1.25),
    "balanced": SocialPacingProfile("balanced", 1.4, 0.35, 1.2, 1.1, 2.0, 0.6, 0.8, 1.0),
    "explanatory": SocialPacingProfile("explanatory", 1.8, 0.45, 1.5, 1.5, 2.4, 0.8, 1.1, 0.85),
}


def resolve_caption_frame(requested_timestamp: float, event_timestamp: float, fps: int) -> dict[str, Any]:
    """Resolve to the latest frame no later than the requested/event boundary."""
    target = min(float(requested_timestamp), float(event_timestamp))
    frame = max(0, math.floor(target * fps + 1e-9))
    actual = frame / fps
    return {
        "requested_activation_timestamp": round(float(requested_timestamp), 6),
        "event_timestamp": round(float(event_timestamp), 6),
        "resolved_frame_index": frame,
        "actual_displayed_timestamp": round(actual, 6),
        "offset_from_event_boundary": round(actual - float(event_timestamp), 6),
        "clamped_or_shifted": abs(actual - float(requested_timestamp)) > 1e-9,
        "shift_reason": "quantized_to_frame_on_or_before_event" if abs(actual - float(requested_timestamp)) > 1e-9 else None,
        "late": actual > float(event_timestamp) + 1e-9,
    }


def build_social_video_plan(
    scene_plan: dict[str, Any],
    possession: dict[str, Any],
    *,
    pacing: str = "balanced",
    portrait_path: str | None = None,
    hook_text: str | None = None,
) -> dict[str, Any]:
    profile = PACING_PROFILES[pacing]
    chain = scene_plan.get("action_chain") or {}
    steps = list(chain.get("steps") or [])[:4]
    events = {event["id"]: event for event in possession.get("events", [])}
    first = events.get(steps[0].get("event_id")) if steps else None
    featured_id = (steps[0].get("actor_id") if steps else None) or (first or {}).get("player_id")
    player_name = str((first or {}).get("player_name") or "Featured player")
    shirt = str((first or {}).get("jersey_number") or "") or None
    team = possession.get("team") or possession.get("match_label")
    supplied_hook = hook_text or scene_plan.get("hook_text") or f"Watch {player_name.split()[-1]}'s run after the pass."
    if len(supplied_hook) > 72:
        supplied_hook = supplied_hook[:69].rstrip() + "..."
    portrait = portrait_path if portrait_path and Path(portrait_path).is_file() else None
    identity = PlayerIdentityHook(player_name, shirt, team, supplied_hook, profile.hook_duration, "crossfade", portrait)
    beats = []
    for index, step in enumerate(steps, 1):
        actors = [value for value in (step.get("actor_id"), step.get("receiver_id")) if value]
        beats.append(SocialTacticalBeat(
            f"beat_{index}", str(step.get("event_id")), "event", "next_event", actors,
            str(step.get("caption") or ""), "payoff" if index == len(steps) else "standard",
        ))
    payoff = beats[-1].caption if beats else None
    return asdict(SocialVideoPlan(featured_id, identity, profile, beats, payoff))


def apply_social_format(scene_plan: dict[str, Any], social_plan: dict[str, Any]) -> dict[str, Any]:
    """Add editorial timing without changing event anchors or tactical metadata."""
    plan = {**scene_plan, "social_video": social_plan}
    profile = social_plan["pacing_profile"]
    scenes = []
    for scene in scene_plan.get("scenes", []):
        item = dict(scene)
        if item.get("type") == "tactical_pause":
            requested = float(item.get("duration_seconds") or profile["caption_hold_min"])
            item["duration_seconds"] = min(profile["caption_hold_max"], max(profile["caption_hold_min"], requested))
            item.pop("pause_frame_offset", None)
        elif item.get("type") == "hold":
            item["duration_seconds"] = max(float(item.get("duration_seconds") or 0), profile["final_payoff_hold"])
        scenes.append(item)
    plan["scenes"] = scenes
    return plan
