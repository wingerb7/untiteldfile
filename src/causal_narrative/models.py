from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CausalNarrativeUnit:
    schema_id: str
    unit_id: str
    narrative_role: str
    primary_episode_id: str
    supporting_episode_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    graph_relation_ids: tuple[str, ...]
    continuation_relation_ids: tuple[str, ...]
    start_ordering_key: tuple[Any, ...]
    end_ordering_key: tuple[Any, ...]
    primary_actor_ids: tuple[str, ...]
    causal_predecessor_unit_id: str | None
    causal_successor_unit_id: str | None
    tactical_purpose: str
    factual_caption: str
    limitations: tuple[str, ...]
    selection_provenance: dict[str, Any]


@dataclass(frozen=True)
class NarrativeExclusion:
    schema_id: str
    episode_id: str
    classification: str
    reason: str
    causal_relation_to_finish: str
    selection_provenance: dict[str, Any]


@dataclass(frozen=True)
class CausalNarrativeSelection:
    schema_id: str
    contract_version: str
    graph_episode_dataset_sha256: str
    action_graph_sha256: str
    action_continuation_sha256: str
    match_id: str
    possession_id: str
    finish_candidate_episode_ids: tuple[str, ...]
    selected_finish_episode_id: str
    units: tuple[CausalNarrativeUnit, ...]
    exclusions: tuple[NarrativeExclusion, ...]
    source_episode_ids: tuple[str, ...]
    selection_policy: str
    limitations: tuple[str, ...]
    input_provenance: dict[str, str]
