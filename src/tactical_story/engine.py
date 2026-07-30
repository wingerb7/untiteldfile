from __future__ import annotations

import hashlib

from src.contracts import Artifact
from src.tactical_patterns import validate_tactical_pattern_dataset


MEDIA_TYPE = "application/vnd.tip.tactical-story+json"


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()}"


def build_tactical_story(patterns: Artifact, continuation: Artifact, graph: Artifact, recognition: Artifact, semantic: Artifact, display_names: dict[str, str] | None = None) -> Artifact | None:
    validate_tactical_pattern_dataset(patterns, continuation, graph, recognition, semantic)
    if not patterns["matches"]:
        return None
    match = patterns["matches"][0]
    names = dict(sorted((display_names or {}).items()))
    initial = names.get(match["initial_actor_id"], match["initial_actor_id"])
    teammate = names.get(match["teammate_actor_id"], match["teammate_actor_id"])
    by_role = {action["role"]: action for action in match["actions"]}
    beat_specs = (
        (
            "initial_pass_and_continuation",
            by_role["initial_pass"],
            by_role["teammate_receipt"],
            f"Watch {initial} after the pass.",
            "What happens after the first pass?",
            ("initial_passer", "first_receiver"),
        ),
        (
            "teammate_carry",
            by_role["teammate_receipt"],
            by_role["return_pass"],
            f"{teammate} receives, carries, then returns the ball.",
            "How does the ball come back?",
            ("ball_carrier", "return_receiver"),
        ),
        (
            "return_arrival_and_shot",
            by_role["return_pass"],
            by_role["finish"],
            f"The return reaches {initial}; the shot follows.",
            "Where does the combination end?",
            ("return_passer", "return_receiver", "shooter"),
        ),
    )
    beats = tuple({
        "schema_id": "tip.tactical_story_beat", "beat_id": _id("story_beat", match["pattern_id"], role),
        "ordinal": ordinal, "beat_type": role, "start_event_uuid": start["event_uuid"], "end_event_uuid": end["event_uuid"],
        "actor_ids": tuple(dict.fromkeys((start["actor_id"], end["actor_id"]))), "caption": caption,
        "football_question": question, "participant_roles": participant_roles,
        "caption_schedule": {"lead_seconds": 0.75, "fade_in_seconds": 0.25, "fade_out_seconds": 0.25},
        "supporting_action_node_ids": (
            (by_role["initial_pass"]["node_id"], by_role["return_receipt"]["node_id"])
            if role == "initial_pass_and_continuation" else
            tuple(action["node_id"] for action in match["actions"] if start["canonical_ordering_key"] <= action["canonical_ordering_key"] <= end["canonical_ordering_key"])
        ),
    } for ordinal, (role, start, end, caption, question, participant_roles) in enumerate(beat_specs, 1))
    data = {
        "schema_id": "tip.tactical_story", "contract_version": "0.1.0", "pattern_dataset_sha256": patterns.sha256,
        "match_id": patterns["match_id"], "possession_id": patterns["possession_id"], "story_id": _id("tactical_story", match["pattern_id"]),
        "pattern_id": match["pattern_id"], "selection_rule": "FIRST_CANONICAL_VALID_RETURN_COMBINATION",
        "beats": beats, "display_names": names,
    }
    return Artifact(data, MEDIA_TYPE, patterns.sha256, patterns.source_hashes, validated=True)
