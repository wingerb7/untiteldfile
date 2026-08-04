from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "renders/.matplotlib"))

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import yaml

from render.production_reconstruction import render_production_reconstruction
from render.reconstruction import render_reconstruction
from src.reconstruction import build_window_reconstruction, load_statsbomb_match


CASES = (
    {
        "slug": "goal_1",
        "goal_type": "FAST_COMBINATION_GOAL",
        "match_id": 3893808,
        "fixture": "USA Women's vs Netherlands Women's — FIFA Women's World Cup 2023",
        "anchor_event_id": "46e24a82-e3db-46d1-8f3c-32c203c44cc2",
        "goal_event_id": "91322304-6c97-4963-8b1d-6752236e8131",
    },
    {
        "slug": "goal_2",
        "goal_type": "CARRY_GOAL",
        "match_id": 3869321,
        "fixture": "Netherlands vs Argentina — FIFA World Cup 2022",
        "anchor_event_id": "64d3c14b-f388-482c-8816-9294824c2f37",
        "goal_event_id": "1a46edaa-ca09-435a-b841-aa201d1f0e14",
    },
    {
        "slug": "goal_3",
        "goal_type": "BUILD_UP_GOAL",
        "match_id": 3869321,
        "fixture": "Netherlands vs Argentina — FIFA World Cup 2022",
        "anchor_event_id": "18277025-8bba-4408-a015-14768a4421f8",
        "goal_event_id": "758f3a76-791e-4a71-8cb4-d776a6bd293d",
    },
)


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def still(video: Path, output: Path, timestamp: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{timestamp:.3f}", "-i", str(video), "-frames:v", "1", str(output)],
        check=True,
    )


def make_sheet(directory: Path, duration: float) -> None:
    still_dir = directory / ".stills"
    still_dir.mkdir(exist_ok=True)
    videos = (("Production", directory / "production.mp4"), ("QA", directory / "qa.mp4"))
    times = (duration * .18, duration * .50, duration * .82)
    figure, axes = plt.subplots(2, 3, figsize=(16, 8), facecolor="#081B14")
    for row, (label, video) in enumerate(videos):
        for column, timestamp in enumerate(times):
            image_path = still_dir / f"{row}_{column}.png"
            still(video, image_path, timestamp)
            axes[row, column].imshow(mpimg.imread(image_path))
            axes[row, column].axis("off")
            if column == 0:
                axes[row, column].set_title(label, color="white", fontsize=15, loc="left", pad=8)
    figure.subplots_adjust(left=.02, right=.98, top=.96, bottom=.03, wspace=.025, hspace=.12)
    figure.savefig(directory / "contact_sheet.png", dpi=150, facecolor=figure.get_facecolor())
    plt.close(figure)


def make_overview(output: Path, results: list[dict[str, object]]) -> None:
    figure, axes = plt.subplots(3, 3, figsize=(16, 12), facecolor="#081B14")
    for row, result in enumerate(results):
        directory = output / str(result["slug"])
        duration = float(result["duration_seconds"])
        for column, fraction in enumerate((.18, .50, .82)):
            image_path = directory / ".stills" / f"overview_{column}.png"
            still(directory / "production.mp4", image_path, duration * fraction)
            axes[row, column].imshow(mpimg.imread(image_path))
            axes[row, column].axis("off")
            if column == 0:
                axes[row, column].set_title(
                    f"Goal {row + 1} — {str(result['goal_type']).replace('_', ' ').title()}",
                    color="white", fontsize=15, loc="left", pad=8,
                )
    figure.subplots_adjust(left=.02, right=.98, top=.97, bottom=.025, wspace=.025, hspace=.12)
    figure.savefig(output / "contact_sheet_overview.png", dpi=150, facecolor=figure.get_facecolor())
    plt.close(figure)


def main() -> None:
    output = ROOT / "viewer_benchmark"
    output.mkdir(exist_ok=True)
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    qa_config = dict(config)
    qa_config["animation"] = {**config.get("animation", {}), "fps": 30, "width": 1080, "height": 1920}
    results = []
    for case in CASES:
        directory = output / case["slug"]
        directory.mkdir(exist_ok=True)
        match_id = int(case["match_id"])
        match = load_statsbomb_match(
            ROOT / f"data/open-data/data/events/{match_id}.json",
            ROOT / f"data/open-data/data/three-sixty/{match_id}.json",
            match_id=match_id,
        )
        result = build_window_reconstruction(
            match,
            event_id=str(case["anchor_event_id"]),
            sequence_end_event_id=str(case["goal_event_id"]),
            pre_roll_seconds=.5,
            post_roll_seconds=.75,
            config=config,
        )
        selection = result["selection"]
        reconstruction = result["reconstruction"]
        if selection["admission"] != "ACCEPTED" or reconstruction is None:
            raise SystemExit(f"{case['slug']} was not strictly accepted: {selection}")
        dump(directory / "selection.json", selection)
        dump(directory / "reconstruction.json", reconstruction)
        render_production_reconstruction(reconstruction, directory / "production.mp4", variant="polished")
        render_reconstruction(
            reconstruction,
            qa_config,
            directory / "qa.mp4",
            visual_qa=True,
            uncertainty_presentation=True,
            selection_timeline=True,
        )
        make_sheet(directory, float(selection["duration_seconds"]))
        results.append({
            **case,
            "admission": selection["admission"],
            "duration_seconds": selection["duration_seconds"],
            "selected_actions": selection["selected_actions"],
            "source_360_frame_count": selection["source_360_frame_count"],
            "longest_observation_gap_seconds": selection["longest_observation_gap_seconds"],
            "quality_estimates": selection["quality_estimates"],
            "reconstruction_sha256": reconstruction["sha256"],
        })
    dump(output / "manifest.json", {"benchmark": "production_viewer_benchmark_v1", "renderer_variant": "polished", "fps": 30, "width": 1920, "height": 1080, "windows": results})
    make_overview(output, results)


if __name__ == "__main__":
    main()
