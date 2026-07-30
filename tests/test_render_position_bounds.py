from analysis.interpolate import build_animation_model, state_at
from analysis.normalize import load_and_normalize
from src.pipelines.render_analysis import load_config


def test_locatelli_render_states_exclude_out_of_bounds_source_observations():
    config = load_config()
    possession = load_and_normalize("data/second_goal.json")
    model = build_animation_model(possession, config)
    diagnostics = model["tracking_diagnostics"]
    assert diagnostics["summary"]["invalid_source_position_count"] == 3
    assert {(121.70684030671742, 53.353738324154826), (121.10684183259633, 55.45373679827592)} <= {tuple(item["location"]) for item in diagnostics["invalid_source_positions"]}
    for frame in range(int(model["duration"] * 24) + 1):
        state = state_at(model, frame / 24)
        assert all(0.0 <= player["location"][0] <= 120.0 and 0.0 <= player["location"][1] <= 80.0 for player in state["players"])


def test_terminal_receipt_shot_sequence_has_one_post_shot_hold():
    from src.domain.models import ActionChain, Event, NarrativeStep, NormalizedPossession, Position
    from src.intelligence.scene_builder import build_scene_plan
    events = [Event(str(i), kind, float(i), 1, "t", "p", Position(1, 1), Position(2, 2), None, None, []) for i, kind in enumerate(("Pass", "Ball Receipt*", "Shot"), 1)]
    possession = NormalizedPossession(1, "t", "o", events, 1.0, 3.0, "test")
    steps = [NarrativeStep(str(i), kind, str(i), "p", None, text) for i, (kind, text) in enumerate((("pass_event", "pass"), ("ball_receipt_event", "receipt"), ("shot_event", "shot")), 1)]
    plan = build_scene_plan(possession, None, None, ActionChain("c", "continuation", "1", "3", 1.0, steps))
    assert [scene["type"] for scene in plan["scenes"]] == ["tactical_pause", "play", "hold"]
    assert plan["scenes"][-2]["to_event_id"] == "3"
    assert plan["scenes"][-1]["at_event_id"] == "3" and plan["scenes"][-1]["at_event_boundary"] == "end"
