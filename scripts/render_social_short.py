from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis.interpolate import build_animation_model
from analysis.normalize import load_and_normalize
from src.pipelines.analyze_possession import load_config
from src.pipelines.render_analysis import caption_timing_diagnostics, render_scene_plan, scene_trace
from src.presentation.social_format import apply_social_format, build_social_video_plan


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--scene-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--portrait", type=str)
    parser.add_argument("--hook", type=str)
    parser.add_argument("--pacing", choices=("fast", "balanced", "explanatory"), default="balanced")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()
    possession = load_and_normalize(args.input)
    source_plan = json.loads(args.scene_plan.read_text(encoding="utf-8"))
    social = build_social_video_plan(source_plan, possession, pacing=args.pacing, portrait_path=args.portrait, hook_text=args.hook)
    plan = apply_social_format(source_plan, social)
    config = load_config(args.config)
    config["animation"]["hook_hold_seconds"] = 0.0
    model = build_animation_model(possession, config)
    stem = args.output.with_suffix("")
    write(stem.with_name(stem.name + "_social_plan.json"), social)
    write(stem.with_name(stem.name + "_scene_plan.json"), plan)
    write(stem.with_name(stem.name + "_scene_trace.json"), scene_trace(plan, model))
    write(stem.with_name(stem.name + "_caption_timing.json"), caption_timing_diagnostics(plan, model))
    render_scene_plan(possession, plan, config, args.output)


if __name__ == "__main__":
    main()
