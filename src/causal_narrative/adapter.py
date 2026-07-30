from __future__ import annotations

from src.contracts import Artifact
from src.tactical_episodes.models import TacticalEpisode


def adapt_causal_units_for_scene_direction(
    selection: Artifact,
    graph_episodes: Artifact,
) -> list[TacticalEpisode]:
    episodes = {item["episode_id"]: item for item in graph_episodes["episodes"]}
    result = []
    for unit in selection["units"]:
        members = [episodes[episode_id] for episode_id in unit["supporting_episode_ids"]]
        event_ids = [
            event_id.removeprefix("event:statsbomb:")
            for event_id in unit["source_event_ids"]
        ]
        actors = list(dict.fromkeys(
            actor.removeprefix("player:statsbomb:") for member in members
            for actor in (*member["primary_actor_ids"], *member["relevant_participant_ids"])
        ))
        result.append(TacticalEpisode(
            episode_id=unit["unit_id"],
            episode_type="PROGRESSION" if unit["narrative_role"] == "PROGRESSION" else members[-1]["episode_type"],
            start_event_id=event_ids[0],
            end_event_id=event_ids[-1],
            participating_action_ids=event_ids,
            primary_actor_ids=actors,
            relevant_defender_ids=[],
            tactical_question=unit["tactical_purpose"],
            cause=unit["factual_caption"],
            created_advantage="",
            decisive_action=unit["tactical_purpose"],
            evidence={
                "graph_backed": True,
                "causal_narrative_unit_id": unit["unit_id"],
                "narrative_role": unit["narrative_role"],
                "supporting_episode_ids": list(unit["supporting_episode_ids"]),
                "graph_relation_ids": list(unit["graph_relation_ids"]),
                "continuation_relation_ids": list(unit["continuation_relation_ids"]),
            },
            confidence=min(float(member["confidence"]) for member in members),
            limitations=list(unit["limitations"]),
            eligibility_verdict="CAUSAL_NARRATIVE_SELECTED",
            selection_reasons=[unit["tactical_purpose"]],
        ))
    return result
