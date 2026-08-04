from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from render.cinematography_reconstruction import render_cinematography_reconstruction
from src.cinematography import build_benchmark_cinematography_plan


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def _still(video: Path, output: Path, timestamp: float) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{timestamp:.3f}", "-i", str(video), "-frames:v", "1", str(output)], check=True)


def _duration(video: Path) -> float:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video)], check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def _comparison_sheet(directory: Path) -> None:
    videos = [("CURRENT", directory / "current.mp4"), ("CINEMATOGRAPHY", directory / "cinematography.mp4")]
    stills = directory / ".stills"
    stills.mkdir(exist_ok=True)
    figure, axes = plt.subplots(2, 4, figsize=(18, 8), facecolor="#081B14")
    for row, (label, video) in enumerate(videos):
        duration = _duration(video)
        for column, fraction in enumerate((.18, .42, .66, .86)):
            image_path = stills / f"{row}_{column}.png"
            _still(video, image_path, duration * fraction)
            axes[row, column].imshow(mpimg.imread(image_path))
            axes[row, column].axis("off")
            if column == 0:
                axes[row, column].set_title(label, color="white", fontsize=15, loc="left", pad=8)
    figure.subplots_adjust(left=.015, right=.985, top=.96, bottom=.02, wspace=.02, hspace=.10)
    figure.savefig(directory / "comparison.png", dpi=140, facecolor=figure.get_facecolor())
    plt.close(figure)


def main() -> None:
    output = ROOT / "cinematography_benchmark"
    output.mkdir(exist_ok=True)
    manifest = []
    for goal in ("goal_1", "goal_2", "goal_3"):
        source = ROOT / "viewer_benchmark" / goal
        directory = output / goal
        directory.mkdir(exist_ok=True)
        reconstruction = json.loads((source / "reconstruction.json").read_text(encoding="utf-8"))
        plan = build_benchmark_cinematography_plan(reconstruction)
        current = directory / "current.mp4"
        shutil.copyfile(source / "production.mp4", current)
        _write(directory / "cinematography_plan.json", plan)
        render_cinematography_reconstruction(reconstruction, plan, directory / "cinematography.mp4")
        _comparison_sheet(directory)
        manifest.append({
            "goal": goal,
            "strategy": plan["strategy"],
            "reconstruction_sha256": reconstruction["sha256"],
            "plan_sha256": plan["sha256"],
            "current": str(current.relative_to(ROOT)),
            "cinematography": str((directory / "cinematography.mp4").relative_to(ROOT)),
            "comparison": str((directory / "comparison.png").relative_to(ROOT)),
        })
    _write(output / "manifest.json", {"slice": "benchmark_goals_1_to_3", "comparisons": manifest})
    (output / "evaluation.md").write_text("""# Cinematography vertical-slice evaluation

Review each pair blind and on first viewing. Do not use the QA render or plan before scoring.

| Goal | Variant | Ball findability (1-5) | Receipt legibility (1-5) | Protagonist handoff (1-5) | Full-action comprehension (1-5) | Notes |
|---|---|---:|---:|---:|---:|---|
| 1 | Current | | | | | |
| 1 | Cinematography | | | | | |
| 2 | Current | | | | | |
| 2 | Cinematography | | | | | |
| 3 | Current | | | | | |
| 3 | Cinematography | | | | | |

Questions:

1. Could you locate the ball immediately and keep it through the decisive action?
2. Was the receipt a distinct, visible moment?
3. Did attention move naturally from passer to receiver to shooter?
4. Could you explain the complete action after one viewing without labels?

Goal 2 is the non-regression control. Prefer the cinematography version only if Goals 1 and 3 improve without making Goal 2 less clear or less natural.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
