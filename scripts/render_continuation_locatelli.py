from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from analysis.normalize import load_and_normalize
from src.action_continuation import build_action_continuation_dataset
from src.action_graph import build_action_graph_dataset
from src.domain.models import ActionChain, NarrativeStep
from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.scene_builder import build_scene_plan
from src.narrative_adapter import build_continuation_narrative
from src.normalization import build_normalized_dataset
from src.perception import build_perception_dataset, validate_perception_dataset
from src.pipelines.render_analysis import caption_timing_diagnostics, render_scene_plan, scene_trace
from src.recognition import build_recognition_dataset
from src.semantic_resolution import build_semantic_resolution_dataset
from src.tactical_patterns import detect_return_combination_patterns
from src.tactical_story import build_tactical_story
from src.source_selection import PINNED_REVISION, select_source_documents
from src.synchronization import build_synchronized_dataset
from src.world_model import build_world_model_dataset, validate_world_model_dataset


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/second_goal.json"
OPEN_DATA = ROOT / "data/open-data/data"
OUTPUT = ROOT / "renders/continuation_locatelli"


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def upstream():
    events = json.loads((OPEN_DATA / "events/3788754.json").read_text())
    frames = json.loads((OPEN_DATA / "three-sixty/3788754.json").read_text())
    selected = select_source_documents(events, frames, {"source_dataset": "statsbomb-open-data", "source_revision": PINNED_REVISION, "match_id": 3788754, "possession_id": 40})
    normalized = build_normalized_dataset(selected)
    synchronized = build_synchronized_dataset(normalized)
    world = validate_world_model_dataset(build_world_model_dataset(synchronized))
    perception = validate_perception_dataset(build_perception_dataset(world), source_hashes=world.source_hashes)
    recognition = build_recognition_dataset(perception)
    graph = build_action_graph_dataset(recognition)
    semantic = build_semantic_resolution_dataset(graph, recognition)
    continuation = build_action_continuation_dataset(graph, recognition, semantic)
    patterns = detect_return_combination_patterns(continuation, graph, recognition, semantic)
    return recognition, graph, semantic, continuation, patterns


def main() -> None:
    recognition, graph, semantic, continuation, patterns = upstream()
    render_possession = load_and_normalize(SOURCE)
    names = {f"player:statsbomb:{event['player_id']}": event["player_name"] for event in render_possession["events"] if event.get("player_id") and event.get("player_name")}
    story = build_tactical_story(patterns, continuation, graph, recognition, semantic, names)
    if story is not None:
        overlay_roles = ("initial_pass", "teammate_carry", "return_pass")
        match = patterns["matches"][0]
        action_by_role = {action["role"]: action for action in match["actions"]}
        steps = [NarrativeStep(
            beat["beat_id"], beat["beat_type"], beat["end_event_uuid"], beat["actor_ids"][0], None, beat["caption"],
            {"pattern_id": story["pattern_id"], "supporting_action_node_ids": beat["supporting_action_node_ids"],
             "overlay_event_id": action_by_role[overlay_roles[index]]["event_uuid"],
             "arrow_type": "draw_carry_arrow" if index == 1 else "draw_pass_arrow",
             "protagonist_id": match["initial_actor_id"], "teammate_id": match["teammate_actor_id"],
             "initial_pass_event_id": action_by_role["initial_pass"]["event_uuid"],
             "teammate_receipt_event_id": action_by_role["teammate_receipt"]["event_uuid"],
             "teammate_carry_event_id": action_by_role["teammate_carry"]["event_uuid"],
             "return_pass_event_id": action_by_role["return_pass"]["event_uuid"],
             "return_receipt_event_id": action_by_role["return_receipt"]["event_uuid"],
             "shot_event_id": action_by_role["finish"]["event_uuid"],
             "football_question": beat["football_question"],
             "participant_roles": beat["participant_roles"],
             "caption_schedule": beat["caption_schedule"]},
        ) for index, beat in enumerate(story["beats"])]
        action_chain = ActionChain(story["story_id"], "authenticated_tactical_pattern", steps[0].event_id, steps[-1].event_id, 1.0, steps, {"pattern_dataset_sha256": patterns.sha256, "pattern_id": story["pattern_id"], "protagonist_id": match["initial_actor_id"], "teammate_id": match["teammate_actor_id"]})
        narrative = story
    else:
        narrative = build_continuation_narrative(continuation, graph, recognition, semantic, names)
        steps = [NarrativeStep(step["step_id"], step["step_type"], step["event_id"], step["actor_id"], None, step["caption"], {"continuation_node_id": step["action_graph_node_id"], "canonical_ordering_key": step["canonical_ordering_key"]}) for step in narrative["steps"]]
        action_chain = ActionChain(narrative["chain_id"], "authenticated_player_action_continuation", steps[0].event_id, steps[-1].event_id, 1.0, steps, {"continuation_dataset_sha256": continuation.sha256, "continuation_edge_ids": list(narrative["supporting_continuation_edge_ids"])})
    possession = load_normalized_possession(SOURCE)
    plan = build_scene_plan(possession, None, None, action_chain=action_chain, width=720, height=1280, fps=24)
    plan["narrative_window"] = {"window_start_event_id": steps[0].event_id, "window_end_event_id": steps[-1].event_id}
    config = json.loads(json.dumps(__import__("yaml").safe_load((ROOT / "config.yaml").read_text())))
    config["animation"].update({"width": 720, "height": 1280, "fps": 24, "hook_hold_seconds": 0.0, "hook_text": "", "annotations_file": None})
    model = render_scene_plan(render_possession, plan, config, OUTPUT / "locatelli_continuation.mp4")
    trace = {"schema_id": "tip.continuation_render_trace", "narrative_sha256": narrative.sha256, "scene_trace": scene_trace(plan, model), "caption_timing": caption_timing_diagnostics(plan, model)}
    analysis = {"schema_id": "tip.continuation_render_analysis", "analysis_status": "supported", "match_id": continuation["match_id"], "possession_id": continuation["possession_id"], "pipeline": ["Recognition", "ActionGraph", "SOURCE_RELATED_EVENT", "PASS_RECEIPT_LINK", "PLAYER_ACTION_CONTINUATION", "TacticalPattern", "TacticalStory" if story is not None else "FactualNarrativeFallback"], "artifact_hashes": {"recognition": recognition.sha256, "action_graph": graph.sha256, "semantic_resolution": semantic.sha256, "action_continuation": continuation.sha256, "tactical_patterns": patterns.sha256, "narrative": narrative.sha256}, "pattern_ids": [item["pattern_id"] for item in patterns["matches"]], "limitations": ["Display names are presentation labels from the render possession.", "StatsBomb 360 supplies event snapshots rather than continuous tracking.", "The pattern states authenticated action linkage and re-involvement; it does not infer player intent or defensive effects."]}
    write(OUTPUT / "tactical_patterns.json", patterns.data)
    write(OUTPUT / "narrative.json", narrative.data)
    write(OUTPUT / "scene_plan.json", plan)
    write(OUTPUT / "trace.json", trace)
    write(OUTPUT / "analysis.json", analysis)
    print(json.dumps({"mp4": str(OUTPUT / "locatelli_continuation.mp4"), "narrative": str(OUTPUT / "narrative.json"), "scene_plan": str(OUTPUT / "scene_plan.json"), "trace": str(OUTPUT / "trace.json"), "analysis": str(OUTPUT / "analysis.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
