from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Any

from src.action_graph import validate_action_graph_dataset
from src.contracts import Artifact
from src.recognition import validate_recognition_dataset

from .errors import GraphBackedTacticalEpisodeError
from .models import EpisodeDecision, GraphBackedEpisode


MEDIA_TYPE = "application/vnd.tip.graph-backed-tactical-episodes+json"
CONTRACT_VERSION = "0.1.0"
RETURN_PATTERN_TYPE = "PASS_CONTINUE_TEAMMATE_ADVANCE_RETURN_FINISH"
EVENT_ACTION_TYPES = frozenset({"PASS_EVENT", "BALL_RECEIPT_EVENT", "CARRY_EVENT", "SHOT_EVENT"})

_LINE_BREAK_UNSUPPORTED = "No complete authenticated defensive-line crossing and successful reception path is present."


def _identifier(episode_type: str, node_ids: tuple[str, ...], relation_ids: tuple[str, ...]) -> str:
    payload = "\x1f".join((episode_type, *node_ids, *relation_ids))
    return f"graph_episode:{hashlib.sha256(payload.encode()).hexdigest()}"


def _ordering_key(node: dict[str, Any]) -> tuple[int, float, str]:
    return (
        int(node["world_state_index"]),
        float(node["canonical_time_seconds"]),
        str(node.get("event_id") or node["node_id"]),
    )


def _event_nodes(graph: Artifact) -> dict[str, dict[str, Any]]:
    return {
        node["node_id"]: node
        for node in graph["nodes"]
        if node["action_type"] in EVENT_ACTION_TYPES and node.get("event_evidence_id")
    }


def _recognition_index(recognition: Artifact) -> dict[str, dict[str, Any]]:
    return {
        record["recognition_id"]: record
        for frame in recognition["frames"]
        for record in frame["records"]
    }


def _episode(
    episode_type: str,
    nodes: tuple[dict[str, Any], ...],
    relation_ids: tuple[str, ...],
    recognition_by_id: dict[str, dict[str, Any]],
    summary: str,
    confidence: float,
    limitations: tuple[str, ...] = (),
    additional_recognition_ids: tuple[str, ...] = (),
) -> GraphBackedEpisode:
    ordered_nodes = tuple(sorted(nodes, key=_ordering_key))
    node_ids = tuple(node["node_id"] for node in ordered_nodes)
    relation_ids = tuple(sorted(dict.fromkeys(relation_ids)))
    event_ids = tuple(
        dict.fromkeys(str(node["event_evidence_id"]) for node in ordered_nodes if node.get("event_evidence_id"))
    )
    actors = tuple(dict.fromkeys(str(node["actor"]) for node in ordered_nodes if node.get("actor")))
    recipients = tuple(
        dict.fromkeys(str(node["recipient"]) for node in ordered_nodes if node.get("recipient"))
    )
    recognition_ids = tuple(dict.fromkeys((*(
        str(node["recognition_record_id"]) for node in ordered_nodes
    ),*additional_recognition_ids)))
    feature_ids = tuple(
        sorted(
            {
                str(feature_id)
                for recognition_id in recognition_ids
                for feature_id in recognition_by_id.get(recognition_id, {}).get("supporting_feature_ids", ())
            }
        )
    )
    return GraphBackedEpisode(
        episode_id=_identifier(episode_type, node_ids, relation_ids),
        episode_type=episode_type,
        start_ordering_key=_ordering_key(ordered_nodes[0]),
        end_ordering_key=_ordering_key(ordered_nodes[-1]),
        supporting_action_node_ids=node_ids,
        supporting_relation_ids=relation_ids,
        authenticated_source_event_ids=event_ids,
        primary_actor_ids=actors,
        relevant_participant_ids=tuple(participant for participant in recipients if participant not in actors),
        recognition_record_ids=recognition_ids,
        perception_feature_ids=feature_ids,
        confidence=confidence,
        limitations=limitations,
        causal_evidence_summary=summary,
        temporal_context_node_ids=(),
    )

def _line_break_episodes(graph:Artifact,recognition:Artifact,recognition_by_id:dict[str,dict[str,Any]])->tuple[list[GraphBackedEpisode],list[EpisodeDecision]]:
    nodes={node["node_id"]:node for node in graph["nodes"]}
    evidence={item["event_id"]:item for item in recognition["event_evidence"]}
    crossing_edges=[edge for edge in graph["edges"] if edge["relation_type"]=="PASS_CROSSES_DEFENSIVE_LINE"]
    related_edges=[edge for edge in graph["edges"] if edge["relation_type"]=="SOURCE_RELATED_EVENT"]
    episodes=[];decisions=[];seen=set()
    for crossing in crossing_edges:
        pass_node=nodes[crossing["source_node_id"]];line_node=nodes[crossing["target_node_id"]]
        pass_evidence=evidence.get(pass_node.get("event_evidence_id"))
        if not pass_evidence or pass_evidence.get("outcome")!="COMPLETED":
            decisions.append(EpisodeDecision("LINE_BREAK","REJECTED",("Authenticated pass is incomplete.",),(pass_node["node_id"],line_node["node_id"])))
            continue
        receipts=[]
        for edge in related_edges:
            if edge["source_node_id"]!=pass_node["node_id"]:continue
            candidate=nodes[edge["target_node_id"]]
            if candidate["action_type"]=="BALL_RECEIPT_EVENT" and candidate.get("actor")==pass_node.get("recipient") and candidate.get("timestamp")>pass_node.get("timestamp"):
                receipts.append((candidate,edge))
        if not receipts:
            decisions.append(EpisodeDecision("LINE_BREAK","WARN",("Line crossing is authenticated, but subsequent receiver control is not.",),(pass_node["node_id"],line_node["node_id"])))
            continue
        receipt,receipt_edge=min(receipts,key=lambda item:_ordering_key(item[0]))
        signature=(pass_node["node_id"],line_node["node_id"],receipt["node_id"])
        if signature in seen:
            decisions.append(EpisodeDecision("LINE_BREAK","REJECTED_DUPLICATE",("Duplicate authenticated causal path.",),signature));continue
        seen.add(signature)
        crossing_recognition=tuple(rid for rid in crossing["supporting_evidence"]["recognition_record_ids"] if recognition_by_id.get(rid,{}).get("concept_code")=="PASS_CROSSES_DEFENSIVE_LINE")
        episodes.append(_episode("LINE_BREAK",(pass_node,line_node,receipt),(crossing["edge_id"],receipt_edge["edge_id"]),recognition_by_id,
            "A recognized defensive line, authenticated pass-line crossing, completed pass, and subsequent receiver control form one causal path.",
            1.0,("Defensive-line recognition is observation-scoped and does not claim the entire defensive block.",),crossing_recognition))
        decisions.append(EpisodeDecision("LINE_BREAK","SELECTED",("Complete authenticated line-break causal path.",),signature))
    if not crossing_edges:decisions.append(EpisodeDecision("LINE_BREAK","UNSUPPORTED",(_LINE_BREAK_UNSUPPORTED,)))
    return episodes,decisions


def _return_episodes(
    graph: Artifact,
    recognition_by_id: dict[str, dict[str, Any]],
    patterns: Artifact | None,
) -> tuple[list[GraphBackedEpisode], list[EpisodeDecision]]:
    if patterns is None:
        return [], [
            EpisodeDecision(
                "RETURN_COMBINATION",
                "UNSUPPORTED",
                ("No validated authenticated return-combination pattern artifact was supplied.",),
            )
        ]
    if not patterns.validated or patterns.get("schema_id") != "tip.tactical_pattern_dataset":
        raise GraphBackedTacticalEpisodeError("TIP-GTE-PATTERN-ARTIFACT-INVALID")
    expected_hash = patterns.get("input_hashes", {}).get("action_graph")
    if expected_hash != graph.sha256 or patterns.get("pattern_definition", {}).get("pattern_type") != RETURN_PATTERN_TYPE:
        raise GraphBackedTacticalEpisodeError("TIP-GTE-PATTERN-ARTIFACT-INVALID")

    nodes_by_id = _event_nodes(graph)
    episodes: list[GraphBackedEpisode] = []
    decisions: list[EpisodeDecision] = []
    seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    claimed_nodes: set[str] = set()
    for match in patterns["matches"]:
        node_ids = tuple(action["node_id"] for action in match["actions"])
        relation_ids = tuple(match["supporting_relations"][key] for key in sorted(match["supporting_relations"]))
        signature = (node_ids, tuple(sorted(relation_ids)))
        if signature in seen:
            decisions.append(EpisodeDecision("RETURN_COMBINATION", "REJECTED_DUPLICATE", ("Duplicate causal path.",), node_ids))
            continue
        seen.add(signature)
        if claimed_nodes.intersection(node_ids):
            decisions.append(
                EpisodeDecision(
                    "RETURN_COMBINATION",
                    "REJECTED_CONTRADICTORY_OVERLAP",
                    ("A different selected return-combination path already claims one or more causal action nodes.",),
                    node_ids,
                )
            )
            continue
        if any(node_id not in nodes_by_id for node_id in node_ids):
            decisions.append(EpisodeDecision("RETURN_COMBINATION", "REJECTED", ("Causal path references an unavailable authenticated action node.",), node_ids))
            continue
        if any(not relation_id for relation_id in relation_ids):
            decisions.append(EpisodeDecision("RETURN_COMBINATION", "REJECTED", ("Causal path contains an empty relation reference.",), node_ids))
            continue
        graph_relation_ids = tuple(
            edge["edge_id"]
            for edge in graph["edges"]
            if edge["source_node_id"] in node_ids and edge["target_node_id"] in node_ids
        )
        episodes.append(
            _episode(
                "RETURN_COMBINATION",
                tuple(nodes_by_id[node_id] for node_id in node_ids),
                (*relation_ids, *graph_relation_ids),
                recognition_by_id,
                "Authenticated pass-to-receipt and continuation relations support a pass, teammate advance, return, renewed involvement, and shot.",
                1.0,
            )
        )
        claimed_nodes.update(node_ids)
        decisions.append(EpisodeDecision("RETURN_COMBINATION", "SELECTED", ("Complete authenticated return-combination causal path.",), node_ids))
    if not patterns["matches"]:
        decisions.append(EpisodeDecision("RETURN_COMBINATION", "UNSUPPORTED", ("No complete authenticated return-combination path was recognized.",)))
    return episodes, decisions


def build_graph_backed_tactical_episode_dataset(
    recognition: Artifact,
    graph: Artifact,
    patterns: Artifact | None = None,
) -> Artifact:
    try:
        validate_recognition_dataset(recognition)
        validate_action_graph_dataset(graph, recognition)
    except Exception as exc:
        raise GraphBackedTacticalEpisodeError("TIP-GTE-UPSTREAM-INVALID") from exc

    recognition_by_id = _recognition_index(recognition)
    event_nodes = _event_nodes(graph)
    return_episodes, decisions = _return_episodes(graph, recognition_by_id, patterns)
    episodes = list(return_episodes)
    line_breaks,line_decisions=_line_break_episodes(graph,recognition,recognition_by_id)
    episodes.extend(line_breaks);decisions.extend(line_decisions)

    shot_nodes = sorted(
        (node for node in event_nodes.values() if node["action_type"] == "SHOT_EVENT"),
        key=_ordering_key,
    )
    for shot in shot_nodes:
        incident_relation_ids = tuple(
            edge["edge_id"]
            for edge in graph["edges"]
            if shot["node_id"] in (edge["source_node_id"], edge["target_node_id"])
        )
        episodes.append(
            _episode(
                "FINISH",
                (shot,),
                incident_relation_ids,
                recognition_by_id,
                "Authenticated source-declared shot action.",
                1.0,
                ("This is a factual finish episode; no additional tactical mechanism is inferred.",),
            )
        )
        decisions.append(EpisodeDecision("FINISH", "SELECTED", ("Authenticated SHOT_EVENT is always retained.",), (shot["node_id"],)))
    if not shot_nodes:
        decisions.append(EpisodeDecision("FINISH", "UNSUPPORTED", ("No authenticated SHOT_EVENT is present.",)))

    unique: dict[tuple[str, tuple[str, ...]], GraphBackedEpisode] = {}
    for episode in episodes:
        key = (episode.episode_type, episode.supporting_action_node_ids)
        unique.setdefault(key, episode)
    episodes = sorted(unique.values(), key=lambda item: (item.start_ordering_key, item.end_ordering_key, item.episode_type, item.episode_id))

    data = {
        "schema_id": "tip.graph_backed_tactical_episode_dataset",
        "contract_version": CONTRACT_VERSION,
        "recognition_dataset_sha256": recognition.sha256,
        "action_graph_sha256": graph.sha256,
        "pattern_dataset_sha256": patterns.sha256 if patterns is not None else None,
        "match_id": graph["match_id"],
        "possession_id": graph["possession_id"],
        "episodes": tuple(asdict(episode) for episode in episodes),
        "decisions": tuple(asdict(decision) for decision in decisions),
        "selection_policy": "AUTHENTICATED_CAUSAL_EVIDENCE_THEN_CANONICAL_ORDER;SUPPORTED_FINISH_ALWAYS_RETAINED",
        "line_break_evidence_policy": {
            "PASS": "Recognized defensive-line state plus authenticated crossing relation, completed pass, and subsequent receiver control.",
            "WARN": "Possible corridor or crossing with insufficient proof of subsequent receiver control; no episode is emitted.",
            "UNSUPPORTED": "No recognized defensive line, unsupported crossing relation, or incomplete perception.",
        },
    }
    return Artifact(data, MEDIA_TYPE, graph.sha256, graph.source_hashes, validated=True)


def validate_graph_backed_tactical_episode_dataset(
    dataset: Artifact,
    recognition: Artifact,
    graph: Artifact,
    patterns: Artifact | None = None,
) -> Artifact:
    if not isinstance(dataset, Artifact) or not dataset.authentic(MEDIA_TYPE, "tip.graph_backed_tactical_episode_dataset"):
        raise GraphBackedTacticalEpisodeError("TIP-GTE-ARTIFACT-INVALID")
    expected = build_graph_backed_tactical_episode_dataset(recognition, graph, patterns)
    if dataset.payload != expected.payload:
        raise GraphBackedTacticalEpisodeError("TIP-GTE-PROVENANCE-INVALID")
    return dataset.validated_copy()
