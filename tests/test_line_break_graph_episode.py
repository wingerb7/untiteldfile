from copy import deepcopy

import pytest

from src.action_graph import build_action_graph_dataset
from src.contracts import Artifact
from src.graph_tactical_episodes import (
    GraphBackedTacticalEpisodeError,
    build_graph_backed_tactical_episode_dataset,
)
from src.perception.authentication import PERCEPTION_MEDIA_TYPE
from src.recognition import RecognitionError,build_recognition_dataset


def _provenance(index):
    return {
        field: {
            "class": "PRESERVED_AUTHENTICATED_INPUT",
            "operation": "WORLD_PRESERVE_EVENT_EVIDENCE",
            "sources": [{"source_record_id": f"source:{index}", "source_path": f"synchronized_dataset#/timeline/{index}/{field}"}],
        }
        for field in ("/event_id", "/event_type", "/actor", "/recipient", "/canonical_timestamp", "/source_record_id", "/related_event_ids", "/outcome")
    }


def _feature(frame, code, subjects, value):
    suffix = ":".join(subjects)
    return {
        "schema_id": "tip.perception_feature",
        "feature_id": f"feature:{frame}:{code.lower()}:{suffix}",
        "feature_code": code,
        "feature_name": code,
        "category": "SPATIAL",
        "world_state_id": f"world:{frame}",
        "world_state_index": frame,
        "canonical_time_seconds": float(frame + 1),
        "subject_ids": subjects,
        "input_observation_ids": tuple(f"observation:{frame}:{subject}" for subject in subjects),
        "dependency_feature_ids": (),
        "status": "AVAILABLE",
        "unavailable_reason": None,
        "value": value,
        "unit": "NONE",
        "perception_provenance": {},
    }


def line_break_inputs(*, crossing=True, complete=True, line=True, end_x=None, receipt_related=True,
                      receipt_time=2.0, receipt_actor="player:b", mutate_perception=None):
    endpoint_x=(70 if crossing else 40) if end_x is None else end_x
    positions = {
        "player:d1": (50, 10),
        "player:d2": (51, 30),
        "player:d3": (49, 50),
    }
    if not line:
        positions.pop("player:d3")
    features = [
        _feature(0, "ABSOLUTE_POSITION", (player,), {"position2": {"x_m": point[0], "y_m": point[1]}})
        for player, point in positions.items()
    ]
    features.extend((
        _feature(0, "PASS_START_POSITION", ("event:statsbomb:pass",), {"position2": {"x_m": 30, "y_m": 34}}),
        _feature(0, "PASS_END_POSITION", ("event:statsbomb:pass",), {"position2": {"x_m": endpoint_x, "y_m": 34}}),
    ))
    for feature in features[-2:]:
        field = "start_position" if feature["feature_code"] == "PASS_START_POSITION" else "end_position"
        feature["feature_id"] = f"feature:world:0:{feature['feature_code'].lower()}:event:statsbomb:pass"
        feature["input_observation_ids"] = ()
        feature["perception_provenance"] = {"/value": {
            "class": "DERIVED_DETERMINISTICALLY",
            "operation": "PER_CALCULATE_FEATURE",
            "sources": [{"source_record_id": "event:statsbomb:pass", "source_path": f"world_model_dataset#/pass_trajectory_evidence/0/{field}"}],
        }}
    same_team_pairs = [("player:a", "player:b")]
    defenders = sorted(player for player in positions if player.startswith("player:d"))
    same_team_pairs.extend((a, b) for a in defenders for b in defenders if a != b)
    features.extend(_feature(0, "CONNECTION_DISTANCE", pair, {"scalar": 20.0}) for pair in same_team_pairs)
    events = (
        {
            "event_id": "event:statsbomb:pass",
            "event_type": "PASS",
            "actor": "player:a",
            "recipient": "player:b",
            "canonical_timestamp": 1.0,
            "source_record_id": "source:0",
            "related_event_ids": ("receipt",) if receipt_related else (),
            "outcome": "COMPLETED" if complete else "INCOMPLETE",
            "authenticated_provenance": _provenance(0),
        },
        {
            "event_id": "event:statsbomb:receipt",
            "event_type": "BALL_RECEIPT",
            "actor": receipt_actor,
            "recipient": None,
            "canonical_timestamp": receipt_time,
            "source_record_id": "source:1",
            "related_event_ids": ("pass",),
            "outcome": None,
            "authenticated_provenance": _provenance(1),
        },
    )
    frames = (
        {
            "schema_id": "tip.perception_frame",
            "perception_frame_id": "perception_frame:world:0",
            "world_state_id": "world:0",
            "world_state_index": 0,
            "canonical_time_seconds": 1.0,
            "features": tuple(features),
            "perception_provenance": {},
        },
        {
            "schema_id": "tip.perception_frame",
            "perception_frame_id": "perception_frame:world:1",
            "world_state_id": "world:1",
            "world_state_index": 1,
            "canonical_time_seconds": receipt_time,
            "features": (),
            "perception_provenance": {},
        },
    )
    definitions = tuple(
        {"feature_code": code}
        for code in ("ENTITY_SPEED", "PAIR_DISTANCE", "CONNECTION_CORRIDOR", "CORRIDOR_OCCUPANCY", "ABSOLUTE_POSITION", "CONNECTION_DISTANCE", "PASS_START_POSITION", "PASS_END_POSITION")
    )
    data={
            "schema_id": "tip.perception_dataset",
            "contract_version": "0.1.0",
            "input_contract_version": "0.1.0",
            "world_model_sha256": "0" * 64,
            "match_id": "match:line",
            "possession_id": "possession:1",
            "event_evidence": events,
            "pass_trajectory_evidence": ({
                "event_id": "event:statsbomb:pass",
                "canonical_timestamp": 1.0,
                "start_position": {"availability": "AVAILABLE", "x_m": 30, "y_m": 34},
                "end_position": {"availability": "AVAILABLE", "x_m": endpoint_x, "y_m": 34},
            },),
            "feature_definitions": definitions,
            "frames": frames,
            "input_provenance": {},
            "perception_provenance": {},
        }
    if mutate_perception:mutate_perception(data)
    perception = Artifact(
        data,
        PERCEPTION_MEDIA_TYPE,
        "0" * 64,
        validated=True,
    )
    recognition = build_recognition_dataset(perception)
    return recognition, build_action_graph_dataset(recognition)


def test_authentic_line_break_is_deterministic_and_evidence_complete():
    recognition, graph = line_break_inputs()
    one = build_graph_backed_tactical_episode_dataset(recognition, graph)
    two = build_graph_backed_tactical_episode_dataset(recognition, graph)
    assert one.canonical_bytes() == two.canonical_bytes()
    assert one.sha256 == two.sha256
    episodes = [episode for episode in one["episodes"] if episode["episode_type"] == "LINE_BREAK"]
    assert len(episodes) == 1
    episode = episodes[0]
    assert len(episode["supporting_action_node_ids"]) == 3
    assert len(episode["supporting_relation_ids"]) == 2
    assert episode["perception_feature_ids"]
    assert episode["authenticated_source_event_ids"] == ("event:statsbomb:pass", "event:statsbomb:receipt")
    assert episode["confidence"] == 1.0
    assert episode["selection_provenance"] == "AUTHENTICATED_GRAPH_RELATIONS"


@pytest.mark.parametrize(
    "kwargs",
    ({"line": False}, {"crossing": False}, {"complete": False}),
)
def test_line_break_fails_closed_without_each_required_fact(kwargs):
    recognition, graph = line_break_inputs(**kwargs)
    dataset = build_graph_backed_tactical_episode_dataset(recognition, graph)
    assert not [episode for episode in dataset["episodes"] if episode["episode_type"] == "LINE_BREAK"]


@pytest.mark.parametrize("code", ("PASS_START_POSITION", "PASS_END_POSITION"))
def test_missing_pass_endpoint_emits_no_crossing(code):
    def remove(data):
        data["frames"][0]["features"] = tuple(
            feature for feature in data["frames"][0]["features"] if feature["feature_code"] != code
        )
    recognition, graph = line_break_inputs(mutate_perception=remove)
    assert not [edge for edge in graph["edges"] if edge["relation_type"] == "PASS_CROSSES_DEFENSIVE_LINE"]


@pytest.mark.parametrize(
    "change",
    (
        lambda feature: feature.update(subject_ids=("event:statsbomb:other",)),
        lambda feature: feature["perception_provenance"]["/value"]["sources"][0].update(
            source_path="world_model_dataset#/pass_trajectory_evidence/0/start_position"
        ),
        lambda feature: feature["value"].update(position2={"x_m": "bad", "y_m": 34}),
        lambda feature: feature["value"].update(position2={"x_m": 106, "y_m": 34}),
    ),
)
def test_substituted_malformed_or_wrongly_provenanced_endpoint_is_rejected(change):
    def mutate(data):
        endpoint = next(feature for feature in data["frames"][0]["features"] if feature["feature_code"] == "PASS_END_POSITION")
        change(endpoint)
    with pytest.raises(RecognitionError, match="TIP-REC-INPUT-SCHEMA-INVALID"):
        line_break_inputs(mutate_perception=mutate)


@pytest.mark.parametrize("end_x", (40, 50))
def test_same_side_or_boundary_endpoint_emits_no_crossing(end_x):
    recognition, graph = line_break_inputs(end_x=end_x)
    assert not [edge for edge in graph["edges"] if edge["relation_type"] == "PASS_CROSSES_DEFENSIVE_LINE"]


@pytest.mark.parametrize(
    "kwargs",
    (
        {"receipt_related": False},
        {"receipt_time": 1.0},
        {"receipt_actor": "player:other"},
    ),
)
def test_reception_proof_remains_mandatory(kwargs):
    recognition, graph = line_break_inputs(**kwargs)
    dataset = build_graph_backed_tactical_episode_dataset(recognition, graph)
    assert not [episode for episode in dataset["episodes"] if episode["episode_type"] == "LINE_BREAK"]


def test_contradictory_graph_is_rejected_and_build_suppresses_duplicates():
    recognition, graph = line_break_inputs()
    raw = graph.data
    crossing = next(edge for edge in raw["edges"] if edge["relation_type"] == "PASS_CROSSES_DEFENSIVE_LINE")
    crossing["target_node_id"] = next(node["node_id"] for node in raw["nodes"] if node["action_type"] == "BALL_RECEIPT_EVENT")
    bad = Artifact(raw, graph.media_type, graph.direct_input_sha256, graph.source_hashes, validated=True)
    with pytest.raises(GraphBackedTacticalEpisodeError, match="TIP-GTE-UPSTREAM-INVALID"):
        build_graph_backed_tactical_episode_dataset(recognition, bad)
    dataset = build_graph_backed_tactical_episode_dataset(recognition, graph)
    assert len([episode for episode in dataset["episodes"] if episode["episode_type"] == "LINE_BREAK"]) == 1


def test_graph_rejects_endpoint_feature_from_another_pass():
    recognition, graph = line_break_inputs()
    raw = graph.data
    crossing = next(edge for edge in raw["edges"] if edge["relation_type"] == "PASS_CROSSES_DEFENSIVE_LINE")
    crossing["endpoint_feature_ids"] = (
        crossing["endpoint_feature_ids"][0],
        "feature:world:9:pass_end_position:event:statsbomb:other",
    )
    bad = Artifact(raw, graph.media_type, graph.direct_input_sha256, graph.source_hashes, validated=True)
    with pytest.raises(GraphBackedTacticalEpisodeError, match="TIP-GTE-UPSTREAM-INVALID"):
        build_graph_backed_tactical_episode_dataset(recognition, bad)


def test_line_connected_to_attacking_team_is_not_recognized():
    def connect(data):
        feature = _feature(0, "CONNECTION_DISTANCE", ("player:a", "player:d1"), {"scalar": 20.0})
        data["frames"][0]["features"] = (*data["frames"][0]["features"], feature)
    recognition, graph = line_break_inputs(mutate_perception=connect)
    assert not [edge for edge in graph["edges"] if edge["relation_type"] == "PASS_CROSSES_DEFENSIVE_LINE"]


def test_feature_input_order_does_not_change_semantic_episode_identifiers():
    first_recognition, first_graph = line_break_inputs()
    def reverse(data):
        data["frames"][0]["features"] = tuple(reversed(data["frames"][0]["features"]))
    second_recognition, second_graph = line_break_inputs(mutate_perception=reverse)
    first = build_graph_backed_tactical_episode_dataset(first_recognition, first_graph)
    second = build_graph_backed_tactical_episode_dataset(second_recognition, second_graph)
    assert [episode["episode_id"] for episode in first["episodes"]] == [episode["episode_id"] for episode in second["episodes"]]
