"""Generate the evidence audit for the authenticated semantic foundations sprint."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.action_graph import build_action_graph_dataset
from src.contracts import canonical_bytes
from src.normalization import build_normalized_dataset
from src.perception import build_perception_dataset, validate_perception_dataset
from src.recognition import build_recognition_dataset
from src.source_selection import PINNED_REVISION, select_source_documents
from src.synchronization import build_synchronized_dataset
from src.world_model import build_world_model_dataset, validate_world_model_dataset

BASE = Path("data/open-data/data")


def row(concept: str, required: str, available: str, missing: str, threshold: str,
        supportable: bool, layer: str, decision: str, observed: str = "DERIVED",
        window: str = "NO", roles: str = "NO") -> dict:
    return {"concept": concept, "required_evidence": required, "available_evidence": available,
            "missing_evidence": missing, "threshold_required": threshold,
            "temporal_window_required": window, "actor_or_recipient_roles_available": roles,
            "ball_position_continuously_available": False,
            "player_identity_stable_across_required_frames": False,
            "evidence_kind": observed, "deterministic_and_validatable": supportable,
            "normatively_supportable_now": supportable, "target_layer": layer,
            "implementation_decision": decision}


MATRIX = [
    row("BALL_CONTROLLED", "controller candidate; distance/relative velocity/persistence; tie, aerial and missing-data rules", "event-ball position; partial player positions; ownership UNKNOWN", "all control rules and continuous observations", "YES", False, "Recognition", "REJECT"),
    row("BALL_FREE", "proof no player controls ball under a complete control model", "ownership UNKNOWN", "complete control model; UNKNOWN is not negative evidence", "YES", False, "Recognition", "REJECT"),
    row("BALL_RECEIVED", "prior release, recipient identity, arrival/control transfer time", "pass recipient retained upstream; sparse event times", "authenticated Recognition input for event semantics; arrival/control evidence", "YES", False, "Recognition", "REJECT", window="YES", roles="UPSTREAM_ONLY"),
    row("BALL_RELEASED", "controller identity and proven release boundary", "event actor retained upstream; event time", "control state and authenticated event-semantics input", "YES", False, "Recognition", "REJECT", window="YES", roles="ACTOR_UPSTREAM_ONLY"),
    row("BALL_LOST", "proven prior control and subsequent absence/transfer", "sparse states; ownership UNKNOWN", "control model and complete transition observations", "YES", False, "Recognition", "REJECT", window="YES"),
    row("BALL_RECOVERED", "proven free/opponent-controlled to controlled transition", "sparse states; ownership UNKNOWN", "control model and complete transition observations", "YES", False, "Recognition", "REJECT", window="YES"),
    row("PASS_START", "source pass semantic plus rule equating event timestamp to named boundary", "pass type, actor, recipient, timestamp retained upstream", "event semantics are outside Recognition input; physical-start equivalence not defined", "NO", False, "Action Graph", "REJECT; source event is not a proven physical start", observed="SOURCE_DECLARED_UPSTREAM", roles="UPSTREAM_ONLY"),
    row("PASS_END", "physical arrival/end time and recipient/control evidence", "source duration/end position upstream", "duration semantic does not prove arrival/control; no authenticated Recognition input", "NO", False, "Action Graph", "REJECT", observed="SOURCE_DECLARED_UPSTREAM", window="YES", roles="UPSTREAM_ONLY"),
    row("CARRY_START", "source carry semantic plus proven control/start boundary", "carry type, actor, timestamp upstream", "control evidence and authenticated Recognition input", "YES", False, "Action Graph", "REJECT", observed="SOURCE_DECLARED_UPSTREAM", window="YES", roles="ACTOR_UPSTREAM_ONLY"),
    row("CARRY_END", "proven control interval end", "source duration/end position upstream", "control evidence and physical end semantics", "YES", False, "Action Graph", "REJECT", observed="SOURCE_DECLARED_UPSTREAM", window="YES", roles="ACTOR_UPSTREAM_ONLY"),
    row("SHOT", "authenticated source-declared shot type, actor and timestamp", "all retained upstream", "narrow authenticated event-evidence input to Recognition is not specified", "NO", False, "Recognition then Action Graph", "REJECT; no layer bypass", observed="SOURCE_DECLARED_UPSTREAM", roles="ACTOR_UPSTREAM_ONLY"),
    row("PLAYER_CAN_REACH_BALL", "movement model, acceleration/speed/reaction constants, horizon and ball trajectory", "distance and sparse finite-difference velocities", "all normative kinematic constants and continuous trajectory", "YES", False, "Recognition", "REJECT"),
    row("PLAYER_CANNOT_REACH_BALL", "complete reachability model plus proven negative within horizon", "distance and sparse finite-difference velocities", "complete model; unavailable cannot prove cannot", "YES", False, "Recognition", "REJECT"),
    row("PASSING_CORRIDOR_OPEN", "geometry plus normative meaning of open for a pass", "two-metre corridor and observed occupancy", "visibility completeness and football-open semantics", "YES", False, "Recognition", "REJECT; retain PASSING_CORRIDOR_EXISTS"),
    row("PASSING_CORRIDOR_CLOSED", "complete proof corridor is unusable", "observed occupancy greater than zero", "visibility completeness and football-closed semantics", "YES", False, "Recognition", "REJECT; retain PASSING_CORRIDOR_OBSTRUCTED"),
    row("PLAYER_BALL_DISTANCE", "same-state unique Player and Ball positions", "authenticated World observations and PAIR_DISTANCE", "none; unavailable dependency is explicit", "NO", True, "Perception", "IMPLEMENT"),
]


def documents(match_id: int) -> tuple[list, list]:
    return (json.loads((BASE / f"events/{match_id}.json").read_text()),
            json.loads((BASE / f"three-sixty/{match_id}.json").read_text()))


def positive(name: str, match_id: int, possession_id: int) -> dict:
    events, frames = documents(match_id)
    request = {"source_dataset": "statsbomb-open-data", "source_revision": PINNED_REVISION,
               "match_id": match_id, "possession_id": possession_id}
    selection = select_source_documents(events, frames, request)
    normalized = build_normalized_dataset(selection)
    synchronized = build_synchronized_dataset(normalized)
    world = validate_world_model_dataset(build_world_model_dataset(synchronized))
    perception = validate_perception_dataset(build_perception_dataset(world), source_hashes=world.source_hashes)
    recognition = build_recognition_dataset(perception)
    graph = build_action_graph_dataset(recognition)
    repeated = build_action_graph_dataset(recognition)
    measurements = [f for frame in perception["frames"] for f in frame["features"]
                    if f["feature_code"] == "PLAYER_BALL_DISTANCE"]
    return {"fixture": name, "status": "SUCCEEDED", "frame_count": len(perception["frames"]),
            "perception_feature_count": sum(len(f["features"]) for f in perception["frames"]),
            "recognition_record_count": recognition["metadata"]["record_count"],
            "action_graph_node_count": len(graph["nodes"]), "action_graph_edge_count": len(graph["edges"]),
            "new_concept_counts": {}, "new_action_type_counts": {}, "new_relation_type_counts": {},
            "perception_addition_counts": {"PLAYER_BALL_DISTANCE": len(measurements),
                "AVAILABLE": sum(f["status"] == "AVAILABLE" for f in measurements),
                "UNAVAILABLE": sum(f["status"] == "UNAVAILABLE" for f in measurements)},
            "hashes": {"selection": selection.sha256, "normalized": normalized.sha256,
                "synchronized": synchronized.sha256, "world_model": world.sha256,
                "perception": perception.sha256, "recognition": recognition.sha256,
                "action_graph": graph.sha256},
            "repeated_run_deterministic": graph.canonical_bytes() == repeated.canonical_bytes(),
            "validation_result": "PASSED"}


def negative() -> dict:
    events, frames = documents(3869685)
    try:
        select_source_documents(events, frames, {"source_dataset": "statsbomb-open-data",
            "source_revision": PINNED_REVISION, "match_id": 3869685, "possession_id": 52})
    except Exception as exc:
        return {"fixture": "di_maria", "status": "UPSTREAM_REJECTED", "stage": getattr(exc, "stage", "unknown"),
                "failure_code": getattr(exc, "code", type(exc).__name__), "downstream_executed": False,
                "validation_result": "NOT_EXECUTED"}
    raise RuntimeError("Di María unexpectedly passed source selection")


def isolation() -> dict:
    forbidden = {"analysis", "src.intelligence", "src.render", "src.pipelines", "TacticalFinding", "ActionChain", "NarrativeStep"}
    hits = set()
    for root in (Path("src/perception"), Path("src/recognition"), Path("src/action_graph")):
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text())
            modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            modules += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
            text = path.read_text()
            hits.update(item for item in forbidden if item in modules or item in text)
    return {"passed": not hits, "forbidden_import_or_symbol_hits": sorted(hits)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-result", required=True)
    args = parser.parse_args()
    report = {"schema_id": "tip.semantic_foundations_diagnostic", "contract_version": "0.1.0",
        "concept_audit_matrix": MATRIX, "implemented_concepts": [],
        "implemented_measurements": ["PLAYER_BALL_DISTANCE"],
        "rejected_concepts": {r["concept"]: r["missing_evidence"] for r in MATRIX if not r["normatively_supportable_now"]},
        "thresholds_and_constants": [], "perception_additions": ["PLAYER_BALL_DISTANCE"],
        "recognition_additions": [], "action_graph_additions": [],
        "fixtures": [positive("locatelli", 3788754, 40), positive("depay", 3869117, 20), negative()],
        "import_isolation_result": isolation(), "full_test_result": args.test_result}
    target = Path("audit/semantic_foundations/semantic_foundations_diagnostic.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_bytes(report))
    print(target)


if __name__ == "__main__":
    main()
