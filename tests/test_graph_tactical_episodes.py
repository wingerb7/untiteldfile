from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

from src.contracts import Artifact
from src.domain.models import Event, NormalizedPossession, Position
from src.graph_tactical_episodes import (
    adapt_graph_episodes_for_rendering,
    build_graph_backed_tactical_episode_dataset,
    validate_graph_backed_tactical_episode_dataset,
)
from src.tactical_patterns import detect_return_combination_patterns
from src.scene_direction import build_scene_direction
from src.tactical_relevance import classify_episode_players
from src.tactical_story.episodic_scene_plan import build_episodic_scene_plan
from test_action_continuation import chain


def return_chain():
    first_pass = "11111111-1111-4111-8111-111111111111"
    first_receipt = "22222222-2222-4222-8222-222222222222"
    return_pass = "33333333-3333-4333-8333-333333333333"
    return_receipt = "44444444-4444-4444-8444-444444444444"
    recognition, graph, semantic, continuation = chain(
        [
            {"uuid": first_pass, "type": "PASS", "actor": "player:a", "recipient": "player:b", "related": (first_receipt,)},
            {"uuid": first_receipt, "type": "BALL_RECEIPT", "actor": "player:b", "related": (first_pass,)},
            {"type": "CARRY", "actor": "player:b"},
            {"uuid": return_pass, "type": "PASS", "actor": "player:b", "recipient": "player:a", "related": (return_receipt,)},
            {"uuid": return_receipt, "type": "BALL_RECEIPT", "actor": "player:a", "related": (return_pass,)},
            {"type": "SHOT", "actor": "player:a"},
        ]
    )
    patterns = detect_return_combination_patterns(continuation, graph, recognition, semantic)
    return recognition, graph, patterns


def test_serialization_ids_ordering_provenance_and_adapter_are_stable():
    recognition, graph, patterns = return_chain()
    one = build_graph_backed_tactical_episode_dataset(recognition, graph, patterns)
    two = build_graph_backed_tactical_episode_dataset(recognition, graph, patterns)
    assert one.canonical_bytes() == two.canonical_bytes()
    assert one.sha256 == two.sha256
    assert validate_graph_backed_tactical_episode_dataset(one, recognition, graph, patterns).validated
    assert [episode["episode_type"] for episode in one["episodes"]] == ["RETURN_COMBINATION", "FINISH"]
    assert list(one["episodes"]) == sorted(
        one["episodes"],
        key=lambda episode: (
            episode["start_ordering_key"],
            episode["end_ordering_key"],
            episode["episode_type"],
            episode["episode_id"],
        ),
    )
    for episode in one["episodes"]:
        assert episode["supporting_action_node_ids"]
        assert episode["supporting_relation_ids"]
        assert episode["authenticated_source_event_ids"]
        assert episode["recognition_record_ids"]
        assert episode["temporal_context_node_ids"] == ()
    adapted = adapt_graph_episodes_for_rendering(one)
    assert [item.participating_action_ids for item in adapted.episodes] == [
        [event_id.removeprefix("event:statsbomb:") for event_id in one["episodes"][0]["authenticated_source_event_ids"]],
        [event_id.removeprefix("event:statsbomb:") for event_id in one["episodes"][1]["authenticated_source_event_ids"]],
    ]
    assert adapted.episodes[0].evidence["supporting_action_node_ids"] == list(one["episodes"][0]["supporting_action_node_ids"])

    event_types = {
        "PASS_EVENT": "Pass",
        "BALL_RECEIPT_EVENT": "Ball Receipt*",
        "CARRY_EVENT": "Carry",
        "SHOT_EVENT": "Shot",
    }
    graph_nodes = {node["node_id"]: node for node in graph["nodes"]}
    events = []
    for node_id in one["episodes"][0]["supporting_action_node_ids"]:
        node = graph_nodes[node_id]
        events.append(
            Event(
                node["event_id"].removeprefix("event:statsbomb:"),
                event_types[node["action_type"]],
                node["canonical_time_seconds"],
                1,
                "team",
                node["actor"],
                Position(20, 40),
                Position(30, 40),
                node["recipient"],
                None,
                [],
                {},
            )
        )
    possession = NormalizedPossession(1, "team", "opponent", events, 1.0, 6.0, "synthetic", "1")
    directions = {}
    for episode in adapted.episodes:
        relevance = classify_episode_players(possession, episode)
        directions[episode.episode_id] = build_scene_direction(possession, episode, relevance)
    plan = build_episodic_scene_plan(possession, adapted.episodes, directions)
    assert plan["planning_basis"] == "TACTICAL_EPISODES_FROM_GENERIC_EPISODE_BUILDER"
    assert {scene["episode_id"] for scene in plan["scenes"]} == {episode.episode_id for episode in adapted.episodes}


def test_temporal_proximity_does_not_create_causal_members_and_finish_is_retained():
    recognition, graph, _, _ = chain(
        [
            {"type": "PASS", "actor": "player:a", "recipient": "player:b"},
            {"type": "CARRY", "actor": "player:b"},
            {"type": "SHOT", "actor": "player:c"},
        ]
    )
    dataset = build_graph_backed_tactical_episode_dataset(recognition, graph)
    assert [episode["episode_type"] for episode in dataset["episodes"]] == ["FINISH"]
    finish = dataset["episodes"][0]
    assert len(finish["supporting_action_node_ids"]) == 1
    assert len(finish["authenticated_source_event_ids"]) == 1
    assert finish["temporal_context_node_ids"] == ()
    statuses = {(decision["candidate_type"], decision["status"]) for decision in dataset["decisions"]}
    assert ("RETURN_COMBINATION", "UNSUPPORTED") in statuses
    assert ("LINE_BREAK", "UNSUPPORTED") in statuses
    assert ("FINISH", "SELECTED") in statuses


def test_duplicate_and_contradictory_return_paths_are_rejected_without_losing_finish():
    recognition, graph, patterns = return_chain()
    raw = deepcopy(patterns.data)
    raw["matches"] = (*raw["matches"], deepcopy(raw["matches"][0]))
    duplicated = Artifact(raw, patterns.media_type, patterns.direct_input_sha256, patterns.source_hashes, validated=True)
    dataset = build_graph_backed_tactical_episode_dataset(recognition, graph, duplicated)
    assert [episode["episode_type"] for episode in dataset["episodes"]].count("RETURN_COMBINATION") == 1
    assert [episode["episode_type"] for episode in dataset["episodes"]].count("FINISH") == 1
    assert any(decision["status"] == "REJECTED_DUPLICATE" for decision in dataset["decisions"])

    raw = deepcopy(patterns.data)
    contradictory = deepcopy(raw["matches"][0])
    contradictory["pattern_id"] = f"{contradictory['pattern_id']}:alternative"
    contradictory["actions"] = tuple(contradictory["actions"][1:])
    raw["matches"] = (*raw["matches"], contradictory)
    overlapped = Artifact(raw, patterns.media_type, patterns.direct_input_sha256, patterns.source_hashes, validated=True)
    decisions = build_graph_backed_tactical_episode_dataset(recognition, graph, overlapped)["decisions"]
    assert any(decision["status"] == "REJECTED_CONTRADICTORY_OVERLAP" for decision in decisions)


def test_line_break_contract_is_explicitly_unsupported_not_guessed():
    recognition, graph, _, _ = chain(
        [
            {"type": "PASS", "actor": "player:a", "recipient": "player:b"},
            {"type": "SHOT", "actor": "player:b"},
        ]
    )
    dataset = build_graph_backed_tactical_episode_dataset(recognition, graph)
    assert "LINE_BREAK" not in [episode["episode_type"] for episode in dataset["episodes"]]
    assert "defensive-line" in dataset["line_break_evidence_policy"]["PASS"]
    assert "insufficient" in dataset["line_break_evidence_policy"]["WARN"]


def test_production_rules_contain_no_fixture_specific_identifiers():
    root = Path(__file__).resolve().parents[1] / "src"
    paths = [
        root / "graph_tactical_episodes" / "engine.py",
        root / "graph_tactical_episodes" / "adapter.py",
        root / "pipelines" / "semantic_route.py",
    ]
    forbidden = (
        "Locatelli",
        "Depay",
        "3788754",
        "3869117",
        "e51fde20-708e-49e4-ae77-5bc768e5f411",
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert not [literal for literal in forbidden if literal in text]


def test_semantic_cli_mode_is_explicit_and_never_silently_falls_back(tmp_path, monkeypatch):
    import src.cli as cli

    input_path = tmp_path / "possession.json"
    events_path = tmp_path / "events.json"
    frames_path = tmp_path / "frames.json"
    config_path = tmp_path / "config.yaml"
    analysis_path = tmp_path / "analysis.json"
    scene_path = tmp_path / "scene.json"
    output_path = tmp_path / "output.mp4"
    for path, value in ((input_path, {}), (events_path, []), (frames_path, [])):
        path.write_text(json.dumps(value), encoding="utf-8")
    config_path.write_text("animation:\n  width: 720\n  height: 1280\n  fps: 24\n", encoding="utf-8")

    recognition, graph, patterns = return_chain()
    dataset = build_graph_backed_tactical_episode_dataset(recognition, graph, patterns)
    captured = {}

    def fake_route(events, frames, request, render_path, **kwargs):
        captured.update(request=request, render_path=render_path, kwargs=kwargs)
        return {
            "graph_backed_episodes": dataset,
            "scene_plan": {
                "possession_id": 1,
                "format": {"width": 720, "height": 1280, "fps": 24},
                "scenes": [],
                "planning_basis": "GRAPH_BACKED_TACTICAL_EPISODES",
                "legacy_fallback": {"used": False, "available": True, "activation": "explicit_only"},
            },
        }

    monkeypatch.setattr(cli, "build_semantic_route", fake_route)
    monkeypatch.setattr(cli, "load_and_normalize", lambda path: {"match_id": 1, "possession_id": 1})
    monkeypatch.setattr(cli, "render_scene_plan", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tip",
            "run",
            "--mode",
            "semantic",
            "--input",
            str(input_path),
            "--events",
            str(events_path),
            "--frames",
            str(frames_path),
            "--match-id",
            "1",
            "--possession-id",
            "1",
            "--config",
            str(config_path),
            "--analysis-output",
            str(analysis_path),
            "--scene-output",
            str(scene_path),
            "--output",
            str(output_path),
        ],
    )
    cli.main()
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert analysis["pipeline_mode"] == "semantic"
    assert analysis["legacy_fallback"]["used"] is False
    assert captured["request"]["match_id"] == 1
    assert captured["render_path"] == input_path


def test_locatelli_and_depay_use_the_same_graph_backed_builder():
    from scripts.render_tactical_storytelling import upstream

    results = {}
    for fixture, match_id, possession_id in (
        ("locatelli", 3788754, 40),
        ("depay", 3869117, 20),
    ):
        recognition, graph, _, _, patterns = upstream(match_id, possession_id)
        dataset = build_graph_backed_tactical_episode_dataset(recognition, graph, patterns)
        results[fixture] = [episode["episode_type"] for episode in dataset["episodes"]]
    assert results["locatelli"] == ["LINE_BREAK", "RETURN_COMBINATION", "FINISH"]
    assert results["depay"] == ["LINE_BREAK"] * 6 + ["FINISH"]
