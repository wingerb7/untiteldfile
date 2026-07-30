from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraphBackedEpisode:
    episode_id: str
    episode_type: str
    start_ordering_key: tuple[int, float, str]
    end_ordering_key: tuple[int, float, str]
    supporting_action_node_ids: tuple[str, ...]
    supporting_relation_ids: tuple[str, ...]
    authenticated_source_event_ids: tuple[str, ...]
    primary_actor_ids: tuple[str, ...]
    relevant_participant_ids: tuple[str, ...]
    recognition_record_ids: tuple[str, ...]
    perception_feature_ids: tuple[str, ...]
    confidence: float
    limitations: tuple[str, ...]
    causal_evidence_summary: str
    temporal_context_node_ids: tuple[str, ...] = ()
    selection_provenance: str = "AUTHENTICATED_GRAPH_RELATIONS"


@dataclass(frozen=True)
class EpisodeDecision:
    candidate_type: str
    status: str
    reasons: tuple[str, ...]
    supporting_action_node_ids: tuple[str, ...] = ()
