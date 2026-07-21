from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.patterns.positional import PositionalPatternConfig, detect_positional_patterns
from src.intelligence.reasoning.build_causal_chain import action_chain_to_dict, build_causal_chain
from src.intelligence.reasoning.explain import explain_finding
from src.intelligence.reasoning.rank_findings import rank_findings
from src.intelligence.scene_builder import build_scene_plan


def load_config(path: Path = Path("config.yaml")) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def line_break_config(config: dict[str, Any]) -> LineBreakConfig:
    values = config.get("intelligence", {}).get("line_break", {})
    return LineBreakConfig(**{key: value for key, value in values.items() if key in LineBreakConfig.__dataclass_fields__})


def positional_pattern_config(config: dict[str, Any]) -> PositionalPatternConfig:
    values = config.get("intelligence", {}).get("positional_patterns", {})
    return PositionalPatternConfig(
        **{key: value for key, value in values.items() if key in PositionalPatternConfig.__dataclass_fields__}
    )


def analyze(input_path: Path, config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    possession = load_normalized_possession(input_path)
    lb_config = line_break_config(config)
    positional_config = positional_pattern_config(config)
    detected_findings = [
        *detect_line_breaking_passes(possession, lb_config),
        *detect_positional_patterns(possession, positional_config),
    ]
    findings = rank_findings(possession, detected_findings)
    minimum_confidence = min(lb_config.minimum_confidence, positional_config.minimum_confidence)
    selected = next((finding for finding in findings if finding.confidence >= minimum_confidence), None)
    action_chain = build_causal_chain(possession, findings, selected)
    language = config.get("narrative", {}).get("language", "en")

    finding_payloads = []
    for finding in findings:
        payload = asdict(finding)
        payload["explanation"] = explain_finding(finding, language)
        finding_payloads.append(payload)

    analysis_status = "supported" if selected else "limited"
    reason = None if selected else "No sufficiently reliable tactical pattern was detected."
    analysis = {
        "possession_id": possession.possession_id,
        "analysis_status": analysis_status,
        "attack_type": None,
        "selected_finding_id": selected.finding_id if selected else None,
        "action_chain": action_chain_to_dict(action_chain),
        "findings": finding_payloads if selected else [],
        "reason": reason,
        "limitations": possession.limitations,
    }
    scene_plan = build_scene_plan(
        possession,
        selected,
        explain_finding(selected, language) if selected else None,
        action_chain=action_chain,
        width=int(config.get("animation", {}).get("width", 1080)),
        height=int(config.get("animation", {}).get("height", 1920)),
        fps=int(config.get("animation", {}).get("fps", 30)),
    )
    return analysis, scene_plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--analysis-output", required=True, type=Path)
    parser.add_argument("--scene-output", required=True, type=Path)
    parser.add_argument("--config", default=Path("config.yaml"), type=Path)
    args = parser.parse_args()

    config = load_config(args.config)
    analysis, scene_plan = analyze(args.input, config)
    args.analysis_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    args.analysis_output.write_text(json.dumps(analysis, indent=2, ensure_ascii=True), encoding="utf-8")
    args.scene_output.write_text(json.dumps(scene_plan, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Wrote {args.analysis_output}")
    print(f"Wrote {args.scene_output}")


if __name__ == "__main__":
    main()
