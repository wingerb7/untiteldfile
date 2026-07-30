from __future__ import annotations

import json
from pathlib import Path

from analysis.interpolate import build_animation_model, state_at, supported_pitch_position
from analysis.normalize import load_and_normalize
from src.pipelines.analyze_possession import analyze, load_config
from src.pipelines.render_analysis import scene_segments
from scripts.narrative_window import build_short_scene_plan, select_narrative_anchor


ROOT = Path(__file__).resolve().parents[1]
POSSESSIONS = [ROOT / "data" / "possession_52.json", ROOT / "data" / "second_goal.json"]


def test_exact_snapshot_fidelity_for_both_possessions() -> None:
    config = load_config(ROOT / "config.yaml")
    for path in POSSESSIONS:
        possession = load_and_normalize(path)
        model = build_animation_model(possession, config)
        events = {event["id"]: event for event in possession["events"]}
        for frame in model["frame_states"]:
            event = events[frame.event_id]
            expected = {
                player.get("source_index", idx): tuple(player["location"])
                for idx, player in enumerate(event.get("freeze_frame", []))
                if supported_pitch_position(player.get("location"))
            }
            actual = {
                player.source_index: (player.position.x, player.position.y, player.status.value)
                for player in frame.players
                if player.visible and player.source_event_id == frame.event_id
            }
            for source_index, location in expected.items():
                assert source_index in actual
                assert actual[source_index][:2] == location
                assert actual[source_index][2] == "OBSERVED"


def test_no_duplicate_or_over_11_visible_players_for_both_possessions() -> None:
    config = load_config(ROOT / "config.yaml")
    for path in POSSESSIONS:
        possession = load_and_normalize(path)
        model = build_animation_model(possession, config)
        fps = int(config["animation"]["fps"])
        for idx in range(max(1, int(model["duration"] * fps))):
            players = state_at(model, idx / fps)["players"]
            ids = [player["tracking_id"] for player in players]
            assert len(ids) == len(set(ids))
            for team_id in {player["team_id"] for player in players}:
                assert sum(1 for player in players if player["team_id"] == team_id) <= 11
            assert all(0.0 <= float(player["confidence"]) <= 1.0 for player in players)


def test_analysis_and_scene_plan_are_deterministic_for_both_possessions() -> None:
    config = load_config(ROOT / "config.yaml")
    for path in POSSESSIONS:
        first_analysis, first_scene = analyze(path, config)
        second_analysis, second_scene = analyze(path, config)
        assert first_analysis == second_analysis
        assert first_scene == second_scene


def test_findings_reference_valid_events_and_supported_labels() -> None:
    config = load_config(ROOT / "config.yaml")
    supported = {
        "line_breaking_pass",
        "width_creation",
        "switch_of_play",
        "third_man_combination",
        "free_man_creation",
        "cutback_candidate",
        "late_support",
        "ball_side_overload",
    }
    for path in POSSESSIONS:
        possession = load_and_normalize(path)
        event_ids = {event["id"] for event in possession["events"]}
        analysis, _ = analyze(path, config)
        for finding in analysis["findings"]:
            assert finding["event_id"] in event_ids
            assert finding["pattern_type"] in supported
            assert finding["players_involved"] or finding["actors"] or finding["receivers"]
            assert isinstance(finding["feature_values"], dict)
            assert "feature_values" in finding["evidence"]


def test_renderer_module_does_not_import_tactical_detectors() -> None:
    text = (ROOT / "src" / "pipelines" / "render_analysis.py").read_text(encoding="utf-8")
    assert "detect_line_breaking_passes" not in text
    assert "LineBreakConfig" not in text


def test_required_second_goal_reports_exist_and_are_json() -> None:
    for name in [
        "second_goal_candidate.json",
        "second_goal_analysis.json",
        "second_goal_scene_plan.json",
        "second_goal_event_timeline.json",
        "second_goal_fidelity_report.json",
        "generalisation_report.json",
    ]:
        with (ROOT / "renders" / name).open("r", encoding="utf-8") as f:
            json.load(f)


def test_narrative_window_selection_is_deterministic() -> None:
    possession = load_and_normalize(ROOT / "data" / "second_goal.json")
    analysis = json.loads((ROOT / "renders" / "second_goal_analysis.json").read_text(encoding="utf-8"))
    assert select_narrative_anchor(possession, analysis) == select_narrative_anchor(possession, analysis)


def test_short_scene_plan_contains_goal_and_selected_finding() -> None:
    possession = load_and_normalize(ROOT / "data" / "second_goal.json")
    analysis = json.loads((ROOT / "renders" / "second_goal_analysis.json").read_text(encoding="utf-8"))
    selection = select_narrative_anchor(possession, analysis)
    scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
    start_id = scene_plan["narrative_window"]["window_start_event_id"]
    end_id = scene_plan["narrative_window"]["window_end_event_id"]
    event_ids = [event["id"] for event in possession["events"]]
    included = set(event_ids[event_ids.index(start_id) : event_ids.index(end_id) + 1])
    assert possession["shot"]["id"] in included
    assert scene_plan["selected_finding"]["event_id"] in included
    assert scene_plan["action_chain"] is not None
    assert len(scene_plan["action_chain"]["steps"]) >= 3


def test_short_scene_plan_duration_constraints() -> None:
    config = load_config(ROOT / "config.yaml")
    possession = load_and_normalize(ROOT / "data" / "second_goal.json")
    analysis = json.loads((ROOT / "renders" / "second_goal_analysis.json").read_text(encoding="utf-8"))
    selection = select_narrative_anchor(possession, analysis)
    scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
    model = build_animation_model(possession, config)
    segments = scene_segments(scene_plan, model)
    assert 16.0 <= segments[-1]["output_end"] <= 18.0
    window = scene_plan["narrative_window"]
    event_by_id = {event["id"]: event for event in possession["events"]}
    football_duration = event_by_id[window["window_end_event_id"]]["timestamp"] - event_by_id[window["window_start_event_id"]]["timestamp"]
    assert 10.0 <= football_duration <= 18.0


def test_short_scene_plan_communicates_multiple_causal_steps() -> None:
    possession = load_and_normalize(ROOT / "data" / "second_goal.json")
    analysis = json.loads((ROOT / "renders" / "second_goal_analysis.json").read_text(encoding="utf-8"))
    selection = select_narrative_anchor(possession, analysis)
    scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
    pause_captions = [
        instruction["text"]
        for scene in scene_plan["scenes"]
        if scene["type"] == "tactical_pause"
        for instruction in scene.get("instructions", [])
        if instruction.get("type") == "show_caption"
    ]
    joined = " ".join(pause_captions)
    assert len(pause_captions) >= 3
    assert "breaks the defensive line" in joined
    assert "keeps the attack wide" in joined
    assert "continued run" in joined


def test_short_scene_plan_causal_pauses_use_distinct_model_times() -> None:
    config = load_config(ROOT / "config.yaml")
    possession = load_and_normalize(ROOT / "data" / "second_goal.json")
    analysis = json.loads((ROOT / "renders" / "second_goal_analysis.json").read_text(encoding="utf-8"))
    selection = select_narrative_anchor(possession, analysis)
    scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
    model = build_animation_model(possession, config)
    pause_times = [
        round(segment["model_time"], 3)
        for segment in scene_segments(scene_plan, model)
        if segment["type"] == "tactical_pause"
    ]
    assert len(pause_times) == len(set(pause_times))


def test_short_scene_plan_return_pass_play_starts_after_carry() -> None:
    possession = load_and_normalize(ROOT / "data" / "second_goal.json")
    analysis = json.loads((ROOT / "renders" / "second_goal_analysis.json").read_text(encoding="utf-8"))
    selection = select_narrative_anchor(possession, analysis)
    scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
    return_step = next(
        step for step in scene_plan["action_chain"]["steps"] if step["step_type"] == "return_pass"
    )
    return_scene_index = next(
        idx
        for idx, scene in enumerate(scene_plan["scenes"])
        if scene["type"] == "tactical_pause" and scene["instructions"][-1]["text"] == return_step["caption"]
    )
    play_scene = scene_plan["scenes"][return_scene_index - 1]
    assert play_scene["type"] == "play"
    assert play_scene["from_event_boundary"] == "end"


def test_short_scene_plan_uses_story_first_scene_contract() -> None:
    possession = load_and_normalize(ROOT / "data" / "second_goal.json")
    analysis = json.loads((ROOT / "renders" / "second_goal_analysis.json").read_text(encoding="utf-8"))
    selection = select_narrative_anchor(possession, analysis)
    scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
    required = {
        "scene_goal",
        "viewer_question",
        "tactical_message",
        "required_visual_state",
        "caption",
        "camera_instruction",
        "overlay_instruction",
        "required_event_anchor",
    }
    for scene in scene_plan["scenes"]:
        assert required.issubset(scene)
        assert scene["scene_goal"]
        assert scene["viewer_question"]
        assert scene["tactical_message"]
        assert scene["required_visual_state"]
        assert scene["camera_instruction"]
        assert isinstance(scene["overlay_instruction"], list)
        assert scene["required_event_anchor"]["event_id"]
    return_pause = next(
        scene for scene in scene_plan["scenes"] if scene["caption"] and "return pass" in scene["caption"]
    )
    assert return_pause.get("pause_frame_offset") == 1
    assert "pause_offset_seconds" not in return_pause


def test_narrative_window_code_has_no_possession_specific_hardcoding() -> None:
    text = (ROOT / "scripts" / "narrative_window.py").read_text(encoding="utf-8")
    for forbidden in ["Locatelli", "3788754", "e51fde20", "60719aaf", "e0c628ae", "5a0ce72c"]:
        assert forbidden not in text
