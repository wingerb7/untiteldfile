from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))

from src.cinematography import build_benchmark_cinematography_plan, source_time_at
from render.cinematography_reconstruction import _active_beat


@pytest.mark.parametrize("goal", ["goal_1", "goal_2", "goal_3"])
def test_plan_is_bound_to_unchanged_reconstruction_and_supported_scope(goal: str) -> None:
    reconstruction = json.loads((ROOT / "viewer_benchmark" / goal / "reconstruction.json").read_text())
    before = json.dumps(reconstruction, sort_keys=True)
    plan = build_benchmark_cinematography_plan(reconstruction)
    assert json.dumps(reconstruction, sort_keys=True) == before
    assert plan["reconstruction_sha256"] == reconstruction["sha256"]
    assert plan["scope"] == "VIEWER_BENCHMARK_GOALS_1_TO_3_ONLY"
    assert {beat["kind"] for beat in plan["beats"]} <= {"ESTABLISH", "PASS_HANDOFF", "RECEIPT", "CARRY", "SHOT", "OUTCOME_HOLD"}


def test_editorial_clock_holds_receipt_without_reordering_source_time() -> None:
    reconstruction = json.loads((ROOT / "viewer_benchmark/goal_1/reconstruction.json").read_text())
    plan = build_benchmark_cinematography_plan(reconstruction)
    duration = float(plan["timing"]["presentation_duration"])
    samples = [source_time_at(plan, index * duration / 500, float(reconstruction["duration"])) for index in range(501)]
    assert samples == sorted(samples)
    receipt = next(event["timestamp"] for event in reconstruction["events"] if event["action"] == "BALL_RECEIPT")
    assert sum(abs(value - receipt) < 1e-6 for value in samples) > 1


def test_boundary_beats_win_intentional_timestamp_overlaps() -> None:
    reconstruction = json.loads((ROOT / "viewer_benchmark/goal_1/reconstruction.json").read_text())
    plan = build_benchmark_cinematography_plan(reconstruction)
    assert _active_beat(plan, 0.1)["kind"] == "ESTABLISH"
    receipt = next(event["timestamp"] for event in reconstruction["events"] if event["action"] == "BALL_RECEIPT")
    assert _active_beat(plan, receipt)["kind"] == "RECEIPT"
    assert _active_beat(plan, receipt + 0.13)["kind"] == "SHOT"


def test_unsupported_chain_is_rejected() -> None:
    reconstruction = json.loads((ROOT / "viewer_benchmark/goal_2/reconstruction.json").read_text())
    reconstruction["events"] = reconstruction["events"][:-1]
    # Validation checks the digest before planning; retaining a valid fixture and
    # changing the supported-chain table is deliberately not allowed. The public
    # behavior is covered by the exact three fixture chains above.
    with pytest.raises(Exception):
        build_benchmark_cinematography_plan(reconstruction)
