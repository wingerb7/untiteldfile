from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticRelationDefinition:
    schema_id: str
    relation_type: str
    definition_version: str
    normative_meaning: str


@dataclass(frozen=True)
class PassReceiptRelation:
    schema_id: str
    edge_id: str
    relation_type: str
    source_node_id: str
    target_node_id: str
    source_recognition_id: str
    target_recognition_id: str
    source_event_evidence_id: str
    target_event_evidence_id: str
    source_event_uuid: str
    target_event_uuid: str
    supporting_source_related_edge_ids: tuple[str, ...]
    supporting_declarations: tuple[dict[str, Any], ...]
    pass_actor_id: str | None
    pass_recipient_id: str | None
    receipt_actor_id: str | None
    pass_outcome: str | None
    receipt_outcome: str | None
    resolution_status: str


@dataclass(frozen=True)
class PassResolution:
    schema_id: str
    pass_node_id: str
    pass_event_uuid: str
    status: str
    rejection_code: str | None
    semantic_edge_id: str | None


@dataclass(frozen=True)
class SemanticResolutionMetadata:
    schema_id: str
    eligible_pass_count: int
    emitted_relation_count: int
    rejected_explicit_unsuccessful_count: int
    rejected_no_authenticated_receipt_count: int
    rejected_ambiguity_or_validation_count: int


@dataclass(frozen=True)
class SemanticResolutionDataset:
    schema_id: str
    contract_version: str
    input_contract_version: str
    action_graph_sha256: str
    recognition_dataset_sha256: str
    match_id: str
    possession_id: str
    relation_types: tuple[SemanticRelationDefinition, ...]
    relations: tuple[PassReceiptRelation, ...]
    pass_resolutions: tuple[PassResolution, ...]
    metadata: SemanticResolutionMetadata
    input_provenance: dict[str, Any]
