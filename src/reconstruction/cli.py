from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml

from src.reconstruction import build_window_reconstruction, load_statsbomb_match


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic 2D StatsBomb match reconstruction")
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--three-sixty", type=Path)
    parser.add_argument("--lineups", type=Path)
    parser.add_argument("--matches", type=Path)
    parser.add_argument("--match-id")
    anchor = parser.add_mutually_exclusive_group(required=True)
    anchor.add_argument("--event-id")
    anchor.add_argument("--event-index", type=int)
    parser.add_argument("--sequence-end-event-id")
    parser.add_argument("--pre-roll", type=float, default=1.0)
    parser.add_argument("--post-roll", type=float, default=1.0)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--reconstruction-output", required=True, type=Path)
    parser.add_argument("--video-output", type=Path)
    parser.add_argument("--visual-qa", action="store_true")
    parser.add_argument("--uncertainty-presentation", action="store_true")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    match = load_statsbomb_match(args.events, args.three_sixty, args.lineups, args.matches, match_id=args.match_id)
    result = build_window_reconstruction(match, event_id=args.event_id, event_index=args.event_index, sequence_end_event_id=args.sequence_end_event_id, pre_roll_seconds=args.pre_roll, post_roll_seconds=args.post_roll, config=config)
    reconstruction = result["reconstruction"]
    args.reconstruction_output.parent.mkdir(parents=True, exist_ok=True)
    args.reconstruction_output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    accepted = str(result["selection"]["admission"]).startswith("ACCEPTED")
    if args.video_output and accepted and reconstruction is not None:
        cache = Path("renders/.matplotlib").resolve()
        cache.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(cache))
        from render.reconstruction import render_reconstruction

        render_reconstruction(reconstruction, config, args.video_output, visual_qa=args.visual_qa, uncertainty_presentation=args.uncertainty_presentation)
    print(f"Wrote {args.reconstruction_output} (admission={result['selection']['admission']})")
    if args.video_output and accepted:
        print(f"Wrote {args.video_output}")


if __name__ == "__main__":
    main()
