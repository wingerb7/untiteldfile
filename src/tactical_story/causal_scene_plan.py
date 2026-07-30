from __future__ import annotations

from typing import Any

from src.contracts import Artifact
from src.domain.models import NormalizedPossession
from src.scene_direction.models import SceneDirection
from src.tactical_episodes.models import TacticalEpisode


ROLE_TIMING = {
    "SETUP": {"pause": 2.4, "play": 3.2},
    "PROGRESSION": {"pause": 1.4, "play": 4.6},
    "DECISIVE_MECHANISM": {"pause": 2.2, "play": 3.2},
    "FINAL_ACTION": {"pause": 2.4, "play": 3.2},
    "FINISH": {"pause": 2.2, "play": 0.0},
}
FINAL_HOLD_SECONDS = 2.4


def _resolve_instruction(
    overlay_type: str | None,
    episode: TacticalEpisode,
) -> dict[str, Any] | None:
    if overlay_type is None:
        return None
    if overlay_type in {"draw_pass_arrow", "draw_carry_arrow"}:
        return {"type": "draw_pass_arrow", "event_id": episode.start_event_id}
    if overlay_type == "highlight_player":
        return {"type": "highlight_player", "target": "passer", "event_id": episode.start_event_id}
    # Graph-backed defensive-line geometry is intentionally not reconstructed here:
    # omitting an unsupported overlay is safer than bypassing Perception evidence.
    return None


def build_causal_narrative_scene_plan(
    possession: NormalizedPossession,
    selection: Artifact,
    episodes: list[TacticalEpisode],
    directions: dict[str, SceneDirection],
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict[str, Any]:
    units = list(selection["units"])
    if not units or units[-1]["narrative_role"] != "FINISH":
        raise ValueError("CAUSAL_SCENE_PLAN_FINISH_MISSING")
    if len(units) != len(episodes) or {item["unit_id"] for item in units} != {item.episode_id for item in episodes}:
        raise ValueError("CAUSAL_SCENE_PLAN_SELECTION_MISMATCH")
    episode_by_id = {episode.episode_id: episode for episode in episodes}
    scenes: list[dict[str, Any]] = []
    mandatory: set[str] = set()
    for unit in units:
        role = unit["narrative_role"]
        if role not in ROLE_TIMING:
            raise ValueError("CAUSAL_SCENE_PLAN_ROLE_INVALID")
        episode = episode_by_id[unit["unit_id"]]
        direction = directions[episode.episode_id]
        instructions = [
            item
            for item in (
                _resolve_instruction(direction.primary_overlay, episode),
                _resolve_instruction(direction.secondary_overlay, episode),
            )
            if item is not None
        ]
        instructions.append({"type": "show_caption", "text": unit["factual_caption"]})
        scenes.append({
            "scene_id": f"scene_{len(scenes) + 1}",
            "episode_id": episode.episode_id,
            "causal_narrative_unit_id": unit["unit_id"],
            "narrative_role": role,
            "supporting_episode_ids": list(unit["supporting_episode_ids"]),
            "football_question": unit["tactical_purpose"],
            "type": "tactical_pause",
            "at_event_id": episode.start_event_id,
            "at_event_boundary": "start",
            "duration_seconds": ROLE_TIMING[role]["pause"],
            "caption_timing": {"lead_seconds": 0.5, "fade_in_seconds": 0.2, "fade_out_seconds": 0.2},
            "instructions": instructions,
        })
        if role != "FINISH" and episode.start_event_id != episode.end_event_id:
            scenes.append({
                "scene_id": f"scene_{len(scenes) + 1}",
                "episode_id": episode.episode_id,
                "causal_narrative_unit_id": unit["unit_id"],
                "narrative_role": role,
                "supporting_episode_ids": list(unit["supporting_episode_ids"]),
                "type": "play",
                "from_event_id": episode.start_event_id,
                "to_event_id": episode.end_event_id,
                "target_duration_seconds": ROLE_TIMING[role]["play"],
                "camera_target_event_id": episode.end_event_id,
                "instructions": [{"type": "show_caption", "text": unit["factual_caption"]}],
            })
        mandatory.update(f"player:statsbomb:{player_id}" for player_id in episode.primary_actor_ids)
    finish = episode_by_id[units[-1]["unit_id"]]
    scenes.append({
        "scene_id": f"scene_{len(scenes) + 1}",
        "episode_id": finish.episode_id,
        "causal_narrative_unit_id": units[-1]["unit_id"],
        "narrative_role": "FINISH",
        "supporting_episode_ids": list(units[-1]["supporting_episode_ids"]),
        "type": "hold",
        "at_event_id": finish.end_event_id,
        "at_event_boundary": "end",
        "duration_seconds": FINAL_HOLD_SECONDS,
        "instructions": [{"type": "show_caption", "text": units[-1]["factual_caption"]}],
    })
    return {
        "possession_id": possession.possession_id,
        "format": {"width": width, "height": height, "fps": fps},
        "selected_finding_id": None,
        "selected_finding": None,
        "action_chain": None,
        "scenes": scenes,
        "narrative_window": {
            "window_start_event_id": episodes[0].start_event_id,
            "window_end_event_id": finish.end_event_id,
        },
        "visual_focus": {
            "protagonist_id": finish.primary_actor_ids[0] if finish.primary_actor_ids else None,
            "secondary_player_ids": sorted({
                player_id for episode in episodes for player_id in episode.primary_actor_ids
                if not finish.primary_actor_ids or player_id != finish.primary_actor_ids[0]
            })[:4],
        },
        "tactical_participants": {
            "mandatory_player_ids": sorted(mandatory),
            "maximum_context_players": 6,
        },
        "planning_basis": "CAUSAL_NARRATIVE_SELECTION_FROM_GRAPH_BACKED_EPISODES",
        "pipeline_mode": "causal",
        "causal_narrative_selection_sha256": selection.sha256,
        "legacy_fallback": {
            "used": False,
            "available": True,
            "activation": "explicit_only",
        },
        "presentation": {"hide_event_hud": True, "mode": "consumer"},
    }
