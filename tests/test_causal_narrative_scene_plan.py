from src.contracts import Artifact
from src.domain.models import Event, NormalizedPossession, Position
from src.scene_direction.models import SceneDirection
from src.tactical_episodes.models import TacticalEpisode
from src.tactical_story import build_causal_narrative_scene_plan


def _episode(unit_id, role, start, end):
    return TacticalEpisode(
        unit_id,
        "PROGRESSION" if role == "PROGRESSION" else ("FINISH" if role == "FINISH" else "LINE_BREAK"),
        start,
        end,
        [start] if start == end else [start, end],
        ["1"],
        [],
        "Authenticated purpose",
        "Authenticated action.",
        "",
        "Authenticated purpose",
        {"narrative_role": role},
        1.0,
    )


def test_grouped_progression_is_one_pause_and_one_play_not_member_pauses():
    units = [
        {
            "unit_id": "unit:setup", "narrative_role": "SETUP",
            "supporting_episode_ids": ("episode:a",), "tactical_purpose": "setup",
            "factual_caption": "An authenticated line-breaking action establishes the attack.",
        },
        {
            "unit_id": "unit:progression", "narrative_role": "PROGRESSION",
            "supporting_episode_ids": ("episode:b", "episode:c"), "tactical_purpose": "progression",
            "factual_caption": "Connected authenticated actions sustain the progression.",
        },
        {
            "unit_id": "unit:final", "narrative_role": "FINAL_ACTION",
            "supporting_episode_ids": ("episode:d",), "tactical_purpose": "final",
            "factual_caption": "The final authenticated action supplies the finish.",
        },
        {
            "unit_id": "unit:finish", "narrative_role": "FINISH",
            "supporting_episode_ids": ("episode:e",), "tactical_purpose": "finish",
            "factual_caption": "The authenticated sequence concludes with the shot.",
        },
    ]
    selection = Artifact(
        {"schema_id": "tip.causal_narrative_selection", "units": units},
        "application/vnd.tip.causal-narrative-selection+json",
        validated=True,
    )
    episodes = [
        _episode("unit:setup", "SETUP", "e1", "e2"),
        _episode("unit:progression", "PROGRESSION", "e3", "e6"),
        _episode("unit:final", "FINAL_ACTION", "e7", "e8"),
        _episode("unit:finish", "FINISH", "e9", "e9"),
    ]
    directions = {
        episode.episode_id: SceneDirection(
            episode.episode_id, "message", "question", ["1"], ["1"], [],
            "track", "draw_pass_arrow", None, "caption",
            {"captions": 1, "primary_overlays": 1, "secondary_overlays": 0}, [],
        )
        for episode in episodes
    }
    possession = NormalizedPossession(
        1, "attack", "defense",
        [
            Event(f"e{i}", "Pass" if i < 9 else "Shot", float(i), 1, "attack", "1",
                  Position(i, 1), Position(i + 1, 1), "2" if i < 9 else None, None, [])
            for i in range(1, 10)
        ],
        1.0, 9.0, "test", "match",
    )
    plan = build_causal_narrative_scene_plan(possession, selection, episodes, directions)
    progression = [scene for scene in plan["scenes"] if scene["narrative_role"] == "PROGRESSION"]
    assert [scene["type"] for scene in progression] == ["tactical_pause", "play"]
    assert all(scene["supporting_episode_ids"] == ["episode:b", "episode:c"] for scene in progression)
    assert plan["planning_basis"] == "CAUSAL_NARRATIVE_SELECTION_FROM_GRAPH_BACKED_EPISODES"
    assert plan["legacy_fallback"]["used"] is False


def test_role_durations_come_from_narrative_units_and_captions_remain_supported():
    source = open("src/tactical_story/causal_scene_plan.py").read()
    assert '"SETUP": {"pause": 2.4, "play": 3.2}' in source
    assert '"PROGRESSION": {"pause": 1.4, "play": 4.6}' in source
    assert "box entry" not in source.lower()
    assert "final-third" not in source.lower()
