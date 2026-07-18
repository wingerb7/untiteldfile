from __future__ import annotations

import json
from pathlib import Path

from analysis.interpolate import build_animation_model, state_at
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
    supported = {"line_breaking_pass"}
    for path in POSSESSIONS:
        possession = load_and_normalize(path)
        event_ids = {event["id"] for event in possession["events"]}
        analysis, _ = analyze(path, config)
        for finding in analysis["findings"]:
            assert finding["event_id"] in event_ids
            assert finding["pattern_type"] in supported
            evidence = finding["evidence"]
            assert evidence["line_crossed"] is True
            assert evidence["defenders_bypassed"] >= config["intelligence"]["line_break"]["minimum_defenders_bypassed"]


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


def test_short_scene_plan_duration_constraints() -> None:
    config = load_config(ROOT / "config.yaml")
    possession = load_and_normalize(ROOT / "data" / "second_goal.json")
    analysis = json.loads((ROOT / "renders" / "second_goal_analysis.json").read_text(encoding="utf-8"))
    selection = select_narrative_anchor(possession, analysis)
    scene_plan, _ = build_short_scene_plan(possession, analysis, selection)
    model = build_animation_model(possession, config)
    segments = scene_segments(scene_plan, model)
    assert segments[-1]["output_end"] <= 20.0
    window = scene_plan["narrative_window"]
    event_by_id = {event["id"]: event for event in possession["events"]}
    football_duration = event_by_id[window["window_end_event_id"]]["timestamp"] - event_by_id[window["window_start_event_id"]]["timestamp"]
    assert 10.0 <= football_duration <= 18.0


def test_narrative_window_code_has_no_possession_specific_hardcoding() -> None:
    text = (ROOT / "scripts" / "narrative_window.py").read_text(encoding="utf-8")
    for forbidden in ["Locatelli", "3788754", "e51fde20", "60719aaf", "e0c628ae", "5a0ce72c"]:
        assert forbidden not in text
