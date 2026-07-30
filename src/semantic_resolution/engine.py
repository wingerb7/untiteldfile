from __future__ import annotations

from dataclasses import asdict
import hashlib
from typing import Any

from src.action_graph.engine import MEDIA_TYPE as ACTION_GRAPH_MEDIA_TYPE, validate_action_graph_dataset
from src.contracts import Artifact
from src.recognition.engine import MEDIA_TYPE as RECOGNITION_MEDIA_TYPE, validate_recognition_dataset

from .errors import SemanticResolutionError
from .models import (
    PassReceiptRelation,
    PassResolution,
    SemanticResolutionDataset,
    SemanticResolutionMetadata,
)
from .registry import RELATION_TYPES


MEDIA_TYPE = "application/vnd.tip.semantic-resolution-dataset+json"
UNSUCCESSFUL_PASS_OUTCOMES = frozenset({"INCOMPLETE", "OUT", "OFFSIDE", "UNKNOWN", "UNSUCCESSFUL"})
UNSUCCESSFUL_RECEIPT_OUTCOMES = frozenset({"INCOMPLETE", "FAILED", "FAILURE", "UNSUCCESSFUL"})


def _identifier(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()}"


def _uuid(event_id: str) -> str:
    prefix = "event:statsbomb:"
    if not isinstance(event_id, str) or not event_id.startswith(prefix) or not event_id[len(prefix):]:
        raise SemanticResolutionError("TIP-SEM-EVENT-EVIDENCE-INVALID")
    return event_id[len(prefix):]


def _validate_inputs(action_graph: Artifact, recognition: Artifact) -> None:
    if not isinstance(action_graph, Artifact) or not action_graph.authentic(ACTION_GRAPH_MEDIA_TYPE, "tip.action_graph_dataset"):
        raise SemanticResolutionError("TIP-SEM-INPUT-ARTIFACT-INVALID")
    if not isinstance(recognition, Artifact) or not recognition.authentic(RECOGNITION_MEDIA_TYPE, "tip.recognition_dataset"):
        raise SemanticResolutionError("TIP-SEM-INPUT-ARTIFACT-INVALID")
    try:
        validate_recognition_dataset(recognition)
        validate_action_graph_dataset(action_graph, recognition)
    except Exception as exc:
        raise SemanticResolutionError("TIP-SEM-UPSTREAM-INVALID") from exc
    if action_graph["recognition_dataset_sha256"] != recognition.sha256:
        raise SemanticResolutionError("TIP-SEM-INPUT-HASH-INVALID")
    if (action_graph["match_id"], action_graph["possession_id"]) != (recognition["match_id"], recognition["possession_id"]):
        raise SemanticResolutionError("TIP-SEM-CONTEXT-MISMATCH")


def _build_data(action_graph: Artifact, recognition: Artifact) -> dict[str, Any]:
    graph = action_graph.payload
    rec = recognition.payload
    nodes = graph["nodes"]
    node_by_id = {node["node_id"]: node for node in nodes}
    if len(node_by_id) != len(nodes):
        raise SemanticResolutionError("TIP-SEM-ENDPOINT-AMBIGUOUS")
    evidence_groups: dict[str, list[dict[str, Any]]] = {}
    for item in rec["event_evidence"]:
        evidence_groups.setdefault(item["event_id"], []).append(item)
    recognition_groups: dict[str, list[dict[str, Any]]] = {}
    for frame in rec["frames"]:
        for record in frame["records"]:
            recognition_groups.setdefault(record["recognition_id"], []).append(record)
    related_edges = [edge for edge in graph["edges"] if edge["relation_type"] == "SOURCE_RELATED_EVENT"]
    relations: list[PassReceiptRelation] = []
    resolutions: list[PassResolution] = []

    for pass_node in sorted((n for n in nodes if n["action_type"] == "PASS_EVENT"), key=lambda n: n["node_id"]):
        pass_uuid = _uuid(pass_node["event_id"])
        pass_evidence_items = evidence_groups.get(pass_node["event_evidence_id"], [])
        pass_records = recognition_groups.get(pass_node["recognition_record_id"], [])
        if len(pass_evidence_items) != 1 or len(pass_records) != 1:
            resolutions.append(PassResolution("tip.pass_resolution", pass_node["node_id"], pass_uuid, "REJECTED", "TIP-SEM-ENDPOINT-AMBIGUOUS", None))
            continue
        pass_evidence = pass_evidence_items[0]
        if pass_evidence["event_type"] != "PASS" or pass_node["event_type"] != "PASS":
            resolutions.append(PassResolution("tip.pass_resolution", pass_node["node_id"], pass_uuid, "REJECTED", "TIP-SEM-NODE-TYPE-INVALID", None))
            continue
        if pass_evidence.get("outcome") in UNSUCCESSFUL_PASS_OUTCOMES:
            resolutions.append(PassResolution("tip.pass_resolution", pass_node["node_id"], pass_uuid, "REJECTED", "TIP-SEM-PASS-OUTCOME-UNSUCCESSFUL", None))
            continue
        if pass_evidence.get("outcome") != "COMPLETED":
            resolutions.append(PassResolution("tip.pass_resolution", pass_node["node_id"], pass_uuid, "REJECTED", "TIP-SEM-PASS-OUTCOME-INVALID", None))
            continue

        candidates: dict[str, list[dict[str, Any]]] = {}
        for edge in related_edges:
            other_id = None
            if edge["source_node_id"] == pass_node["node_id"]:
                other_id = edge["target_node_id"]
            elif edge["target_node_id"] == pass_node["node_id"]:
                other_id = edge["source_node_id"]
            if other_id is None:
                continue
            other = node_by_id.get(other_id)
            if other is not None and other["action_type"] == "BALL_RECEIPT_EVENT":
                candidates.setdefault(other_id, []).append(edge)
        if not candidates:
            resolutions.append(PassResolution("tip.pass_resolution", pass_node["node_id"], pass_uuid, "REJECTED", "TIP-SEM-NO-AUTHENTICATED-RECEIPT-RELATION", None))
            continue
        if len(candidates) != 1:
            resolutions.append(PassResolution("tip.pass_resolution", pass_node["node_id"], pass_uuid, "REJECTED", "TIP-SEM-ENDPOINT-AMBIGUOUS", None))
            continue

        receipt_id, supports = next(iter(candidates.items()))
        receipt = node_by_id[receipt_id]
        receipt_evidence_items = evidence_groups.get(receipt["event_evidence_id"], [])
        receipt_records = recognition_groups.get(receipt["recognition_record_id"], [])
        rejection = None
        if len(receipt_evidence_items) != 1 or len(receipt_records) != 1:
            rejection = "TIP-SEM-ENDPOINT-AMBIGUOUS"
        else:
            receipt_evidence = receipt_evidence_items[0]
            if receipt_evidence["event_type"] != "BALL_RECEIPT" or receipt["event_type"] != "BALL_RECEIPT":
                rejection = "TIP-SEM-NODE-TYPE-INVALID"
            elif receipt_evidence.get("outcome") in UNSUCCESSFUL_RECEIPT_OUTCOMES:
                rejection = "TIP-SEM-RECEIPT-OUTCOME-UNSUCCESSFUL"
            elif receipt_evidence.get("outcome") not in (None, "COMPLETED"):
                rejection = "TIP-SEM-RECEIPT-OUTCOME-INVALID"
            elif receipt["timestamp"] < pass_node["timestamp"] or receipt["world_state_index"] < pass_node["world_state_index"]:
                rejection = "TIP-SEM-TEMPORAL-ORDER-INVALID"
            elif pass_evidence.get("recipient") is not None and pass_evidence["recipient"] != receipt_evidence["actor"]:
                rejection = "TIP-SEM-RECIPIENT-CONFLICT"
        if rejection:
            resolutions.append(PassResolution("tip.pass_resolution", pass_node["node_id"], pass_uuid, "REJECTED", rejection, None))
            continue

        receipt_evidence = receipt_evidence_items[0]
        declarations = []
        for edge in sorted(supports, key=lambda e: e["edge_id"]):
            if {edge["source_node_id"], edge["target_node_id"]} != {pass_node["node_id"], receipt["node_id"]}:
                raise SemanticResolutionError("TIP-SEM-SUPPORTING-EDGE-INVALID")
            direction = "PASS_TO_RECEIPT" if edge["source_node_id"] == pass_node["node_id"] else "RECEIPT_TO_PASS"
            declaration_source = node_by_id[edge["source_node_id"]]
            declaration_target = node_by_id[edge["target_node_id"]]
            declarations.append({
                "source_related_edge_id": edge["edge_id"], "declaration_direction": direction,
                "declaration_source_event_uuid": _uuid(declaration_source["event_id"]),
                "declaration_target_event_uuid": _uuid(declaration_target["event_id"]),
                "related_event_index": edge["related_event_index"],
            })
        support_ids = tuple(item["source_related_edge_id"] for item in declarations)
        edge_id = _identifier("semantic_edge", pass_node["node_id"], "PASS_RECEIPT_LINK", receipt["node_id"])
        relations.append(PassReceiptRelation(
            "tip.pass_receipt_relation", edge_id, "PASS_RECEIPT_LINK", pass_node["node_id"], receipt["node_id"],
            pass_node["recognition_record_id"], receipt["recognition_record_id"], pass_node["event_evidence_id"],
            receipt["event_evidence_id"], pass_uuid, _uuid(receipt["event_id"]), support_ids, tuple(declarations),
            pass_evidence.get("actor"), pass_evidence.get("recipient"), receipt_evidence.get("actor"),
            pass_evidence.get("outcome"), receipt_evidence.get("outcome"), "RESOLVED",
        ))
        resolutions.append(PassResolution("tip.pass_resolution", pass_node["node_id"], pass_uuid, "RESOLVED", None, edge_id))

    relations.sort(key=lambda relation: (relation.source_node_id, relation.target_node_id, relation.edge_id))
    resolutions.sort(key=lambda resolution: resolution.pass_node_id)
    if len({relation.edge_id for relation in relations}) != len(relations):
        raise SemanticResolutionError("TIP-SEM-RELATION-DUPLICATE")
    unsuccessful = sum(item.rejection_code == "TIP-SEM-PASS-OUTCOME-UNSUCCESSFUL" for item in resolutions)
    no_receipt = sum(item.rejection_code == "TIP-SEM-NO-AUTHENTICATED-RECEIPT-RELATION" for item in resolutions)
    metadata = SemanticResolutionMetadata(
        "tip.semantic_resolution_metadata", len(resolutions), len(relations), unsuccessful, no_receipt,
        len(resolutions) - len(relations) - unsuccessful - no_receipt,
    )
    dataset = SemanticResolutionDataset(
        "tip.semantic_resolution_dataset", "0.1.0", "0.1.0", action_graph.sha256, recognition.sha256,
        graph["match_id"], graph["possession_id"], RELATION_TYPES, tuple(relations), tuple(resolutions), metadata,
        {"action_graph_sha256": action_graph.sha256, "recognition_dataset_sha256": recognition.sha256},
    )
    return asdict(dataset)


def build_semantic_resolution_dataset(action_graph: Artifact, recognition: Artifact) -> Artifact:
    _validate_inputs(action_graph, recognition)
    artifact = Artifact(_build_data(action_graph, recognition), MEDIA_TYPE, action_graph.sha256, action_graph.source_hashes)
    return validate_semantic_resolution_dataset(artifact, action_graph, recognition)


def validate_semantic_resolution_dataset(semantic: Artifact, action_graph: Artifact, recognition: Artifact) -> Artifact:
    _validate_inputs(action_graph, recognition)
    if not isinstance(semantic, Artifact) or not semantic.authentic(MEDIA_TYPE, "tip.semantic_resolution_dataset"):
        raise SemanticResolutionError("TIP-SEM-INPUT-ARTIFACT-INVALID")
    if semantic.direct_input_sha256 != action_graph.sha256 or semantic.get("action_graph_sha256") != action_graph.sha256 or semantic.get("recognition_dataset_sha256") != recognition.sha256:
        raise SemanticResolutionError("TIP-SEM-INPUT-HASH-INVALID")
    data = semantic.payload
    exact = {"schema_id", "contract_version", "input_contract_version", "action_graph_sha256", "recognition_dataset_sha256", "match_id", "possession_id", "relation_types", "relations", "pass_resolutions", "metadata", "input_provenance"}
    if set(data) != exact or data.get("contract_version") != "0.1.0" or data.get("input_contract_version") != "0.1.0":
        raise SemanticResolutionError("TIP-SEM-MALFORMED-RELATION")
    relations = data.get("relations")
    if not isinstance(relations, (list, tuple)):
        raise SemanticResolutionError("TIP-SEM-MALFORMED-RELATION")
    ids = [item.get("edge_id") for item in relations if isinstance(item, dict)]
    if len(ids) != len(relations) or len(ids) != len(set(ids)):
        raise SemanticResolutionError("TIP-SEM-RELATION-DUPLICATE")
    expected = _build_data(action_graph, recognition)
    if data.get("match_id") != action_graph["match_id"] or data.get("possession_id") != action_graph["possession_id"]:
        raise SemanticResolutionError("TIP-SEM-CONTEXT-MISMATCH")
    expected_by_id = {item["edge_id"]: item for item in expected["relations"]}
    if set(ids) != set(expected_by_id):
        raise SemanticResolutionError("TIP-SEM-DEPENDENCY-INVALID")
    if list(relations) != sorted(relations, key=lambda item: (item["source_node_id"], item["target_node_id"], item["edge_id"])):
        raise SemanticResolutionError("TIP-SEM-ORDERING-INVALID")
    for relation in relations:
        required = set(PassReceiptRelation.__dataclass_fields__)
        if set(relation) != required or relation.get("relation_type") != "PASS_RECEIPT_LINK" or relation.get("resolution_status") != "RESOLVED":
            raise SemanticResolutionError("TIP-SEM-MALFORMED-RELATION")
        expected_relation = expected_by_id[relation["edge_id"]]
        if relation != expected_relation:
            if relation.get("supporting_declarations") != expected_relation["supporting_declarations"] or relation.get("supporting_source_related_edge_ids") != expected_relation["supporting_source_related_edge_ids"]:
                raise SemanticResolutionError("TIP-SEM-PROVENANCE-INVALID")
            raise SemanticResolutionError("TIP-SEM-DEPENDENCY-INVALID")
    if data != expected:
        if data.get("pass_resolutions") != expected["pass_resolutions"] or data.get("metadata") != expected["metadata"]:
            raise SemanticResolutionError("TIP-SEM-INVARIANT-VIOLATION")
        raise SemanticResolutionError("TIP-SEM-PROVENANCE-INVALID")
    return semantic.validated_copy()
