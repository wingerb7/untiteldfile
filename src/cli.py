from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.pipelines.analyze_possession import analyze, load_config
from src.pipelines.narrative_config import apply_narrative, load_narrative_config
from src.pipelines.provenance import validate_config_match
from src.pipelines.render_analysis import render_scene_plan
from analysis.normalize import load_and_normalize
from src.pipelines.semantic_route import build_semantic_route
from src.pipelines.causal_narrative_route import build_causal_narrative_route
from src.source_selection import PINNED_REVISION


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    # Deprecated compatibility default. Production causal storytelling is opt-in until
    # its reviewed render set replaces the findings-based route.
    run.add_argument("--mode", choices=("legacy", "semantic", "causal"), default="legacy")
    run.add_argument("--input", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--analysis-output", default=Path("renders/analysis.json"), type=Path)
    run.add_argument("--scene-output", default=Path("renders/scene_plan.json"), type=Path)
    run.add_argument("--config", default=Path("config.yaml"), type=Path)
    run.add_argument(
        "--narrative",
        required=False,
        type=Path,
        help="Per-possession narrative file (see narratives/*.yaml). Provides this "
        "possession's hook_text, hook_model_time, and annotations_file explicitly; "
        "never inherited from --config.",
    )
    run.add_argument("--events", type=Path)
    run.add_argument("--frames", type=Path)
    run.add_argument("--match-id", type=int)
    run.add_argument("--possession-id", type=int)
    run.add_argument("--source-revision", default=PINNED_REVISION)
    args = parser.parse_args()

    if args.mode == "legacy" and args.narrative is None:
        parser.error("legacy mode requires --narrative")
    config = load_config(args.config)
    possession = load_and_normalize(args.input)
    if args.mode in {"semantic", "causal"}:
        missing = [
            name
            for name, value in (
                ("--events", args.events),
                ("--frames", args.frames),
                ("--match-id", args.match_id),
                ("--possession-id", args.possession_id),
            )
            if value is None
        ]
        if missing:
            parser.error(f"{args.mode} mode requires {', '.join(missing)}")
        route_builder = build_causal_narrative_route if args.mode == "causal" else build_semantic_route
        route = route_builder(
            json.loads(args.events.read_text(encoding="utf-8")),
            json.loads(args.frames.read_text(encoding="utf-8")),
            {
                "source_dataset": "statsbomb-open-data",
                "source_revision": args.source_revision,
                "match_id": args.match_id,
                "possession_id": args.possession_id,
            },
            args.input,
            width=int(config.get("animation", {}).get("width", 1080)),
            height=int(config.get("animation", {}).get("height", 1920)),
            fps=int(config.get("animation", {}).get("fps", 30)),
        )
        scene_plan = route["scene_plan"]
        analysis = {
            "analysis_status": "supported",
            "pipeline_mode": args.mode,
            "planning_basis": scene_plan["planning_basis"],
            "graph_backed_episode_dataset_sha256": route["graph_backed_episodes"].sha256,
            "episode_decisions": route["graph_backed_episodes"]["decisions"],
            "legacy_fallback": scene_plan["legacy_fallback"],
        }
        if args.mode == "causal":
            analysis["causal_narrative_selection_sha256"] = route["causal_narrative_selection"].sha256
            analysis["causal_narrative_units"] = route["causal_narrative_selection"]["units"]
            analysis["causal_narrative_exclusions"] = route["causal_narrative_selection"]["exclusions"]
        args.analysis_output.parent.mkdir(parents=True, exist_ok=True)
        args.scene_output.parent.mkdir(parents=True, exist_ok=True)
        args.analysis_output.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        args.scene_output.write_text(json.dumps(scene_plan, indent=2), encoding="utf-8")
        render_scene_plan(possession, scene_plan, config, args.output)
        return
    narrative = load_narrative_config(args.narrative)
    validate_config_match(narrative, possession.get("match_id"), possession.get("possession_id"))
    resolved_config = apply_narrative(config, narrative)
    analysis, scene_plan = analyze(args.input, resolved_config)
    analysis["pipeline_mode"] = "legacy"
    analysis["legacy_fallback"] = {
        "used": True,
        "activation": "explicit_mode",
        "reason": "The caller explicitly selected the findings-based legacy route.",
    }
    scene_plan["pipeline_mode"] = "legacy"
    scene_plan["legacy_fallback"] = analysis["legacy_fallback"]
    args.analysis_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    args.analysis_output.write_text(json.dumps(analysis, indent=2, ensure_ascii=True), encoding="utf-8")
    args.scene_output.write_text(json.dumps(scene_plan, indent=2, ensure_ascii=True), encoding="utf-8")
    render_scene_plan(possession, scene_plan, resolved_config, args.output)


if __name__ == "__main__":
    main()
