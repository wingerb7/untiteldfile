from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from analysis.interpolate import build_animation_model
from analysis.normalize import load_and_normalize
from scripts.narrative_window import build_short_scene_plan, select_narrative_anchor
from src.pipelines.analyze_possession import load_config
from src.pipelines.render_analysis import caption_timing_diagnostics, scene_segments, social_intro
from src.presentation.social_format import PACING_PROFILES, apply_social_format, build_social_video_plan, resolve_caption_frame

ROOT = Path(__file__).resolve().parents[1]


def fixture(path: str = "second_goal.json"):
    possession = load_and_normalize(ROOT / "data" / path)
    prefix = "second_goal" if path == "second_goal.json" else "argentina_52"
    analysis = json.loads((ROOT / "renders" / f"{prefix}_analysis.json").read_text())
    selection = select_narrative_anchor(possession, analysis)
    plan, _ = build_short_scene_plan(possession, analysis, selection)
    return possession, plan


def test_caption_resolution_is_deterministic_and_never_late():
    first = resolve_caption_frame(9.551, 9.551, 30)
    assert first == resolve_caption_frame(9.551, 9.551, 30)
    assert first["actual_displayed_timestamp"] <= first["event_timestamp"]
    assert first["late"] is False


def test_fallback_and_local_portrait_hooks(tmp_path):
    possession, scene = fixture()
    fallback = build_social_video_plan(scene, possession)
    assert fallback["identity_hook"]["portrait_path"] is None
    portrait = tmp_path / "portrait.png"
    portrait.write_bytes(b"local")
    local = build_social_video_plan(scene, possession, portrait_path=str(portrait))
    assert local["identity_hook"]["portrait_path"] == str(portrait)


def test_hook_transition_and_serialization():
    possession, scene = fixture()
    social = build_social_video_plan(scene, possession)
    plan = apply_social_format(scene, social)
    hook, transition, _ = social_intro(plan)
    assert hook == 1.4 and transition == 0.35
    json.dumps(social)


def test_balanced_is_longer_than_fast_and_captions_do_not_overlap():
    assert PACING_PROFILES["balanced"].hook_duration > PACING_PROFILES["fast"].hook_duration
    possession, scene = fixture()
    config = load_config(ROOT / "config.yaml")
    plan = apply_social_format(scene, build_social_video_plan(scene, possession))
    segments = scene_segments(plan, build_animation_model(possession, config))
    captions = [s for s in segments if any(i.get("type") == "show_caption" for i in s.get("instructions", []))]
    assert all(left["output_end"] <= right["output_start"] for left, right in zip(captions, captions[1:]))
    assert all(not row["late"] for row in caption_timing_diagnostics(plan, build_animation_model(possession, config)))


def test_caption_segment_boundaries_are_real_frames():
    possession, scene = fixture()
    config = load_config(ROOT / "config.yaml")
    plan = apply_social_format(scene, build_social_video_plan(scene, possession))
    fps = plan["format"]["fps"]
    segments = scene_segments(plan, build_animation_model(possession, config))
    starts = [s["output_start"] for s in segments if s["type"] == "tactical_pause"]
    assert all(abs(start * fps - round(start * fps)) < 1e-9 for start in starts)


def test_generic_for_two_fixtures_and_no_specific_names_in_production():
    for name in ("second_goal.json", "possession_52.json"):
        possession, scene = fixture(name)
        assert build_social_video_plan(scene, possession)["beats"]
    text = (ROOT / "src" / "presentation" / "social_format.py").read_text()
    assert "Locatelli" not in text
    assert "e51fde20" not in text
