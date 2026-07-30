import json
from pathlib import Path


DIRECTORY = Path("audit/line_break_granularity")


def _read(name: str) -> dict:
    path = DIRECTORY / name
    data = json.loads(path.read_text())
    assert path.read_text() == json.dumps(data, sort_keys=True, indent=2) + "\n"
    return data


def test_production_line_breaks_have_unique_authenticated_causal_signatures():
    expected = {"locatelli": (1, 0), "depay": (6, 15)}
    for fixture, (episode_count, pair_count) in expected.items():
        audit = _read(f"{fixture}_granularity.json")
        assert audit["episode_count"] == episode_count
        assert len(audit["pairwise_comparisons"]) == pair_count
        assert audit["granularity_assessment"] == "CORRECT"
        assert audit["implementation_defect"] is None
        assert all(pair["verdict"] == "DISTINCT" for pair in audit["pairwise_comparisons"])
        assert all(not pair["identical_authenticated_causal_evidence"] for pair in audit["pairwise_comparisons"])
        assert not any(audit["graph_quality_checks"]["duplicate_counts"].values())
        assert all(
            len({
                episode["source_pass_event_id"],
                episode["related_receipt_event_id"],
            }) == 2
            for episode in audit["episodes"]
        )


def test_dependency_graph_contains_each_episode_causal_chain():
    dependency = _read("dependency_graph.json")
    fixtures = {item["fixture"]: item for item in dependency["fixtures"]}
    for fixture, episode_count in {"locatelli": 1, "depay": 6}.items():
        graph = fixtures[fixture]
        nodes = {node["id"]: node for node in graph["nodes"]}
        edges = graph["edges"]
        episodes = [node for node in nodes.values() if node["type"] == "LINE_BREAK_EPISODE"]
        assert len(episodes) == episode_count
        assert sum(edge["type"] == "PASS_CROSSES_DEFENSIVE_LINE" for edge in edges) == episode_count
        assert sum(edge["type"] == "SOURCE_RELATED_EVENT" for edge in edges) == episode_count
        assert sum(edge["type"] == "SUPPORTS" for edge in edges) == episode_count * 2
