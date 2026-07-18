from __future__ import annotations

from dataclasses import asdict

from src.domain.models import NormalizedPossession
from src.intelligence.patterns.line_break import TacticalFinding


def build_scene_plan(
    possession: NormalizedPossession,
    selected: TacticalFinding | None,
    explanation: str | None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict:
    scenes = [
        {
            "scene_id": "scene_1",
            "type": "play",
            "from_event_id": possession.events[0].event_id if possession.events else None,
            "to_event_id": selected.event_id if selected else (possession.events[-1].event_id if possession.events else None),
            "playback_speed": 1.0,
        }
    ]
    if selected:
        line_x = selected.evidence.get("defensive_line_x")
        scenes.append(
            {
                "scene_id": "scene_2",
                "type": "tactical_pause",
                "at_event_id": selected.event_id,
                "duration_seconds": 1.8,
                "instructions": [
                    {"type": "highlight_player", "target": "passer", "event_id": selected.event_id},
                    {"type": "highlight_player", "target": "receiver", "event_id": selected.event_id},
                    {"type": "draw_pass_arrow", "event_id": selected.event_id},
                    {"type": "draw_defensive_line", "x": line_x},
                    {"type": "show_caption", "text": explanation or ""},
                ],
            }
        )
        scenes.append(
            {
                "scene_id": "scene_3",
                "type": "play",
                "from_event_id": selected.event_id,
                "to_event_id": possession.events[-1].event_id if possession.events else selected.event_id,
                "playback_speed": 0.85,
            }
        )
    return {
        "possession_id": possession.possession_id,
        "format": {"width": width, "height": height, "fps": fps},
        "selected_finding_id": selected.finding_id if selected else None,
        "selected_finding": asdict(selected) if selected else None,
        "scenes": scenes,
    }
