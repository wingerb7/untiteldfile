from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SceneDirection:
    episode_id: str
    primary_message: str
    tactical_question: str
    visible_players: list[str]
    highlighted_players: list[str]
    hidden_players: list[str]
    camera_intent: str
    primary_overlay: str | None
    secondary_overlay: str | None
    caption_intent: str
    visual_budget: dict[str, int]
    forbidden_overlays: list[str] = field(default_factory=list)
