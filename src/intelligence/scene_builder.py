from __future__ import annotations

from dataclasses import asdict

from src.domain.models import ActionChain, NormalizedPossession, TacticalFinding


def build_scene_plan(
    possession: NormalizedPossession,
    selected: TacticalFinding | None,
    explanation: str | None,
    action_chain: ActionChain | None = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> dict:
    chain_steps = action_chain.steps if action_chain else []
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
                "duration_seconds": 1.5 if chain_steps else 1.8,
                "instructions": [
                    {"type": "highlight_player", "target": "passer", "event_id": selected.event_id},
                    {"type": "highlight_player", "target": "receiver", "event_id": selected.event_id},
                    {"type": "draw_pass_arrow", "event_id": selected.event_id},
                    {"type": "draw_defensive_line", "x": line_x},
                    {"type": "show_caption", "text": chain_steps[0].caption if chain_steps else (explanation or "")},
                ],
            }
        )
        scene_number = 3
        play_start_event_id = selected.event_id
        previous_step_type = None
        for step in chain_steps[1:-1]:
            skip_play_into_step = previous_step_type == "wide_carry" and step.step_type == "return_pass"
            if not skip_play_into_step:
                scenes.append(
                    {
                        "scene_id": f"scene_{scene_number}",
                        "type": "play",
                        "from_event_id": play_start_event_id,
                        "to_event_id": step.event_id,
                        "playback_speed": 1.0,
                    }
                )
                scene_number += 1
            scenes.append(
                {
                    "scene_id": f"scene_{scene_number}",
                    "type": "tactical_pause",
                    "at_event_id": step.event_id,
                    **({"at_event_boundary": "end"} if step.step_type == "wide_carry" else {}),
                    "duration_seconds": 1.2,
                    "instructions": [
                        {"type": "show_caption", "text": step.caption},
                    ],
                }
            )
            scene_number += 1
            play_start_event_id = step.event_id
            previous_step_type = step.step_type
        scenes.append(
            {
                "scene_id": f"scene_{scene_number}",
                "type": "play",
                "from_event_id": play_start_event_id,
                "to_event_id": possession.events[-1].event_id if possession.events else selected.event_id,
                "playback_speed": 0.85,
            }
        )
    return {
        "possession_id": possession.possession_id,
        "format": {"width": width, "height": height, "fps": fps},
        "selected_finding_id": selected.finding_id if selected else None,
        "selected_finding": asdict(selected) if selected else None,
        "action_chain": asdict(action_chain) if action_chain else None,
        "scenes": scenes,
    }
