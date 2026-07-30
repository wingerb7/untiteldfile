from __future__ import annotations

from .eligibility import evaluate_candidates, select_episodes
from .engine import EPISODE_TYPES, PATTERN_TO_EPISODE_TYPE, build_tactical_episodes
from .errors import TacticalEpisodeError
from .geometry import is_in_box, is_in_half_space, nearest_defender
from .models import CandidateEvaluation, TacticalEpisode, TacticalEpisodeDataset

__all__ = [
    "CandidateEvaluation",
    "EPISODE_TYPES",
    "PATTERN_TO_EPISODE_TYPE",
    "TacticalEpisode",
    "TacticalEpisodeDataset",
    "TacticalEpisodeError",
    "build_tactical_episodes",
    "evaluate_candidates",
    "is_in_box",
    "is_in_half_space",
    "nearest_defender",
    "select_episodes",
]
