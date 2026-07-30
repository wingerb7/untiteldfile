from __future__ import annotations

from pathlib import Path

import pytest

from src.pipelines.provenance import (
    RenderProvenanceError,
    validate_annotations_payload,
    validate_config_match,
    validate_scene_plan_possession,
)
from src.pipelines.render_analysis import render_scene_plan

ROOT = Path(__file__).resolve().parents[1]

# Real identities from the reported contamination incident: the Depay render
# (Netherlands vs United States) surfaced the hook_text and annotation overlays
# that belong to the Di Maria/Argentina possession (match_id 3869685, possession 52).
DEPAY_MATCH_ID = 3869117
DEPAY_POSSESSION_ID = 20
DI_MARIA_MATCH_ID = 3869685
DI_MARIA_POSSESSION_ID = 52


def test_validate_config_match_raises_on_match_id_mismatch() -> None:
    config = {"match": {"match_id": DI_MARIA_MATCH_ID, "possession_id": DI_MARIA_POSSESSION_ID}}
    with pytest.raises(RenderProvenanceError):
        validate_config_match(config, DEPAY_MATCH_ID, DEPAY_POSSESSION_ID)


def test_validate_config_match_raises_on_possession_id_mismatch() -> None:
    config = {"match": {"match_id": DEPAY_MATCH_ID, "possession_id": DI_MARIA_POSSESSION_ID}}
    with pytest.raises(RenderProvenanceError):
        validate_config_match(config, DEPAY_MATCH_ID, DEPAY_POSSESSION_ID)


def test_validate_config_match_accepts_matching_identity() -> None:
    config = {"match": {"match_id": DEPAY_MATCH_ID, "possession_id": DEPAY_POSSESSION_ID}}
    validate_config_match(config, DEPAY_MATCH_ID, DEPAY_POSSESSION_ID)


def test_validate_config_match_allows_config_without_match_block() -> None:
    validate_config_match({}, DEPAY_MATCH_ID, DEPAY_POSSESSION_ID)


def test_validate_scene_plan_possession_raises_on_mismatch() -> None:
    with pytest.raises(RenderProvenanceError):
        validate_scene_plan_possession({"possession_id": DI_MARIA_POSSESSION_ID}, DEPAY_POSSESSION_ID)


def test_validate_scene_plan_possession_accepts_matching_identity() -> None:
    validate_scene_plan_possession({"possession_id": DEPAY_POSSESSION_ID}, DEPAY_POSSESSION_ID)


def test_validate_annotations_payload_raises_on_match_id_mismatch() -> None:
    payload = {"match_id": DI_MARIA_MATCH_ID, "possession": DI_MARIA_POSSESSION_ID, "annotations": []}
    with pytest.raises(RenderProvenanceError):
        validate_annotations_payload(payload, DEPAY_MATCH_ID, DEPAY_POSSESSION_ID)


def test_validate_annotations_payload_accepts_matching_identity() -> None:
    payload = {"match_id": DEPAY_MATCH_ID, "possession": DEPAY_POSSESSION_ID, "annotations": []}
    validate_annotations_payload(payload, DEPAY_MATCH_ID, DEPAY_POSSESSION_ID)


def test_validate_annotations_payload_ignores_files_without_declared_identity() -> None:
    validate_annotations_payload({"annotations": []}, DEPAY_MATCH_ID, DEPAY_POSSESSION_ID)


def test_render_scene_plan_aborts_on_stale_scene_plan_possession_id(tmp_path) -> None:
    possession = {"match_id": DEPAY_MATCH_ID, "possession_id": DEPAY_POSSESSION_ID, "events": [], "match_label": "x"}
    scene_plan = {"possession_id": DI_MARIA_POSSESSION_ID, "format": {}, "scenes": []}
    config = {"animation": {}}
    with pytest.raises(RenderProvenanceError):
        render_scene_plan(possession, scene_plan, config, tmp_path / "out.mp4")


def test_render_scene_plan_aborts_before_drawing_a_different_matchs_annotations(tmp_path) -> None:
    """Regression test for the reported contamination: rendering the Depay
    possession must never silently draw overlay annotations authored for the
    Di Maria/Argentina possession (annotations/possession_52.json)."""
    possession = {
        "match_id": DEPAY_MATCH_ID,
        "possession_id": DEPAY_POSSESSION_ID,
        "events": [],
        "match_label": "Netherlands 3-1 United States, FIFA World Cup 2022 (Memphis Depay goal)",
    }
    scene_plan = {"possession_id": DEPAY_POSSESSION_ID, "format": {}, "scenes": []}
    config = {"animation": {"annotations_file": "annotations/possession_52.json"}}
    with pytest.raises(RenderProvenanceError):
        render_scene_plan(possession, scene_plan, config, tmp_path / "out.mp4")


def test_render_scene_plan_allows_di_maria_possession_to_use_its_own_annotations() -> None:
    """The original single-match workflow must keep working: possession 52 is
    allowed to use annotations/possession_52.json because the identities agree."""
    possession = {"match_id": DI_MARIA_MATCH_ID, "possession_id": DI_MARIA_POSSESSION_ID}
    validate_scene_plan_possession({"possession_id": DI_MARIA_POSSESSION_ID}, possession["possession_id"])
    payload = (ROOT / "annotations" / "possession_52.json")
    import json

    validate_annotations_payload(
        json.loads(payload.read_text(encoding="utf-8")), possession["match_id"], possession["possession_id"]
    )
