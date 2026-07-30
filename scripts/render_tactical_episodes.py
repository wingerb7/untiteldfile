from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOCAL_CACHE = ROOT / "renders" / ".cache"
LOCAL_MPLCONFIG = ROOT / "renders" / ".matplotlib"
LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
LOCAL_MPLCONFIG.mkdir(parents=True, exist_ok=True)
import os

os.environ.setdefault("XDG_CACHE_HOME", str(LOCAL_CACHE))
os.environ.setdefault("MPLCONFIGDIR", str(LOCAL_MPLCONFIG))

from analysis.normalize import load_and_normalize
from src.domain.models import NormalizedPossession, TacticalFinding
from src.ingest.possession_loader import load_normalized_possession
from src.intelligence.patterns.line_break import LineBreakConfig, detect_line_breaking_passes
from src.intelligence.patterns.positional import PositionalPatternConfig, detect_positional_patterns
from src.intelligence.reasoning.rank_findings import rank_findings
from src.pipelines.narrative_config import apply_narrative, load_narrative_config
from src.pipelines.provenance import validate_config_match
from src.pipelines.render_analysis import load_config, render_scene_plan
from src.scene_direction import SceneDirection, build_scene_direction
from src.tactical_episodes import TacticalEpisode, TacticalEpisodeDataset, build_tactical_episodes
from src.tactical_relevance import PlayerRelevance, classify_episode_players
from src.tactical_story.episodic_scene_plan import build_episodic_scene_plan

OUTPUT = ROOT / "renders" / "tactical_episodes"

# Fixture identity only (which files to load); all tactical reasoning below is generic.
FIXTURES = (
    ("depay", ROOT / "data" / "depay_goal.json", ROOT / "narratives" / "depay.yaml"),
    ("locatelli", ROOT / "data" / "second_goal.json", ROOT / "narratives" / "locatelli.yaml"),
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")


def _detect_findings(possession: NormalizedPossession) -> list[TacticalFinding]:
    findings = [
        *detect_line_breaking_passes(possession, LineBreakConfig()),
        *detect_positional_patterns(possession, PositionalPatternConfig()),
    ]
    return rank_findings(possession, findings)


def _episode_dict(episode: TacticalEpisode) -> dict[str, Any]:
    return asdict(episode)


def _direction_dict(direction: SceneDirection) -> dict[str, Any]:
    return asdict(direction)


def _relevance_dict(record: PlayerRelevance) -> dict[str, Any]:
    return asdict(record)


def _build_narrative(dataset: TacticalEpisodeDataset) -> dict[str, Any]:
    return {
        "schema_id": "tip.tactical_episode_narrative",
        "match_id": dataset.match_id,
        "possession_id": dataset.possession_id,
        "beats": [
            {
                "ordinal": index,
                "episode_id": episode.episode_id,
                "episode_type": episode.episode_type,
                "tactical_question": episode.tactical_question,
                "caption": f"{episode.cause} {episode.created_advantage}".strip(),
                "decisive_action": episode.decisive_action,
                "confidence": episode.confidence,
            }
            for index, episode in enumerate(dataset.episodes, start=1)
        ],
    }


def _build_audit_trace(
    possession: NormalizedPossession,
    dataset: TacticalEpisodeDataset,
    relevance_by_episode: dict[str, list[PlayerRelevance]],
) -> dict[str, Any]:
    covered_event_ids = {event_id for episode in dataset.episodes for event_id in episode.participating_action_ids}
    omitted_event_ids = [event.event_id for event in possession.events if event.event_id not in covered_event_ids]
    episodes_trace = []
    for episode in dataset.episodes:
        records = relevance_by_episode[episode.episode_id]
        episodes_trace.append(
            {
                "episode_id": episode.episode_id,
                "episode_type": episode.episode_type,
                "why_selected": episode.cause,
                "tactical_question_answered": episode.tactical_question,
                "grouped_action_ids": episode.participating_action_ids,
                "grouped_action_count": len(episode.participating_action_ids),
                "opponents_retained": [
                    {"player_id": record.player_id, "reason": record.reason, "relevance_score": record.relevance_score}
                    for record in records
                    if record.category != "MANDATORY"
                ],
                "supporting_evidence": episode.evidence,
                "confidence": episode.confidence,
            }
        )
    return {
        "schema_id": "tip.tactical_episode_audit_trace",
        "match_id": dataset.match_id,
        "possession_id": dataset.possession_id,
        "total_possession_events": len(possession.events),
        "events_covered_by_episodes": len(covered_event_ids),
        "events_omitted_or_compressed": omitted_event_ids,
        "omission_reason": (
            "Events outside a selected episode's window belong to circulation that did not meet any generic "
            "tactical-pattern threshold (line break, width, switch, third-man, free man, cutback, late support, "
            "overload, press escape, half-space entry, box arrival); they are compressed into the surrounding "
            "episode's play segment rather than given their own scene."
        ),
        "episodes": episodes_trace,
    }


def render_fixture(slug: str, source: Path, narrative_path: Path) -> dict[str, Any]:
    out = OUTPUT / slug
    possession = load_normalized_possession(source)
    findings = _detect_findings(possession)
    dataset = build_tactical_episodes(possession, findings)

    relevance_by_episode: dict[str, list[PlayerRelevance]] = {}
    directions: dict[str, SceneDirection] = {}
    for episode in dataset.episodes:
        records = classify_episode_players(possession, episode)
        relevance_by_episode[episode.episode_id] = records
        directions[episode.episode_id] = build_scene_direction(possession, episode, records)

    scene_plan = build_episodic_scene_plan(possession, dataset.episodes, directions)
    narrative = _build_narrative(dataset)
    audit_trace = _build_audit_trace(possession, dataset, relevance_by_episode)

    _write_json(out / "tactical_episodes.json", {"episodes": [_episode_dict(episode) for episode in dataset.episodes]})
    _write_json(out / "scene_directions.json", {"directions": [_direction_dict(directions[e.episode_id]) for e in dataset.episodes]})
    _write_json(out / "narrative.json", narrative)
    _write_json(out / "scene_plan.json", scene_plan)
    _write_json(out / "audit_trace.json", audit_trace)

    render_possession = load_and_normalize(source)
    config = load_config(ROOT / "config.yaml")
    narrative_config = load_narrative_config(narrative_path)
    validate_config_match(narrative_config, render_possession.get("match_id"), render_possession.get("possession_id"))
    resolved_config = apply_narrative(config, narrative_config)

    consumer_config = json.loads(json.dumps(resolved_config))
    consumer_plan = json.loads(json.dumps(scene_plan))
    consumer_plan["presentation"] = {"hide_event_hud": True, "mode": "consumer"}
    render_scene_plan(render_possession, consumer_plan, consumer_config, out / f"{slug}_consumer.mp4")

    audit_config = json.loads(json.dumps(resolved_config))
    audit_plan = json.loads(json.dumps(scene_plan))
    audit_plan["presentation"] = {"hide_event_hud": False, "mode": "audit"}
    render_scene_plan(render_possession, audit_plan, audit_config, out / f"{slug}_audit.mp4")

    return {"fixture": slug, "episode_count": len(dataset.episodes), "episode_types": [e.episode_type for e in dataset.episodes]}


def main() -> None:
    results = [render_fixture(*fixture) for fixture in FIXTURES]
    _write_json(OUTPUT / "render_results.json", {"schema_id": "tip.tactical_episode_render_results", "results": results})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
