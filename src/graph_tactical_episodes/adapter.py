from __future__ import annotations

from src.contracts import Artifact
from src.tactical_episodes.models import TacticalEpisode, TacticalEpisodeDataset


_COPY = {
    "LINE_BREAK": (
        "How does the pass get in behind the defensive line?",
        "Authenticated evidence supports a pass beyond the defensive line.",
        "The receiver gains access behind the defensive block.",
        "The line-breaking pass.",
    ),
    "RETURN_COMBINATION": (
        "How does the first player return to finish the move?",
        "A pass, teammate advance, and authenticated return reconnect the initial player to the move.",
        "The combination restores the initial player in a decisive position.",
        "The return combination.",
    ),
    "FINISH": (
        "How does the sequence end?",
        "The supported sequence concludes with an authenticated shot.",
        "The attack is converted into an attempt on goal.",
        "The shot.",
    ),
}


def _raw_event_id(event_id: str) -> str:
    return event_id.removeprefix("event:statsbomb:")


def adapt_graph_episodes_for_rendering(dataset: Artifact) -> TacticalEpisodeDataset:
    episodes: list[TacticalEpisode] = []
    for graph_episode in dataset["episodes"]:
        question, cause, advantage, decisive = _COPY[graph_episode["episode_type"]]
        event_ids = [_raw_event_id(event_id) for event_id in graph_episode["authenticated_source_event_ids"]]
        evidence = {
            "graph_backed": True,
            "supporting_action_node_ids": list(graph_episode["supporting_action_node_ids"]),
            "supporting_relation_ids": list(graph_episode["supporting_relation_ids"]),
            "authenticated_source_event_ids": list(graph_episode["authenticated_source_event_ids"]),
            "recognition_record_ids": list(graph_episode["recognition_record_ids"]),
            "perception_feature_ids": list(graph_episode["perception_feature_ids"]),
            "causal_evidence_summary": graph_episode["causal_evidence_summary"],
            "temporal_context_node_ids": list(graph_episode["temporal_context_node_ids"]),
        }
        actors = list(dict.fromkeys((*graph_episode["primary_actor_ids"], *graph_episode["relevant_participant_ids"])))
        episodes.append(
            TacticalEpisode(
                episode_id=graph_episode["episode_id"],
                episode_type=graph_episode["episode_type"],
                start_event_id=event_ids[0],
                end_event_id=event_ids[-1],
                participating_action_ids=event_ids,
                primary_actor_ids=actors,
                relevant_defender_ids=[],
                tactical_question=question,
                cause=cause,
                created_advantage=advantage,
                decisive_action=decisive,
                evidence=evidence,
                confidence=float(graph_episode["confidence"]),
                limitations=list(graph_episode["limitations"]),
                eligibility_verdict="GRAPH_AUTHENTICATED",
                selection_reasons=[graph_episode["causal_evidence_summary"]],
            )
        )
    return TacticalEpisodeDataset(
        match_id=str(dataset["match_id"]),
        possession_id=int(str(dataset["possession_id"]).rsplit(":", 1)[-1]),
        episodes=episodes,
    )
