from __future__ import annotations

from pathlib import Path
from typing import Any

from src.action_continuation import build_action_continuation_dataset
from src.action_graph import build_action_graph_dataset
from src.graph_tactical_episodes import (
    adapt_graph_episodes_for_rendering,
    build_graph_backed_tactical_episode_dataset,
)
from src.ingest.possession_loader import load_normalized_possession
from src.normalization import build_normalized_dataset
from src.perception import build_perception_dataset, validate_perception_dataset
from src.recognition import build_recognition_dataset
from src.scene_direction import build_scene_direction
from src.semantic_resolution import build_semantic_resolution_dataset
from src.source_selection import select_source_documents
from src.synchronization import build_synchronized_dataset
from src.tactical_patterns import detect_return_combination_patterns
from src.tactical_relevance import classify_episode_players
from src.tactical_story.episodic_scene_plan import build_episodic_scene_plan
from src.world_model import build_world_model_dataset, validate_world_model_dataset


def build_semantic_route(
    events: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    request: dict[str, Any],
    render_possession_path: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict[str, Any]:
    selected = select_source_documents(events, frames, request)
    normalized = build_normalized_dataset(selected)
    synchronized = build_synchronized_dataset(normalized)
    world = validate_world_model_dataset(build_world_model_dataset(synchronized))
    perception = validate_perception_dataset(build_perception_dataset(world), source_hashes=world.source_hashes)
    recognition = build_recognition_dataset(perception)
    graph = build_action_graph_dataset(recognition)
    semantic = build_semantic_resolution_dataset(graph, recognition)
    continuation = build_action_continuation_dataset(graph, recognition, semantic)
    patterns = detect_return_combination_patterns(continuation, graph, recognition, semantic)
    graph_episodes = build_graph_backed_tactical_episode_dataset(recognition, graph, patterns)

    possession = load_normalized_possession(render_possession_path)
    render_episodes = adapt_graph_episodes_for_rendering(graph_episodes)
    relevance_by_episode = {
        episode.episode_id: classify_episode_players(possession, episode)
        for episode in render_episodes.episodes
    }
    directions = {
        episode.episode_id: build_scene_direction(
            possession, episode, relevance_by_episode[episode.episode_id]
        )
        for episode in render_episodes.episodes
    }
    scene_plan = build_episodic_scene_plan(
        possession,
        render_episodes.episodes,
        directions,
        width=width,
        height=height,
        fps=fps,
    )
    scene_plan["planning_basis"] = "GRAPH_BACKED_TACTICAL_EPISODES"
    scene_plan["pipeline_mode"] = "semantic"
    scene_plan["graph_backed_episode_dataset_sha256"] = graph_episodes.sha256
    scene_plan["legacy_fallback"] = {
        "used": False,
        "available": True,
        "activation": "explicit_only",
    }
    return {
        "source_selection": selected,
        "normalized": normalized,
        "synchronized": synchronized,
        "world_model": world,
        "perception": perception,
        "recognition": recognition,
        "action_graph": graph,
        "semantic_resolution": semantic,
        "action_continuation": continuation,
        "tactical_patterns": patterns,
        "graph_backed_episodes": graph_episodes,
        "render_episodes": render_episodes,
        "relevance_by_episode": relevance_by_episode,
        "scene_directions": directions,
        "scene_plan": scene_plan,
    }
