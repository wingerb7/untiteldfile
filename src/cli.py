from __future__ import annotations

import argparse
from pathlib import Path

from src.pipelines.analyze_possession import analyze, load_config
from src.pipelines.render_analysis import render_scene_plan
from analysis.normalize import load_and_normalize


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--input", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--analysis-output", default=Path("renders/analysis.json"), type=Path)
    run.add_argument("--scene-output", default=Path("renders/scene_plan.json"), type=Path)
    run.add_argument("--config", default=Path("config.yaml"), type=Path)
    args = parser.parse_args()

    config = load_config(args.config)
    analysis, scene_plan = analyze(args.input, config)
    args.analysis_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    import json

    args.analysis_output.write_text(json.dumps(analysis, indent=2, ensure_ascii=True), encoding="utf-8")
    args.scene_output.write_text(json.dumps(scene_plan, indent=2, ensure_ascii=True), encoding="utf-8")
    render_scene_plan(load_and_normalize(args.input), scene_plan, config, args.output)


if __name__ == "__main__":
    main()
