# LINE_BREAK episode-granularity audit

## Executive verdict

Locatelli's one episode and Depay's six episodes are correctly granular. Every episode is one distinct authenticated completed-pass, defensive-line crossing, and receiver-control path. No duplicate, shadow, contradiction, or improper nesting was found.

## Why Locatelli produces one

Exactly one crossing relation has the full completed-pass and later declared-receiver receipt path. It is converted once into one deterministic episode.

## Why Depay produces six

1. `33afe8ec-1aea-40be-a7cc-97610032e3b5`: `3311` → `2988`, receipt `b4491768-f744-4de3-87b0-ccd4ef7be5a2`.
2. `ac15aa15-db77-464e-89c6-e0ab2dce8077`: `6994` → `4318`, receipt `fbb669e7-25a0-4046-a0d5-07f25d313b72`.
3. `8d6e145c-7e04-420d-b346-3514e3fbfb9b`: `4318` → `2988`, receipt `541e8c54-a938-4d39-bb18-e3db49e71c72`.
4. `d3264b17-4393-4e4d-8970-51128f9d9bf3`: `2988` → `20750`, receipt `37ed1aa4-d393-4e6d-9b3a-42ee3eb52716`.
5. `fb2800dc-0e2c-42f6-9708-aaf3caf2b6e7`: `20750` → `8125`, receipt `cd4dc2d3-79fe-448a-a970-607196d54290`.
6. `f13d1fcc-d78b-4932-a6ae-f24f0e153753`: `8125` → `2988`, receipt `7aa42ebe-62ce-4dcb-a700-296e34d9b6c5`.

All 15 Depay episode pairs are `DISTINCT`. Each pair differs in pass event, endpoint features, defensive-line Recognition, crossing Recognition, crossing relation, and receipt relation. Some consecutive actions share a player or graph ancestry; that proves an extended attacking sequence, not duplicate tactical actions.

## Human analyst interpretation

A human analyst can explain each pass independently because each crosses a separately authenticated observation-scoped line and reaches a separately authenticated receipt. For concise storytelling, an analyst may group the six as a sustained progression, but that is a higher-level concept rather than evidence that the LINE_BREAK episodes are duplicates.

## Architecture and graph quality

Perception endpoints authenticate crossing Recognition; crossing Recognition and the defensive-line Recognition authenticate the Action Graph crossing relation; the source pass and related receipt authenticate episode eligibility. Unique pass-line-receipt signatures and the final episode deduplication key prevent repeated conversion.

No duplicated traversal, component expansion, crossing relation, receipt linkage, graph edge, graph-to-episode conversion, adapter conversion, or ordering artifact was found. No production layer should change.

## Next graph-backed concept

The next concept should model a higher-level sustained line-breaking progression: an authenticated sequence that contains multiple distinct LINE_BREAK actions connected by receiver-to-next-passer continuation. It should nest the existing episodes without merging or suppressing them.

