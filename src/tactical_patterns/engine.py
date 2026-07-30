from __future__ import annotations

import hashlib
from typing import Any

from src.action_continuation import validate_action_continuation_dataset
from src.action_graph.engine import validate_action_graph_dataset
from src.contracts import Artifact
from src.recognition.engine import validate_recognition_dataset
from src.semantic_resolution import validate_semantic_resolution_dataset

from .errors import TacticalPatternError


MEDIA_TYPE = "application/vnd.tip.return-combination-patterns+json"
PATTERN_TYPE = "PASS_CONTINUE_TEAMMATE_ADVANCE_RETURN_FINISH"


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()}"


def _validate_inputs(continuation: Artifact, graph: Artifact, recognition: Artifact, semantic: Artifact) -> None:
    try:
        validate_recognition_dataset(recognition)
        validate_action_graph_dataset(graph, recognition)
        validate_semantic_resolution_dataset(semantic, graph, recognition)
        validate_action_continuation_dataset(continuation, graph, recognition, semantic)
    except Exception as exc:
        raise TacticalPatternError("TIP-PAT-UPSTREAM-INVALID") from exc
    if continuation["action_graph_sha256"] != graph.sha256 or continuation["semantic_resolution_sha256"] != semantic.sha256:
        raise TacticalPatternError("TIP-PAT-UPSTREAM-HASH-INVALID")


def _action(node: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "role": role,
        "node_id": node["node_id"],
        "action_type": node["action_type"],
        "actor_id": node["actor"],
        "recognition_id": node["recognition_record_id"],
        "event_evidence_id": node["event_evidence_id"],
        "event_uuid": node["event_id"].removeprefix("event:statsbomb:"),
        "canonical_ordering_key": (node["world_state_index"], node["timestamp"], node["event_id"]),
    }


def _build_data(continuation: Artifact, graph: Artifact, recognition: Artifact, semantic: Artifact) -> dict[str, Any]:
    nodes = {node["node_id"]: node for node in graph["nodes"]}
    if len(nodes) != len(graph["nodes"]):
        raise TacticalPatternError("TIP-PAT-ENDPOINT-AMBIGUOUS")
    semantic_by_source: dict[str, list[dict[str, Any]]] = {}
    for relation in semantic["relations"]:
        semantic_by_source.setdefault(relation["source_node_id"], []).append(relation)
    continuation_by_source: dict[str, list[dict[str, Any]]] = {}
    for relation in continuation["relations"]:
        continuation_by_source.setdefault(relation["source_node_id"], []).append(relation)

    matches = []
    for initial_link in semantic["relations"]:
        initial_pass = nodes[initial_link["source_node_id"]]
        teammate_receipt = nodes[initial_link["target_node_id"]]
        initial_actor = initial_pass.get("actor")
        teammate = teammate_receipt.get("actor")
        if not initial_actor or not teammate or initial_actor == teammate:
            continue
        receipt_carries = [r for r in continuation_by_source.get(teammate_receipt["node_id"], ()) if r["source_action_type"] == "BALL_RECEIPT_EVENT" and r["target_action_type"] == "CARRY_EVENT" and not r["intervening_events"]]
        for receipt_carry in receipt_carries:
            carry = nodes[receipt_carry["target_node_id"]]
            carry_passes = [r for r in continuation_by_source.get(carry["node_id"], ()) if r["target_action_type"] == "PASS_EVENT" and not r["intervening_events"]]
            for carry_pass in carry_passes:
                return_pass = nodes[carry_pass["target_node_id"]]
                for return_link in semantic_by_source.get(return_pass["node_id"], ()):
                    return_receipt = nodes[return_link["target_node_id"]]
                    if return_receipt.get("actor") != initial_actor:
                        continue
                    continued = [r for r in continuation_by_source.get(initial_pass["node_id"], ()) if r["target_node_id"] == return_receipt["node_id"]]
                    finishes = [r for r in continuation_by_source.get(return_receipt["node_id"], ()) if r["target_action_type"] == "SHOT_EVENT" and not r["intervening_events"]]
                    if len(continued) != 1 or len(finishes) != 1:
                        continue
                    shot = nodes[finishes[0]["target_node_id"]]
                    action_nodes = (initial_pass, teammate_receipt, carry, return_pass, return_receipt, shot)
                    keys = [(n["world_state_index"], n["timestamp"], n["event_id"]) for n in action_nodes]
                    if keys != sorted(keys) or len({n["node_id"] for n in action_nodes}) != len(action_nodes):
                        continue
                    relation_ids = {
                        "initial_pass_receipt_link_id": initial_link["edge_id"],
                        "initial_actor_continuation_id": continued[0]["edge_id"],
                        "teammate_receipt_carry_continuation_id": receipt_carry["edge_id"],
                        "teammate_carry_pass_continuation_id": carry_pass["edge_id"],
                        "return_pass_receipt_link_id": return_link["edge_id"],
                        "finish_continuation_id": finishes[0]["edge_id"],
                    }
                    edge_parts = tuple(relation_ids[key] for key in sorted(relation_ids))
                    matches.append({
                        "schema_id": "tip.tactical_pattern_match",
                        "pattern_id": _id("tactical_pattern", PATTERN_TYPE, *edge_parts),
                        "pattern_type": PATTERN_TYPE,
                        "initial_actor_id": initial_actor,
                        "teammate_actor_id": teammate,
                        "actions": (
                            _action(initial_pass, "initial_pass"),
                            _action(teammate_receipt, "teammate_receipt"),
                            _action(carry, "teammate_carry"),
                            _action(return_pass, "return_pass"),
                            _action(return_receipt, "return_receipt"),
                            _action(shot, "finish"),
                        ),
                        "supporting_relations": relation_ids,
                        "resolution_status": "RESOLVED",
                    })
    matches.sort(key=lambda item: (item["actions"][0]["canonical_ordering_key"], item["pattern_id"]))
    if len({item["pattern_id"] for item in matches}) != len(matches):
        raise TacticalPatternError("TIP-PAT-DUPLICATE")
    return {
        "schema_id": "tip.tactical_pattern_dataset", "contract_version": "0.1.0",
        "pattern_definition": {
            "pattern_type": PATTERN_TYPE,
            "normative_meaning": "An authenticated pass is linked to a teammate receipt; that teammate directly receives, carries and passes; the return pass is linked to a receipt by the initial passer, whose direct next supported action is a shot.",
        },
        "match_id": graph["match_id"], "possession_id": graph["possession_id"],
        "input_hashes": {"action_graph": graph.sha256, "recognition": recognition.sha256, "semantic_resolution": semantic.sha256, "action_continuation": continuation.sha256},
        "matches": tuple(matches),
    }


def detect_return_combination_patterns(continuation: Artifact, graph: Artifact, recognition: Artifact, semantic: Artifact) -> Artifact:
    _validate_inputs(continuation, graph, recognition, semantic)
    artifact = Artifact(_build_data(continuation, graph, recognition, semantic), MEDIA_TYPE, continuation.sha256, continuation.source_hashes)
    return validate_tactical_pattern_dataset(artifact, continuation, graph, recognition, semantic)


def validate_tactical_pattern_dataset(patterns: Artifact, continuation: Artifact, graph: Artifact, recognition: Artifact, semantic: Artifact) -> Artifact:
    _validate_inputs(continuation, graph, recognition, semantic)
    if not isinstance(patterns, Artifact) or not patterns.authentic(MEDIA_TYPE, "tip.tactical_pattern_dataset") or patterns.direct_input_sha256 != continuation.sha256:
        raise TacticalPatternError("TIP-PAT-ARTIFACT-INVALID")
    expected = _build_data(continuation, graph, recognition, semantic)
    if patterns.payload != expected:
        raise TacticalPatternError("TIP-PAT-PROVENANCE-INVALID")
    return patterns.validated_copy()
