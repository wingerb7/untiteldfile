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
    if selected is None and chain_steps and action_chain.primary_finding_id == "authenticated_tactical_pattern":
        if len(chain_steps) != 3:
            raise ValueError("TACTICAL_STORY_BEAT_COUNT_INVALID")
        setup, carry, finish = chain_steps
        required = (
            "initial_pass_event_id", "teammate_receipt_event_id", "teammate_carry_event_id",
            "return_pass_event_id", "return_receipt_event_id", "shot_event_id", "protagonist_id", "teammate_id",
        )
        if any(not finish.evidence.get(key) for key in required):
            raise ValueError("TACTICAL_STORY_EVIDENCE_INVALID")
        initial_pass = finish.evidence["initial_pass_event_id"]
        teammate_receipt = finish.evidence["teammate_receipt_event_id"]
        teammate_carry = finish.evidence["teammate_carry_event_id"]
        return_pass = finish.evidence["return_pass_event_id"]
        return_receipt = finish.evidence["return_receipt_event_id"]
        shot = finish.evidence["shot_event_id"]
        def episode_scene(
            scene_id: str, beat: NarrativeStep, episode_id: str, event_id: str, instructions: list[dict],
        ) -> dict:
            return {
                "scene_id": scene_id, "beat_id": beat.step_id, "episode_id": episode_id,
                "football_question": beat.evidence.get("football_question"), "type": "tactical_pause",
                "at_event_id": event_id, "at_event_boundary": "start", "duration_seconds": 0.75,
                "caption_timing": {"lead_seconds": 0.75, "fade_in_seconds": 0.25, "fade_out_seconds": 0.25},
                "instructions": [*instructions, {"type": "show_caption", "text": beat.caption}],
            }

        scenes = [
            episode_scene("scene_1", setup, "episode_1", initial_pass, [
                {"type": "highlight_player", "target": "passer", "event_id": initial_pass},
                {"type": "draw_pass_arrow", "event_id": initial_pass},
            ]),
            {"scene_id": "scene_2", "beat_id": setup.step_id, "episode_id": "episode_1", "type": "play",
             "from_event_id": initial_pass, "to_event_id": teammate_receipt, "to_event_boundary": "start",
             "target_duration_seconds": 1.5, "camera_target_event_id": teammate_receipt,
             "instructions": [{"type": "show_caption", "text": setup.caption},
                              {"type": "draw_pass_arrow", "event_id": initial_pass}]},
            episode_scene("scene_3", carry, "episode_2", teammate_carry, [
                {"type": "highlight_player", "target": "passer", "event_id": teammate_carry},
                {"type": "draw_carry_arrow", "event_id": teammate_carry},
            ]),
            {"scene_id": "scene_4", "beat_id": carry.step_id, "episode_id": "episode_2", "type": "play",
             "from_event_id": teammate_carry, "to_event_id": return_pass, "to_event_boundary": "start",
             "target_duration_seconds": 4.0, "camera_target_event_id": return_pass,
             "instructions": [{"type": "show_caption", "text": carry.caption},
                              {"type": "draw_carry_arrow", "event_id": teammate_carry}]},
            episode_scene("scene_5", finish, "episode_3", return_pass, [
                {"type": "highlight_player", "target": "passer", "event_id": return_pass},
                {"type": "draw_pass_arrow", "event_id": return_pass},
            ]),
            {"scene_id": "scene_6", "beat_id": finish.step_id, "episode_id": "episode_3", "type": "play",
             "from_event_id": return_pass, "to_event_id": return_receipt, "to_event_boundary": "start",
             "target_duration_seconds": 1.6, "camera_target_event_id": return_receipt,
             "instructions": [{"type": "show_caption", "text": finish.caption},
                              {"type": "draw_pass_arrow", "event_id": return_pass}]},
            {"scene_id": "scene_7", "beat_id": finish.step_id, "episode_id": "episode_3", "type": "play",
             "from_event_id": return_receipt, "to_event_id": shot, "target_duration_seconds": 1.2,
             "camera_target_event_id": shot,
             "instructions": [{"type": "show_caption", "text": finish.caption}]},
            {"scene_id": "scene_8", "beat_id": finish.step_id, "episode_id": "episode_3", "type": "hold",
             "at_event_id": shot, "at_event_boundary": "end", "duration_seconds": 2.2, "instructions": []},
        ]
        return {
            "possession_id": possession.possession_id, "format": {"width": width, "height": height, "fps": fps},
            "selected_finding_id": None, "selected_finding": None, "action_chain": asdict(action_chain), "scenes": scenes,
            "visual_focus": {"protagonist_id": finish.evidence["protagonist_id"], "secondary_player_ids": [finish.evidence["teammate_id"]],
                             "from_event_id": initial_pass, "through_event_id": return_receipt},
            "tactical_participants": {
                "mandatory_player_ids": [finish.evidence["protagonist_id"], finish.evidence["teammate_id"]],
                "mandatory_roles": {finish.evidence["protagonist_id"]: ["initial_passer", "return_receiver", "shooter"],
                                    finish.evidence["teammate_id"]: ["first_receiver", "ball_carrier", "return_passer"]},
                "secondary_roles": ["nearest_defender", "pressing_defender", "last_defensive_line"],
                "context_roles": ["passing_lane_context"], "maximum_context_players": 6,
            },
            "planning_basis": "TACTICAL_EPISODES_FROM_AUTHENTICATED_RETURN_COMBINATION",
            "presentation": {"hide_event_hud": True},
        }
    if selected is None and chain_steps:
        first = chain_steps[0]
        terminal = chain_steps[-1]
        episode_id = "episode_1"
        scenes = [
            {
                "scene_id": "scene_1", "episode_id": episode_id, "beat_id": first.step_id,
                "football_question": "How does the same player return to the move?",
                "type": "tactical_pause", "at_event_id": first.event_id, "at_event_boundary": "start",
                "duration_seconds": 0.75,
                "caption_timing": {"lead_seconds": 0.75, "fade_in_seconds": 0.25, "fade_out_seconds": 0.25},
                "instructions": [{"type": "highlight_player", "target": "passer", "event_id": first.event_id},
                                 {"type": "show_caption", "text": first.caption}],
            },
            {
                "scene_id": "scene_2", "episode_id": episode_id, "beat_id": first.step_id, "type": "play",
                "from_event_id": first.event_id, "to_event_id": terminal.event_id,
                "target_duration_seconds": max(2.5, min(6.0, len(chain_steps) * 1.4)),
                "camera_target_event_id": terminal.event_id,
                "instructions": [{"type": "show_caption", "text": first.caption}],
            },
            {
                "scene_id": "scene_3", "episode_id": episode_id, "beat_id": terminal.step_id,
                "type": "hold", "at_event_id": terminal.event_id, "at_event_boundary": "end",
                "duration_seconds": 2.2, "instructions": [{"type": "show_caption", "text": terminal.caption}],
            },
        ]
        return {
            "possession_id": possession.possession_id,
            "format": {"width": width, "height": height, "fps": fps},
            "selected_finding_id": None, "selected_finding": None,
            "action_chain": asdict(action_chain), "scenes": scenes,
            "tactical_participants": {
                "mandatory_player_ids": sorted({step.actor_id for step in chain_steps if step.actor_id}),
                "mandatory_roles": {str(first.actor_id): ["continuing_actor"]} if first.actor_id else {},
                "secondary_roles": ["nearest_defender", "pressing_defender", "last_defensive_line"],
                "context_roles": ["passing_lane_context"], "maximum_context_players": 6,
            },
            "planning_basis": "ONE_EPISODE_FROM_AUTHENTICATED_PLAYER_ACTION_CONTINUATION",
            "presentation": {"hide_event_hud": True},
        }
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
