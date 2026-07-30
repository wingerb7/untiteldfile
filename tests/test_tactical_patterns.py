from __future__ import annotations

from src.narrative_adapter import build_continuation_narrative
from src.domain.models import ActionChain, Event, NarrativeStep, NormalizedPossession, Position
from src.intelligence.scene_builder import build_scene_plan
from src.tactical_patterns import detect_return_combination_patterns
from src.tactical_story import build_tactical_story
from test_action_continuation import chain


def pattern_chain():
    first_pass = "11111111-1111-4111-8111-111111111111"
    first_receipt = "22222222-2222-4222-8222-222222222222"
    return_pass = "33333333-3333-4333-8333-333333333333"
    return_receipt = "44444444-4444-4444-8444-444444444444"
    return chain([
        {"uuid": first_pass, "type": "PASS", "actor": "player:a", "recipient": "player:b", "related": (first_receipt,)},
        {"uuid": first_receipt, "type": "BALL_RECEIPT", "actor": "player:b", "related": (first_pass,)},
        {"type": "CARRY", "actor": "player:b"},
        {"uuid": return_pass, "type": "PASS", "actor": "player:b", "recipient": "player:a", "related": (return_receipt,)},
        {"uuid": return_receipt, "type": "BALL_RECEIPT", "actor": "player:a", "related": (return_pass,)},
        {"type": "SHOT", "actor": "player:a"},
    ])


def test_generic_pattern_has_complete_direct_deterministic_provenance():
    recognition, graph, semantic, continuation = pattern_chain()
    one = detect_return_combination_patterns(continuation, graph, recognition, semantic)
    two = detect_return_combination_patterns(continuation, graph, recognition, semantic)
    assert one.canonical_bytes() == two.canonical_bytes() and one.sha256 == two.sha256
    assert len(one["matches"]) == 1
    match = one["matches"][0]
    assert [action["role"] for action in match["actions"]] == ["initial_pass", "teammate_receipt", "teammate_carry", "return_pass", "return_receipt", "finish"]
    assert len({action["node_id"] for action in match["actions"]}) == 6
    assert set(match["supporting_relations"]) == {
        "initial_pass_receipt_link_id", "initial_actor_continuation_id", "teammate_receipt_carry_continuation_id",
        "teammate_carry_pass_continuation_id", "return_pass_receipt_link_id", "finish_continuation_id",
    }


def test_story_has_three_supported_beats_and_factual_fallback_remains_available():
    recognition, graph, semantic, continuation = pattern_chain()
    patterns = detect_return_combination_patterns(continuation, graph, recognition, semantic)
    story = build_tactical_story(patterns, continuation, graph, recognition, semantic, {"player:a": "A", "player:b": "B"})
    assert story is not None
    assert [beat["beat_type"] for beat in story["beats"]] == ["initial_pass_and_continuation", "teammate_carry", "return_arrival_and_shot"]
    assert [beat["caption"] for beat in story["beats"]] == [
        "Watch A after the pass.",
        "B receives, carries, then returns the ball.",
        "The return reaches A; the shot follows.",
    ]
    assert [beat["football_question"] for beat in story["beats"]] == [
        "What happens after the first pass?", "How does the ball come back?", "Where does the combination end?",
    ]
    assert all(beat["caption_schedule"]["lead_seconds"] == 0.75 for beat in story["beats"])
    factual = build_continuation_narrative(continuation, graph, recognition, semantic, {"player:a": "A"})
    assert factual["schema_id"] == "tip.continuation_narrative"


def test_negative_fixture_without_authenticated_return_link_does_not_match():
    recognition, graph, semantic, continuation = chain([
        {"type": "PASS", "actor": "player:a"}, {"type": "BALL_RECEIPT", "actor": "player:b"},
        {"type": "CARRY", "actor": "player:b"}, {"type": "PASS", "actor": "player:b"},
        {"type": "BALL_RECEIPT", "actor": "player:a"}, {"type": "SHOT", "actor": "player:a"},
    ])
    patterns = detect_return_combination_patterns(continuation, graph, recognition, semantic)
    assert patterns["matches"] == ()
    assert build_tactical_story(patterns, continuation, graph, recognition, semantic) is None


def test_story_beats_are_grouped_into_three_calm_visual_beats():
    events = [Event(str(i), kind, float(i), 1, "t", "p", Position(1, 1), Position(2, 2), None, None, []) for i, kind in enumerate(("Pass", "Carry", "Shot"), 1)]
    possession = NormalizedPossession(1, "t", "o", events, 1.0, 3.0, "test")
    common = {"initial_pass_event_id": "1", "teammate_receipt_event_id": "2", "teammate_carry_event_id": "2", "return_pass_event_id": "2", "return_receipt_event_id": "3", "shot_event_id": "3", "protagonist_id": "player:statsbomb:1", "teammate_id": "player:statsbomb:2"}
    steps = [NarrativeStep(f"beat-{i}", kind, str(i), "p", None, f"Beat {i}", {**common, "overlay_event_id": str(i), "arrow_type": "draw_carry_arrow" if i == 2 else "draw_pass_arrow"}) for i, kind in enumerate(("initial_pass_and_continuation", "teammate_carry", "return_arrival_and_shot"), 1)]
    plan = build_scene_plan(possession, None, None, ActionChain("story", "authenticated_tactical_pattern", "1", "3", 1.0, steps))
    assert len({scene["beat_id"] for scene in plan["scenes"]}) == 3
    assert [scene["type"] for scene in plan["scenes"]] == ["tactical_pause", "play", "tactical_pause", "play", "tactical_pause", "play", "play", "hold"]
    assert {scene["episode_id"] for scene in plan["scenes"]} == {"episode_1", "episode_2", "episode_3"}
    assert plan["visual_focus"] == {"protagonist_id": "player:statsbomb:1", "secondary_player_ids": ["player:statsbomb:2"], "from_event_id": "1", "through_event_id": "3"}
    assert next(item for item in plan["scenes"][2]["instructions"] if item["type"] == "draw_carry_arrow")["event_id"] == plan["scenes"][2]["at_event_id"]
    assert next(item for item in plan["scenes"][4]["instructions"] if item["type"] == "draw_pass_arrow")["event_id"] == plan["scenes"][4]["at_event_id"]
    assert all(plan["scenes"][index].get("at_event_boundary") == "start" for index in (0, 2, 4))
    assert all(plan["scenes"][index]["caption_timing"]["lead_seconds"] == 0.75 for index in (0, 2, 4))
    assert all(plan["scenes"][index].get("camera_target_event_id") for index in (1, 3, 5, 6))
    assert plan["tactical_participants"]["maximum_context_players"] == 6
