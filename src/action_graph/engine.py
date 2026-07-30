from __future__ import annotations

from dataclasses import asdict
import hashlib
from typing import Any

from src.contracts import Artifact
from src.recognition.engine import MEDIA_TYPE as RECOGNITION_MEDIA_TYPE, validate_recognition_dataset

from .errors import ActionGraphError
from .models import (
    ActionEdge,
    ActionGraphDataset,
    ActionGraphFrame,
    ActionGraphMetadata,
    ActionNode,
    ActionParticipant,
    SupportingEvidence,
)
from .registry import ACTION_TYPES, CONCEPT_TO_ACTION, RELATION_TYPES


MEDIA_TYPE = "application/vnd.tip.action-graph-dataset+json"
EVENT_ACTIONS={"SOURCE_DECLARED_PASS":"PASS_EVENT","SOURCE_DECLARED_CARRY":"CARRY_EVENT","SOURCE_DECLARED_SHOT":"SHOT_EVENT","SOURCE_DECLARED_BALL_RECEIPT":"BALL_RECEIPT_EVENT"}


def _source(record_id: str, path: str) -> dict[str, str]:
    return {"source_record_id": record_id, "source_path": f"recognition_dataset#{path}"}


def _prov(operation: str, sources: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "/value": {
            "class": "DERIVED_DETERMINISTICALLY",
            "operation": operation,
            "sources": sorted(sources, key=lambda source: (source["source_record_id"], source["source_path"])),
        }
    }


def _record_path(frame_index: int, record_index: int) -> str:
    return f"/frames/{frame_index}/records/{record_index}"


def _identifier(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()}"

def _edge_key(edge:ActionEdge|dict[str,Any])->tuple:
    get=edge.get if isinstance(edge,dict) else lambda key:getattr(edge,key)
    index=get("related_event_index")
    return (get("source_node_id"),get("relation_type"),index if index is not None else -1,get("target_node_id"),get("edge_id"))


def _node(record: dict[str, Any], frame: dict[str, Any], frame_index: int, record_index: int, evidence_by_id:dict[str,dict[str,Any]]) -> ActionNode:
    action_type = CONCEPT_TO_ACTION[record["concept_code"]]
    node_id = _identifier("action_node", record["recognition_id"], action_type)
    recognition_id = record["recognition_id"]
    source = _source(recognition_id, _record_path(frame_index, record_index))
    event_ids=tuple(record.get("supporting_event_evidence_ids",()))
    event_evidence=None
    if record["concept_code"] in EVENT_ACTIONS:
        if len(event_ids)!=1 or event_ids[0] not in evidence_by_id:raise ActionGraphError("TIP-AG-EVENT-EVIDENCE-INVALID")
        event_evidence=evidence_by_id[event_ids[0]]
    participants = tuple(
        ActionParticipant("tip.action_participant", entity_id, ordinal)
        for ordinal, entity_id in enumerate(record["participant_entity_ids"])
    )
    evidence = SupportingEvidence("tip.action_supporting_evidence", (recognition_id,))
    sources=[source]
    if event_evidence is not None:sources.append(_source(event_evidence["event_id"],f"/event_evidence/{event_evidence['_index']}"))
    return ActionNode(
        "tip.action_node",
        node_id,
        action_type,
        frame["recognition_frame_id"],
        frame["world_state_index"],
        frame["canonical_time_seconds"],
        participants,
        evidence,
        (recognition_id,),
        _prov("AG_CREATE_SOURCE_DECLARED_EVENT_NODE" if event_evidence is not None else "AG_CREATE_STATE_NODE", sources),
        recognition_id,
        event_evidence["event_id"] if event_evidence is not None else None,
        event_evidence["event_id"] if event_evidence is not None else None,
        event_evidence["event_type"] if event_evidence is not None else None,
        event_evidence["actor"] if event_evidence is not None else None,
        event_evidence["recipient"] if event_evidence is not None else None,
        event_evidence["canonical_timestamp"] if event_evidence is not None else frame["canonical_time_seconds"],
    )


def _build_data(recognition: Artifact) -> dict[str, Any]:
    data = recognition.payload
    evidence_by_id={item["event_id"]:{**item,"_index":index} for index,item in enumerate(data.get("event_evidence",()))}
    frames: list[ActionGraphFrame] = []
    nodes: list[ActionNode] = []
    nodes_by_frame: list[list[ActionNode]] = []
    for frame_index, frame in enumerate(data["frames"]):
        frame_nodes = [_node(record, frame, frame_index, record_index,evidence_by_id) for record_index, record in enumerate(frame["records"]) if record["concept_code"] in CONCEPT_TO_ACTION]
        frame_nodes.sort(key=lambda node: (node.action_type, tuple(p.entity_id for p in node.participants), node.node_id))
        nodes_by_frame.append(frame_nodes)
        nodes.extend(frame_nodes)
        frames.append(
            ActionGraphFrame(
                "tip.action_graph_frame",
                f"action_graph_frame:{frame['recognition_frame_id']}",
                frame["recognition_frame_id"],
                frame["world_state_index"],
                frame["canonical_time_seconds"],
                tuple(node.node_id for node in frame_nodes),
                _prov("AG_BUILD_FRAME", [_source(frame["recognition_frame_id"], f"/frames/{frame_index}")]),
            )
        )

    edges: list[ActionEdge] = []
    record_locations = {
        record["recognition_id"]: (frame_index, record_index)
        for frame_index, frame in enumerate(data["frames"])
        for record_index, record in enumerate(frame["records"])
    }
    recognition_record_by_id={record["recognition_id"]:record for frame in data["frames"] for record in frame["records"]}
    for frame_index in range(1, len(nodes_by_frame)):
        previous = {(node.action_type, tuple(p.entity_id for p in node.participants)): node for node in nodes_by_frame[frame_index - 1] if node.action_type not in EVENT_ACTIONS.values()}
        for target in nodes_by_frame[frame_index]:
            if target.action_type in EVENT_ACTIONS.values():
                continue
            source = previous.get((target.action_type, tuple(p.entity_id for p in target.participants)))
            if source is None:
                continue
            evidence_ids = tuple(sorted((*source.supporting_evidence.recognition_record_ids, *target.supporting_evidence.recognition_record_ids)))
            sources = []
            for recognition_id in evidence_ids:
                fi, ri = record_locations[recognition_id]
                sources.append(_source(recognition_id, _record_path(fi, ri)))
            edge_id = _identifier("action_edge", source.node_id, "STATE_CONTINUATION", target.node_id)
            edges.append(
                ActionEdge(
                    "tip.action_edge",
                    edge_id,
                    source.node_id,
                    target.node_id,
                    "STATE_CONTINUATION",
                    SupportingEvidence("tip.action_supporting_evidence", evidence_ids),
                    evidence_ids,
                    _prov("AG_LINK_ADJACENT_EQUAL_STATE", sources),
                    None,None,None,None,None,None,None,
                )
            )
    for frame_nodes in nodes_by_frame:
        pass_nodes=[node for node in frame_nodes if node.action_type=="PASS_EVENT"]
        line_nodes=[node for node in frame_nodes if node.action_type=="DEFENSIVE_LINE_STATE"]
        crossing_nodes=[node for node in frame_nodes if node.action_type=="PASS_LINE_CROSSING_FACT"]
        for crossing in crossing_nodes:
            crossing_record=recognition_record_by_id[crossing.recognition_record_id]
            participants=tuple(p.entity_id for p in crossing.participants)
            source=next((node for node in pass_nodes if tuple(p.entity_id for p in node.participants)==participants[:2]),None)
            target=next((node for node in line_nodes if tuple(p.entity_id for p in node.participants)==participants[2:]),None)
            if source is None or target is None:raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
            evidence_ids=tuple(sorted((source.recognition_record_id,target.recognition_record_id,crossing.recognition_record_id)))
            sources=[_source(rid,_record_path(*record_locations[rid])) for rid in evidence_ids]
            edges.append(ActionEdge("tip.action_edge",_identifier("action_edge",source.node_id,"PASS_CROSSES_DEFENSIVE_LINE",target.node_id),
                source.node_id,target.node_id,"PASS_CROSSES_DEFENSIVE_LINE",SupportingEvidence("tip.action_supporting_evidence",evidence_ids),
                evidence_ids,_prov("AG_LINK_AUTHENTICATED_PASS_LINE_CROSSING",sources),source.recognition_record_id,
                target.recognition_record_id,source.event_evidence_id,None,None,None,None,
                tuple(sorted(fid for fid in crossing_record["supporting_feature_ids"]
                    if ":pass_start_position:" in fid or ":pass_end_position:" in fid))))
    event_nodes=sorted((node for node in nodes if node.action_type in EVENT_ACTIONS.values()),key=lambda node:(node.timestamp,node.world_state_index,node.event_id or "",node.node_id))
    for index,source in enumerate(event_nodes):
        if not isinstance(source.timestamp,(int,float)):
            continue
        target=next((candidate for candidate in event_nodes[index+1:] if isinstance(candidate.timestamp,(int,float)) and candidate.timestamp>source.timestamp),None)
        if target is None:
            continue
        evidence_ids=tuple(sorted((source.recognition_record_id,target.recognition_record_id)));sources=[]
        for node in (source,target):
            fi,ri=record_locations[node.recognition_record_id]
            sources.append(_source(node.recognition_record_id,_record_path(fi,ri)))
            sources.append(_source(node.event_evidence_id or "",f"/event_evidence/{fi}"))
        edges.append(ActionEdge("tip.action_edge",_identifier("action_edge",source.node_id,"TEMPORAL_SUCCESSION",target.node_id),source.node_id,target.node_id,"TEMPORAL_SUCCESSION",SupportingEvidence("tip.action_supporting_evidence",evidence_ids),evidence_ids,_prov("AG_LINK_AUTHENTICATED_TEMPORAL_SUCCESSION",sources),None,None,None,None,None,None,None))
    event_node_by_source_id:dict[str,list[ActionNode]]={}
    for node in event_nodes:
        source_id=(node.event_id or "").removeprefix("event:statsbomb:")
        event_node_by_source_id.setdefault(source_id,[]).append(node)
    for source in event_nodes:
        source_evidence=evidence_by_id.get(source.event_evidence_id or "")
        if source_evidence is None:raise ActionGraphError("TIP-AG-EVENT-EVIDENCE-INVALID")
        related_provenance=source_evidence.get("authenticated_provenance",{}).get("/related_event_ids")
        if not isinstance(related_provenance,dict) or not related_provenance.get("sources"):raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        for related_index,related_id in enumerate(source_evidence.get("related_event_ids",())):
            targets=event_node_by_source_id.get(related_id,[])
            if not targets:
                continue
            if len(targets)!=1:raise ActionGraphError("TIP-AG-EVENT-EVIDENCE-INVALID")
            target=targets[0];evidence_ids=tuple(sorted((source.recognition_record_id,target.recognition_record_id)))
            sources=[_source(source.recognition_record_id,_record_path(*record_locations[source.recognition_record_id])),_source(target.recognition_record_id,_record_path(*record_locations[target.recognition_record_id])),_source(source.event_evidence_id or "",f"/event_evidence/{source_evidence['_index']}/related_event_ids")]
            edges.append(ActionEdge("tip.action_edge",_identifier("action_edge",source.node_id,"SOURCE_RELATED_EVENT",str(related_index),target.node_id),source.node_id,target.node_id,"SOURCE_RELATED_EVENT",SupportingEvidence("tip.action_supporting_evidence",evidence_ids),evidence_ids,_prov("AG_PRESERVE_SOURCE_RELATED_EVENT",sources),source.recognition_record_id,target.recognition_record_id,source.event_evidence_id,target.event_evidence_id,related_id,related_index,related_provenance))
    edges.sort(key=_edge_key)
    metadata = ActionGraphMetadata(
        "tip.action_graph_metadata",
        "0.1.0",
        "0.1.0",
        len(frames),
        len(nodes),
        len(edges),
        _prov("AG_BUILD_METADATA", [_source(data["match_id"], "")]),
    )
    dataset = ActionGraphDataset(
        "tip.action_graph_dataset",
        "0.1.0",
        "0.1.0",
        recognition.sha256,
        data["match_id"],
        data["possession_id"],
        ACTION_TYPES,
        RELATION_TYPES,
        tuple(frames),
        tuple(nodes),
        tuple(edges),
        metadata,
        {"input_provenance": data["input_provenance"], "recognition_provenance": data["recognition_provenance"]},
        _prov("AG_BUILD_DATASET", [_source(data["match_id"], "")]),
    )
    return asdict(dataset)


def _validate_recognition_input(recognition: Artifact) -> None:
    if not isinstance(recognition, Artifact) or not recognition.validated or not recognition.authentic(RECOGNITION_MEDIA_TYPE, "tip.recognition_dataset"):
        raise ActionGraphError("TIP-AG-INPUT-ARTIFACT-INVALID")
    if recognition.get("contract_version") != "0.1.0":
        raise ActionGraphError("TIP-AG-INPUT-VERSION-UNSUPPORTED")
    if recognition.get("perception_dataset_sha256") != recognition.direct_input_sha256:
        raise ActionGraphError("TIP-AG-INPUT-HASH-INVALID")
    try:
        validate_recognition_dataset(recognition)
    except Exception as exc:
        raise ActionGraphError("TIP-AG-INPUT-SCHEMA-INVALID") from exc


def build_action_graph_dataset(recognition: Artifact) -> Artifact:
    _validate_recognition_input(recognition)
    artifact = Artifact(_build_data(recognition), MEDIA_TYPE, recognition.sha256, recognition.source_hashes)
    return validate_action_graph_dataset(artifact, recognition)


def validate_action_graph_dataset(action_graph: Artifact, recognition: Artifact) -> Artifact:
    _validate_recognition_input(recognition)
    if not isinstance(action_graph, Artifact) or not action_graph.authentic(MEDIA_TYPE, "tip.action_graph_dataset"):
        raise ActionGraphError("TIP-AG-INPUT-ARTIFACT-INVALID")
    if action_graph.get("contract_version") != "0.1.0" or action_graph.get("input_contract_version") != "0.1.0":
        raise ActionGraphError("TIP-AG-INPUT-VERSION-UNSUPPORTED")
    if action_graph.direct_input_sha256 != recognition.sha256 or action_graph.get("recognition_dataset_sha256") != recognition.sha256:
        raise ActionGraphError("TIP-AG-INPUT-HASH-INVALID")

    data = action_graph.payload
    exact_fields = {
        "schema_id", "contract_version", "input_contract_version", "recognition_dataset_sha256", "match_id",
        "possession_id", "action_types", "relation_types", "frames", "nodes", "edges", "metadata",
        "input_provenance", "action_graph_provenance",
    }
    if set(data) != exact_fields:
        raise ActionGraphError("TIP-AG-INPUT-SCHEMA-INVALID")
    expected_actions = tuple(asdict(item) for item in ACTION_TYPES)
    expected_relations = tuple(asdict(item) for item in RELATION_TYPES)
    if data.get("action_types") != expected_actions:
        raise ActionGraphError("TIP-AG-ACTION-TYPE-INVALID")
    if data.get("relation_types") != expected_relations:
        raise ActionGraphError("TIP-AG-RELATION-TYPE-INVALID")

    recognition_data = recognition.payload
    recognition_frames = {frame["recognition_frame_id"]: frame for frame in recognition_data["frames"]}
    recognition_records = {
        record["recognition_id"]: (frame, record)
        for frame in recognition_data["frames"]
        for record in frame["records"]
    }
    expected_data = _build_data(recognition)
    expected_nodes = {node["node_id"]: node for node in expected_data["nodes"]}
    expected_edges = {edge["edge_id"]: edge for edge in expected_data["edges"]}
    expected_frames = {frame["recognition_frame_id"]: frame for frame in expected_data["frames"]}
    if data.get("match_id") != recognition_data["match_id"] or data.get("possession_id") != recognition_data["possession_id"]:
        raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
    frames = data.get("frames", [])
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if [frame.get("world_state_index") for frame in frames] != list(range(len(frames))):
        raise ActionGraphError("TIP-AG-ORDERING-INVALID")
    previous_time = None
    for frame in frames:
        if set(frame) != {"schema_id", "action_graph_frame_id", "recognition_frame_id", "world_state_index", "canonical_time_seconds", "node_ids", "action_graph_provenance"} or frame.get("schema_id") != "tip.action_graph_frame":
            raise ActionGraphError("TIP-AG-INPUT-SCHEMA-INVALID")
        timestamp = frame.get("canonical_time_seconds")
        upstream = recognition_frames.get(frame.get("recognition_frame_id"))
        if upstream is None:
            raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        if not isinstance(timestamp, (int, float)) or timestamp != upstream["canonical_time_seconds"] or (previous_time is not None and timestamp < previous_time):
            raise ActionGraphError("TIP-AG-TIMESTAMP-INVALID")
        expected_frame = expected_frames[frame["recognition_frame_id"]]
        if frame.get("action_graph_frame_id") != expected_frame["action_graph_frame_id"] or tuple(frame.get("node_ids", [])) != tuple(expected_frame["node_ids"]):
            raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        if frame.get("action_graph_provenance") != expected_frame["action_graph_provenance"]:
            raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        previous_time = timestamp

    node_ids = [node.get("node_id") for node in nodes]
    if None in node_ids or len(node_ids) != len(set(node_ids)):
        raise ActionGraphError("TIP-AG-NODE-DUPLICATE")
    if set(node_ids) != set(expected_nodes):
        raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
    node_by_id = {node["node_id"]: node for node in nodes}
    node_keys = [(node["world_state_index"], node["action_type"], tuple(p["entity_id"] for p in node["participants"]), node["node_id"]) for node in nodes]
    if node_keys != sorted(node_keys):
        raise ActionGraphError("TIP-AG-ORDERING-INVALID")
    allowed_actions = set(CONCEPT_TO_ACTION.values())
    for node in nodes:
        if set(node) != {"schema_id", "node_id", "action_type", "recognition_frame_id", "world_state_index", "canonical_time_seconds", "participants", "supporting_evidence", "provenance_record_ids", "action_graph_provenance", "recognition_record_id", "event_evidence_id", "event_id", "event_type", "actor", "recipient", "timestamp"} or node.get("schema_id") != "tip.action_node":
            raise ActionGraphError("TIP-AG-INPUT-SCHEMA-INVALID")
        if node.get("action_type") not in allowed_actions:
            raise ActionGraphError("TIP-AG-ACTION-TYPE-INVALID")
        evidence = tuple(node.get("supporting_evidence", {}).get("recognition_record_ids", []))
        if not evidence or evidence != tuple(node.get("provenance_record_ids", [])):
            raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        if any(record_id not in recognition_records for record_id in evidence):
            raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        if len(evidence) != 1:
            raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        frame, record = recognition_records[evidence[0]]
        if node.get("recognition_record_id")!=evidence[0]:raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        participants = node.get("participants", [])
        if any(set(participant) != {"schema_id", "entity_id", "ordinal"} or participant.get("schema_id") != "tip.action_participant" for participant in participants):
            raise ActionGraphError("TIP-AG-INPUT-SCHEMA-INVALID")
        if [p.get("ordinal") for p in participants] != list(range(len(participants))) or tuple(p.get("entity_id") for p in participants) != tuple(record["participant_entity_ids"]):
            raise ActionGraphError("TIP-AG-PARTICIPANT-INVALID")
        if node["action_type"] != CONCEPT_TO_ACTION.get(record["concept_code"]):
            raise ActionGraphError("TIP-AG-ACTION-TYPE-INVALID")
        if node.get("canonical_time_seconds")!=frame["canonical_time_seconds"] or node.get("timestamp")!=node.get("canonical_time_seconds"):raise ActionGraphError("TIP-AG-TIMESTAMP-INVALID")
        if node["action_type"] in EVENT_ACTIONS.values():
            event_ids=tuple(record.get("supporting_event_evidence_ids",()))
            evidence_items=[item for item in recognition_data.get("event_evidence",()) if item["event_id"] in event_ids]
            if len(event_ids)!=1 or len(evidence_items)!=1:raise ActionGraphError("TIP-AG-EVENT-EVIDENCE-INVALID")
            event_item=evidence_items[0]
            if (node.get("event_evidence_id"),node.get("event_id"),node.get("event_type"),node.get("actor"),node.get("recipient"),node.get("timestamp"))!=(event_item["event_id"],event_item["event_id"],event_item["event_type"],event_item["actor"],event_item["recipient"],event_item["canonical_timestamp"]):raise ActionGraphError("TIP-AG-EVENT-EVIDENCE-INVALID")
            provenance=event_item.get("authenticated_provenance",{})
            if not provenance or any(not value.get("sources") for value in provenance.values()):raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        elif any(node.get(field) is not None for field in ("event_evidence_id","event_id","event_type","actor","recipient")):raise ActionGraphError("TIP-AG-EVENT-EVIDENCE-INVALID")
        if node.get("recognition_frame_id") != frame["recognition_frame_id"] or node.get("world_state_index") != frame["world_state_index"]:
            raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        expected_node = expected_nodes.get(node["node_id"])
        if expected_node is None:
            raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        if node.get("action_graph_provenance") != expected_node["action_graph_provenance"]:
            raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")

    frame_node_ids = [node_id for frame in frames for node_id in frame.get("node_ids", [])]
    if sorted(frame_node_ids) != sorted(node_ids) or len(frame_node_ids) != len(set(frame_node_ids)):
        raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")

    edge_ids = [edge.get("edge_id") for edge in edges]
    if None in edge_ids or len(edge_ids) != len(set(edge_ids)):
        raise ActionGraphError("TIP-AG-EDGE-DUPLICATE")
    if set(edge_ids) != set(expected_edges):
        raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
    for edge in edges:
        if set(edge) != {"schema_id", "edge_id", "source_node_id", "target_node_id", "relation_type", "supporting_evidence", "provenance_record_ids", "action_graph_provenance", "source_recognition_record_id", "target_recognition_record_id", "source_event_evidence_id", "target_event_evidence_id", "related_event_id", "related_event_index", "related_event_provenance","endpoint_feature_ids"} or edge.get("schema_id") != "tip.action_edge":
            raise ActionGraphError("TIP-AG-INPUT-SCHEMA-INVALID")
        if edge.get("relation_type") not in {"STATE_CONTINUATION","TEMPORAL_SUCCESSION","SOURCE_RELATED_EVENT","PASS_CROSSES_DEFENSIVE_LINE"}:
            raise ActionGraphError("TIP-AG-RELATION-TYPE-INVALID")
        if edge.get("source_node_id") not in node_by_id or edge.get("target_node_id") not in node_by_id:
            raise ActionGraphError("TIP-AG-EDGE-ENDPOINT-INVALID")
        source, target = node_by_id[edge["source_node_id"]], node_by_id[edge["target_node_id"]]
        if edge["relation_type"]=="STATE_CONTINUATION":
            if target["world_state_index"] != source["world_state_index"] + 1 or source["action_type"] != target["action_type"] or source["participants"] != target["participants"]:raise ActionGraphError("TIP-AG-RELATION-TYPE-INVALID")
        elif edge["relation_type"]=="TEMPORAL_SUCCESSION":
            if source["action_type"] not in EVENT_ACTIONS.values() or target["action_type"] not in EVENT_ACTIONS.values():raise ActionGraphError("TIP-AG-RELATION-TYPE-INVALID")
            if not isinstance(source.get("timestamp"),(int,float)) or not isinstance(target.get("timestamp"),(int,float)) or target["timestamp"]<=source["timestamp"]:raise ActionGraphError("TIP-AG-TIMESTAMP-INVALID")
        elif edge["relation_type"]=="SOURCE_RELATED_EVENT":
            if source["action_type"] not in EVENT_ACTIONS.values() or target["action_type"] not in EVENT_ACTIONS.values():raise ActionGraphError("TIP-AG-RELATION-TYPE-INVALID")
            source_evidence=next((item for item in recognition_data.get("event_evidence",()) if item["event_id"]==source["event_evidence_id"]),None)
            target_evidence=next((item for item in recognition_data.get("event_evidence",()) if item["event_id"]==target["event_evidence_id"]),None)
            index=edge.get("related_event_index");related=edge.get("related_event_id")
            if source_evidence is None or target_evidence is None or not isinstance(index,int) or index<0 or index>=len(source_evidence["related_event_ids"]) or source_evidence["related_event_ids"][index]!=related or target_evidence["event_id"].removeprefix("event:statsbomb:")!=related:raise ActionGraphError("TIP-AG-EVENT-EVIDENCE-INVALID")
            if (edge.get("source_recognition_record_id"),edge.get("target_recognition_record_id"),edge.get("source_event_evidence_id"),edge.get("target_event_evidence_id"))!=(source["recognition_record_id"],target["recognition_record_id"],source["event_evidence_id"],target["event_evidence_id"]):raise ActionGraphError("TIP-AG-EVENT-EVIDENCE-INVALID")
            expected_related_provenance=source_evidence["authenticated_provenance"]["/related_event_ids"]
            if edge.get("related_event_provenance")!=expected_related_provenance or not expected_related_provenance.get("sources"):raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        else:
            if source["action_type"]!="PASS_EVENT" or target["action_type"]!="DEFENSIVE_LINE_STATE":raise ActionGraphError("TIP-AG-RELATION-TYPE-INVALID")
            crossing_records=[record for _,record in recognition_records.values()
                if record["concept_code"]=="PASS_CROSSES_DEFENSIVE_LINE"
                and tuple(record["participant_entity_ids"])==tuple([p["entity_id"] for p in source["participants"]]+[p["entity_id"] for p in target["participants"]])]
            if len(crossing_records)!=1:raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
            crossing_record=crossing_records[0]
            if tuple(crossing_record.get("supporting_event_evidence_ids",()))!=(source["event_evidence_id"],):raise ActionGraphError("TIP-AG-EVENT-EVIDENCE-INVALID")
            expected_endpoints=tuple(sorted(fid for fid in crossing_record["supporting_feature_ids"] if ":pass_start_position:" in fid or ":pass_end_position:" in fid))
            if len(expected_endpoints)!=2 or tuple(edge.get("endpoint_feature_ids",()))!=expected_endpoints:raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
            if edge.get("source_recognition_record_id")!=source["recognition_record_id"] or edge.get("target_recognition_record_id")!=target["recognition_record_id"]:raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        if edge["relation_type"]!="PASS_CROSSES_DEFENSIVE_LINE" and edge.get("endpoint_feature_ids"):raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        evidence = tuple(edge.get("supporting_evidence", {}).get("recognition_record_ids", []))
        expected_evidence = tuple(sorted((*source["supporting_evidence"]["recognition_record_ids"], *target["supporting_evidence"]["recognition_record_ids"],
            *((crossing_record["recognition_id"],) if edge["relation_type"]=="PASS_CROSSES_DEFENSIVE_LINE" else ()))))
        if evidence != expected_evidence or evidence != tuple(edge.get("provenance_record_ids", [])):
            raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        expected_edge = expected_edges.get(edge["edge_id"])
        if expected_edge is None:
            raise ActionGraphError("TIP-AG-DEPENDENCY-INVALID")
        if edge.get("action_graph_provenance") != expected_edge["action_graph_provenance"]:
            raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        if edge["relation_type"]=="TEMPORAL_SUCCESSION":
            prov=edge.get("action_graph_provenance",{}).get("/value",{})
            if prov.get("operation")!="AG_LINK_AUTHENTICATED_TEMPORAL_SUCCESSION" or len(prov.get("sources",[]))!=4:raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        elif edge["relation_type"]=="SOURCE_RELATED_EVENT":
            prov=edge.get("action_graph_provenance",{}).get("/value",{})
            if prov.get("operation")!="AG_PRESERVE_SOURCE_RELATED_EVENT" or len(prov.get("sources",[]))!=3:raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        elif edge["relation_type"]=="PASS_CROSSES_DEFENSIVE_LINE":
            prov=edge.get("action_graph_provenance",{}).get("/value",{})
            if prov.get("operation")!="AG_LINK_AUTHENTICATED_PASS_LINE_CROSSING" or len(prov.get("sources",[]))!=3:raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")

    edge_keys = [_edge_key(edge) for edge in edges]
    if edge_keys != sorted(edge_keys):
        raise ActionGraphError("TIP-AG-ORDERING-INVALID")

    metadata = data.get("metadata", {})
    if (metadata.get("frame_count"), metadata.get("node_count"), metadata.get("edge_count")) != (len(frames), len(nodes), len(edges)):
        raise ActionGraphError("TIP-AG-INVARIANT-VIOLATION")
    if metadata != expected_data["metadata"]:
        if metadata.get("action_graph_provenance") != expected_data["metadata"]["action_graph_provenance"]:
            raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
        raise ActionGraphError("TIP-AG-INVARIANT-VIOLATION")
    if data.get("input_provenance") != expected_data["input_provenance"] or data.get("action_graph_provenance") != expected_data["action_graph_provenance"]:
        raise ActionGraphError("TIP-AG-PROVENANCE-INVALID")
    return action_graph.validated_copy()
