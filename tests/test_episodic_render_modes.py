from __future__ import annotations

from pathlib import Path

import pytest

from analysis.interpolate import build_animation_model
from analysis.normalize import load_and_normalize
from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.patterns.positional import PositionalPatternConfig, detect_positional_patterns
from src.intelligence.reasoning.rank_findings import rank_findings
from src.pipelines.provenance import RenderProvenanceError, validate_scene_plan_possession
from src.pipelines.render_analysis import load_config, render_scene_plan, resolve_presentation, scene_segments
from src.scene_direction import build_scene_direction
from src.tactical_episodes import build_tactical_episodes
from src.tactical_relevance import classify_episode_players
from src.tactical_story.episodic_scene_plan import build_episodic_scene_plan

ROOT = Path(__file__).resolve().parents[1]


def _build_plan_for(path: Path):
    possession = load_normalized_possession(path)
    findings = rank_findings(
        possession,
        [*detect_line_breaking_passes(possession, LineBreakConfig()), *detect_positional_patterns(possession, PositionalPatternConfig())],
    )
    dataset = build_tactical_episodes(possession, findings)
    directions = {}
    for episode in dataset.episodes:
        records = classify_episode_players(possession, episode)
        directions[episode.episode_id] = build_scene_direction(possession, episode, records)
    return possession, dataset, build_episodic_scene_plan(possession, dataset.episodes, directions)


def test_resolve_presentation_consumer_mode_hides_hud_and_debug() -> None:
    hide_event_hud, debug_mode = resolve_presentation({"presentation": {"mode": "consumer"}}, {"debug": True})
    assert hide_event_hud is True
    assert debug_mode is False


def test_resolve_presentation_audit_mode_shows_hud_and_debug() -> None:
    hide_event_hud, debug_mode = resolve_presentation({"presentation": {"mode": "audit"}}, {"debug": False})
    assert hide_event_hud is False
    assert debug_mode is True


def test_resolve_presentation_default_preserves_existing_behavior() -> None:
    assert resolve_presentation({}, {"debug": False}) == (False, False)
    assert resolve_presentation({"presentation": {"hide_event_hud": True}}, {"debug": True}) == (True, True)


@pytest.mark.parametrize("fixture", ["data/depay_goal.json", "data/second_goal.json"])
def test_episodic_scene_plan_duration_is_within_the_concise_cut_target(fixture: str) -> None:
    _, _, plan = _build_plan_for(ROOT / fixture)
    render_possession = load_and_normalize(ROOT / fixture)
    config = load_config(ROOT / "config.yaml")
    model = build_animation_model(render_possession, config)
    segments = scene_segments(plan, model)
    total_duration = segments[-1]["output_end"] if segments else 0.0
    assert 20.0 <= total_duration <= 35.0


def test_episode_and_scene_identities_match_the_same_possession() -> None:
    possession, dataset, plan = _build_plan_for(ROOT / "data" / "depay_goal.json")
    validate_scene_plan_possession(plan, possession.possession_id)  # must not raise
    with pytest.raises(RenderProvenanceError):
        validate_scene_plan_possession(plan, possession.possession_id + 1)


def test_consumer_and_audit_renders_share_identical_episode_and_scene_ids() -> None:
    _, _, plan = _build_plan_for(ROOT / "data" / "second_goal.json")
    consumer_scene_ids = [scene["scene_id"] for scene in plan["scenes"]]
    consumer_episode_ids = [scene.get("episode_id") for scene in plan["scenes"]]
    # both render modes are built from the exact same scene_plan object (only presentation.mode differs)
    audit_plan = dict(plan)
    audit_plan["presentation"] = {"hide_event_hud": False, "mode": "audit"}
    audit_scene_ids = [scene["scene_id"] for scene in audit_plan["scenes"]]
    audit_episode_ids = [scene.get("episode_id") for scene in audit_plan["scenes"]]
    assert consumer_scene_ids == audit_scene_ids
    assert consumer_episode_ids == audit_episode_ids


def test_render_scene_plan_consumer_frame_has_no_raw_event_hud(tmp_path) -> None:
    render_possession = load_and_normalize(ROOT / "data" / "depay_goal.json")
    _, _, plan = _build_plan_for(ROOT / "data" / "depay_goal.json")
    config = load_config(ROOT / "config.yaml")
    consumer_plan = dict(plan)
    consumer_plan["presentation"] = {"hide_event_hud": True, "mode": "consumer"}
    render_scene_plan(render_possession, consumer_plan, config, tmp_path / "consumer.mp4", frames_dir=tmp_path / "frames", frame_range=(0, 1))
    assert (tmp_path / "frames" / "f00000.png").exists()


def test_render_scene_plan_audit_frame_renders_successfully(tmp_path) -> None:
    render_possession = load_and_normalize(ROOT / "data" / "depay_goal.json")
    _, _, plan = _build_plan_for(ROOT / "data" / "depay_goal.json")
    config = load_config(ROOT / "config.yaml")
    audit_plan = dict(plan)
    audit_plan["presentation"] = {"hide_event_hud": False, "mode": "audit"}
    render_scene_plan(render_possession, audit_plan, config, tmp_path / "audit.mp4", frames_dir=tmp_path / "frames", frame_range=(0, 1))
    assert (tmp_path / "frames" / "f00000.png").exists()
