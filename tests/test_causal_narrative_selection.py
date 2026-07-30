from copy import deepcopy
from pathlib import Path

import pytest

from src.action_continuation.engine import MEDIA_TYPE as CONTINUATION_MEDIA_TYPE
from src.action_graph.engine import MEDIA_TYPE as GRAPH_MEDIA_TYPE
from src.causal_narrative import CausalNarrativeError, build_causal_narrative_selection
from src.contracts import Artifact
from src.graph_tactical_episodes.engine import MEDIA_TYPE as EPISODE_MEDIA_TYPE


def _fixture(
    *,
    include_finish=True,
    duplicate=False,
    unrelated=False,
    group_connected=True,
    contradictory_group=False,
    reverse=False,
    second_finish=False,
):
    nodes = []
    episodes = []
    specifications = [
        ("setup", "a", "b"),
        ("group1", "c", "d"),
        ("group2", "d" if not contradictory_group else "x", "e"),
        ("mechanism", "shooter", "f"),
        ("final", "f", "shooter"),
    ]
    for index, (name, actor, receiver) in enumerate(specifications):
        pass_id, line_id, receipt_id = f"pass:{name}", f"line:{name}", f"receipt:{name}"
        nodes.extend([
            {"node_id": pass_id, "action_type": "PASS_EVENT", "actor": actor, "recipient": receiver},
            {"node_id": line_id, "action_type": "DEFENSIVE_LINE_STATE", "actor": None, "recipient": None},
            {"node_id": receipt_id, "action_type": "BALL_RECEIPT_EVENT", "actor": receiver, "recipient": None},
        ])
        start = (index, float(index), f"event:{name}")
        end = (index, float(index) + 0.5, f"receipt-event:{name}")
        if reverse and name == "setup":
            start, end = end, start
        episodes.append({
            "episode_id": f"episode:{name}",
            "episode_type": "LINE_BREAK",
            "start_ordering_key": start,
            "end_ordering_key": end,
            "supporting_action_node_ids": (pass_id, line_id, receipt_id),
            "supporting_relation_ids": (f"cross:{name}", f"related:{name}"),
            "authenticated_source_event_ids": (f"event:{name}", f"receipt-event:{name}"),
            "primary_actor_ids": (actor, receiver),
            "relevant_participant_ids": (),
            "recognition_record_ids": (),
            "perception_feature_ids": (),
            "confidence": 1.0,
            "limitations": (),
        })
    if unrelated:
        specifications = specifications[1:]
    finish_ids = []
    if include_finish:
        for offset in range(2 if second_finish else 1):
            suffix = "finish2" if offset else "finish"
            timestamp = 6.0 + offset
            node_id = f"shot:{suffix}"
            nodes.append({"node_id": node_id, "action_type": "SHOT_EVENT", "actor": "shooter", "recipient": None})
            episodes.append({
                "episode_id": f"episode:{suffix}",
                "episode_type": "FINISH",
                "start_ordering_key": (6 + offset, timestamp, f"event:{suffix}"),
                "end_ordering_key": (6 + offset, timestamp, f"event:{suffix}"),
                "supporting_action_node_ids": (node_id,),
                "supporting_relation_ids": (),
                "authenticated_source_event_ids": (f"event:{suffix}",),
                "primary_actor_ids": ("shooter",),
                "relevant_participant_ids": (),
                "recognition_record_ids": (),
                "perception_feature_ids": (),
                "confidence": 1.0,
                "limitations": (),
            })
            finish_ids.append(node_id)
    graph = Artifact(
        {
            "schema_id": "tip.action_graph_dataset",
            "match_id": "match:test",
            "possession_id": "possession:test",
            "nodes": tuple(nodes),
            "edges": (),
        },
        GRAPH_MEDIA_TYPE,
        validated=True,
    )
    relations = []
    episode_by_name = {item["episode_id"].split(":")[-1]: item for item in episodes}
    pairs = [("setup", "group1"), ("group1", "group2"), ("group2", "mechanism"), ("mechanism", "final")]
    if not group_connected:
        pairs.remove(("group1", "group2"))
    if unrelated:
        pairs.remove(("setup", "group1"))
    if include_finish:
        pairs.append(("final", "finish2" if second_finish else "finish"))
    for index, (first, second) in enumerate(pairs):
        first_nodes = episode_by_name[first]["supporting_action_node_ids"]
        second_nodes = episode_by_name[second]["supporting_action_node_ids"]
        relations.append({
            "edge_id": f"continuation:{index}",
            "source_node_id": first_nodes[-1],
            "target_node_id": second_nodes[0],
            "intervening_events": (),
        })
    continuation = Artifact(
        {
            "schema_id": "tip.action_continuation_dataset",
            "match_id": "match:test",
            "possession_id": "possession:test",
            "action_graph_sha256": graph.sha256,
            "relations": tuple(relations),
        },
        CONTINUATION_MEDIA_TYPE,
        validated=True,
    )
    episode_payload = {
        "schema_id": "tip.graph_backed_tactical_episode_dataset",
        "match_id": "match:test",
        "possession_id": "possession:test",
        "action_graph_sha256": graph.sha256,
        "episodes": tuple(episodes + ([episodes[0]] if duplicate else [])),
    }
    episode_artifact = Artifact(episode_payload, EPISODE_MEDIA_TYPE, validated=True)
    return episode_artifact, graph, continuation


def test_selects_setup_grouped_progression_decisive_final_and_finish():
    episodes, graph, continuation = _fixture()
    before = episodes.payload
    selection = build_causal_narrative_selection(episodes, graph, continuation)
    assert [unit["narrative_role"] for unit in selection["units"]] == [
        "SETUP", "PROGRESSION", "DECISIVE_MECHANISM", "FINAL_ACTION", "FINISH"
    ]
    progression = selection["units"][1]
    assert progression["supporting_episode_ids"] == ("episode:group1", "episode:group2")
    assert progression["selection_provenance"]["presentation_abstraction_only"] is True
    assert episodes.payload == before


def test_no_finish_anchor_and_final_action_omission_are_rejected():
    episodes, graph, continuation = _fixture(include_finish=False)
    with pytest.raises(CausalNarrativeError, match="TIP-CNS-FINISH-MISSING"):
        build_causal_narrative_selection(episodes, graph, continuation)

    episodes, graph, continuation = _fixture()
    payload = continuation.data
    payload["relations"] = tuple(
        relation for relation in payload["relations"]
        if relation["target_node_id"] != "shot:finish"
    )
    continuation = Artifact(payload, CONTINUATION_MEDIA_TYPE, validated=True)
    with pytest.raises(CausalNarrativeError, match="TIP-CNS-FINAL-ACTION-MISSING"):
        build_causal_narrative_selection(episodes, graph, continuation)


def test_multiple_finishes_selects_latest_authenticated_candidate():
    episodes, graph, continuation = _fixture(second_finish=True)
    selection = build_causal_narrative_selection(episodes, graph, continuation)
    assert selection["finish_candidate_episode_ids"] == ("episode:finish", "episode:finish2")
    assert selection["selected_finish_episode_id"] == "episode:finish2"


def test_unrelated_same_possession_line_break_is_not_selected_from_chronology():
    episodes, graph, continuation = _fixture(unrelated=True)
    selection = build_causal_narrative_selection(episodes, graph, continuation)
    exclusion = next(item for item in selection["exclusions"] if item["episode_id"] == "episode:setup")
    assert exclusion["classification"] == "OUTSIDE_DECISIVE_CAUSAL_SPINE"
    assert exclusion["causal_relation_to_finish"] == "CHRONOLOGICAL_ONLY"


def test_grouping_requires_continuation_and_consistent_control():
    episodes, graph, continuation = _fixture(group_connected=False)
    selection = build_causal_narrative_selection(episodes, graph, continuation)
    assert not any(
        len(unit["supporting_episode_ids"]) > 1 for unit in selection["units"]
    )

    episodes, graph, continuation = _fixture(contradictory_group=True)
    selection = build_causal_narrative_selection(episodes, graph, continuation)
    assert not any(
        len(unit["supporting_episode_ids"]) > 1 for unit in selection["units"]
    )


def test_duplicate_episode_and_reversed_chronology_are_rejected():
    episodes, graph, continuation = _fixture(duplicate=True)
    with pytest.raises(CausalNarrativeError, match="TIP-CNS-EPISODE-DUPLICATE"):
        build_causal_narrative_selection(episodes, graph, continuation)
    episodes, graph, continuation = _fixture(reverse=True)
    with pytest.raises(CausalNarrativeError, match="TIP-CNS-ORDERING-INVALID"):
        build_causal_narrative_selection(episodes, graph, continuation)


def test_input_order_does_not_change_semantic_output():
    episodes, graph, continuation = _fixture()
    first = build_causal_narrative_selection(episodes, graph, continuation)
    payload = episodes.data
    payload["episodes"] = tuple(reversed(payload["episodes"]))
    reordered = Artifact(payload, EPISODE_MEDIA_TYPE, validated=True)
    second = build_causal_narrative_selection(reordered, graph, continuation)
    assert first["units"] == second["units"]
    assert [
        (item["episode_id"], item["classification"], item["causal_relation_to_finish"])
        for item in first["exclusions"]
    ] == [
        (item["episode_id"], item["classification"], item["causal_relation_to_finish"])
        for item in second["exclusions"]
    ]
    assert first["selected_finish_episode_id"] == second["selected_finish_episode_id"]


def test_captions_cannot_introduce_unsupported_concepts_or_legacy_fallback():
    episodes, graph, continuation = _fixture()
    selection = build_causal_narrative_selection(episodes, graph, continuation)
    forbidden = {"box entry", "final third", "overload", "free man"}
    assert all(
        not any(term in unit["factual_caption"].lower() for term in forbidden)
        for unit in selection["units"]
    )
    source = Path("src/pipelines/causal_narrative_route.py").read_text()
    assert "action_chain_for" not in source
    assert "build_tactical_episodes" not in source
