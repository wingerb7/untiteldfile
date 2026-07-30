from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlayerRelevance:
    player_id: str
    category: str
    reason: str
    episode_id: str
    relevance_score: float
    evidence: dict[str, Any]
    confidence: float
