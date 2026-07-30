from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ActionGraphProvenance = dict[str, dict[str, Any]]


@dataclass(frozen=True)
class ActionTypeDefinition:
    schema_id: str
    action_type: str
    supporting_concept_code: str
    participant_scope: str
    definition_version: str
    action_graph_provenance: ActionGraphProvenance


@dataclass(frozen=True)
class ActionRelationDefinition:
    schema_id: str
    relation_type: str
    definition_version: str
    action_graph_provenance: ActionGraphProvenance


@dataclass(frozen=True)
class ActionParticipant:
    schema_id: str
    entity_id: str
    ordinal: int


@dataclass(frozen=True)
class SupportingEvidence:
    schema_id: str
    recognition_record_ids: tuple[str, ...]


@dataclass(frozen=True)
class ActionNode:
    schema_id: str
    node_id: str
    action_type: str
    recognition_frame_id: str
    world_state_index: int
    canonical_time_seconds: float
    participants: tuple[ActionParticipant, ...]
    supporting_evidence: SupportingEvidence
    provenance_record_ids: tuple[str, ...]
    action_graph_provenance: ActionGraphProvenance
    recognition_record_id: str
    event_evidence_id: str | None
    event_id: str | None
    event_type: str | None
    actor: str | None
    recipient: str | None
    timestamp: float


@dataclass(frozen=True)
class ActionEdge:
    schema_id: str
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    supporting_evidence: SupportingEvidence
    provenance_record_ids: tuple[str, ...]
    action_graph_provenance: ActionGraphProvenance
    source_recognition_record_id: str | None
    target_recognition_record_id: str | None
    source_event_evidence_id: str | None
    target_event_evidence_id: str | None
    related_event_id: str | None
    related_event_index: int | None
    related_event_provenance: dict[str, Any] | None
    endpoint_feature_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionGraphFrame:
    schema_id: str
    action_graph_frame_id: str
    recognition_frame_id: str
    world_state_index: int
    canonical_time_seconds: float
    node_ids: tuple[str, ...]
    action_graph_provenance: ActionGraphProvenance


@dataclass(frozen=True)
class ActionGraphMetadata:
    schema_id: str
    action_catalog_version: str
    relation_catalog_version: str
    frame_count: int
    node_count: int
    edge_count: int
    action_graph_provenance: ActionGraphProvenance


@dataclass(frozen=True)
class ActionGraphDataset:
    schema_id: str
    contract_version: str
    input_contract_version: str
    recognition_dataset_sha256: str
    match_id: str
    possession_id: str
    action_types: tuple[ActionTypeDefinition, ...]
    relation_types: tuple[ActionRelationDefinition, ...]
    frames: tuple[ActionGraphFrame, ...]
    nodes: tuple[ActionNode, ...]
    edges: tuple[ActionEdge, ...]
    metadata: ActionGraphMetadata
    input_provenance: dict[str, Any]
    action_graph_provenance: ActionGraphProvenance
