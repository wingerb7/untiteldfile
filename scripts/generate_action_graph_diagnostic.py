"""Engineering diagnostics for the authenticated Recognition-to-Action-Graph route."""
from __future__ import annotations

import argparse
from collections import Counter
import gc
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.action_graph import build_action_graph_dataset
from src.action_graph.registry import ACTION_TYPES, RELATION_TYPES
from src.contracts import canonical_bytes
from src.normalization import build_normalized_dataset
from src.perception import build_perception_dataset, validate_perception_dataset
from src.recognition import build_recognition_dataset
from src.source_selection import PINNED_REVISION, select_source_documents
from src.synchronization import build_synchronized_dataset
from src.world_model import build_world_model_dataset, validate_world_model_dataset


BASE = Path("data/open-data/data")


def source_documents(match_id: int) -> tuple[list[dict], list[dict]]:
    events = json.loads((BASE / f"events/{match_id}.json").read_text())
    frames = json.loads((BASE / f"three-sixty/{match_id}.json").read_text())
    return events, frames


def positive(name: str, match_id: int, possession_id: int) -> dict:
    events, frames = source_documents(match_id)
    request = {"source_dataset": "statsbomb-open-data", "source_revision": PINNED_REVISION, "match_id": match_id, "possession_id": possession_id}
    selection = select_source_documents(events, frames, request)
    normalized = build_normalized_dataset(selection)
    synchronized = build_synchronized_dataset(normalized)
    world = validate_world_model_dataset(build_world_model_dataset(synchronized))
    perception = validate_perception_dataset(build_perception_dataset(world), source_hashes=world.source_hashes)
    recognition = build_recognition_dataset(perception)
    del events, frames, selection, normalized, synchronized, world, perception
    gc.collect()
    graph = build_action_graph_dataset(recognition)
    repeated = build_action_graph_dataset(recognition)
    return {
        "fixture": name,
        "source_fixture": {"match_id": match_id, "possession_id": possession_id, "source_revision": PINNED_REVISION},
        "status": "SUCCEEDED",
        "frame_count": len(graph["frames"]),
        "recognition_record_count": recognition["metadata"]["record_count"],
        "action_graph_node_count": len(graph["nodes"]),
        "action_graph_edge_count": len(graph["edges"]),
        "node_counts_by_action_type": dict(sorted(Counter(node["action_type"] for node in graph["nodes"]).items())),
        "edge_counts_by_relation_type": dict(sorted(Counter(edge["relation_type"] for edge in graph["edges"]).items())),
        "recognition_input_sha256": recognition.sha256,
        "action_graph_sha256": graph.sha256,
        "repeated_run_deterministic": graph.canonical_bytes() == repeated.canonical_bytes() and graph.sha256 == repeated.sha256,
        "validation_result": "PASSED" if graph.validated else "FAILED",
        "failure_code": None,
    }


def negative(name: str, match_id: int, possession_id: int) -> dict:
    events, frames = source_documents(match_id)
    request = {"source_dataset": "statsbomb-open-data", "source_revision": PINNED_REVISION, "match_id": match_id, "possession_id": possession_id}
    try:
        select_source_documents(events, frames, request)
    except Exception as exc:
        return {
            "fixture": name,
            "source_fixture": {"match_id": match_id, "possession_id": possession_id, "source_revision": PINNED_REVISION},
            "status": "UPSTREAM_REJECTED",
            "stage": getattr(exc, "stage", "unknown"),
            "failure_code": getattr(exc, "code", type(exc).__name__),
            "frame_count": None,
            "recognition_record_count": None,
            "action_graph_node_count": None,
            "action_graph_edge_count": None,
            "node_counts_by_action_type": {},
            "edge_counts_by_relation_type": {},
            "recognition_input_sha256": None,
            "action_graph_sha256": None,
            "repeated_run_deterministic": None,
            "validation_result": "NOT_EXECUTED",
            "recognition_executed": False,
            "action_graph_executed": False,
        }
    raise RuntimeError(f"{name} unexpectedly passed source selection")


def isolation() -> dict:
    forbidden = (
        "analysis", "src.intelligence", "src.render", "src.pipelines", "scripts.narrative_window",
        "src.source_selection", "src.normalization", "src.synchronization", "src.world_model",
        "NormalizedPossession", "TacticalFinding", "ActionChain", "NarrativeStep",
    )
    text = "\n".join(path.read_text() for path in sorted(Path("src/action_graph").glob("*.py")))
    hits = sorted(token for token in forbidden if token in text)
    return {"passed": not hits, "forbidden_import_or_symbol_hits": hits}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-result", default="not run by diagnostic generator")
    args = parser.parse_args()
    unsupported = {
        "PASS": "Recognition has no authenticated event type or passer-recipient action assertion.",
        "BALL_RECEIPT": "Recognition has no authenticated receipt or possession-transition assertion.",
        "CARRY": "Recognition has movement states but no authenticated ball ownership or carry interval.",
        "SHOT": "Recognition has no authenticated event type or shot assertion.",
        "ACTOR_RECIPIENT_RELATION": "Recognition participants describe state subjects, not event actor and recipient roles.",
        "SAME_PLAYER_FOOTBALL_CONTINUATION": "Adjacent state recurrence does not prove continuation of a football action.",
        "CAUSAL_RELATION": "Recognition contains no normative causal evidence.",
        "TACTICAL_PATTERN": "Pattern Recognition is outside this slice and atomic states do not prove a pattern.",
    }
    report = {
        "schema_id": "tip.action_graph_diagnostic",
        "contract_version": "0.1.0",
        "implemented_action_catalogue": [item.action_type for item in ACTION_TYPES],
        "implemented_relation_catalogue": [item.relation_type for item in RELATION_TYPES],
        "deliberately_unsupported_actions": unsupported,
        "import_isolation_result": isolation(),
        "fixtures": [positive("locatelli", 3788754, 40), positive("depay", 3869117, 20), negative("di_maria", 3869685, 52)],
        "full_test_result": args.test_result,
    }
    target = Path("audit/action_graph/action_graph_diagnostic.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_bytes(report))
    print(target)
    for fixture in report["fixtures"]:
        print(fixture["fixture"], fixture["status"], fixture.get("frame_count"), fixture.get("action_graph_node_count"), fixture.get("action_graph_edge_count"), fixture.get("action_graph_sha256"), fixture.get("failure_code"))


if __name__ == "__main__":
    main()
