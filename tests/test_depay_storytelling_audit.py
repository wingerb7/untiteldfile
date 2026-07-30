import json
from pathlib import Path


DIRECTORY = Path("audit/depay_storytelling")


def _read(name: str) -> dict:
    path = DIRECTORY / name
    data = json.loads(path.read_text())
    assert path.read_text() == json.dumps(data, sort_keys=True, indent=2) + "\n"
    return data


def test_canonical_spine_excludes_earlier_possession_circulation():
    spine = _read("canonical_attack_spine.json")
    assert spine["possession_start"]["event_id"] == "df062304-317d-4ecc-940e-848563aa6140"
    assert spine["first_causally_relevant_action"] == "33afe8ec-1aea-40be-a7cc-97610032e3b5"
    assert spine["excluded_earlier_event_count"] == 42
    assert spine["final_action"] == "f13d1fcc-d78b-4932-a6ae-f24f0e153753"
    assert spine["finish"] == spine["possession_end"]["event_id"]
    assert [action["possession_relative_index"] for action in spine["actions"]] == list(range(42, 59))


def test_all_graph_episodes_reach_finish_but_have_different_narrative_roles():
    inventory = _read("episode_inventory.json")
    assert inventory["candidate_count"] == 7
    assert [item["episode_type"] for item in inventory["episodes"]] == ["LINE_BREAK"] * 6 + ["FINISH"]
    assert all(item["selected_by_graph_semantic_route"] for item in inventory["episodes"])
    assert all(
        item["authenticated_path_to_finish"] or item["episode_type"] == "FINISH"
        for item in inventory["episodes"]
    )
    assert inventory["classification_counts"] == {
        "CORE_CAUSAL": 4,
        "SUPPORTING_CONTEXT": 1,
        "TACTICALLY_VALID_BUT_NARRATIVELY_SECONDARY": 2,
        "UNRELATED_TO_DECISIVE_ATTACK": 0,
        "DUPLICATIVE_FOR_STORYTELLING": 0,
    }


def test_narrative_grouping_is_first_divergence_and_renderer_matches_plan():
    selection = _read("selection_trace.json")
    assert selection["first_divergence_layer"] == "NARRATIVE_GROUPING"
    divergent = [stage for stage in selection["stages"] if stage.get("first_divergence")]
    assert len(divergent) == 1
    assert divergent[0]["graph_episode_candidates_received"] == 0
    assert divergent[0]["fallback"] == "FACTUAL_CONTINUATION_FALLBACK"
    assert selection["historical_generic_video_first_divergence_layer"].startswith(
        "GENERIC_EPISODE_GENERATION"
    )
    assert selection["historical_generic_video"]["candidate_episode_types"][-1] == "FINISH"

    scenes = _read("scene_plan_trace.json")
    assert scenes["previous_storytelling_render"]["scene_plan_matches_render"] is True
    assert scenes["previous_storytelling_render"]["rendered_duration"] == 8.95
    assert scenes["known_generic_duration_failure"]["rendered_duration"] == 12.5
    assert scenes["historical_generic_render"]["rendered_duration"] == 23.5
    assert scenes["graph_semantic_plan"]["rendered_duration"] > 20.0
    assert scenes["renderer_verdict"].startswith("NOT_AT_FAULT")
