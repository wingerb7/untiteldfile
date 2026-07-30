from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContinuationRelationDefinition:
    schema_id: str
    relation_type: str
    definition_version: str
    normative_meaning: str


@dataclass(frozen=True)
class PlayerActionContinuation:
    schema_id: str
    schema_version: str
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
    player_id: str
    source_action_type: str
    target_action_type: str
    source_ordering_key: tuple[Any, ...]
    target_ordering_key: tuple[Any, ...]
    match_id: str
    possession_id: str
    intervening_events: tuple[dict[str, Any], ...]
    supporting_pass_receipt_link_ids: tuple[str, ...]
    supporting_action_graph_relation_ids: tuple[str, ...]
    resolution_status: str
    action_graph_sha256: str
    recognition_dataset_sha256: str
    semantic_resolution_sha256: str


@dataclass(frozen=True)
class ContinuationResolution:
    schema_id: str
    source_node_id: str
    source_event_uuid: str
    player_id: str | None
    status: str
    rejection_code: str | None
    continuation_edge_id: str | None


@dataclass(frozen=True)
class ActionContinuationMetadata:
    schema_id: str
    supported_action_count: int
    player_count_with_continuation: int
    emitted_relation_count: int
    rejected_no_later_action_count: int
    rejected_context_mismatch_count: int
    rejected_ambiguity_or_validation_count: int
    maximum_intervening_event_count: int


@dataclass(frozen=True)
class ActionContinuationDataset:
    schema_id: str
    contract_version: str
    input_contract_version: str
    action_graph_sha256: str
    recognition_dataset_sha256: str
    semantic_resolution_sha256: str
    match_id: str
    possession_id: str
    relation_types: tuple[ContinuationRelationDefinition, ...]
    relations: tuple[PlayerActionContinuation, ...]
    resolutions: tuple[ContinuationResolution, ...]
    metadata: ActionContinuationMetadata
    input_provenance: dict[str, str]
