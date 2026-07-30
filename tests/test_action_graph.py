from __future__ import annotations

from copy import deepcopy
import gc
import json
from pathlib import Path

import pytest

from src.action_graph import ActionGraphError, build_action_graph_dataset, validate_action_graph_dataset
from src.action_graph.engine import MEDIA_TYPE
from src.contracts import Artifact
from src.perception.authentication import PERCEPTION_MEDIA_TYPE
from src.recognition import build_recognition_dataset
from src.recognition.engine import MEDIA_TYPE as RECOGNITION_MEDIA_TYPE
from src.source_selection import PINNED_REVISION, SourceSelectionError, select_source_documents
from src.normalization import build_normalized_dataset
from src.synchronization import build_synchronized_dataset
from src.world_model import build_world_model_dataset, validate_world_model_dataset
from src.perception import build_perception_dataset, validate_perception_dataset


def feature(fid: str, code: str, subjects: tuple[str, ...], value: dict) -> dict:
    return {
        "schema_id": "tip.perception_feature", "feature_id": fid, "feature_code": code, "feature_name": code,
        "category": "MOTION", "world_state_id": "world:0", "world_state_index": 0,
        "canonical_time_seconds": 1.0, "subject_ids": subjects, "input_observation_ids": (),
        "dependency_feature_ids": (), "status": "AVAILABLE", "unavailable_reason": None, "value": value,
        "unit": "NONE", "perception_provenance": {},
    }


def recognition() -> Artifact:
    features = [
        feature("speed:a", "ENTITY_SPEED", ("player:a",), {"scalar": 2.0}),
        feature("speed:b", "ENTITY_SPEED", ("player:b",), {"scalar": 0.0}),
        feature("distance:a", "PAIR_DISTANCE", ("ball:m", "player:a"), {"scalar": 1.0}),
        feature("distance:b", "PAIR_DISTANCE", ("ball:m", "player:b"), {"scalar": 2.0}),
        feature("corridor", "CONNECTION_CORRIDOR", ("player:a", "player:b"), {"polygon2": []}),
        feature("occupancy", "CORRIDOR_OCCUPANCY", ("player:a", "player:b"), {"integer": 1}),
    ]
    definitions = [{"feature_code": code} for code in ("ENTITY_SPEED", "PAIR_DISTANCE", "CONNECTION_CORRIDOR", "CORRIDOR_OCCUPANCY")]
    frame = {
        "schema_id": "tip.perception_frame", "perception_frame_id": "perception_frame:world:0", "world_state_id": "world:0",
        "world_state_index": 0, "canonical_time_seconds": 1.0, "features": features, "perception_provenance": {},
    }
    provenance = {field: {"class":"PRESERVED_AUTHENTICATED_INPUT","operation":"WORLD_PRESERVE_EVENT_EVIDENCE","sources":[{"source_record_id":"source:1","source_path":f"synchronized_dataset#/timeline/0/{field}"}]} for field in ("/event_id","/event_type","/actor","/recipient","/canonical_timestamp","/source_record_id","/related_event_ids","/outcome")}
    evidence = {"event_id":"event:1","event_type":"PASS","actor":"player:a","recipient":"player:b","canonical_timestamp":1.0,"source_record_id":"source:1","related_event_ids":(),"outcome":"COMPLETED","authenticated_provenance":provenance}
    data = {
        "schema_id": "tip.perception_dataset", "contract_version": "0.1.0", "input_contract_version": "0.1.0",
        "world_model_sha256": "0" * 64, "match_id": "match:m", "possession_id": "possession:1",
        "event_evidence": [evidence], "feature_definitions": definitions, "frames": [frame], "input_provenance": {}, "perception_provenance": {},
    }
    return build_recognition_dataset(Artifact(data, PERCEPTION_MEDIA_TYPE, "0" * 64, validated=True))


def mutate(good: Artifact, change) -> Artifact:
    raw = good.data
    change(raw)
    return Artifact(raw, good.media_type, good.direct_input_sha256, good.source_hashes)


def duplicate_node(raw: dict) -> None:
    raw["nodes"] = (*raw["nodes"], deepcopy(raw["nodes"][0]))


def reverse_nodes(raw: dict) -> None:
    raw["nodes"] = tuple(reversed(raw["nodes"]))


def duplicate_edge(raw: dict) -> None:
    raw["edges"] = (*raw["edges"], deepcopy(raw["edges"][0]))


def unknown_recognition_dependency(raw: dict) -> None:
    raw["nodes"][0]["supporting_evidence"]["recognition_record_ids"] = ("recognition:unknown",)
    raw["nodes"][0]["provenance_record_ids"] = ("recognition:unknown",)


def fixture_chain(match_id: int, possession_id: int) -> tuple[Artifact, Artifact]:
    base = Path("data/open-data/data")
    events = json.loads((base / f"events/{match_id}.json").read_text())
    frames = json.loads((base / f"three-sixty/{match_id}.json").read_text())
    request = {"source_dataset": "statsbomb-open-data", "source_revision": PINNED_REVISION, "match_id": match_id, "possession_id": possession_id}
    selection = select_source_documents(events, frames, request)
    normalized = build_normalized_dataset(selection)
    synchronized = build_synchronized_dataset(normalized)
    world = validate_world_model_dataset(build_world_model_dataset(synchronized))
    perception = validate_perception_dataset(build_perception_dataset(world), source_hashes=world.source_hashes)
    recognized = build_recognition_dataset(perception)
    del events, frames, selection, normalized, synchronized, world, perception
    gc.collect()
    return recognized, build_action_graph_dataset(recognized)


def test_requires_authenticated_recognition_with_correct_media_schema_version_and_hashes():
    source = recognition()
    with pytest.raises(ActionGraphError, match="TIP-AG-INPUT-ARTIFACT-INVALID"):
        build_action_graph_dataset(source.data)
    with pytest.raises(ActionGraphError, match="TIP-AG-INPUT-ARTIFACT-INVALID"):
        build_action_graph_dataset(Artifact(source.data, "application/json", source.direct_input_sha256, validated=True))
    raw = source.data
    raw["schema_id"] = "tip.wrong"
    with pytest.raises(ActionGraphError, match="TIP-AG-INPUT-ARTIFACT-INVALID"):
        build_action_graph_dataset(Artifact(raw, RECOGNITION_MEDIA_TYPE, source.direct_input_sha256, validated=True))
    raw = source.data
    raw["contract_version"] = "9.9.9"
    with pytest.raises(ActionGraphError, match="TIP-AG-INPUT-VERSION-UNSUPPORTED"):
        build_action_graph_dataset(Artifact(raw, RECOGNITION_MEDIA_TYPE, source.direct_input_sha256, validated=True))
    with pytest.raises(ActionGraphError, match="TIP-AG-INPUT-HASH-INVALID"):
        build_action_graph_dataset(Artifact(source.data, RECOGNITION_MEDIA_TYPE, "f" * 64, validated=True))


def test_action_graph_is_authenticated_validated_and_deterministic():
    source = recognition()
    one = build_action_graph_dataset(source)
    two = build_action_graph_dataset(source)
    assert one.validated and one.media_type == MEDIA_TYPE
    assert one.direct_input_sha256 == source.sha256 == one["recognition_dataset_sha256"]
    assert one.canonical_bytes() == two.canonical_bytes() and one.sha256 == two.sha256
    assert {node["action_type"] for node in one["nodes"]} == {
        "PASS_EVENT", "PASSING_CORRIDOR_OBSTRUCTED_STATE", "PLAYER_MOVING_STATE", "PLAYER_NEAREST_BALL_STATE", "PLAYER_STATIONARY_STATE"
    }
    event_node=next(node for node in one["nodes"] if node["action_type"]=="PASS_EVENT")
    assert event_node["recognition_record_id"]==event_node["supporting_evidence"]["recognition_record_ids"][0]
    assert event_node["event_evidence_id"]==event_node["event_id"]=="event:1"
    assert event_node["event_type"]=="PASS" and event_node["actor"]=="player:a" and event_node["recipient"]=="player:b"
    assert event_node["timestamp"]==1.0 and event_node["action_graph_provenance"]["/value"]["sources"]


def test_action_graph_fails_closed_on_invalid_recognition_event_evidence():
    source=recognition();raw=source.data
    source_record=next(record for record in raw["frames"][0]["records"] if record["concept_code"]=="SOURCE_DECLARED_PASS")
    source_record["supporting_event_evidence_ids"]=("event:missing",)
    with pytest.raises(ActionGraphError,match="TIP-AG-INPUT-SCHEMA-INVALID"):
        build_action_graph_dataset(Artifact(raw,source.media_type,source.direct_input_sha256,source.source_hashes,validated=True))


def test_source_related_event_fails_closed_on_unknown_and_malformed_targets():
    source=recognition();raw=source.data;raw["event_evidence"][0]["related_event_ids"]=("missing:event",)
    graph=build_action_graph_dataset(Artifact(raw,source.media_type,source.direct_input_sha256,source.source_hashes,validated=True))
    assert not [edge for edge in graph["edges"] if edge["relation_type"]=="SOURCE_RELATED_EVENT"]
    extended,good=two_frame_graph();related=next(edge for edge in good["edges"] if edge["relation_type"]=="SOURCE_RELATED_EVENT")
    raw=good.data;edge=next(item for item in raw["edges"] if item["edge_id"]==related["edge_id"]);edge["related_event_index"]=9
    with pytest.raises(ActionGraphError,match="TIP-AG-EVENT-EVIDENCE-INVALID"):
        validate_action_graph_dataset(Artifact(raw,good.media_type,good.direct_input_sha256,good.source_hashes),extended)
    raw=good.data;edge=next(item for item in raw["edges"] if item["edge_id"]==related["edge_id"]);edge["related_event_provenance"]={}
    with pytest.raises(ActionGraphError,match="TIP-AG-PROVENANCE-INVALID"):
        validate_action_graph_dataset(Artifact(raw,good.media_type,good.direct_input_sha256,good.source_hashes),extended)
    raw=source.data;raw["event_evidence"][0]["authenticated_provenance"]={}
    with pytest.raises(ActionGraphError,match="TIP-AG-INPUT-SCHEMA-INVALID"):
        build_action_graph_dataset(Artifact(raw,source.media_type,source.direct_input_sha256,source.source_hashes,validated=True))


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (lambda raw: raw["action_types"][0].update(action_type="PASS"), "TIP-AG-ACTION-TYPE-INVALID"),
        (lambda raw: raw["relation_types"][0].update(relation_type="CAUSES"), "TIP-AG-RELATION-TYPE-INVALID"),
        (unknown_recognition_dependency, "TIP-AG-DEPENDENCY-INVALID"),
        (duplicate_node, "TIP-AG-NODE-DUPLICATE"),
        (lambda raw: raw["nodes"][0]["participants"][0].update(entity_id="player:unknown"), "TIP-AG-PARTICIPANT-INVALID"),
        (lambda raw: raw["nodes"][0].update(canonical_time_seconds=-1.0), "TIP-AG-TIMESTAMP-INVALID"),
        (lambda raw: raw["nodes"][0].update(action_graph_provenance={}), "TIP-AG-PROVENANCE-INVALID"),
        (reverse_nodes, "TIP-AG-ORDERING-INVALID"),
    ],
)
def test_validator_rejects_node_catalog_dependency_participant_timestamp_provenance_and_order(change, code):
    source = recognition()
    good = build_action_graph_dataset(source)
    with pytest.raises(ActionGraphError, match=code):
        validate_action_graph_dataset(mutate(good, change), source)


def two_frame_graph(second_time:float=2.0) -> tuple[Artifact, Artifact]:
    source = recognition()
    raw = source.data
    second = deepcopy(raw["frames"][0])
    second["recognition_frame_id"] = "recognition_frame:perception_frame:world:1"
    second["perception_frame_id"] = "perception_frame:world:1"
    second["world_state_id"] = "world:1"
    second["world_state_index"] = 1
    second["canonical_time_seconds"] = second_time
    for record in second["records"]:
        record["recognition_id"] = record["recognition_id"].replace("world:0", "world:1")
        record["perception_frame_id"] = "perception_frame:world:1"
        record["world_state_id"] = "world:1"
        record["world_state_index"] = 1
        record["canonical_time_seconds"] = second_time
        for item in record["recognition_provenance"]["/value"]["sources"]:
            item["source_path"] = item["source_path"].replace("/frames/0/", "/frames/1/")
        if record["concept_code"].startswith("SOURCE_DECLARED_"):
            record["recognition_id"] = record["recognition_id"].replace("event:1", "event:2")
            record["supporting_event_evidence_ids"] = ("event:2",)
            record["recognition_provenance"]["/value"]["sources"] = [{"source_record_id":"event:2","source_path":"perception_dataset#/event_evidence/1"}]
    second_evidence = deepcopy(raw["event_evidence"][0])
    second_evidence["event_id"] = "event:2"
    second_evidence["canonical_timestamp"] = second_time
    raw["event_evidence"][0]["related_event_ids"]=("event:2",)
    raw["event_evidence"] = (*raw["event_evidence"], second_evidence)
    raw["frames"] = (*raw["frames"], second)
    raw["metadata"]["frame_count"] = 2
    raw["metadata"]["record_count"] *= 2
    extended = Artifact(raw, RECOGNITION_MEDIA_TYPE, source.direct_input_sha256, source.source_hashes, validated=True)
    return extended, build_action_graph_dataset(extended)


def test_identical_authenticated_timestamps_create_no_temporal_succession():
    _,graph=two_frame_graph(1.0)
    assert not [edge for edge in graph["edges"] if edge["relation_type"]=="TEMPORAL_SUCCESSION"]
    related=[edge for edge in graph["edges"] if edge["relation_type"]=="SOURCE_RELATED_EVENT"]
    assert len(related)==1 and related[0]["related_event_index"]==0
    assert related[0]["source_event_evidence_id"]=="event:1" and related[0]["target_event_evidence_id"]=="event:2"
    assert not [edge for edge in related if edge["source_event_evidence_id"]=="event:2"]


def test_validator_rejects_duplicate_edge_unknown_endpoint_relation_and_input_hash():
    source, good = two_frame_graph()
    assert good["edges"]
    temporal=[edge for edge in good["edges"] if edge["relation_type"]=="TEMPORAL_SUCCESSION"]
    assert len(temporal)==1
    related=[edge for edge in good["edges"] if edge["relation_type"]=="SOURCE_RELATED_EVENT"]
    assert len(related)==1 and related[0]["related_event_id"]=="event:2"
    changes = [
        (duplicate_edge, "TIP-AG-EDGE-DUPLICATE"),
        (lambda raw: raw["edges"][0].update(source_node_id="action_node:unknown"), "TIP-AG-EDGE-ENDPOINT-INVALID"),
        (lambda raw: raw["edges"][0].update(relation_type="CAUSES"), "TIP-AG-RELATION-TYPE-INVALID"),
    ]
    for change, code in changes:
        with pytest.raises(ActionGraphError, match=code):
            validate_action_graph_dataset(mutate(good, change), source)
    wrong = Artifact(good.data, good.media_type, "e" * 64)
    with pytest.raises(ActionGraphError, match="TIP-AG-INPUT-HASH-INVALID"):
        validate_action_graph_dataset(wrong, source)


def test_locatelli_and_depay_succeed_and_di_maria_fails_before_action_graph():
    expected_counts={3788754:{"PASS_EVENT":17,"CARRY_EVENT":11,"BALL_RECEIPT_EVENT":17,"SHOT_EVENT":1},3869117:{"PASS_EVENT":21,"CARRY_EVENT":16,"BALL_RECEIPT_EVENT":21,"SHOT_EVENT":1}}
    expected_temporal={3788754:44,3869117:58};expected_related={3788754:59,3869117:74}
    for match_id, possession_id, frame_count in ((3788754, 40, 46), (3869117, 20, 59)):
        source, graph = fixture_chain(match_id, possession_id)
        repeated = build_action_graph_dataset(source)
        assert graph.validated and len(graph["frames"]) == frame_count
        assert graph.canonical_bytes() == repeated.canonical_bytes() and graph.sha256 == repeated.sha256
        assert {action_type:sum(node["action_type"]==action_type for node in graph["nodes"]) for action_type in expected_counts[match_id]}==expected_counts[match_id]
        temporal=[edge for edge in graph["edges"] if edge["relation_type"]=="TEMPORAL_SUCCESSION"]
        assert len(temporal)==expected_temporal[match_id]
        related=[edge for edge in graph["edges"] if edge["relation_type"]=="SOURCE_RELATED_EVENT"]
        assert len(related)==expected_related[match_id]
        node_by_id={node["node_id"]:node for node in graph["nodes"]}
        assert all(node_by_id[edge["target_node_id"]]["timestamp"]>node_by_id[edge["source_node_id"]]["timestamp"] for edge in temporal)
        if match_id == 3788754:
            event_id = "event:statsbomb:e51fde20-708e-49e4-ae77-5bc768e5f411"
            evidence = next(item for item in source["event_evidence"] if item["event_id"] == event_id)
            record = next(item for frame in source["frames"] for item in frame["records"] if item["concept_code"] == "SOURCE_DECLARED_PASS" and item["supporting_event_evidence_ids"] == (event_id,))
            assert record["participant_entity_ids"] == (evidence["actor"], evidence["recipient"])
            assert evidence["authenticated_provenance"]["/event_type"]["sources"]
            assert record["recognition_provenance"]["/value"]["sources"] == [{"source_record_id":event_id,"source_path":f"perception_dataset#/event_evidence/{record['world_state_index']}"}]
            related_by_event={item["event_id"]:item["related_event_ids"] for item in source["event_evidence"]}
            assert related_by_event[event_id]==("9141f1b5-8961-4842-b566-e583d271c6d3",)
            assert related_by_event["event:statsbomb:a10e93ca-9968-4472-8209-1441ac94b02a"]==("1cba92f6-e388-483f-8e77-ecf792df4809","e795a26f-89e9-47eb-97bb-30e681294249")
            nodes={node["event_id"]:node for node in graph["nodes"] if node["event_id"]}
            locatelli_edges=[edge for edge in related if edge["source_node_id"]==nodes[event_id]["node_id"]]
            assert [(edge["related_event_id"],edge["related_event_index"]) for edge in locatelli_edges]==[("9141f1b5-8961-4842-b566-e583d271c6d3",0)]
            incomplete_id="event:statsbomb:a10e93ca-9968-4472-8209-1441ac94b02a"
            incomplete_edges=[edge for edge in related if edge["source_node_id"]==nodes[incomplete_id]["node_id"]]
            assert [(edge["related_event_id"],edge["related_event_index"]) for edge in incomplete_edges]==[("1cba92f6-e388-483f-8e77-ecf792df4809",0),("e795a26f-89e9-47eb-97bb-30e681294249",1)]
            assert nodes[incomplete_id]["event_type"]=="PASS"
    base = Path("data/open-data/data")
    request = {"source_dataset": "statsbomb-open-data", "source_revision": PINNED_REVISION, "match_id": 3869685, "possession_id": 52}
    with pytest.raises(SourceSelectionError, match="SRC_EVENT_INDEX_INVALID"):
        select_source_documents(json.loads((base / "events/3869685.json").read_text()), json.loads((base / "three-sixty/3869685.json").read_text()), request)


def test_action_graph_has_no_forbidden_imports_or_legacy_symbols():
    forbidden = (
        "analysis", "src.intelligence", "src.render", "src.pipelines", "scripts.narrative_window",
        "src.source_selection", "src.normalization", "src.synchronization", "src.world_model",
        "NormalizedPossession", "TacticalFinding", "ActionChain", "NarrativeStep",
    )
    text = "\n".join(path.read_text() for path in sorted(Path("src/action_graph").glob("*.py")))
    assert not [token for token in forbidden if token in text]
