# Production pipeline

The production source of truth is the deterministic event-window reconstruction artifact:

```text
StatsBomb events + lineups + matches + 360
  -> source validation / normalization
  -> deterministic event-window selection and admission
  -> bounded 2D reconstruction (one period, supported actions only)
  -> visual QA / replay / export
  -> football world model
  -> recognition
  -> tactical analysis
  -> optional story and social output
```

`src.reconstruction` owns temporal position state. `render.reconstruction` is a
pure view of that state and accepts no findings, episodes, scene plans, captions,
or narrative configuration. The reconstruction contract records identity,
position state, confidence, last observation, visibility, and source provenance.
Only `OBSERVED` and physically bounded `INTERPOLATED` positions may be displayed;
unsupported held or predicted positions are represented as `UNKNOWN`.

StatsBomb 360 is sparse event evidence, not continuous tracking. Production
requests therefore require an explicit PASS, BALL_RECEIPT, CARRY or SHOT anchor
and may select a short chronological sequence. The default target is 3–8 seconds,
with a hard 12-second maximum. Rejected windows are never rendered. Player and
ball interpolation ends at configured evidence, motion, gap and period gates.

The older narrative CLI and scene-plan renderer remain available for backwards
compatibility, but they are not the reconstruction critical path. Downstream
football intelligence may derive new artifacts from reconstructed state. It must
never mutate the reconstruction artifact or feed coordinates back into it.
`src.world_model.build_world_model_from_reconstruction` is the production-facing,
read-only adapter at this boundary. The synchronized-event adapter remains for
backwards compatibility.

## Standalone milestone command

```bash
python -m src.reconstruction.cli \
  --events data/open-data/data/events/MATCH_ID.json \
  --three-sixty data/open-data/data/three-sixty/MATCH_ID.json \
  --lineups data/open-data/data/lineups/MATCH_ID.json \
  --match-id MATCH_ID \
  --reconstruction-output renders/MATCH_ID.reconstruction.json \
  --video-output renders/MATCH_ID.mp4 \
  --visual-qa
```

The JSON digest makes repeated builds comparable. Video export samples the same
pauseable `reconstruction_state_at` function used by visual QA.
