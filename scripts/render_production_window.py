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

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import yaml

from render.production_reconstruction import render_production_reconstruction
from render.reconstruction import render_reconstruction
from src.reconstruction import build_window_reconstruction, load_statsbomb_match


MATCH_ID = 3869321
PASS_EVENT_ID = "64d3c14b-f388-482c-8816-9294824c2f37"
GOAL_EVENT_ID = "1a46edaa-ca09-435a-b841-aa201d1f0e14"


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def contact_sheet(output: Path, videos: list[tuple[str, Path]], duration: float) -> None:
    stills = output / ".contact_stills"
    stills.mkdir(exist_ok=True)
    times = (duration * 0.20, duration * 0.50, duration * 0.80)
    paths: list[list[Path]] = []
    for row, (_, video) in enumerate(videos):
        row_paths = []
        for column, timestamp in enumerate(times):
            still = stills / f"{row}_{column}.png"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{timestamp:.3f}", "-i", str(video), "-frames:v", "1", str(still)],
                check=True,
            )
            row_paths.append(still)
        paths.append(row_paths)

    figure, axes = plt.subplots(3, 3, figsize=(16, 12), facecolor="#081B14")
    for row, (label, _) in enumerate(videos):
        for column, still in enumerate(paths[row]):
            axes[row, column].imshow(mpimg.imread(still))
            axes[row, column].axis("off")
            if column == 0:
                axes[row, column].set_title(label, color="white", fontsize=16, loc="left", pad=10)
    figure.subplots_adjust(left=0.025, right=0.975, top=0.97, bottom=0.025, wspace=0.025, hspace=0.14)
    figure.savefig(output / "contact_sheet.png", dpi=150, facecolor=figure.get_facecolor())
    plt.close(figure)


def main() -> None:
    output = ROOT / "renders/production"
    output.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    match = load_statsbomb_match(
        ROOT / f"data/open-data/data/events/{MATCH_ID}.json",
        ROOT / f"data/open-data/data/three-sixty/{MATCH_ID}.json",
        match_id=MATCH_ID,
    )
    result = build_window_reconstruction(
        match,
        event_id=PASS_EVENT_ID,
        sequence_end_event_id=GOAL_EVENT_ID,
        pre_roll_seconds=1.0,
        post_roll_seconds=2.0,
        config=config,
    )
    if result["selection"]["admission"] != "ACCEPTED" or result["reconstruction"] is None:
        raise SystemExit(f"production window was not accepted: {result['selection']}")
    reconstruction = result["reconstruction"]
    dump(output / "selection.json", result["selection"])
    dump(output / "reconstruction.json", reconstruction)

    minimal = output / "production_minimal.mp4"
    polished = output / "production_polished.mp4"
    qa = output / "qa_reference.mp4"
    render_production_reconstruction(reconstruction, minimal, variant="minimal")
    render_production_reconstruction(reconstruction, polished, variant="polished")

    qa_config = dict(config)
    qa_config["animation"] = {**config.get("animation", {}), "fps": 30, "width": 1080, "height": 1920}
    render_reconstruction(
        reconstruction,
        qa_config,
        qa,
        visual_qa=True,
        uncertainty_presentation=True,
        selection_timeline=True,
    )
    contact_sheet(
        output,
        [("A — Minimal", minimal), ("B — Polished", polished), ("C — QA reference", qa)],
        float(result["selection"]["duration_seconds"]),
    )


if __name__ == "__main__":
    main()
