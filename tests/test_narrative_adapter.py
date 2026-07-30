from src.domain.models import ActionChain, Event, NarrativeStep, NormalizedPossession, Position
from src.intelligence.scene_builder import build_scene_plan
from src.narrative_adapter import build_continuation_narrative
from test_action_continuation import chain


def test_adapter_selects_direct_shot_chain_generically_and_deterministically():
    recognition, graph, semantic, continuation = chain([
        {"type": "PASS", "actor": "player:a"}, {"type": "CARRY", "actor": "player:b"},
        {"type": "BALL_RECEIPT", "actor": "player:a"}, {"type": "SHOT", "actor": "player:a"},
    ])
    one = build_continuation_narrative(continuation, graph, recognition, semantic, {"player:a": "Player A"})
    two = build_continuation_narrative(continuation, graph, recognition, semantic, {"player:a": "Player A"})
    assert [step["step_type"] for step in one["steps"]] == ["pass_event", "ball_receipt_event", "shot_event"]
    assert [step["caption"] for step in one["steps"]] == [
        "Watch Player A after releasing the ball.",
        "Player A becomes involved again.",
        "The sequence reaches Player A's shot.",
    ]
    assert one["episode"]["football_question"] == "How does the same player return to the move?"
    assert one.canonical_bytes() == two.canonical_bytes() and one.sha256 == two.sha256


def test_scene_planner_accepts_non_tactical_continuation_chain_with_calm_exact_boundaries():
    events = [Event(str(i), kind, float(i), 1, "t", "p", Position(1, 1), Position(2, 2), None, None, []) for i, kind in enumerate(("Pass", "Ball Receipt*", "Shot"), 1)]
    possession = NormalizedPossession(1, "t", "o", events, 1.0, 3.0, "test")
    steps = [NarrativeStep(f"s{i}", kind, str(i), "p", None, caption) for i, (kind, caption) in enumerate((("pass_event", "P passes."), ("ball_receipt_event", "P receives."), ("shot_event", "P shoots.")), 1)]
    plan = build_scene_plan(possession, None, None, ActionChain("c", "continuation", "1", "3", 1.0, steps))
    assert plan["selected_finding"] is None
    pauses = [scene for scene in plan["scenes"] if scene["type"] == "tactical_pause"]
    assert [scene["at_event_id"] for scene in pauses] == ["1"]
    assert all(scene["duration_seconds"] == 0.75 for scene in pauses)
    assert plan["scenes"][-2]["type"] == "play" and plan["scenes"][-2]["camera_target_event_id"] == "3"
    assert plan["scenes"][-1]["type"] == "hold" and plan["scenes"][-1]["at_event_id"] == "3" and plan["scenes"][-1]["duration_seconds"] == 2.2
    assert plan["planning_basis"] == "ONE_EPISODE_FROM_AUTHENTICATED_PLAYER_ACTION_CONTINUATION"
