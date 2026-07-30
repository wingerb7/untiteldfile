from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.render_tactical_storytelling import OPEN_DATA
from src.action_continuation import build_action_continuation_dataset
from src.action_graph import build_action_graph_dataset
from src.contracts import Artifact
from src.graph_tactical_episodes import build_graph_backed_tactical_episode_dataset
from src.normalization import build_normalized_dataset
from src.perception import build_perception_dataset, validate_perception_dataset
from src.recognition import build_recognition_dataset
from src.semantic_resolution import build_semantic_resolution_dataset
from src.source_selection import PINNED_REVISION, select_source_documents
from src.synchronization import build_synchronized_dataset
from src.tactical_patterns import detect_return_combination_patterns
from src.world_model import build_world_model_dataset, validate_world_model_dataset


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "audit/line_break_production"
FIXTURES = {"locatelli": (3788754, 40), "depay": (3869117, 20)}
PRIOR_DIAGNOSTIC_CROSSINGS = {
    "locatelli": {
        "event:statsbomb:60719aaf-0c36-4aa6-a13f-ad6c69943646",
        "event:statsbomb:98a22299-e98a-486d-b6cf-5b25a7659b89",
        "event:statsbomb:e51fde20-708e-49e4-ae77-5bc768e5f411",
    },
    "depay": {
        "event:statsbomb:b3a34ac0-981c-4ad0-8155-be43abeac9b5",
        "event:statsbomb:671c26ef-5cdb-4628-8e92-6a37309cc5b8",
        "event:statsbomb:7ec90a6a-4dde-4be8-bacd-4d6a77f65600",
        "event:statsbomb:ac15aa15-db77-464e-89c6-e0ab2dce8077",
        "event:statsbomb:8d6e145c-7e04-420d-b346-3514e3fbfb9b",
        "event:statsbomb:d3264b17-4393-4e4d-8970-51128f9d9bf3",
        "event:statsbomb:fb2800dc-0e2c-42f6-9708-aaf3caf2b6e7",
        "event:statsbomb:f13d1fcc-d78b-4932-a6ae-f24f0e153753",
    },
}


def _raw(event_id: str) -> str:
    return event_id.removeprefix("event:statsbomb:")


def _position(feature: dict[str, Any]) -> tuple[float, float] | None:
    value = (feature.get("value") or {}).get("position2") or {}
    x, y = value.get("x_m"), value.get("y_m")
    return (float(x), float(y)) if isinstance(x, (int, float)) and isinstance(y, (int, float)) else None


def _ordering(node: dict[str, Any]) -> tuple[int, float, str]:
    return node["world_state_index"], node["canonical_time_seconds"], node.get("event_id") or node["node_id"]


def _candidate(
    fixture: str,
    evidence: dict[str, Any],
    frame: dict[str, Any],
    normalized_event: dict[str, Any] | None,
    world: Artifact,
    recognition: Artifact,
    graph: Artifact,
    episodes: Artifact,
) -> dict[str, Any]:
    available = [feature for feature in frame["features"] if feature["status"] == "AVAILABLE"]
    absolute = {
        feature["subject_ids"][0]: feature
        for feature in available
        if feature["feature_code"] == "ABSOLUTE_POSITION"
        and len(feature["subject_ids"]) == 1
        and feature["subject_ids"][0].startswith("player:")
        and _position(feature) is not None
    }
    positions = {player: _position(feature) for player, feature in absolute.items()}
    all_connections = [
        feature for feature in frame["features"]
        if feature["feature_code"] == "CONNECTION_DISTANCE"
        and len(feature["subject_ids"]) == 2
    ]
    connections=[feature for feature in all_connections if feature["status"]=="AVAILABLE" and all(subject in positions for subject in feature["subject_ids"])]
    adjacency = {player: set() for player in positions}
    for feature in all_connections:
        first, second = feature["subject_ids"]
        adjacency.setdefault(first,set()).add(second)
        adjacency.setdefault(second,set()).add(first)
    actor, receiver = evidence["actor"], evidence["recipient"]
    attacking: set[str] = set()
    pending = [actor]
    while pending:
        player = pending.pop()
        if player in attacking:
            continue
        attacking.add(player)
        pending.extend(sorted(adjacency.get(player, ()) - attacking))
    opponents = sorted(set(positions) - attacking)
    player_team = {player["player_id"]: player["team_id"] for player in world["players"]}
    defender_teams = sorted({player_team.get(player) for player in opponents if player_team.get(player)})
    line_candidates = []
    for anchor in opponents:
        members = tuple(sorted(player for player in opponents if abs(positions[player][0] - positions[anchor][0]) <= 4.0))
        xs = [positions[player][0] for player in members]
        ys = [positions[player][1] for player in members]
        span = max(ys) - min(ys) if ys else 0.0
        mean_x = sum(xs) / len(xs) if xs else None
        member_connections=[feature for feature in connections if set(feature["subject_ids"])<=set(members)]
        line_candidates.append({
            "anchor_defender_id": anchor,
            "defender_ids": members,
            "defender_count": len(members),
            "defender_positions": [
                {
                    "defender_id": player,
                    "position": {"x_m": positions[player][0], "y_m": positions[player][1]},
                    "absolute_position_feature_id": absolute[player]["feature_id"],
                    "input_observation_ids": absolute[player]["input_observation_ids"],
                }
                for player in members
            ],
            "longitudinal_compactness_m": (max(xs) - min(xs)) if xs else None,
            "lateral_span_m": span,
            "calculated_line_x_m": mean_x,
            "has_at_least_three_defenders": len(members) >= 3,
            "has_meaningful_lateral_span": span >= 8.0,
            "connection_distance_feature_ids":sorted(feature["feature_id"] for feature in member_connections),
            "has_connection_distance_evidence":bool(member_connections),
            "valid": len(members) >= 3 and span >= 8.0 and bool(member_connections),
        })
    valid = [candidate for candidate in line_candidates if candidate["valid"]]
    selected = min(
        valid,
        key=lambda candidate: (
            -candidate["defender_count"],
            -candidate["lateral_span_m"],
            candidate["calculated_line_x_m"],
            candidate["defender_ids"],
        ),
        default=None,
    )
    recognition_frame = recognition["frames"][frame["world_state_index"]]
    line_records = [
        record for record in recognition_frame["records"]
        if record["concept_code"] == "DEFENSIVE_LINE_STATE"
    ]
    crossing_records = [
        record for record in recognition_frame["records"]
        if record["concept_code"] == "PASS_CROSSES_DEFENSIVE_LINE"
    ]
    graph_nodes = {node["node_id"]: node for node in graph["nodes"]}
    event_node = next(
        (node for node in graph_nodes.values() if node.get("event_evidence_id") == evidence["event_id"]),
        None,
    )
    crossing_edges = [
        edge for edge in graph["edges"]
        if edge["relation_type"] == "PASS_CROSSES_DEFENSIVE_LINE"
        and event_node is not None and edge["source_node_id"] == event_node["node_id"]
    ]
    related_edges = [
        edge for edge in graph["edges"]
        if edge["relation_type"] == "SOURCE_RELATED_EVENT"
        and event_node is not None and edge["source_node_id"] == event_node["node_id"]
    ]
    receipts = []
    for edge in related_edges:
        target = graph_nodes[edge["target_node_id"]]
        if target["action_type"] == "BALL_RECEIPT_EVENT":
            receipts.append({
                "event_id": target["event_id"],
                "actor": target["actor"],
                "timestamp": target["timestamp"],
                "action_node_id": target["node_id"],
                "relation_id": edge["edge_id"],
                "after_pass": target["timestamp"] > evidence["canonical_timestamp"],
                "actor_matches_declared_receiver": target["actor"] == receiver,
            })
    line_x = selected["calculated_line_x_m"] if selected else None
    start_feature=next((feature for feature in available if feature["feature_code"]=="PASS_START_POSITION" and tuple(feature["subject_ids"])==(evidence["event_id"],)),None)
    end_feature=next((feature for feature in available if feature["feature_code"]=="PASS_END_POSITION" and tuple(feature["subject_ids"])==(evidence["event_id"],)),None)
    origin=_position(start_feature) if start_feature else None
    observed_receiver=_position(end_feature) if end_feature else None
    origin_side = None if line_x is None or origin is None else origin[0] - line_x
    endpoint_side = None if line_x is None or observed_receiver is None else observed_receiver[0] - line_x
    episode_matches = [
        episode for episode in episodes["episodes"]
        if episode["episode_type"] == "LINE_BREAK"
        and event_node is not None
        and event_node["node_id"] in episode["supporting_action_node_ids"]
    ]
    if start_feature is None:
        status, first_failure = "UNSUPPORTED", "PASS_START_POSITION_MISSING"
    elif end_feature is None:
        status, first_failure = "UNSUPPORTED", "PASS_END_POSITION_MISSING"
    elif selected is None:
        status, first_failure = "UNSUPPORTED", "DEFENSIVE_LINE_RECOGNITION_REJECTED"
    elif origin_side is None or endpoint_side is None or origin_side * endpoint_side >= 0:
        status, first_failure = "WARN", "PASS_DOES_NOT_CROSS_RECOGNIZED_LINE"
    elif not crossing_records:
        status, first_failure = "UNSUPPORTED", "CROSSING_RECOGNITION_NOT_EMITTED"
    elif not crossing_edges:
        status, first_failure = "UNSUPPORTED", "ACTION_GRAPH_CROSSING_RELATION_NOT_EMITTED"
    elif evidence["outcome"] != "COMPLETED":
        status, first_failure = "UNSUPPORTED", "PASS_NOT_SOURCE_DECLARED_COMPLETE"
    elif not receipts:
        status, first_failure = "WARN", "RELATED_RECEIPT_MISSING"
    elif not any(receipt["after_pass"] and receipt["actor_matches_declared_receiver"] for receipt in receipts):
        status, first_failure = "UNSUPPORTED", "RECEIVER_CONTROL_NOT_AUTHENTICATED"
    elif not episode_matches:
        status, first_failure = "UNSUPPORTED", "ELIGIBLE_EPISODE_NOT_CONSTRUCTED"
    else:
        status, first_failure = "PASS", None
    source_start = (normalized_event or {}).get("start_position")
    source_end = (normalized_event or {}).get("end_position")
    return {
        "source_event_id": evidence["event_id"],
        "passer": actor,
        "declared_receiver": receiver,
        "pass_timestamp": evidence["canonical_timestamp"],
        "pass_completion_status": evidence["outcome"],
        "related_event_ids": evidence["related_event_ids"],
        "source_pass_start_position": source_start,
        "source_pass_end_position": source_end,
        "evaluated_origin_position": None if origin is None else {"x_m": origin[0], "y_m": origin[1]},
        "evaluated_endpoint_position": None if observed_receiver is None else {"x_m": observed_receiver[0], "y_m": observed_receiver[1]},
        "pass_start_feature_id": start_feature["feature_id"] if start_feature else None,
        "pass_end_feature_id": end_feature["feature_id"] if end_feature else None,
        "endpoint_semantics": "AUTHENTICATED_SOURCE_PASS_START_AND_END_POSITION",
        "coordinate_system": "canonical pitch metres, 105x68",
        "perception_frame_id": frame["perception_frame_id"],
        "applicable_perception_feature_ids": sorted(feature["feature_id"] for feature in available if actor in feature["subject_ids"] or receiver in feature["subject_ids"] or evidence["event_id"] in feature["subject_ids"]),
        "defensive_team_ids": defender_teams,
        "attacking_component_player_ids": sorted(attacking),
        "opponent_candidate_player_ids": opponents,
        "connection_distance_feature_ids": sorted(feature["feature_id"] for feature in connections),
        "candidate_lines": line_candidates,
        "selected_line": selected,
        "candidate_defensive_line_recognition_ids": [record["recognition_id"] for record in line_records],
        "crossing_recognition_ids": [record["recognition_id"] for record in crossing_records],
        "origin_signed_distance_to_line_m": origin_side,
        "endpoint_signed_distance_to_line_m": endpoint_side,
        "authenticated_opposite_sides": origin_side is not None and endpoint_side is not None and origin_side * endpoint_side < 0,
        "crossing_relation_emitted": bool(crossing_edges),
        "pass_action_node_id": event_node["node_id"] if event_node else None,
        "crossing_relation_ids": [edge["edge_id"] for edge in crossing_edges],
        "related_receipts": receipts,
        "line_break_episode_ids": [episode["episode_id"] for episode in episode_matches],
        "graph_episode_eligibility": status == "PASS",
        "prior_audit_only_diagnostic_crossing": evidence["event_id"] in PRIOR_DIAGNOSTIC_CROSSINGS[fixture],
        "geometric_crossing_decision": "CROSSES" if origin_side is not None and endpoint_side is not None and origin_side * endpoint_side < 0 else "DOES_NOT_CROSS",
        "authenticated_crossing_recognition_decision": "EMITTED" if crossing_records else "NOT_EMITTED",
        "completed_pass_decision": "AUTHENTICATED_COMPLETED" if evidence["outcome"] == "COMPLETED" else "NOT_COMPLETED",
        "authenticated_related_receipt_decision": "PRESENT_AFTER_PASS" if any(receipt["after_pass"] for receipt in receipts) else "NOT_PRESENT_AFTER_PASS",
        "receiver_identity_decision": "MATCHES_DECLARED_RECEIVER" if any(receipt["after_pass"] and receipt["actor_matches_declared_receiver"] for receipt in receipts) else "NOT_AUTHENTICATED",
        "final_episode_eligibility": "ELIGIBLE" if status == "PASS" else "INELIGIBLE",
        "final_status": status,
        "first_failing_condition": first_failure,
        "source_data_limitation": source_end is None,
        "previous_rejection_reason": "INCOMPLETE_ABSOLUTE_POSITION_EVIDENCE",
        "implementation_defect": None,
    }


def audit_fixture(name: str) -> dict[str, Any]:
    match_id, possession_id = FIXTURES[name]
    started = time.perf_counter()
    events = json.loads((OPEN_DATA / f"events/{match_id}.json").read_text())
    frames = json.loads((OPEN_DATA / f"three-sixty/{match_id}.json").read_text())
    selection = select_source_documents(events, frames, {
        "source_dataset": "statsbomb-open-data",
        "source_revision": PINNED_REVISION,
        "match_id": match_id,
        "possession_id": possession_id,
    })
    normalized = build_normalized_dataset(selection)
    synchronized = build_synchronized_dataset(normalized)
    world = validate_world_model_dataset(build_world_model_dataset(synchronized))
    perception = validate_perception_dataset(build_perception_dataset(world), source_hashes=world.source_hashes)
    recognition = build_recognition_dataset(perception)
    graph = build_action_graph_dataset(recognition)
    semantic = build_semantic_resolution_dataset(graph, recognition)
    continuation = build_action_continuation_dataset(graph, recognition, semantic)
    patterns = detect_return_combination_patterns(continuation, graph, recognition, semantic)
    episodes = build_graph_backed_tactical_episode_dataset(recognition, graph, patterns)
    normalized_events = {event["event_id"]: event for event in normalized["events"]}
    candidates = []
    for index, evidence in enumerate(recognition["event_evidence"]):
        if evidence["event_type"] != "PASS" or evidence["outcome"] != "COMPLETED":
            continue
        candidates.append(_candidate(
            name,
            evidence,
            perception["frames"][index],
            normalized_events.get(evidence["event_id"]),
            world,
            recognition,
            graph,
            episodes,
        ))
    line_breaks = [episode for episode in episodes["episodes"] if episode["episode_type"] == "LINE_BREAK"]
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = peak if peak > 10_000_000 else peak * 1024
    return {
        "schema_id": "tip.line_break_production_audit",
        "contract_version": "0.1.0",
        "fixture": name,
        "match_id": match_id,
        "possession_id": possession_id,
        "artifact_hashes": {
            "world_model": world.sha256,
            "perception": perception.sha256,
            "recognition": recognition.sha256,
            "action_graph": graph.sha256,
            "graph_backed_episodes": episodes.sha256,
        },
        "line_break_episode_ids": [episode["episode_id"] for episode in line_breaks],
        "final_verdict": "PASS" if line_breaks else "UNSUPPORTED",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "audit_measurement": {
            "wall_seconds": round(time.perf_counter() - started, 6),
            "peak_rss_bytes": int(peak_bytes),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", choices=FIXTURES)
    args = parser.parse_args()
    result = audit_fixture(args.fixture)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f"{args.fixture}_line_break_trace.json"
    path.write_text(json.dumps(result, sort_keys=True, indent=2, default=float) + "\n")
    print(json.dumps({"path": str(path), **result["audit_measurement"], "candidate_count": result["candidate_count"], "verdict": result["final_verdict"]}, sort_keys=True))


if __name__ == "__main__":
    main()
