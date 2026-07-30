from __future__ import annotations

from copy import deepcopy

import pytest

from src.action_continuation import (
    MEDIA_TYPE,
    ActionContinuationError,
    build_action_continuation_dataset,
    validate_action_continuation_dataset,
)
from src.action_graph import build_action_graph_dataset
from src.contracts import Artifact, digest
from src.perception.authentication import PERCEPTION_MEDIA_TYPE
from src.recognition import build_recognition_dataset
from src.semantic_resolution import build_semantic_resolution_dataset


def _prov(index: int) -> dict:
    fields = ("/event_id", "/event_type", "/actor", "/recipient", "/canonical_timestamp", "/source_record_id", "/related_event_ids", "/outcome")
    return {field: {"class": "PRESERVED_AUTHENTICATED_INPUT", "operation": "WORLD_PRESERVE_EVENT_EVIDENCE", "sources": [{"source_record_id": f"source:{index}", "source_path": f"synchronized_dataset#/timeline/{index}/{field}"}]} for field in fields}


def chain(events: list[dict], match: str = "match:statsbomb:1", possession: str = "match:statsbomb:1:possession:1"):
    evidence, frames = [], []
    for index, event in enumerate(events):
        uuid = event.get("uuid", f"00000000-0000-4000-8000-{index:012d}")
        event_id = f"event:statsbomb:{uuid}"
        timestamp = event.get("time", float(index + 1))
        event_type = event["type"]
        outcome = event.get("outcome", "COMPLETED" if event_type == "PASS" else "GOAL" if event_type == "SHOT" else None)
        evidence.append({"event_id": event_id, "event_type": event_type, "actor": event["actor"], "recipient": event.get("recipient"), "canonical_timestamp": timestamp, "source_record_id": f"source:{index}", "related_event_ids": tuple(event.get("related", ())), "outcome": outcome, "authenticated_provenance": _prov(index)})
        frames.append({"schema_id": "tip.perception_frame", "perception_frame_id": f"perception_frame:world:{index}", "world_state_id": f"world:{index}", "world_state_index": index, "canonical_time_seconds": timestamp, "features": [], "perception_provenance": {}})
    definitions = [{"feature_code": code} for code in ("ENTITY_SPEED", "PAIR_DISTANCE", "CONNECTION_CORRIDOR", "CORRIDOR_OCCUPANCY")]
    perception = Artifact({"schema_id": "tip.perception_dataset", "contract_version": "0.1.0", "input_contract_version": "0.1.0", "world_model_sha256": "0" * 64, "match_id": match, "possession_id": possession, "event_evidence": evidence, "feature_definitions": definitions, "frames": frames, "input_provenance": {}, "perception_provenance": {}}, PERCEPTION_MEDIA_TYPE, "0" * 64, validated=True)
    recognition = build_recognition_dataset(perception)
    graph = build_action_graph_dataset(recognition)
    semantic = build_semantic_resolution_dataset(graph, recognition)
    continuation = build_action_continuation_dataset(graph, recognition, semantic)
    return recognition, graph, semantic, continuation


@pytest.mark.parametrize("source,target", [("PASS", "BALL_RECEIPT"), ("BALL_RECEIPT", "CARRY"), ("CARRY", "PASS"), ("BALL_RECEIPT", "SHOT")])
def test_supported_direct_action_pairs(source, target):
    *_, result = chain([{"type": source, "actor": "player:a"}, {"type": target, "actor": "player:a"}])
    assert [(edge["source_action_type"], edge["target_action_type"]) for edge in result["relations"]] == [(f"{source}_EVENT", f"{target}_EVENT")]


def test_intervening_actions_and_direct_non_transitive_rule():
    *_, result = chain([
        {"type": "PASS", "actor": "player:a"}, {"type": "CARRY", "actor": "player:b"},
        {"type": "BALL_RECEIPT", "actor": "player:a"}, {"type": "PASS", "actor": "player:b"},
        {"type": "SHOT", "actor": "player:a"},
    ])
    a_edges = [edge for edge in result["relations"] if edge["player_id"] == "player:a"]
    assert [(e["source_action_type"], e["target_action_type"]) for e in a_edges] == [("PASS_EVENT", "BALL_RECEIPT_EVENT"), ("BALL_RECEIPT_EVENT", "SHOT_EVENT")]
    assert [len(e["intervening_events"]) for e in a_edges] == [1, 1]
    assert not any(e["source_action_type"] == "PASS_EVENT" and e["target_action_type"] == "SHOT_EVENT" for e in a_edges)


def test_equal_timestamp_uses_canonical_source_order():
    *_, result = chain([{"type": "PASS", "actor": "player:a", "time": 1.0}, {"type": "BALL_RECEIPT", "actor": "player:a", "time": 1.0}])
    edge = result["relations"][0]
    assert edge["source_ordering_key"][0] == 0 and edge["target_ordering_key"][0] == 1


def test_reverse_or_malformed_ordering_is_rejected():
    recognition, graph, semantic, result = chain([{"type": "PASS", "actor": "player:a"}, {"type": "SHOT", "actor": "player:a"}])
    raw = result.data
    raw["relations"][0]["target_ordering_key"] = raw["relations"][0]["source_ordering_key"]
    with pytest.raises(ActionContinuationError, match="TIP-CONT-DEPENDENCY-INVALID"):
        validate_action_continuation_dataset(Artifact(raw, MEDIA_TYPE, semantic.sha256), graph, recognition, semantic)


def test_recipient_is_not_actor_and_incomplete_pass_is_valid_source():
    *_, result = chain([{"type": "PASS", "actor": "player:a", "recipient": "player:b", "outcome": "INCOMPLETE"}, {"type": "CARRY", "actor": "player:b"}, {"type": "SHOT", "actor": "player:a"}])
    edge = next(edge for edge in result["relations"] if edge["source_action_type"] == "PASS_EVENT")
    assert edge["player_id"] == "player:a" and edge["target_action_type"] == "SHOT_EVENT"
    assert edge["intervening_events"][0]["actor_id"] == "player:b"


def test_no_later_action_is_audited():
    *_, result = chain([{"type": "PASS", "actor": "player:a"}])
    assert result["relations"] == ()
    assert result["resolutions"][0]["rejection_code"] == "TIP-CONT-NO-LATER-SAME-PLAYER-ACTION"


def test_semantic_and_graph_support_is_real_and_upstream_is_immutable():
    pass_uuid = "11111111-1111-4111-8111-111111111111"
    receipt_uuid = "22222222-2222-4222-8222-222222222222"
    recognition, graph, semantic, result = chain([
        {"uuid": pass_uuid, "type": "PASS", "actor": "player:a", "recipient": "player:b", "related": (receipt_uuid,)},
        {"uuid": receipt_uuid, "type": "BALL_RECEIPT", "actor": "player:b", "related": (pass_uuid,)},
        {"type": "SHOT", "actor": "player:a"},
    ])
    graph_bytes, semantic_bytes = graph.canonical_bytes(), semantic.canonical_bytes()
    edge = next(edge for edge in result["relations"] if edge["player_id"] == "player:a")
    assert edge["supporting_pass_receipt_link_ids"] == (semantic["relations"][0]["edge_id"],)
    assert edge["supporting_action_graph_relation_ids"]
    assert graph.canonical_bytes() == graph_bytes and semantic.canonical_bytes() == semantic_bytes


def test_malformed_intervening_or_missing_support_is_reported():
    recognition, graph, semantic, result = chain([{"type": "PASS", "actor": "player:a"}, {"type": "CARRY", "actor": "player:b"}, {"type": "SHOT", "actor": "player:a"}])
    for field in ("intervening_events", "supporting_action_graph_relation_ids"):
        raw = result.data
        raw["relations"][0][field] = ()
        with pytest.raises(ActionContinuationError, match="TIP-CONT-PROVENANCE-INVALID"):
            validate_action_continuation_dataset(Artifact(raw, MEDIA_TYPE, semantic.sha256), graph, recognition, semantic)


def test_duplicate_and_malformed_relations_are_reported():
    recognition, graph, semantic, result = chain([{"type": "PASS", "actor": "player:a"}, {"type": "SHOT", "actor": "player:a"}])
    raw = result.data
    raw["relations"] = (*raw["relations"], deepcopy(raw["relations"][0]))
    with pytest.raises(ActionContinuationError, match="TIP-CONT-RELATION-DUPLICATE"):
        validate_action_continuation_dataset(Artifact(raw, MEDIA_TYPE, semantic.sha256), graph, recognition, semantic)
    raw = result.data
    del raw["relations"][0]["player_id"]
    with pytest.raises(ActionContinuationError, match="TIP-CONT-MALFORMED-RELATION"):
        validate_action_continuation_dataset(Artifact(raw, MEDIA_TYPE, semantic.sha256), graph, recognition, semantic)


def test_deterministic_id_serialization_ordering_and_hashing():
    recognition, graph, semantic, one = chain([{"type": "PASS", "actor": "player:a"}, {"type": "CARRY", "actor": "player:b"}, {"type": "SHOT", "actor": "player:a"}])
    two = build_action_continuation_dataset(graph, recognition, semantic)
    assert one["relations"][0]["edge_id"] == two["relations"][0]["edge_id"]
    assert one.canonical_bytes() == two.canonical_bytes()
    assert one.sha256 == two.sha256 == digest(one.data)
    assert list(one["relations"]) == sorted(one["relations"], key=lambda item: (item["source_ordering_key"], item["target_ordering_key"], item["edge_id"]))


def test_context_and_upstream_hash_fail_closed():
    recognition, graph, semantic, result = chain([{"type": "PASS", "actor": "player:a"}, {"type": "SHOT", "actor": "player:a"}])
    raw = result.data
    raw["possession_id"] = "match:statsbomb:1:possession:2"
    with pytest.raises(ActionContinuationError, match="TIP-CONT-CONTEXT-MISMATCH"):
        validate_action_continuation_dataset(Artifact(raw, MEDIA_TYPE, semantic.sha256), graph, recognition, semantic)
    with pytest.raises(ActionContinuationError, match="TIP-CONT-UPSTREAM-HASH-INVALID"):
        validate_action_continuation_dataset(Artifact(result.data, MEDIA_TYPE, "f" * 64), graph, recognition, semantic)
