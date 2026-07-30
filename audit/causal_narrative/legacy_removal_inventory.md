# Legacy route removal inventory

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
