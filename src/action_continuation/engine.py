from __future__ import annotations

from dataclasses import asdict
import hashlib
from typing import Any

from src.action_graph.engine import MEDIA_TYPE as ACTION_GRAPH_MEDIA_TYPE, validate_action_graph_dataset
from src.contracts import Artifact
from src.recognition.engine import MEDIA_TYPE as RECOGNITION_MEDIA_TYPE, validate_recognition_dataset
from src.semantic_resolution.engine import MEDIA_TYPE as SEMANTIC_MEDIA_TYPE, validate_semantic_resolution_dataset

from .errors import ActionContinuationError
from .models import (
    ActionContinuationDataset,
    ActionContinuationMetadata,
    ContinuationResolution,
    PlayerActionContinuation,
)
from .registry import RELATION_TYPES, SUPPORTED_ACTION_TYPES


MEDIA_TYPE = "application/vnd.tip.action-continuation-dataset+json"


def _identifier(prefix: str, *parts: str) -> str:
    return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode('utf-8')).hexdigest()}"


def _uuid(event_id: str) -> str:
    prefix = "event:statsbomb:"
    if not isinstance(event_id, str) or not event_id.startswith(prefix) or not event_id[len(prefix):]:
        raise ActionContinuationError("TIP-CONT-EVENT-EVIDENCE-INVALID")
    return event_id[len(prefix):]


def _ordering_key(node: dict[str, Any]) -> tuple[int, float, str]:
    index = node.get("world_state_index")
    timestamp = node.get("timestamp")
    event_id = node.get("event_id")
    if not isinstance(index, int) or index < 0 or not isinstance(timestamp, (int, float)) or not isinstance(event_id, str):
        raise ActionContinuationError("TIP-CONT-ORDERING-PROVENANCE-INVALID")
    return index, timestamp, event_id


def _validate_inputs(action_graph: Artifact, recognition: Artifact, semantic: Artifact) -> None:
    if not isinstance(action_graph, Artifact) or not action_graph.authentic(ACTION_GRAPH_MEDIA_TYPE, "tip.action_graph_dataset"):
        raise ActionContinuationError("TIP-CONT-INPUT-ARTIFACT-INVALID")
    if not isinstance(recognition, Artifact) or not recognition.authentic(RECOGNITION_MEDIA_TYPE, "tip.recognition_dataset"):
        raise ActionContinuationError("TIP-CONT-INPUT-ARTIFACT-INVALID")
    if not isinstance(semantic, Artifact) or not semantic.authentic(SEMANTIC_MEDIA_TYPE, "tip.semantic_resolution_dataset"):
        raise ActionContinuationError("TIP-CONT-INPUT-ARTIFACT-INVALID")
    try:
        validate_recognition_dataset(recognition)
        validate_action_graph_dataset(action_graph, recognition)
        validate_semantic_resolution_dataset(semantic, action_graph, recognition)
    except Exception as exc:
        raise ActionContinuationError("TIP-CONT-UPSTREAM-INVALID") from exc
    if action_graph["recognition_dataset_sha256"] != recognition.sha256 or semantic["action_graph_sha256"] != action_graph.sha256 or semantic["recognition_dataset_sha256"] != recognition.sha256:
        raise ActionContinuationError("TIP-CONT-UPSTREAM-HASH-INVALID")
    contexts = {(artifact["match_id"], artifact["possession_id"]) for artifact in (action_graph, recognition, semantic)}
    if len(contexts) != 1:
        raise ActionContinuationError("TIP-CONT-CONTEXT-MISMATCH")


def _build_data(action_graph: Artifact, recognition: Artifact, semantic: Artifact) -> dict[str, Any]:
    graph = action_graph.payload
    rec = recognition.payload
    nodes = [node for node in graph["nodes"] if node["action_type"] in SUPPORTED_ACTION_TYPES]
    nodes.sort(key=_ordering_key)
    node_by_id = {node["node_id"]: node for node in graph["nodes"]}
    if len(node_by_id) != len(graph["nodes"]):
        raise ActionContinuationError("TIP-CONT-ENDPOINT-AMBIGUOUS")
    evidence_groups: dict[str, list[dict[str, Any]]] = {}
    for item in rec["event_evidence"]:
        evidence_groups.setdefault(item["event_id"], []).append(item)
    record_groups: dict[str, list[dict[str, Any]]] = {}
    for frame in rec["frames"]:
        for record in frame["records"]:
            record_groups.setdefault(record["recognition_id"], []).append(record)

    validated: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for node in nodes:
        evidence = evidence_groups.get(node.get("event_evidence_id"), [])
        records = record_groups.get(node.get("recognition_record_id"), [])
        if len(evidence) != 1 or len(records) != 1:
            raise ActionContinuationError("TIP-CONT-ENDPOINT-AMBIGUOUS")
        item = evidence[0]
        if node.get("actor") != item.get("actor") or not isinstance(item.get("actor"), str):
            raise ActionContinuationError("TIP-CONT-PLAYER-IDENTITY-AMBIGUOUS")
        if node.get("event_id") != item.get("event_id") or node.get("event_evidence_id") != item.get("event_id"):
            raise ActionContinuationError("TIP-CONT-EVENT-EVIDENCE-INVALID")
        _uuid(item["event_id"])
        _ordering_key(node)
        validated.append((node, item, records[0]))

    relations: list[PlayerActionContinuation] = []
    resolutions: list[ContinuationResolution] = []
    semantic_relations = semantic["relations"]
    graph_edges = graph["edges"]
    for source_position, (source, source_evidence, _) in enumerate(validated):
        target_position = next((index for index in range(source_position + 1, len(validated)) if validated[index][1]["actor"] == source_evidence["actor"]), None)
        source_uuid = _uuid(source_evidence["event_id"])
        if target_position is None:
            resolutions.append(ContinuationResolution("tip.continuation_resolution", source["node_id"], source_uuid, source_evidence["actor"], "REJECTED", "TIP-CONT-NO-LATER-SAME-PLAYER-ACTION", None))
            continue
        target, target_evidence, _ = validated[target_position]
        source_key = _ordering_key(source)
        target_key = _ordering_key(target)
        if target_key <= source_key:
            raise ActionContinuationError("TIP-CONT-NON-LATER-TARGET")
        between = validated[source_position + 1:target_position]
        intervening = tuple({
            "source_event_uuid": _uuid(evidence["event_id"]),
            "action_graph_node_id": node["node_id"],
            "recognition_id": node["recognition_record_id"],
            "event_evidence_id": node["event_evidence_id"],
            "actor_id": evidence["actor"],
            "event_type": node["action_type"],
            "canonical_ordering_key": _ordering_key(node),
        } for node, evidence, _ in between)
        chain_ids = {source["node_id"], target["node_id"], *(item["action_graph_node_id"] for item in intervening)}
        semantic_ids = tuple(sorted(relation["edge_id"] for relation in semantic_relations if relation["source_node_id"] in chain_ids and relation["target_node_id"] in chain_ids))
        graph_relation_ids = tuple(sorted(edge["edge_id"] for edge in graph_edges if edge["source_node_id"] in chain_ids and edge["target_node_id"] in chain_ids))
        edge_id = _identifier("continuation_edge", source["node_id"], "PLAYER_ACTION_CONTINUATION", target["node_id"])
        relations.append(PlayerActionContinuation(
            "tip.player_action_continuation", "0.1.0", edge_id, "PLAYER_ACTION_CONTINUATION",
            source["node_id"], target["node_id"], source["recognition_record_id"], target["recognition_record_id"],
            source["event_evidence_id"], target["event_evidence_id"], source_uuid, _uuid(target_evidence["event_id"]),
            source_evidence["actor"], source["action_type"], target["action_type"], source_key, target_key,
            graph["match_id"], graph["possession_id"], intervening, semantic_ids, graph_relation_ids, "RESOLVED",
            action_graph.sha256, recognition.sha256, semantic.sha256,
        ))
        resolutions.append(ContinuationResolution("tip.continuation_resolution", source["node_id"], source_uuid, source_evidence["actor"], "RESOLVED", None, edge_id))

    relations.sort(key=lambda relation: (relation.source_ordering_key, relation.target_ordering_key, relation.edge_id))
    resolutions.sort(key=lambda resolution: resolution.source_node_id)
    if len({relation.edge_id for relation in relations}) != len(relations):
        raise ActionContinuationError("TIP-CONT-RELATION-DUPLICATE")
    players = {relation.player_id for relation in relations}
    metadata = ActionContinuationMetadata(
        "tip.action_continuation_metadata", len(nodes), len(players), len(relations),
        sum(item.rejection_code == "TIP-CONT-NO-LATER-SAME-PLAYER-ACTION" for item in resolutions), 0, 0,
        max((len(relation.intervening_events) for relation in relations), default=0),
    )
    return asdict(ActionContinuationDataset(
        "tip.action_continuation_dataset", "0.1.0", "0.1.0", action_graph.sha256, recognition.sha256,
        semantic.sha256, graph["match_id"], graph["possession_id"], RELATION_TYPES, tuple(relations),
        tuple(resolutions), metadata, {"action_graph_sha256": action_graph.sha256, "recognition_dataset_sha256": recognition.sha256, "semantic_resolution_sha256": semantic.sha256},
    ))


def build_action_continuation_dataset(action_graph: Artifact, recognition: Artifact, semantic: Artifact) -> Artifact:
    _validate_inputs(action_graph, recognition, semantic)
    artifact = Artifact(_build_data(action_graph, recognition, semantic), MEDIA_TYPE, semantic.sha256, semantic.source_hashes)
    return validate_action_continuation_dataset(artifact, action_graph, recognition, semantic)


def validate_action_continuation_dataset(continuation: Artifact, action_graph: Artifact, recognition: Artifact, semantic: Artifact) -> Artifact:
    _validate_inputs(action_graph, recognition, semantic)
    if not isinstance(continuation, Artifact) or not continuation.authentic(MEDIA_TYPE, "tip.action_continuation_dataset"):
        raise ActionContinuationError("TIP-CONT-INPUT-ARTIFACT-INVALID")
    if continuation.direct_input_sha256 != semantic.sha256:
        raise ActionContinuationError("TIP-CONT-UPSTREAM-HASH-INVALID")
    data = continuation.payload
    exact = {"schema_id", "contract_version", "input_contract_version", "action_graph_sha256", "recognition_dataset_sha256", "semantic_resolution_sha256", "match_id", "possession_id", "relation_types", "relations", "resolutions", "metadata", "input_provenance"}
    if set(data) != exact or data.get("contract_version") != "0.1.0" or data.get("input_contract_version") != "0.1.0":
        raise ActionContinuationError("TIP-CONT-MALFORMED-RELATION")
    relations = data.get("relations")
    if not isinstance(relations, (list, tuple)) or any(not isinstance(item, dict) for item in relations):
        raise ActionContinuationError("TIP-CONT-MALFORMED-RELATION")
    ids = [relation.get("edge_id") for relation in relations]
    if None in ids or len(ids) != len(set(ids)):
        raise ActionContinuationError("TIP-CONT-RELATION-DUPLICATE")
    expected = _build_data(action_graph, recognition, semantic)
    if (data.get("match_id"), data.get("possession_id")) != (action_graph["match_id"], action_graph["possession_id"]):
        raise ActionContinuationError("TIP-CONT-CONTEXT-MISMATCH")
    expected_by_id = {relation["edge_id"]: relation for relation in expected["relations"]}
    if set(ids) != set(expected_by_id):
        raise ActionContinuationError("TIP-CONT-DIRECT-SELECTION-INVALID")
    if list(relations) != sorted(relations, key=lambda item: (item["source_ordering_key"], item["target_ordering_key"], item["edge_id"])):
        raise ActionContinuationError("TIP-CONT-ORDERING-INVALID")
    required = set(PlayerActionContinuation.__dataclass_fields__)
    for relation in relations:
        if set(relation) != required or relation.get("relation_type") != "PLAYER_ACTION_CONTINUATION" or relation.get("resolution_status") != "RESOLVED":
            raise ActionContinuationError("TIP-CONT-MALFORMED-RELATION")
        expected_relation = expected_by_id[relation["edge_id"]]
        if relation != expected_relation:
            if relation.get("intervening_events") != expected_relation["intervening_events"] or relation.get("supporting_pass_receipt_link_ids") != expected_relation["supporting_pass_receipt_link_ids"] or relation.get("supporting_action_graph_relation_ids") != expected_relation["supporting_action_graph_relation_ids"]:
                raise ActionContinuationError("TIP-CONT-PROVENANCE-INVALID")
            raise ActionContinuationError("TIP-CONT-DEPENDENCY-INVALID")
    if data != expected:
        if data.get("metadata") != expected["metadata"] or data.get("resolutions") != expected["resolutions"]:
            raise ActionContinuationError("TIP-CONT-INVARIANT-VIOLATION")
        raise ActionContinuationError("TIP-CONT-PROVENANCE-INVALID")
    return continuation.validated_copy()
