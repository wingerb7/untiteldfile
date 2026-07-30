from __future__ import annotations

from typing import Any

from src.domain.models import Event, NormalizedPossession
from src.scene_direction.models import SceneDirection
from src.tactical_episodes.models import TacticalEpisode

PAUSE_DURATION_SECONDS = 1.3
SINGLE_EVENT_PAUSE_DURATION_SECONDS = 2.1
FINAL_HOLD_SECONDS = 2.0
PLAY_DURATION_MIN_SECONDS = 1.8
PLAY_DURATION_MAX_SECONDS = 4.0

# Which side of the anchor event to highlight: the acting player ("passer", whose
# position is the event's start_location) or the "receiver" (end_location).
_HIGHLIGHT_TARGET_BY_EPISODE_TYPE = {"FINISH": "passer", "BUILDUP": "passer", "PRESS_ESCAPE": "passer"}


def _events_by_id(possession: NormalizedPossession) -> dict[str, Event]:
    return {event.event_id: event for event in possession.events}


def _play_duration_seconds(action_count: int) -> float:
    return max(PLAY_DURATION_MIN_SECONDS, min(PLAY_DURATION_MAX_SECONDS, 1.4 + 0.16 * action_count))


def _resolve_overlay(overlay_type: str | None, episode: TacticalEpisode, anchor_event: Event | None) -> dict[str, Any] | None:
    if overlay_type is None or anchor_event is None:
        return None
    if overlay_type in ("draw_pass_arrow", "draw_carry_arrow"):
        actual_type = "draw_carry_arrow" if anchor_event.event_type == "Carry" else "draw_pass_arrow"
        return {"type": actual_type, "event_id": anchor_event.event_id}
    if overlay_type == "highlight_player":
        target = _HIGHLIGHT_TARGET_BY_EPISODE_TYPE.get(episode.episode_type, "receiver")
        return {"type": "highlight_player", "target": target, "event_id": anchor_event.event_id}
    if overlay_type == "draw_defensive_line":
        line_x = episode.evidence.get("defensive_line_x")
        if line_x is None:
            line_x = (episode.evidence.get("defensive_line") or {}).get("line_x")
        return {"type": "draw_defensive_line", "x": line_x} if line_x is not None else None
    return None


def build_episodic_scene_plan(
    possession: NormalizedPossession,
    episodes: list[TacticalEpisode],
    directions: dict[str, SceneDirection],
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict[str, Any]:
    """Turn tactical episodes + scene directions into the render-ready `scenes` schema
    already understood by `render_scene_plan` (play/tactical_pause/hold + the existing
    overlay instruction vocabulary). Compresses the possession to only the selected
    episodes, targeting a concise consumer cut rather than a full replay."""
    if not episodes:
        raise ValueError("TACTICAL_SCENE_PLAN_NO_EPISODES")

    events_by_id = _events_by_id(possession)
    scenes: list[dict[str, Any]] = []
    mandatory_player_ids: set[str] = set()

    for episode in episodes:
        direction = directions[episode.episode_id]
        anchor_event = events_by_id.get(episode.start_event_id)

        instructions: list[dict[str, Any]] = []
        for overlay_type in (direction.primary_overlay, direction.secondary_overlay):
            resolved = _resolve_overlay(overlay_type, episode, anchor_event)
            if resolved:
                instructions.append(resolved)
        instructions.append({"type": "show_caption", "text": direction.caption_intent})

        single_event_episode = episode.start_event_id == episode.end_event_id
        scenes.append(
            {
                "scene_id": f"scene_{len(scenes) + 1}",
                "episode_id": episode.episode_id,
                "episode_confidence": episode.confidence,
                "football_question": episode.tactical_question,
                "type": "tactical_pause",
                "at_event_id": episode.start_event_id,
                "at_event_boundary": "start",
                "duration_seconds": SINGLE_EVENT_PAUSE_DURATION_SECONDS if single_event_episode else PAUSE_DURATION_SECONDS,
                "caption_timing": {"lead_seconds": 0.5, "fade_in_seconds": 0.2, "fade_out_seconds": 0.2},
                "instructions": instructions,
            }
        )

        if not single_event_episode:
            scenes.append(
                {
                    "scene_id": f"scene_{len(scenes) + 1}",
                    "episode_id": episode.episode_id,
                    "episode_confidence": episode.confidence,
                    "type": "play",
                    "from_event_id": episode.start_event_id,
                    "to_event_id": episode.end_event_id,
                    "target_duration_seconds": _play_duration_seconds(len(episode.participating_action_ids)),
                    "camera_target_event_id": episode.end_event_id,
                    "instructions": [{"type": "show_caption", "text": direction.caption_intent}],
                }
            )

        mandatory_player_ids.update(f"player:statsbomb:{player_id}" for player_id in episode.primary_actor_ids)

    final_episode = episodes[-1]
    final_direction = directions[final_episode.episode_id]
    scenes.append(
        {
            "scene_id": f"scene_{len(scenes) + 1}",
            "episode_id": final_episode.episode_id,
            "episode_confidence": final_episode.confidence,
            "type": "hold",
            "at_event_id": final_episode.end_event_id,
            "at_event_boundary": "end",
            "duration_seconds": FINAL_HOLD_SECONDS,
            "instructions": [{"type": "show_caption", "text": final_direction.caption_intent}],
        }
    )

    protagonist_id = final_episode.primary_actor_ids[0] if final_episode.primary_actor_ids else None
    secondary_player_ids = [
        player_id
        for episode in episodes
        for player_id in episode.primary_actor_ids
        if player_id != protagonist_id
    ]

    return {
        "possession_id": possession.possession_id,
        "format": {"width": width, "height": height, "fps": fps},
        "selected_finding_id": None,
        "selected_finding": None,
        "action_chain": None,
        "scenes": scenes,
        "narrative_window": {
            "window_start_event_id": episodes[0].start_event_id,
            "window_end_event_id": episodes[-1].end_event_id,
        },
        "visual_focus": {
            "protagonist_id": protagonist_id,
            "secondary_player_ids": sorted(dict.fromkeys(secondary_player_ids))[:4],
        },
        "tactical_participants": {
            "mandatory_player_ids": sorted(mandatory_player_ids),
            "maximum_context_players": 6,
        },
        "planning_basis": "TACTICAL_EPISODES_FROM_GENERIC_EPISODE_BUILDER",
        "presentation": {"hide_event_hud": True, "mode": "consumer"},
    }
