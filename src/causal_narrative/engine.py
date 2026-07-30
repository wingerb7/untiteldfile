from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
from typing import Any

from src.action_continuation.engine import MEDIA_TYPE as CONTINUATION_MEDIA_TYPE
from src.action_graph.engine import MEDIA_TYPE as GRAPH_MEDIA_TYPE
from src.contracts import Artifact
from src.graph_tactical_episodes.engine import MEDIA_TYPE as EPISODE_MEDIA_TYPE

from .errors import CausalNarrativeError
from .models import CausalNarrativeSelection, CausalNarrativeUnit, NarrativeExclusion


MEDIA_TYPE = "application/vnd.tip.causal-narrative-selection+json"
CONTRACT_VERSION = "0.1.0"
ROLES = frozenset({"SETUP", "PROGRESSION", "DECISIVE_MECHANISM", "FINAL_ACTION", "FINISH"})
EXCLUSIONS = frozenset({
    "SECONDARY_CONTEXT",
    "GROUPED_PROGRESSION",
    "OUTSIDE_DECISIVE_CAUSAL_SPINE",
    "DUPLICATIVE_FOR_NARRATIVE",
})
CAPTIONS = {
    "SETUP": "An authenticated line-breaking action establishes the attack.",
    "PROGRESSION": "Connected authenticated actions sustain the progression.",
    "DECISIVE_MECHANISM": "The authenticated passing chain creates the decisive mechanism.",
    "FINAL_ACTION": "The final authenticated action supplies the finish.",
    "FINISH": "The authenticated sequence concludes with the shot.",
}
PURPOSES = {
    "SETUP": "Establish the initial tactical structure of the decisive attack.",
    "PROGRESSION": "Summarize connected progression without restating each atomic detection.",
    "DECISIVE_MECHANISM": "Show the causal actions that construct the scoring mechanism.",
    "FINAL_ACTION": "Show the final action directly enabling the shot.",
    "FINISH": "Conclude the causal story with the authenticated shot.",
}


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()}"


def _key(episode: dict[str, Any]) -> tuple[Any, ...]:
    return (*episode["start_ordering_key"], *episode["end_ordering_key"], episode["episode_id"])


def _validate_inputs(episodes: Artifact, graph: Artifact, continuation: Artifact) -> None:
    if not isinstance(episodes, Artifact) or not episodes.validated or not episodes.authentic(
        EPISODE_MEDIA_TYPE, "tip.graph_backed_tactical_episode_dataset"
    ):
        raise CausalNarrativeError("TIP-CNS-EPISODE-ARTIFACT-INVALID")
    if not isinstance(graph, Artifact) or not graph.validated or not graph.authentic(
        GRAPH_MEDIA_TYPE, "tip.action_graph_dataset"
    ):
        raise CausalNarrativeError("TIP-CNS-GRAPH-ARTIFACT-INVALID")
    if not isinstance(continuation, Artifact) or not continuation.validated or not continuation.authentic(
        CONTINUATION_MEDIA_TYPE, "tip.action_continuation_dataset"
    ):
        raise CausalNarrativeError("TIP-CNS-CONTINUATION-ARTIFACT-INVALID")
    if episodes["action_graph_sha256"] != graph.sha256 or continuation["action_graph_sha256"] != graph.sha256:
        raise CausalNarrativeError("TIP-CNS-UPSTREAM-HASH-INVALID")
    contexts = {(item["match_id"], item["possession_id"]) for item in (episodes, graph, continuation)}
    if len(contexts) != 1:
        raise CausalNarrativeError("TIP-CNS-CONTEXT-MISMATCH")


def _chain_ids(relation: dict[str, Any]) -> set[str]:
    return {
        relation["source_node_id"],
        relation["target_node_id"],
        *(item["action_graph_node_id"] for item in relation["intervening_events"]),
    }


def _connections(
    ordered: list[dict[str, Any]],
    continuation: Artifact,
) -> tuple[dict[tuple[str, str], tuple[str, ...]], dict[str, set[str]]]:
    relation_chains = [(relation, _chain_ids(relation)) for relation in continuation["relations"]]
    links: dict[tuple[str, str], tuple[str, ...]] = {}
    adjacency = {episode["episode_id"]: set() for episode in ordered}
    for first in ordered:
        first_nodes = set(first["supporting_action_node_ids"])
        for second in ordered:
            if _key(second) <= _key(first):
                continue
            second_nodes = set(second["supporting_action_node_ids"])
            relation_ids = tuple(sorted(
                relation["edge_id"]
                for relation, chain in relation_chains
                if chain & first_nodes and chain & second_nodes
            ))
            if relation_ids:
                links[(first["episode_id"], second["episode_id"])] = relation_ids
                adjacency[first["episode_id"]].add(second["episode_id"])
    return links, adjacency


def _reaches(start: str, finish: str, adjacency: dict[str, set[str]]) -> bool:
    pending = [start]
    seen = set()
    while pending:
        current = pending.pop()
        if current == finish:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(sorted(adjacency.get(current, ()) - seen, reverse=True))
    return False


def _participants(episode: dict[str, Any], graph_nodes: dict[str, dict[str, Any]]) -> tuple[str | None, str | None]:
    pass_node = next(
        (graph_nodes[node_id] for node_id in episode["supporting_action_node_ids"]
         if graph_nodes[node_id]["action_type"] == "PASS_EVENT"),
        None,
    )
    if pass_node is None:
        return None, None
    return pass_node.get("actor"), pass_node.get("recipient")


def _unit(
    role: str,
    members: list[dict[str, Any]],
    continuation_ids: tuple[str, ...],
) -> CausalNarrativeUnit:
    episode_ids = tuple(item["episode_id"] for item in members)
    source_ids = tuple(dict.fromkeys(
        event_id for item in members for event_id in item["authenticated_source_event_ids"]
    ))
    graph_ids = tuple(sorted({
        relation_id for item in members for relation_id in item["supporting_relation_ids"]
    }))
    actors = tuple(dict.fromkeys(
        actor for item in members for actor in item["primary_actor_ids"]
    ))
    unit_id = _id("causal_unit", role, *episode_ids, *continuation_ids)
    return CausalNarrativeUnit(
        "tip.causal_narrative_unit",
        unit_id,
        role,
        episode_ids[-1],
        episode_ids,
        source_ids,
        graph_ids,
        continuation_ids,
        tuple(members[0]["start_ordering_key"]),
        tuple(members[-1]["end_ordering_key"]),
        actors,
        None,
        None,
        PURPOSES[role],
        CAPTIONS[role],
        tuple(dict.fromkeys(
            limitation for item in members for limitation in item["limitations"]
        )),
        {
            "operation": "SELECT_AUTHENTICATED_CAUSAL_NARRATIVE_UNIT",
            "role": role,
            "ordered_member_episode_ids": episode_ids,
            "presentation_abstraction_only": len(members) > 1,
        },
    )


def _build(episodes: Artifact, graph: Artifact, continuation: Artifact) -> dict[str, Any]:
    source = sorted(list(episodes["episodes"]), key=_key)
    if len({item["episode_id"] for item in source}) != len(source):
        raise CausalNarrativeError("TIP-CNS-EPISODE-DUPLICATE")
    if any(tuple(item["end_ordering_key"]) < tuple(item["start_ordering_key"]) for item in source):
        raise CausalNarrativeError("TIP-CNS-ORDERING-INVALID")
    finishes = [item for item in source if item["episode_type"] == "FINISH"]
    if not finishes:
        raise CausalNarrativeError("TIP-CNS-FINISH-MISSING")
    finish = max(finishes, key=_key)
    nodes = {node["node_id"]: node for node in graph["nodes"]}
    finish_node = nodes[finish["supporting_action_node_ids"][-1]]
    finish_actor = finish_node.get("actor")
    links, adjacency = _connections(source, continuation)
    causal = [
        item for item in source
        if item["episode_id"] == finish["episode_id"]
        or _reaches(item["episode_id"], finish["episode_id"], adjacency)
    ]
    causal.sort(key=_key)
    preceding = [item for item in causal if item["episode_id"] != finish["episode_id"]]
    if not preceding:
        raise CausalNarrativeError("TIP-CNS-FINAL-ACTION-MISSING")
    final_action = preceding[-1]
    prefix = preceding[:-1]

    mechanism_index = None
    for index in range(len(prefix) - 1, -1, -1):
        actor, _ = _participants(prefix[index], nodes)
        if actor == finish_actor and _reaches(prefix[index]["episode_id"], final_action["episode_id"], adjacency):
            mechanism_index = index
            break
    if mechanism_index is None and prefix:
        mechanism_index = len(prefix) - 1

    units: list[CausalNarrativeUnit] = []
    selected_ids: set[str] = set()
    grouped_ids: set[str] = set()
    if mechanism_index is not None:
        earlier = prefix[:mechanism_index]
        mechanism = prefix[mechanism_index:]
    else:
        earlier, mechanism = [], []
    if earlier:
        setup = earlier[0]
        units.append(_unit("SETUP", [setup], ()))
        selected_ids.add(setup["episode_id"])
        group_members = earlier[1:]
        if group_members:
            continuation_ids: set[str] = set()
            valid_group = True
            for first, second in zip(group_members, group_members[1:]):
                edge_ids = links.get((first["episode_id"], second["episode_id"]), ())
                _, first_receiver = _participants(first, nodes)
                second_actor, _ = _participants(second, nodes)
                if (
                    not edge_ids
                    or _key(second) <= _key(first)
                    or first_receiver is None
                    or first_receiver != second_actor
                ):
                    valid_group = False
                    break
                continuation_ids.update(edge_ids)
            if len(group_members) == 1:
                # A single intervening episode is progression, but not a grouped abstraction.
                units.append(_unit("PROGRESSION", group_members, ()))
                selected_ids.add(group_members[0]["episode_id"])
            elif valid_group:
                if len({item["episode_id"] for item in group_members}) != len(group_members):
                    raise CausalNarrativeError("TIP-CNS-GROUP-DUPLICATE")
                units.append(_unit("PROGRESSION", group_members, tuple(sorted(continuation_ids))))
                selected_ids.update(item["episode_id"] for item in group_members)
                grouped_ids.update(item["episode_id"] for item in group_members)
    for item in mechanism:
        units.append(_unit("DECISIVE_MECHANISM", [item], ()))
        selected_ids.add(item["episode_id"])
    units.append(_unit("FINAL_ACTION", [final_action], ()))
    selected_ids.add(final_action["episode_id"])
    units.append(_unit("FINISH", [finish], ()))
    selected_ids.add(finish["episode_id"])

    if not any(unit.narrative_role == "FINAL_ACTION" for unit in units):
        raise CausalNarrativeError("TIP-CNS-FINAL-ACTION-MISSING")
    if units[-1].narrative_role != "FINISH":
        raise CausalNarrativeError("TIP-CNS-FINISH-ORDERING-INVALID")
    for first, second in zip(units, units[1:]):
        if second.start_ordering_key < first.start_ordering_key:
            raise CausalNarrativeError("TIP-CNS-ORDERING-INVALID")
    units = [
        replace(
            unit,
            causal_predecessor_unit_id=units[index - 1].unit_id if index else None,
            causal_successor_unit_id=units[index + 1].unit_id if index + 1 < len(units) else None,
        )
        for index, unit in enumerate(units)
    ]
    exclusions = []
    causal_ids = {item["episode_id"] for item in causal}
    for item in source:
        episode_id = item["episode_id"]
        if episode_id in selected_ids:
            if episode_id not in grouped_ids:
                continue
            classification = "GROUPED_PROGRESSION"
            reason = "Retained inside one presentation-only progression unit."
            relation = "ENABLING"
        elif episode_id in causal_ids:
            classification = "SECONDARY_CONTEXT"
            reason = "Authenticated and causal, but lacks a unique narrative purpose."
            relation = "ENABLING"
        else:
            classification = "OUTSIDE_DECISIVE_CAUSAL_SPINE"
            reason = "No authenticated continuation path connects this episode to the selected finish."
            relation = "CHRONOLOGICAL_ONLY"
        exclusions.append(NarrativeExclusion(
            "tip.causal_narrative_exclusion",
            episode_id,
            classification,
            reason,
            relation,
            {
                "operation": "CLASSIFY_AUTHENTICATED_EPISODE_FOR_NARRATIVE",
                "source_episode_id": episode_id,
                "source_episode_dataset_sha256": episodes.sha256,
            },
        ))
    result = CausalNarrativeSelection(
        "tip.causal_narrative_selection",
        CONTRACT_VERSION,
        episodes.sha256,
        graph.sha256,
        continuation.sha256,
        episodes["match_id"],
        episodes["possession_id"],
        tuple(item["episode_id"] for item in sorted(finishes, key=_key)),
        finish["episode_id"],
        tuple(units),
        tuple(sorted(exclusions, key=lambda item: item.episode_id)),
        tuple(item["episode_id"] for item in source),
        "FINISH_ANCHORED_AUTHENTICATED_CONTINUATION_THEN_CAUSAL_ROLE;CANONICAL_ORDER_TIE_BREAK",
        (
            "Narrative grouping is a presentation abstraction and does not create a tactical fact.",
            "Only existing LINE_BREAK, RETURN_COMBINATION, FINISH, and continuation evidence is described.",
        ),
        {
            "graph_episode_dataset_sha256": episodes.sha256,
            "action_graph_sha256": graph.sha256,
            "action_continuation_sha256": continuation.sha256,
        },
    )
    return asdict(result)


def build_causal_narrative_selection(
    episodes: Artifact,
    graph: Artifact,
    continuation: Artifact,
) -> Artifact:
    _validate_inputs(episodes, graph, continuation)
    artifact = Artifact(_build(episodes, graph, continuation), MEDIA_TYPE, continuation.sha256, continuation.source_hashes)
    return validate_causal_narrative_selection(artifact, episodes, graph, continuation)


def validate_causal_narrative_selection(
    selection: Artifact,
    episodes: Artifact,
    graph: Artifact,
    continuation: Artifact,
) -> Artifact:
    _validate_inputs(episodes, graph, continuation)
    if not isinstance(selection, Artifact) or not selection.authentic(MEDIA_TYPE, "tip.causal_narrative_selection"):
        raise CausalNarrativeError("TIP-CNS-ARTIFACT-INVALID")
    expected = _build(episodes, graph, continuation)
    if selection.payload != expected:
        raise CausalNarrativeError("TIP-CNS-PROVENANCE-INVALID")
    data = selection.payload
    if data["contract_version"] != CONTRACT_VERSION or selection.direct_input_sha256 != continuation.sha256:
        raise CausalNarrativeError("TIP-CNS-UPSTREAM-HASH-INVALID")
    units = data["units"]
    if not units or units[-1]["narrative_role"] != "FINISH":
        raise CausalNarrativeError("TIP-CNS-FINISH-MISSING")
    if any(unit["narrative_role"] not in ROLES for unit in units):
        raise CausalNarrativeError("TIP-CNS-ROLE-INVALID")
    if len({unit["unit_id"] for unit in units}) != len(units):
        raise CausalNarrativeError("TIP-CNS-UNIT-DUPLICATE")
    if any(item["classification"] not in EXCLUSIONS for item in data["exclusions"]):
        raise CausalNarrativeError("TIP-CNS-EXCLUSION-INVALID")
    source_payload_before = episodes.payload
    if episodes.payload != source_payload_before:
        raise CausalNarrativeError("TIP-CNS-SOURCE-MUTATED")
    return selection.validated_copy()
