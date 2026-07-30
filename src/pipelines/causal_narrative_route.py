from __future__ import annotations

from pathlib import Path
from typing import Any

from src.causal_narrative import (
    adapt_causal_units_for_scene_direction,
    build_causal_narrative_selection,
)
from src.ingest.possession_loader import load_normalized_possession
from src.pipelines.semantic_route import build_semantic_route
from src.scene_direction import build_scene_direction
from src.tactical_relevance import classify_episode_players
from src.tactical_story import build_causal_narrative_scene_plan


def build_causal_narrative_route(
    events: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    request: dict[str, Any],
    render_possession_path: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict[str, Any]:
    base = build_semantic_route(
        events,
        frames,
        request,
        render_possession_path,
        width=width,
        height=height,
        fps=fps,
    )
    selection = build_causal_narrative_selection(
        base["graph_backed_episodes"],
        base["action_graph"],
        base["action_continuation"],
    )
    possession = load_normalized_possession(render_possession_path)
    episodes = adapt_causal_units_for_scene_direction(selection, base["graph_backed_episodes"])
    relevance = {
        episode.episode_id: classify_episode_players(possession, episode)
        for episode in episodes
    }
    directions = {
        episode.episode_id: build_scene_direction(
            possession, episode, relevance[episode.episode_id]
        )
        for episode in episodes
    }
    scene_plan = build_causal_narrative_scene_plan(
        possession,
        selection,
        episodes,
        directions,
        width=width,
        height=height,
        fps=fps,
    )
    return {
        **base,
        "causal_narrative_selection": selection,
        "causal_render_episodes": episodes,
        "causal_relevance_by_unit": relevance,
        "causal_scene_directions": directions,
        "scene_plan": scene_plan,
    }
