from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.render_tactical_storytelling import upstream
from src.contracts import artifact_metrics, reset_artifact_metrics
from src.graph_tactical_episodes import build_graph_backed_tactical_episode_dataset


FIXTURES = {
    "locatelli": (3788754, 40),
    "depay": (3869117, 20),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", choices=FIXTURES)
    args = parser.parse_args()
    match_id, possession_id = FIXTURES[args.fixture]
    reset_artifact_metrics()
    started = time.perf_counter()
    recognition, graph, _, _, patterns, perception = upstream(
        match_id, possession_id, include_perception=True
    )
    episodes = build_graph_backed_tactical_episode_dataset(recognition, graph, patterns)
    elapsed = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports KiB.
    peak_bytes = peak if peak > 10_000_000 else peak * 1024
    crossing_records = [
        record
        for frame in recognition["frames"]
        for record in frame["records"]
        if record["concept_code"] == "PASS_CROSSES_DEFENSIVE_LINE"
    ]
    crossing_edges = [
        edge
        for edge in graph["edges"]
        if edge["relation_type"] == "PASS_CROSSES_DEFENSIVE_LINE"
    ]
    endpoint_feature_ids = {
        feature["feature_id"]
        for frame in perception["frames"]
        for feature in frame["features"]
        if feature["feature_code"] in {"PASS_START_POSITION", "PASS_END_POSITION"}
        and feature["status"] == "AVAILABLE"
    }
    line_breaks = [
        episode for episode in episodes["episodes"]
        if episode["episode_type"] == "LINE_BREAK"
    ]
    print(json.dumps({
        "fixture": args.fixture,
        "wall_seconds": round(elapsed, 6),
        "peak_rss_bytes": int(peak_bytes),
        "metrics": artifact_metrics(),
        "recognition_sha256": recognition.sha256,
        "action_graph_sha256": graph.sha256,
        "episode_dataset_sha256": episodes.sha256,
        "episode_types": [episode["episode_type"] for episode in episodes["episodes"]],
        "endpoint_perception_feature_count": len(endpoint_feature_ids),
        "crossing_recognition_count": len(crossing_records),
        "graph_crossing_relation_count": len(crossing_edges),
        "line_break_episode_count": len(line_breaks),
        "completed": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
