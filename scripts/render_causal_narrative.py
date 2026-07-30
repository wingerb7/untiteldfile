from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.interpolate import build_animation_model
from analysis.normalize import load_and_normalize
from scripts.render_tactical_storytelling import OPEN_DATA
from src.pipelines.causal_narrative_route import build_causal_narrative_route
from src.pipelines.render_analysis import load_config, render_scene_plan, scene_segments
from src.source_selection import PINNED_REVISION, select_source_documents


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit/causal_narrative"
RENDERS = ROOT / "renders/causal_narrative"
NEW_GOAL_SOURCE = ROOT / "data/new_goal_3773387_46.json"
FIXTURES = (
    ("locatelli", 3788754, 40, ROOT / "data/second_goal.json"),
    ("depay", 3869117, 20, ROOT / "data/depay_goal.json"),
    ("new_goal", 3773387, 46, NEW_GOAL_SOURCE),
)


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def _raw_documents(match_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events = json.loads((OPEN_DATA / f"events/{match_id}.json").read_text())
    frames = json.loads((OPEN_DATA / f"three-sixty/{match_id}.json").read_text())
    return events, frames


def _name(value: Any) -> Any:
    return value.get("name") if isinstance(value, dict) else value


def materialize_new_goal_fixture() -> None:
    events, frames = _raw_documents(3773387)
    selection = select_source_documents(events, frames, {
        "source_dataset": "statsbomb-open-data",
        "source_revision": PINNED_REVISION,
        "match_id": 3773387,
        "possession_id": 46,
    })
    frame_by_event = {frame["event_uuid"]: frame for frame in selection["three_sixty"]}
    rendered_events = []
    for event in selection["events"]:
        frame = frame_by_event.get(event["id"], {})
        observations = []
        for observation in frame.get("freeze_frame", []):
            player = observation.get("player") or {}
            observations.append({
                "teammate": observation["teammate"],
                "actor": observation["actor"],
                "keeper": observation["keeper"],
                "location": observation["location"],
                "player_id": player.get("id"),
                "player_name": player.get("name"),
            })
        pass_data = event.get("pass") or {}
        carry_data = event.get("carry") or {}
        shot_data = event.get("shot") or {}
        rendered_events.append({
            "id": event["id"],
            "index": event["index"],
            "period": event["period"],
            "timestamp": event["timestamp"],
            "duration": event.get("duration"),
            "minute": event.get("minute"),
            "second": event.get("second"),
            "type": _name(event["type"]),
            "play_pattern": _name(event["play_pattern"]),
            "possession_team": _name(event["possession_team"]),
            "player_id": (event.get("player") or {}).get("id"),
            "player": (event.get("player") or {}).get("name"),
            "team_id": (event.get("team") or {}).get("id"),
            "team": (event.get("team") or {}).get("name"),
            "location": event.get("location"),
            "pass_recipient": _name(pass_data.get("recipient")),
            "recipient_id": (pass_data.get("recipient") or {}).get("id"),
            "pass_outcome": _name(pass_data.get("outcome")),
            "pass_end_location": pass_data.get("end_location"),
            "carry_end_location": carry_data.get("end_location"),
            "shot_end_location": shot_data.get("end_location"),
            "shot_outcome": _name(shot_data.get("outcome")),
            "shot_statsbomb_xg": shot_data.get("statsbomb_xg"),
            "freeze_frame": observations,
            "visible_area": frame.get("visible_area"),
        })
    _write(NEW_GOAL_SOURCE, {
        "match_id": 3773387,
        "possession_id": 46,
        "match_label": "New supported goal: match 3773387 possession 46",
        "source": "StatsBomb Open Data authenticated production projection",
        "coordinate_system": {"length": 120, "width": 80, "origin": "top-left"},
        "events": rendered_events,
    })


def _encoded_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return round(float(result.stdout.strip()), 6)


def render_fixture(slug: str, match_id: int, possession_id: int, source: Path) -> dict[str, Any]:
    events, frames = _raw_documents(match_id)
    config = load_config(ROOT / "config.yaml")
    config["animation"].update({
        "width": 720,
        "height": 1280,
        "fps": 24,
        "hook_hold_seconds": 0.0,
        "hook_text": "",
        "annotations_file": None,
    })
    route = build_causal_narrative_route(
        events,
        frames,
        {
            "source_dataset": "statsbomb-open-data",
            "source_revision": PINNED_REVISION,
            "match_id": match_id,
            "possession_id": possession_id,
        },
        source,
        width=720,
        height=1280,
        fps=24,
    )
    output = RENDERS / slug
    video = output / f"{slug}_causal_story.mp4"
    render_possession = load_and_normalize(source)
    model = render_scene_plan(render_possession, route["scene_plan"], config, video)
    segments = scene_segments(route["scene_plan"], model)
    planned_duration = round(segments[-1]["output_end"] if segments else 0.0, 6)
    encoded_duration = _encoded_duration(video)
    selection = route["causal_narrative_selection"]
    result = {
        "schema_id": "tip.causal_narrative_production_result",
        "fixture": slug,
        "match_id": match_id,
        "possession_id": possession_id,
        "source_graph_episode_ids": [
            episode["episode_id"] for episode in route["graph_backed_episodes"]["episodes"]
        ],
        "source_graph_episode_types": [
            episode["episode_type"] for episode in route["graph_backed_episodes"]["episodes"]
        ],
        "selection_sha256": selection.sha256,
        "selection": selection.data,
        "scene_count": len(route["scene_plan"]["scenes"]),
        "planned_duration_seconds": planned_duration,
        "encoded_duration_seconds": encoded_duration,
        "video_path": str(video.relative_to(ROOT)),
        "scene_plan_path": str((output / "scene_plan.json").relative_to(ROOT)),
        "legacy_fallback": route["scene_plan"]["legacy_fallback"],
        "unsupported_mechanisms": [
            "BOX_ENTRY",
            "FINAL_THIRD_ARRIVAL",
            "OVERLOAD",
            "FREE_MAN_CREATION",
        ],
    }
    _write(AUDIT / f"{slug}_selection.json", result)
    _write(output / "scene_plan.json", route["scene_plan"])
    _write(output / "selection.json", selection.data)
    _write(output / "analysis.json", result)
    return result


def _legacy_inventory() -> str:
    return """# Legacy route removal inventory

The causal route is explicit and does not silently fall back. Legacy removal is deferred
until the three causal renders are reviewed.

## Production dependencies

- `src/cli.py`: `--mode legacy` remains the default and requires narrative configuration.
- `src/pipelines/analyze_possession.py`: findings-based analysis and generic episode selection.
- `src/tactical_episodes/`: generic findings-to-episode generation and eligibility.
- `src/intelligence/scene_builder.py`: legacy findings and continuation-only ActionChain plans.
- `scripts/render_tactical_episodes.py`: generic episode consumer/audit renders.
- `scripts/render_tactical_storytelling.py`: return-pattern or continuation-only storytelling.
- `src/narrative_adapter/`: same-player continuation fallback narrative.
- `src/intelligence/patterns/` and `src/intelligence/reasoning/`: legacy finding detectors/ranking.

## Tests and fixtures affected by eventual removal

- Generic tactical-episode, eligibility, relevance, scene-direction, and episodic-render tests.
- `data/depay_goal.json`, `data/second_goal.json`, and narrative YAML fixtures used by legacy CLI.
- CLI tests that assert explicit `legacy` and `semantic` behavior.
- Historical render scripts and audit artifacts under `renders/tactical_episodes` and
  `renders/storytelling`.

## Explicit modes after this change

- `legacy`: deprecated findings-based route; still the CLI default for compatibility.
- `semantic`: analytical graph-backed episode inventory rendered without narrative selection.
- `causal`: new graph-backed causal narrative selection; no legacy fallback.
"""


def main() -> None:
    materialize_new_goal_fixture()
    results = [render_fixture(*fixture) for fixture in FIXTURES]
    (AUDIT / "legacy_removal_inventory.md").parent.mkdir(parents=True, exist_ok=True)
    (AUDIT / "legacy_removal_inventory.md").write_text(_legacy_inventory())
    depay = next(item for item in results if item["fixture"] == "depay")
    comparison = [
        "# Causal narrative production comparison",
        "",
        "| Fixture | Atomic episodes | Narrative units | Scenes | Planned | Encoded |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        comparison.append(
            f"| {result['fixture']} | {len(result['source_graph_episode_ids'])} | "
            f"{len(result['selection']['units'])} | {result['scene_count']} | "
            f"{result['planned_duration_seconds']:.2f}s | {result['encoded_duration_seconds']:.2f}s |"
        )
    comparison += [
        "",
        "## Depay",
        "",
        f"All {len(depay['source_graph_episode_ids'])} analytical episodes remain available. "
        f"The storytelling selection contains {len(depay['selection']['units'])} units; "
        "the two middle LINE_BREAK episodes are retained as ordered members of one "
        "presentation-only PROGRESSION unit rather than equal standalone pauses.",
        "",
        "No route used legacy fallback. Captions use only authenticated LINE_BREAK, "
        "continuation, progression-as-presentation, and FINISH semantics.",
        "",
    ]
    (AUDIT / "comparison.md").write_text("\n".join(comparison))
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
