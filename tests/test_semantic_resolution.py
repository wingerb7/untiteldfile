from __future__ import annotations

from copy import deepcopy

import pytest

from src.action_graph import build_action_graph_dataset
from src.contracts import Artifact, digest
from src.perception.authentication import PERCEPTION_MEDIA_TYPE
from src.recognition import build_recognition_dataset
from src.semantic_resolution import (
    MEDIA_TYPE,
    SemanticResolutionError,
    build_semantic_resolution_dataset,
    validate_semantic_resolution_dataset,
)


PASS_UUID = "11111111-1111-4111-8111-111111111111"
RECEIPT_UUID = "22222222-2222-4222-8222-222222222222"


def _provenance(index: int) -> dict:
    fields = ("/event_id", "/event_type", "/actor", "/recipient", "/canonical_timestamp", "/source_record_id", "/related_event_ids", "/outcome")
    return {field: {"class": "PRESERVED_AUTHENTICATED_INPUT", "operation": "WORLD_PRESERVE_EVENT_EVIDENCE", "sources": [{"source_record_id": f"source:{index}", "source_path": f"synchronized_dataset#/timeline/{index}/{field}"}]} for field in fields}


def _chain(
    direction: str = "pass_to_receipt", *, pass_outcome: str | None = "COMPLETED",
    recipient: str | None = "player:b", receipt_actor: str = "player:b", equal_time: bool = False,
    target_type: str = "BALL_RECEIPT", receipt_outcome: str | None = None, extra_receipt: bool = False,
) -> tuple[Artifact, Artifact, Artifact]:
    pass_related = (RECEIPT_UUID,) if direction in {"pass_to_receipt", "both"} else ()
    receipt_related = (PASS_UUID,) if direction in {"receipt_to_pass", "both"} else ()
    items = [
        (PASS_UUID, "PASS", "player:a", recipient, 1.0, pass_outcome, pass_related),
        (RECEIPT_UUID, target_type, receipt_actor, None, 1.0 if equal_time else 2.0, receipt_outcome, receipt_related),
    ]
    if extra_receipt:
        items.append(("33333333-3333-4333-8333-333333333333", "BALL_RECEIPT", "player:b", None, 3.0, None, (PASS_UUID,)))
    evidence = []
    frames = []
    for index, (uuid, event_type, actor, event_recipient, timestamp, outcome, related) in enumerate(items):
        event_id = f"event:statsbomb:{uuid}"
        evidence.append({"event_id": event_id, "event_type": event_type, "actor": actor, "recipient": event_recipient, "canonical_timestamp": timestamp, "source_record_id": f"source:{index}", "related_event_ids": related, "outcome": outcome, "authenticated_provenance": _provenance(index)})
        frames.append({"schema_id": "tip.perception_frame", "perception_frame_id": f"perception_frame:world:{index}", "world_state_id": f"world:{index}", "world_state_index": index, "canonical_time_seconds": timestamp, "features": [], "perception_provenance": {}})
    definitions = [{"feature_code": code} for code in ("ENTITY_SPEED", "PAIR_DISTANCE", "CONNECTION_CORRIDOR", "CORRIDOR_OCCUPANCY")]
    perception = Artifact({"schema_id": "tip.perception_dataset", "contract_version": "0.1.0", "input_contract_version": "0.1.0", "world_model_sha256": "0" * 64, "match_id": "match:statsbomb:1", "possession_id": "match:statsbomb:1:possession:1", "event_evidence": evidence, "feature_definitions": definitions, "frames": frames, "input_provenance": {}, "perception_provenance": {}}, PERCEPTION_MEDIA_TYPE, "0" * 64, validated=True)
    recognition = build_recognition_dataset(perception)
    graph = build_action_graph_dataset(recognition)
    return recognition, graph, build_semantic_resolution_dataset(graph, recognition)


@pytest.mark.parametrize("direction,count", [("pass_to_receipt", 1), ("receipt_to_pass", 1), ("both", 1)])
def test_declaration_direction_and_bidirectional_canonicalization(direction, count):
    _, _, semantic = _chain(direction)
    assert len(semantic["relations"]) == count
    relation = semantic["relations"][0]
    assert relation["source_event_uuid"] == PASS_UUID and relation["target_event_uuid"] == RECEIPT_UUID
    assert len(relation["supporting_declarations"]) == (2 if direction == "both" else 1)


def test_equal_timestamps_are_accepted():
    assert len(_chain(equal_time=True)[2]["relations"]) == 1


def test_explicit_incomplete_pass_remains_rejected_despite_receipt_relation():
    _, graph, semantic = _chain(pass_outcome="INCOMPLETE")
    assert any(node["action_type"] == "PASS_EVENT" for node in graph["nodes"])
    assert len([edge for edge in graph["edges"] if edge["relation_type"] == "SOURCE_RELATED_EVENT"]) == 1
    assert semantic["relations"] == ()
    assert semantic["pass_resolutions"][0]["rejection_code"] == "TIP-SEM-PASS-OUTCOME-UNSUCCESSFUL"


def test_explicit_failed_receipt_is_rejected():
    semantic = _chain(receipt_outcome="INCOMPLETE")[2]
    assert semantic["relations"] == ()
    assert semantic["pass_resolutions"][0]["rejection_code"] == "TIP-SEM-RECEIPT-OUTCOME-UNSUCCESSFUL"


def test_missing_or_unknown_pass_outcome_fails_closed():
    assert _chain(pass_outcome=None)[2]["pass_resolutions"][0]["rejection_code"] == "TIP-SEM-PASS-OUTCOME-INVALID"
    assert _chain(pass_outcome="MALFORMED")[2]["pass_resolutions"][0]["rejection_code"] == "TIP-SEM-PASS-OUTCOME-INVALID"


def test_recipient_match_conflict_and_missing_recipient():
    assert len(_chain(recipient="player:b", receipt_actor="player:b")[2]["relations"]) == 1
    conflict = _chain(recipient="player:c", receipt_actor="player:b")[2]
    assert conflict["pass_resolutions"][0]["rejection_code"] == "TIP-SEM-RECIPIENT-CONFLICT"
    assert len(_chain(recipient=None, receipt_actor="player:b")[2]["relations"]) == 1


def test_temporal_adjacency_without_source_relation_does_not_link():
    semantic = _chain(direction="none")[2]
    assert semantic["relations"] == ()
    assert semantic["pass_resolutions"][0]["rejection_code"] == "TIP-SEM-NO-AUTHENTICATED-RECEIPT-RELATION"


def test_unsupported_related_target_does_not_create_relation():
    semantic = _chain(target_type="CARRY")[2]
    assert semantic["relations"] == ()


def test_missing_related_target_does_not_create_relation():
    recognition, _, _ = _chain(direction="none")
    raw = recognition.data
    raw["event_evidence"][0]["related_event_ids"] = ("99999999-9999-4999-8999-999999999999",)
    altered = Artifact(raw, recognition.media_type, recognition.direct_input_sha256, recognition.source_hashes, validated=True)
    graph = build_action_graph_dataset(altered)
    semantic = build_semantic_resolution_dataset(graph, altered)
    assert semantic["relations"] == ()


def test_ambiguous_receipt_candidates_fail_closed():
    semantic = _chain(extra_receipt=True)[2]
    assert semantic["relations"] == ()
    assert semantic["pass_resolutions"][0]["rejection_code"] == "TIP-SEM-ENDPOINT-AMBIGUOUS"


def test_malformed_supporting_provenance_is_reported():
    recognition, graph, semantic = _chain()
    raw = semantic.data
    raw["relations"][0]["supporting_declarations"][0]["related_event_index"] = 99
    with pytest.raises(SemanticResolutionError, match="TIP-SEM-PROVENANCE-INVALID"):
        validate_semantic_resolution_dataset(Artifact(raw, MEDIA_TYPE, graph.sha256, graph.source_hashes), graph, recognition)


def test_duplicate_semantic_edge_is_reported():
    recognition, graph, semantic = _chain()
    raw = semantic.data
    raw["relations"] = (*raw["relations"], deepcopy(raw["relations"][0]))
    with pytest.raises(SemanticResolutionError, match="TIP-SEM-RELATION-DUPLICATE"):
        validate_semantic_resolution_dataset(Artifact(raw, MEDIA_TYPE, graph.sha256, graph.source_hashes), graph, recognition)


def test_deterministic_ids_serialization_ordering_and_hashing():
    recognition, graph, one = _chain(direction="both")
    two = build_semantic_resolution_dataset(graph, recognition)
    assert one["relations"][0]["edge_id"] == two["relations"][0]["edge_id"]
    assert one.canonical_bytes() == two.canonical_bytes()
    assert one.sha256 == two.sha256 == digest(one.data)
    assert list(one["relations"]) == sorted(one["relations"], key=lambda item: (item["source_node_id"], item["target_node_id"], item["edge_id"]))


def test_context_mismatch_fails_closed():
    recognition, graph, semantic = _chain()
    raw = semantic.data
    raw["possession_id"] = "match:statsbomb:1:possession:2"
    with pytest.raises(SemanticResolutionError, match="TIP-SEM-CONTEXT-MISMATCH"):
        validate_semantic_resolution_dataset(Artifact(raw, MEDIA_TYPE, graph.sha256, graph.source_hashes), graph, recognition)


def test_existing_graph_relations_are_unchanged_by_resolution():
    recognition, graph, _ = _chain(direction="both")
    before = graph.canonical_bytes()
    build_semantic_resolution_dataset(graph, recognition)
    assert graph.canonical_bytes() == before
    assert {edge["relation_type"] for edge in graph["edges"]} >= {"SOURCE_RELATED_EVENT"}
