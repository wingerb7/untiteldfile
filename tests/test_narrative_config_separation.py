from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.pipelines.narrative_config import (
    NarrativeConfigError,
    apply_narrative,
    load_narrative_config,
)
from src.pipelines.provenance import RenderProvenanceError, validate_config_match
from src.pipelines.render_analysis import load_config

ROOT = Path(__file__).resolve().parents[1]

DI_MARIA = {"match_id": 3869685, "possession_id": 52, "narrative_file": ROOT / "narratives" / "di_maria.yaml"}
LOCATELLI = {"match_id": 3788754, "possession_id": 40, "narrative_file": ROOT / "narratives" / "locatelli.yaml"}
DEPAY = {"match_id": 3869117, "possession_id": 20, "narrative_file": ROOT / "narratives" / "depay.yaml"}

# Player/team/quote strings that must never appear in the shared, generic render
# config: they belong only to a specific possession's narrative file. (Default
# output-file paths like "possession_52.mp4" are deliberately out of scope here --
# they are not narrative content and were not part of the requested cleanup.)
NARRATIVE_MARKERS = (
    "Di Maria",
    "Maria",
    "Depay",
    "Locatelli",
    "Argentina",
    "France",
    "Netherlands",
    "United States",
    "Italy",
    "Switzerland",
    "Waarom",
)


def test_generic_config_has_no_match_or_narrative_block() -> None:
    config = load_config(ROOT / "config.yaml")
    assert "match" not in config
    animation = config.get("animation", {})
    assert "hook_text" not in animation
    assert "hook_model_time" not in animation
    assert "annotations_file" not in animation


def test_generic_config_contains_no_possession_specific_narrative_strings() -> None:
    text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    for marker in NARRATIVE_MARKERS:
        assert marker not in text, f"config.yaml must not carry possession-specific content: {marker!r}"


@pytest.mark.parametrize("case", [DI_MARIA, LOCATELLI, DEPAY])
def test_each_narrative_file_declares_and_matches_its_own_identity(case: dict) -> None:
    narrative = load_narrative_config(case["narrative_file"])
    # Must not raise: each file's declared identity matches the possession it describes.
    validate_config_match(narrative, case["match_id"], case["possession_id"])


def test_depay_cannot_inherit_di_maria_content() -> None:
    di_maria = load_narrative_config(DI_MARIA["narrative_file"])
    with pytest.raises(RenderProvenanceError):
        validate_config_match(di_maria, DEPAY["match_id"], DEPAY["possession_id"])

    config = load_config(ROOT / "config.yaml")
    depay_narrative = load_narrative_config(DEPAY["narrative_file"])
    resolved = apply_narrative(config, depay_narrative)
    assert resolved["animation"]["hook_text"] == ""
    assert "Maria" not in resolved["animation"]["hook_text"]
    assert resolved["animation"].get("annotations_file") is None


def test_locatelli_cannot_inherit_di_maria_content() -> None:
    di_maria = load_narrative_config(DI_MARIA["narrative_file"])
    with pytest.raises(RenderProvenanceError):
        validate_config_match(di_maria, LOCATELLI["match_id"], LOCATELLI["possession_id"])


@pytest.mark.parametrize(
    "case,expected_hook_text,expected_annotations_file",
    [
        (DI_MARIA, "Waarom stond Di Maria helemaal vrij?", "annotations/possession_52.json"),
        (LOCATELLI, "Can Italy turn circulation into a goal?", "annotations/second_goal.json"),
        (DEPAY, "", None),
    ],
)
def test_each_supported_render_resolves_its_own_explicit_narrative(
    case: dict, expected_hook_text: str, expected_annotations_file: str | None
) -> None:
    config = load_config(ROOT / "config.yaml")
    narrative = load_narrative_config(case["narrative_file"])
    validate_config_match(narrative, case["match_id"], case["possession_id"])
    resolved = apply_narrative(config, narrative)
    assert resolved["animation"]["hook_text"] == expected_hook_text
    assert resolved["animation"].get("annotations_file") == expected_annotations_file


def test_missing_optional_hook_and_annotations_produce_a_clean_config_without_fallback() -> None:
    config = load_config(ROOT / "config.yaml")
    depay_narrative = load_narrative_config(DEPAY["narrative_file"])
    resolved = apply_narrative(config, depay_narrative)
    # No hook text -> no hook hold either, so no blank filler screen is rendered.
    assert resolved["animation"]["hook_text"] == ""
    assert resolved["animation"]["hook_hold_seconds"] == 0.0
    assert resolved["animation"]["annotations_file"] is None


def test_narrative_config_requires_declared_match_identity(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.yaml"
    incomplete.write_text(yaml.safe_dump({"match": {"match_id": 1}, "animation": {}}), encoding="utf-8")
    with pytest.raises(NarrativeConfigError):
        load_narrative_config(incomplete)


def test_mismatched_explicit_narrative_hard_fails(tmp_path: Path) -> None:
    """A narrative file that is explicitly (but wrongly) pointed at the wrong
    possession must still hard-fail, exactly like the config-level mismatch did."""
    wrong = tmp_path / "wrong.yaml"
    wrong.write_text(
        yaml.safe_dump(
            {
                "match": {"match_id": DI_MARIA["match_id"], "possession_id": DI_MARIA["possession_id"]},
                "animation": {"hook_text": "Waarom stond Di Maria helemaal vrij?"},
            }
        ),
        encoding="utf-8",
    )
    narrative = load_narrative_config(wrong)
    with pytest.raises(RenderProvenanceError):
        validate_config_match(narrative, DEPAY["match_id"], DEPAY["possession_id"])


def test_render_analysis_cli_requires_narrative_argument() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.pipelines.render_analysis", "--input", "x", "--scene-plan", "y", "--output", "z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "--narrative" in result.stderr


def test_cli_run_requires_narrative_argument() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "run", "--input", "x", "--output", "z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "--narrative" in result.stderr
