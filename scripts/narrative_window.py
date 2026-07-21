from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LOCAL_CACHE = ROOT / "renders" / ".cache"
LOCAL_MPLCONFIG = ROOT / "renders" / ".matplotlib"
LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
LOCAL_MPLCONFIG.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(LOCAL_CACHE))
os.environ.setdefault("MPLCONFIGDIR", str(LOCAL_MPLCONFIG))

from analysis.interpolate import build_animation_model, state_at
from analysis.normalize import load_and_normalize
from src.intelligence.reasoning.build_causal_chain import action_chain_to_dict, build_causal_chain_from_payload
from src.pipelines.analyze_possession import load_config
from src.pipelines.render_analysis import map_output_time, render_scene_plan, scene_segments


SECOND_GOAL = ROOT / "data" / "second_goal.json"
ANALYSIS = ROOT / "renders" / "second_goal_analysis.json"
OUT = ROOT / "renders"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def event_end_location(event: dict[str, Any]) -> list[float] | None:
    return event.get("end_location") or event.get("start_location")


def final_sequence(possession: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    goal = possession["shot"]
    goal_time = float(goal["timestamp"])
    supported_by_event = {
        finding["event_id"]: finding
        for finding in analysis.get("findings", [])
        if finding.get("pattern_type") == "line_breaking_pass"
    }
    rows = []
    for event in possession["events"]:
        if float(event["timestamp"]) < goal_time - 20.0 or float(event["timestamp"]) > goal_time:
            continue
        finding = supported_by_event.get(event["id"])
        rows.append(
            {
                "event_id": event["id"],
                "timestamp": event["timestamp"],
                "type": event["type"],
                "player": event.get("player_name"),
                "recipient": event.get("recipient_name"),
                "start_location": event.get("start_location"),
                "end_location": event_end_location(event),
                "is_supported_finding": finding is not None,
                "finding_type": finding.get("pattern_type") if finding else None,
            }
        )
    return rows


def receiver_participates_next(events: list[dict[str, Any]], finding_idx: int, recipient: str | None) -> bool:
    if not recipient:
        return False
    for event in events[finding_idx + 1 : finding_idx + 4]:
        if event.get("player_name") == recipient:
            return True
    return False


def receiver_creates_goal_access(events: list[dict[str, Any]], finding_idx: int, goal_idx: int, recipient: str | None) -> bool:
    if not recipient:
        return False
    for event in events[finding_idx + 1 : goal_idx]:
        if event.get("player_name") == recipient and event.get("type") in {"Carry", "Pass"}:
            end = event_end_location(event)
            if end and (float(end[0]) >= 100.0 or float(end[1]) >= 68.0 or float(end[1]) <= 12.0):
                return True
    return False


def score_narrative_finding(possession: dict[str, Any], finding: dict[str, Any]) -> dict[str, Any]:
    events = possession["events"]
    event_ids = [event["id"] for event in events]
    finding_idx = event_ids.index(finding["event_id"])
    goal_idx = event_ids.index(possession["shot"]["id"])
    event = events[finding_idx]
    goal = possession["shot"]
    seconds_before_goal = float(goal["timestamp"]) - float(event["timestamp"])
    events_between = max(0, goal_idx - finding_idx - 1)
    recipient = event.get("recipient_name")
    temporal = max(0.0, min(1.0, 1.0 - seconds_before_goal / 20.0))
    continuous = 1.0 if finding_idx < goal_idx else 0.0
    receiver_next = 1.0 if receiver_participates_next(events, finding_idx, recipient) else 0.0
    final_acceleration = 1.0 if seconds_before_goal <= 12.0 and goal_idx - finding_idx <= 6 else 0.0
    access = 1.0 if receiver_creates_goal_access(events, finding_idx, goal_idx, recipient) else 0.0
    economy = max(0.0, min(1.0, 1.0 - events_between / 10.0))
    score = (
        0.22 * temporal
        + 0.18 * continuous
        + 0.18 * final_acceleration
        + 0.16 * receiver_next
        + 0.16 * access
        + 0.10 * economy
    )
    return {
        "finding": finding,
        "event": event,
        "score": round(score, 3),
        "seconds_before_goal": round(seconds_before_goal, 3),
        "events_between_finding_and_goal": events_between,
        "components": {
            "temporal_proximity": round(temporal, 3),
            "possession_remains_continuous": continuous,
            "initiates_final_acceleration": final_acceleration,
            "receiver_participates_next": receiver_next,
            "creates_goal_access": access,
            "low_unnecessary_play": round(economy, 3),
        },
    }


def select_narrative_anchor(possession: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    scored = []
    for finding in analysis.get("findings", []):
        item = score_narrative_finding(possession, finding)
        chain = build_causal_chain_from_payload(possession, {**analysis, "selected_finding_id": finding["finding_id"]})
        item["action_chain"] = action_chain_to_dict(chain)
        item["score"] = round(min(1.0, item["score"] * 0.55 + (chain.score if chain else 0.0) * 0.45), 3)
        scored.append(item)
    scored.sort(key=lambda item: item["score"], reverse=True)
    if not scored:
        raise RuntimeError("No supported finding available for narrative selection.")
    selected = scored[0]
    alternative = scored[1] if len(scored) > 1 else None
    chain_steps = (selected.get("action_chain") or {}).get("steps") or []
    return {
        "selected": selected,
        "summary": {
            "selected_finding_id": selected["finding"]["finding_id"],
            "selection_reason": " ".join(step["caption"] for step in chain_steps[:4])
            or "This finding starts the immediate goal sequence.",
            "seconds_before_goal": selected["seconds_before_goal"],
            "events_between_finding_and_goal": selected["events_between_finding_and_goal"],
            "action_chain": selected.get("action_chain"),
            "alternative_finding": None
            if alternative is None
            else {
                "finding_id": alternative["finding"]["finding_id"],
                "reason_not_selected": (
                    "It is a supported line-breaking pass, but it occurs earlier in the buildup and is followed by "
                    "more recycling before the final acceleration."
                ),
            },
        },
        "all_scores": scored,
    }


def window_start_event(possession: dict[str, Any], selected_event: dict[str, Any]) -> dict[str, Any]:
    events = possession["events"]
    selected_idx = next(idx for idx, event in enumerate(events) if event["id"] == selected_event["id"])
    passer = selected_event.get("player_name")
    selected_time = float(selected_event["timestamp"])
    for event in reversed(events[:selected_idx]):
        if selected_time - float(event["timestamp"]) > 10.0:
            break
        if event.get("type") == "Pass" and not event.get("outcome") and event.get("recipient_name") == passer:
            return event
    for event in reversed(events[:selected_idx]):
        if selected_time - float(event["timestamp"]) <= 6.0:
            return event
    return selected_event


def previous_event(possession: dict[str, Any], event_id: str) -> dict[str, Any]:
    events = possession["events"]
    idx = next(idx for idx, event in enumerate(events) if event["id"] == event_id)
    return events[max(0, idx - 1)]


def next_receipt_event(possession: dict[str, Any], pass_event: dict[str, Any]) -> dict[str, Any] | None:
    events = possession["events"]
    idx = next(idx for idx, event in enumerate(events) if event["id"] == pass_event["id"])
    recipient_id = pass_event.get("recipient_id")
    recipient_name = pass_event.get("recipient_name")
    for event in events[idx + 1 :]:
        if float(event["timestamp"]) - float(pass_event["timestamp"]) > 3.0:
            return None
        if event.get("type") != "Ball Receipt*":
            continue
        if recipient_id is not None and event.get("player_id") == recipient_id:
            return event
        if recipient_id is None and recipient_name and event.get("player_name") == recipient_name:
            return event
    return None


def event_by_id(possession: dict[str, Any], event_id: str | None) -> dict[str, Any] | None:
    return next((event for event in possession["events"] if event["id"] == event_id), None)


def chain_step(chain_steps: list[dict[str, Any]], step_type: str) -> dict[str, Any] | None:
    return next((step for step in chain_steps if step.get("step_type") == step_type), None)


def actor_name(event: dict[str, Any] | None, fallback: str) -> str:
    return str((event or {}).get("player_name") or fallback)


def receiver_name(event: dict[str, Any] | None, fallback: str) -> str:
    return str((event or {}).get("recipient_name") or fallback)


def story_scene(
    scene: dict[str, Any],
    *,
    scene_goal: str,
    viewer_question: str,
    tactical_message: str,
    required_visual_state: str,
    caption: str,
    camera_instruction: str,
    overlay_instruction: list[dict[str, Any]],
    required_event_anchor: dict[str, Any],
) -> dict[str, Any]:
    return {
        **scene,
        "scene_goal": scene_goal,
        "viewer_question": viewer_question,
        "tactical_message": tactical_message,
        "required_visual_state": required_visual_state,
        "caption": caption,
        "camera_instruction": camera_instruction,
        "overlay_instruction": overlay_instruction,
        "required_event_anchor": required_event_anchor,
    }


def build_short_scene_plan(possession: dict[str, Any], analysis: dict[str, Any], selection: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected_event = selection["selected"]["event"]
    start_event = window_start_event(possession, selected_event)
    goal_event = possession["shot"]
    finding = selection["selected"]["finding"]
    action_chain = selection["selected"].get("action_chain")
    chain_steps = list((action_chain or {}).get("steps") or [])
    if not chain_steps:
        passer = selected_event.get("player_name") or "Passer"
        chain_steps = [
            {
                "step_type": "line_break",
                "event_id": selected_event["id"],
                "caption": f"{passer} breaks the line into the runner.",
            }
        ]

    line_step = chain_step(chain_steps, "line_break") or chain_steps[0]
    carry_step = chain_step(chain_steps, "wide_carry")
    return_step = chain_step(chain_steps, "return_pass")
    finish_step = chain_step(chain_steps, "finish")
    line_event = event_by_id(possession, line_step.get("event_id")) or selected_event
    carry_event = event_by_id(possession, carry_step.get("event_id") if carry_step else None)
    return_event = event_by_id(possession, return_step.get("event_id") if return_step else None)
    receipt_event = next_receipt_event(possession, return_event) if return_event else None
    finish_event = event_by_id(possession, finish_step.get("event_id") if finish_step else None) or goal_event
    passer = actor_name(line_event, "The passer")
    receiver = receiver_name(line_event, "the receiver")

    line_caption = f"{passer} breaks the defensive line."
    carry_caption = f"{receiver} keeps the attack wide."
    return_caption = f"The return pass finds {passer}'s continued run."
    finish_caption = f"{passer} finishes the move he started."

    scenes: list[dict[str, Any]] = [
        story_scene(
            {
                "scene_id": "short_scene_1",
                "type": "play",
                "from_event_id": start_event["id"],
                "to_event_id": line_event["id"],
                "target_duration_seconds": 3.2,
            },
            scene_goal="Introduce the attacking shape before the decisive action.",
            viewer_question="What breaks the defence?",
            tactical_message=f"The attack is set up to find {passer} between the buildup and the final action.",
            required_visual_state="The ball reaches the player who can break the line.",
            caption="",
            camera_instruction="Keep the passer, receiver and defensive line context in frame.",
            overlay_instruction=[],
            required_event_anchor={"event_id": line_event["id"], "boundary": "end", "role": "line-break setup"},
        )
    ]

    scene_number = 2
    play_start_event_id = line_event["id"]
    play_start_boundary = "end"

    line_overlays = [
        {"type": "highlight_player", "target": "passer", "event_id": line_event["id"]},
        {"type": "highlight_player", "target": "receiver", "event_id": line_event["id"]},
        {"type": "draw_pass_arrow", "event_id": line_event["id"]},
        {"type": "draw_defensive_line", "x": finding["evidence"].get("defensive_line_x")},
    ]
    scenes.append(
        story_scene(
            {
                "scene_id": f"short_scene_{scene_number}",
                "type": "tactical_pause",
                "at_event_id": line_event["id"],
                "at_event_boundary": "end",
                "duration_seconds": 2.0,
                "instructions": [*line_overlays, {"type": "show_caption", "text": line_caption}],
            },
            scene_goal="Explain the first tactical advantage.",
            viewer_question="What breaks the defence?",
            tactical_message=f"{passer}'s pass removes the first defensive line from the attack.",
            required_visual_state="The completed pass has reached the receiver beyond the line.",
            caption=line_caption,
            camera_instruction="Freeze with passer, receiver and defensive line visible.",
            overlay_instruction=line_overlays,
            required_event_anchor={"event_id": line_event["id"], "boundary": "end", "role": "completed line break"},
        )
    )
    scene_number += 1

    if carry_event is not None:
        scenes.append(
            story_scene(
                {
                    "scene_id": f"short_scene_{scene_number}",
                    "type": "play",
                    "from_event_id": play_start_event_id,
                    "from_event_boundary": play_start_boundary,
                    "to_event_id": carry_event["id"],
                    "target_duration_seconds": 2.8,
                },
                scene_goal="Show the attack continuing after the line break.",
                viewer_question="What happens after the line break?",
                tactical_message=f"{receiver} carries the attack into a wide finishing lane.",
                required_visual_state="The receiver advances the ball into the wide channel.",
                caption="",
                camera_instruction="Follow the ball while preserving the runner and box context.",
                overlay_instruction=[],
                required_event_anchor={"event_id": carry_event["id"], "boundary": "end", "role": "wide carry completion"},
            )
        )
        scene_number += 1
        play_start_event_id = carry_event["id"]
        play_start_boundary = "end"
        carry_overlays = [{"type": "highlight_player", "target": "passer", "event_id": carry_event["id"]}]
        scenes.append(
            story_scene(
                {
                    "scene_id": f"short_scene_{scene_number}",
                    "type": "tactical_pause",
                    "at_event_id": carry_event["id"],
                    "at_event_boundary": "end",
                    "duration_seconds": 1.8,
                    "instructions": [*carry_overlays, {"type": "show_caption", "text": carry_caption}],
                },
                scene_goal="Explain why the wide carry matters.",
                viewer_question="Why does the carry matter?",
                tactical_message=f"{receiver} preserves width instead of collapsing the attack into traffic.",
                required_visual_state="The ball carrier is high and wide with the attack stretched across the box.",
                caption=carry_caption,
                camera_instruction="Freeze after the carry with the wide lane and central runners visible.",
                overlay_instruction=carry_overlays,
                required_event_anchor={"event_id": carry_event["id"], "boundary": "end", "role": "wide tactical state"},
            )
        )
        scene_number += 1

    if return_event is not None:
        return_to_event = receipt_event or return_event
        scenes.append(
            story_scene(
                {
                    "scene_id": f"short_scene_{scene_number}",
                    "type": "play",
                    "from_event_id": play_start_event_id,
                    **({"from_event_boundary": play_start_boundary} if play_start_boundary else {}),
                    "to_event_id": return_to_event["id"],
                    "target_duration_seconds": 1.5,
                },
                scene_goal="Show the ball coming back after width has been created.",
                viewer_question="How does the original passer become free again?",
                tactical_message=f"The wide action gives {passer} time to arrive for the return.",
                required_visual_state="The return pass travels from the wide player back toward the runner.",
                caption="",
                camera_instruction="Keep the return-pass path and the receiver's run in frame.",
                overlay_instruction=[],
                required_event_anchor={"event_id": return_to_event["id"], "boundary": "start", "role": "return pass completion"},
            )
        )
        scene_number += 1
        return_overlays = [
            {"type": "highlight_player", "target": "passer", "event_id": return_event["id"]},
            {"type": "highlight_player", "target": "receiver", "event_id": return_event["id"]},
            {"type": "draw_pass_arrow", "event_id": return_event["id"]},
        ]
        scenes.append(
            story_scene(
                {
                    "scene_id": f"short_scene_{scene_number}",
                    "type": "tactical_pause",
                    "at_event_id": return_to_event["id"],
                    **({"pause_frame_offset": 1} if receipt_event is not None else {"at_event_boundary": "end"}),
                    "duration_seconds": 2.0,
                    "instructions": [*return_overlays, {"type": "show_caption", "text": return_caption}],
                },
                scene_goal="Explain the second advantage created by the original pass.",
                viewer_question="How does the original passer become free again?",
                tactical_message=f"{passer} continues the move and receives after the ball has gone wide.",
                required_visual_state="The return pass has arrived and the original passer is in the finishing lane.",
                caption=return_caption,
                camera_instruction="Freeze after receipt with the return path and receiving runner visible.",
                overlay_instruction=return_overlays,
                required_event_anchor={"event_id": return_to_event["id"], "boundary": "start", "frame_offset": 1, "role": "receipt after return"},
            )
        )
        scene_number += 1
        play_start_event_id = return_to_event["id"]
        play_start_boundary = None

    scenes.extend(
        [
            story_scene(
                {
                    "scene_id": f"short_scene_{scene_number}",
                    "type": "play",
                    "from_event_id": play_start_event_id,
                    **({"from_event_boundary": play_start_boundary} if play_start_boundary else {}),
                    "to_event_id": finish_event["id"],
                    "target_duration_seconds": 1.4,
                },
                scene_goal="Show the advantage becoming a shot.",
                viewer_question="How is the attack finished?",
                tactical_message=f"{passer} attacks the space opened by the combination.",
                required_visual_state="The receiver of the return pass moves into the shot.",
                caption="",
                camera_instruction="Follow the runner through the shot without adding explanatory text.",
                overlay_instruction=[],
                required_event_anchor={"event_id": finish_event["id"], "boundary": "end", "role": "finish"},
            ),
            story_scene(
                {
                    "scene_id": f"short_scene_{scene_number + 1}",
                    "type": "hold",
                    "at_event_id": finish_event["id"],
                    "at_event_boundary": "end",
                    "duration_seconds": 1.7,
                    "instructions": [
                        {"type": "highlight_player", "target": "passer", "event_id": finish_event["id"]},
                        {"type": "show_caption", "text": finish_caption},
                    ],
                },
                scene_goal="Let the viewer connect the finish back to the first action.",
                viewer_question="Why did the attack succeed?",
                tactical_message=f"The player who broke the line is also the player arriving to finish.",
                required_visual_state="The shot has been taken and the attacking move is complete.",
                caption=finish_caption,
                camera_instruction="Hold the goal frame long enough for the final message to land.",
                overlay_instruction=[{"type": "highlight_player", "target": "passer", "event_id": finish_event["id"]}],
                required_event_anchor={"event_id": finish_event["id"], "boundary": "end", "role": "goal hold"},
            ),
        ]
    )
    scene_plan = {
        "possession_id": possession["possession_id"],
        "format": {"width": 1080, "height": 1920, "fps": 30},
        "selected_finding_id": finding["finding_id"],
        "selected_finding": finding,
        "action_chain": action_chain,
        "narrative_window": {
            "window_start_event_id": start_event["id"],
            "window_end_event_id": goal_event["id"],
            **selection["summary"],
        },
        "scenes": scenes,
    }
    return scene_plan, {"start_event": start_event, "goal_event": goal_event}


def timeline_payload(possession: dict[str, Any], scene_plan: dict[str, Any], config: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    model = build_animation_model(possession, config)
    segments = scene_segments(scene_plan, model)
    starts = {item.event["id"]: item.start for item in model["timeline"]}
    start_id = scene_plan["narrative_window"]["window_start_event_id"]
    end_id = scene_plan["narrative_window"]["window_end_event_id"]
    events = possession["events"]
    start_idx = next(idx for idx, event in enumerate(events) if event["id"] == start_id)
    end_idx = next(idx for idx, event in enumerate(events) if event["id"] == end_id)
    included = events[start_idx : end_idx + 1]
    render_duration = segments[-1]["output_end"] if segments else 0.0
    return {
        "window_start_event_id": start_id,
        "window_end_event_id": end_id,
        "window_duration_seconds": round(float(events[end_idx]["timestamp"]) - float(events[start_idx]["timestamp"]), 3),
        "render_duration_seconds": round(render_duration, 3),
        "selected_finding_id": selection["summary"]["selected_finding_id"],
        "events_included": [
            {
                "event_id": event["id"],
                "timestamp": event["timestamp"],
                "render_start": round(starts[event["id"]], 3),
                "type": event["type"],
                "player": event.get("player_name"),
            }
            for event in included
        ],
        "events_excluded_before_window": start_idx,
        "selection_reason": selection["summary"]["selection_reason"],
    }


def validate_short_outputs(possession: dict[str, Any], scene_plan: dict[str, Any], timeline: dict[str, Any]) -> None:
    event_ids = {event["id"] for event in possession["events"]}
    included_ids = {event["event_id"] for event in timeline["events_included"]}
    assert possession["shot"]["id"] in included_ids
    assert scene_plan["selected_finding"]["event_id"] in included_ids
    assert timeline["window_start_event_id"] in event_ids
    assert timeline["window_end_event_id"] == possession["shot"]["id"]
    assert timeline["render_duration_seconds"] <= 20.0
    assert (OUT / "second_goal.mp4").exists()


def identified_source_player(event: dict[str, Any], player_id: Any) -> dict[str, Any] | None:
    for player in event.get("freeze_frame", []):
        if player.get("player_id") == player_id:
            return player
    return None


def frame_state_player(model: dict[str, Any], event_id: str, player_id: Any) -> Any:
    frame = next((item for item in model["frame_states"] if item.event_id == event_id), None)
    if frame is None:
        return None
    return next((player for player in frame.players if player.visible and player.player_id == player_id), None)


def absence_reason(
    source_present: bool,
    normalized_present: bool,
    frame_present: bool,
    render_present: bool,
    exact_event: dict[str, Any] | None,
) -> str | None:
    if render_present:
        return None
    if exact_event is None:
        return "No exact event snapshot at this sampled time."
    if not source_present:
        return "Selected player is not identified in the source freeze frame at this event."
    if not normalized_present:
        return "Selected player identity is absent after normalization."
    if not frame_present:
        return "Selected player was removed before the reconstructed frame state."
    return "Selected player was filtered before render-state output."


def player_timeline(
    possession: dict[str, Any],
    model: dict[str, Any],
    scene_plan: dict[str, Any],
    render_timeline: dict[str, Any],
) -> dict[str, Any]:
    selected_player_id = possession["shot"].get("player_id")
    selected_player_name = possession["shot"].get("player_name")
    events = {event["id"]: event for event in possession["events"]}
    event_times = {item.event["id"]: item.start for item in model["timeline"]}
    segments = scene_segments(scene_plan, model)
    render_duration = render_timeline["render_duration_seconds"]
    output_times = {round(step * 0.5, 3) for step in range(int(render_duration / 0.5) + 2)}
    output_times.update(round(segment["output_start"], 3) for segment in segments)
    output_times.update(round(segment["output_end"], 3) for segment in segments)
    rows = []
    for output_t in sorted(time for time in output_times if 0.0 <= time <= render_duration):
        model_t, _ = map_output_time(output_t, segments)
        exact_event_id = next((event_id for event_id, event_t in event_times.items() if abs(event_t - model_t) <= 1e-6), None)
        exact_event = events.get(exact_event_id) if exact_event_id else None
        source_player = identified_source_player(exact_event, selected_player_id) if exact_event else None
        normalized_present = source_player is not None
        frame_player = frame_state_player(model, exact_event_id, selected_player_id) if exact_event_id else None
        render_state = state_at(model, model_t)
        render_player = next(
            (player for player in render_state["players"] if player.get("player_id") == selected_player_id),
            None,
        )
        interpolated_state_present = bool(render_player and render_player.get("status") == "INTERPOLATED") or bool(
            frame_player and not frame_player.observed
        )
        rows.append(
            {
                "output_timestamp": round(output_t, 3),
                "model_timestamp": round(model_t, 3),
                "event_id": exact_event_id,
                "source_observation_present": source_player is not None,
                "normalized_state_present": normalized_present,
                "interpolated_state_present": interpolated_state_present,
                "render_state_present": render_player is not None,
                "player_id": selected_player_id if render_player or source_player or frame_player else None,
                "player_name": selected_player_name if render_player or source_player or frame_player else None,
                "track_id": (render_player or {}).get("tracking_id") if render_player else (frame_player.tracking_id if frame_player else None),
                "position": (render_player or {}).get("location") if render_player else ([frame_player.position.x, frame_player.position.y] if frame_player else None),
                "position_source": (render_player or {}).get("status") if render_player else (frame_player.status.value if frame_player else None),
                "absence_reason": absence_reason(
                    source_player is not None,
                    normalized_present,
                    frame_player is not None,
                    render_player is not None,
                    exact_event,
                ),
            }
        )
    return {
        "player_id": selected_player_id,
        "player_name": selected_player_name,
        "timeline": rows,
    }


def main() -> None:
    possession = load_and_normalize(SECOND_GOAL)
    analysis = read_json(ANALYSIS)
    config = load_config(ROOT / "config.yaml")
    short_config = copy.deepcopy(config)
    short_config["animation"] = copy.deepcopy(config.get("animation", {}))
    short_config["animation"]["hook_hold_seconds"] = 0.0
    short_config["animation"]["hook_text"] = ""
    short_config["animation"]["annotations_file"] = "annotations/second_goal.json"
    short_config["animation"]["camera_lookback_seconds"] = 2.5
    short_config["animation"]["camera_lookahead_seconds"] = 8.0
    short_config["animation"]["camera_zoom_out_ease"] = 0.18

    sequence = final_sequence(possession, analysis)
    write_json(OUT / "second_goal_final_sequence.json", {"events": sequence})
    selection = select_narrative_anchor(possession, analysis)
    write_json(OUT / "second_goal_narrative_selection.json", selection["summary"])
    scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
    write_json(OUT / "second_goal_short_scene_plan.json", scene_plan)
    timeline = timeline_payload(possession, scene_plan, short_config, selection)
    write_json(OUT / "second_goal_short_timeline.json", timeline)
    validate_short_outputs(possession, scene_plan, timeline)
    diagnostic_model = build_animation_model(possession, short_config)
    write_json(OUT / "second_goal_selected_player_timeline.json", player_timeline(possession, diagnostic_model, scene_plan, timeline))
    render_scene_plan(possession, scene_plan, short_config, OUT / "second_goal_short.mp4")
    print(json.dumps({"selection": selection["summary"], "timeline": timeline}, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
