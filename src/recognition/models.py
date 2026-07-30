from __future__ import annotations
from dataclasses import dataclass
from typing import Any

RecognitionProvenance = dict[str, dict[str, Any]]
RecognitionValidation = dict[str, Any]

@dataclass(frozen=True)
class RecognitionConcept:
    schema_id: str
    concept_code: str
    concept_name: str
    description: str
    participant_scope: str
    required_feature_codes: tuple[str, ...]
    recognition_rule: str
    definition_version: str
    recognition_provenance: RecognitionProvenance

@dataclass(frozen=True)
class RecognitionRecord:
    schema_id: str
    recognition_id: str
    concept_code: str
    perception_frame_id: str
    world_state_id: str
    world_state_index: int
    canonical_time_seconds: float
    participant_entity_ids: tuple[str, ...]
    supporting_feature_ids: tuple[str, ...]
    supporting_event_evidence_ids: tuple[str, ...]
    recognition_provenance: RecognitionProvenance

@dataclass(frozen=True)
class RecognitionFrame:
    schema_id: str
    recognition_frame_id: str
    perception_frame_id: str
    world_state_id: str
    world_state_index: int
    canonical_time_seconds: float
    records: tuple[RecognitionRecord, ...]
    recognition_provenance: RecognitionProvenance

@dataclass(frozen=True)
class RecognitionMetadata:
    schema_id: str
    concept_catalog_version: str
    concept_count: int
    frame_count: int
    record_count: int
    recognition_provenance: RecognitionProvenance

@dataclass(frozen=True)
class RecognitionDataset:
    schema_id: str
    contract_version: str
    input_contract_version: str
    perception_dataset_sha256: str
    match_id: str
    possession_id: str
    event_evidence: tuple[dict[str, Any], ...]
    concepts: tuple[RecognitionConcept, ...]
    frames: tuple[RecognitionFrame, ...]
    metadata: RecognitionMetadata
    input_provenance: dict[str, Any]
    recognition_provenance: RecognitionProvenance
