from __future__ import annotations

import hashlib
from typing import Any

from src.action_continuation import validate_action_continuation_dataset
from src.contracts import Artifact

from .errors import NarrativeAdapterError


MEDIA_TYPE = "application/vnd.tip.continuation-narrative+json"
CAPTIONS = {
    "PASS_EVENT": "Watch {player} after releasing the ball.",
    "BALL_RECEIPT_EVENT": "{player} becomes involved again.",
    "CARRY_EVENT": "{player} continues with the ball.",
    "SHOT_EVENT": "The sequence reaches {player}'s shot.",
}


def _identifier(prefix: str, *parts: str) -> str:
    return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()}"


def build_continuation_narrative(continuation: Artifact, action_graph: Artifact, recognition: Artifact, semantic: Artifact, display_names: dict[str, str] | None = None) -> Artifact:
    try:
        validate_action_continuation_dataset(continuation, action_graph, recognition, semantic)
    except Exception as exc:
        raise NarrativeAdapterError("TIP-NAR-UPSTREAM-INVALID") from exc
    names = dict(sorted((display_names or {}).items()))
    if any(not isinstance(key, str) or not isinstance(value, str) or not value for key, value in names.items()):
        raise NarrativeAdapterError("TIP-NAR-DISPLAY-NAME-INVALID")
    relations = continuation["relations"]
    shots = sorted((relation for relation in relations if relation["target_action_type"] == "SHOT_EVENT"), key=lambda relation: (relation["target_ordering_key"], relation["edge_id"]))
    if not shots:
        raise NarrativeAdapterError("TIP-NAR-NO-SHOT-CHAIN")
    terminal = shots[0]
    incoming = {relation["target_node_id"]: relation for relation in relations}
    chain_relations = [terminal]
    while chain_relations[0]["source_node_id"] in incoming:
        chain_relations.insert(0, incoming[chain_relations[0]["source_node_id"]])
    player_id = terminal["player_id"]
    if any(relation["player_id"] != player_id for relation in chain_relations):
        raise NarrativeAdapterError("TIP-NAR-CHAIN-INVALID")
    endpoints = [(chain_relations[0]["source_node_id"], chain_relations[0]["source_event_uuid"], chain_relations[0]["source_event_evidence_id"], chain_relations[0]["source_action_type"], chain_relations[0]["source_ordering_key"])]
    endpoints.extend((relation["target_node_id"], relation["target_event_uuid"], relation["target_event_evidence_id"], relation["target_action_type"], relation["target_ordering_key"]) for relation in chain_relations)
    label = names.get(player_id, player_id)
    steps = []
    for ordinal, (node_id, uuid, event_id, action_type, ordering_key) in enumerate(endpoints):
        steps.append({
            "schema_id": "tip.continuation_narrative_step", "step_id": _identifier("narrative_step", node_id),
            "ordinal": ordinal, "step_type": action_type.lower(), "event_id": event_id.removeprefix("event:statsbomb:"),
            "source_event_uuid": uuid, "action_graph_node_id": node_id, "actor_id": player_id,
            "caption": CAPTIONS[action_type].format(player=label), "canonical_ordering_key": ordering_key,
        })
    data = {
        "schema_id": "tip.continuation_narrative", "contract_version": "0.1.0",
        "continuation_dataset_sha256": continuation.sha256, "match_id": continuation["match_id"],
        "possession_id": continuation["possession_id"], "selection_rule": "FIRST_CANONICAL_CHAIN_ENDING_IN_AUTHENTICATED_SHOT",
        "chain_id": _identifier("narrative_chain", *(relation["edge_id"] for relation in chain_relations)),
        "player_id": player_id, "supporting_continuation_edge_ids": tuple(relation["edge_id"] for relation in chain_relations),
        "steps": tuple(steps), "display_names": names,
        "episode": {
            "episode_type": "SUPPORTED_SAME_PLAYER_CONTINUATION",
            "football_question": "How does the same player return to the move?",
            "participant_ids": (player_id,),
            "caption_schedule": {"lead_seconds": 0.75, "fade_in_seconds": 0.25, "fade_out_seconds": 0.25},
        },
    }
    return Artifact(data, MEDIA_TYPE, continuation.sha256, continuation.source_hashes, validated=True)
