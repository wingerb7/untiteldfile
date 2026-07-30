from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TacticalEpisode:
    episode_id: str
    episode_type: str
    start_event_id: str
    end_event_id: str
    participating_action_ids: list[str]
    primary_actor_ids: list[str]
    relevant_defender_ids: list[str]
    tactical_question: str
    cause: str
    created_advantage: str
    decisive_action: str
    evidence: dict[str, Any]
    confidence: float
    limitations: list[str] = field(default_factory=list)
    # Additive fields from the eligibility/ranking layer (see eligibility.py).
    # BUILDUP/FINISH are structural placeholders, not ranked finding candidates,
    # so they carry fixed defaults rather than a candidate evaluation.
    eligibility_verdict: str = "STRUCTURAL"
    selection_reasons: list[str] = field(default_factory=list)
    zone_context: dict[str, Any] = field(default_factory=dict)
    identity_resolution: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateEvaluation:
    """Full, auditable evaluation of a single detected pattern finding as a
    candidate tactical episode -- whether or not it was ultimately selected.

    Every candidate produced by the detectors gets exactly one of these; none
    are silently discarded (see `select_episodes` in eligibility.py).
    """

    finding_id: str
    episode_type: str
    event_id: str
    detection_confidence: float
    semantic_valid: bool
    semantic_validity_reasons: list[str]
    causal_relevant: bool
    causal_relevance_tier: int
    causal_relevance_reasons: list[str]
    narrative_utility_score: float
    redundancy_reasons: list[str]
    zone_context: dict[str, Any]
    eligibility: str  # "SELECTED" | "ELIGIBLE_UNSELECTED" | "REJECTED"
    disqualification_reasons: list[str]
    ranking_key: tuple[float, ...]
    provenance: dict[str, Any]


@dataclass(frozen=True)
class TacticalEpisodeDataset:
    match_id: str
    possession_id: int
    episodes: list[TacticalEpisode]
    # Full candidate audit trail: every detected finding's evaluation, whether
    # selected, eligible-but-outranked, or rejected. Additive/optional so
    # existing construction sites and consumers are unaffected.
    candidate_evaluations: list[CandidateEvaluation] = field(default_factory=list)
    # Deterministic PASS/WARN/FAIL results from src.tactical_validation run
    # against this dataset's own final selected episodes (production
    # validator integration; see engine.py).
    validator_results: list[Any] = field(default_factory=list)
