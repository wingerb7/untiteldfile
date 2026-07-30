# Tactical Episode Semantic/Causal/Render Audit — Root Cause Report

Read-only audit. No tactical concept, overlay, camera feature, or narrative styling was added or changed. The
only code added is additive: `src/identity_bridge.py`, `src/tactical_validation/` (deterministic validators),
and their regression tests. Nothing in `src/tactical_episodes`, `src/tactical_relevance`, `src/scene_direction`,
or their templates was modified.

## Verdict

The generated episodes are **plausible, concise, and data-driven, and four of the six episode-types in both
Depay's and Locatelli's sequence are not tactically valid.** They pass every existing structural test
(temporal ordering, span containment, episode cap, generic-code-has-no-hardcoding) because those tests check
*structure*, not *football meaning*. This audit checked football meaning and found a single root cause behind
almost every failure.

## The root cause

`build_tactical_episodes()` (`src/tactical_episodes/engine.py:309-325`) selects, per episode type, the
candidate finding with the highest `confidence`, then keeps only the top `MAX_FINDING_EPISODES=4` types
possession-wide by that same confidence. But the per-pattern confidence formulas
(`src/intelligence/patterns/positional.py`) are **purely local geometric heuristics with no notion of pitch
zone or stakes**:

- `free_man_creation` (→ ISOLATION) fires whenever no defender is close to a pass receiver — including a
  goalkeeper receiving a routine back-pass in his own third.
- `cutback_candidate` (→ CUTBACK) fires on `backward_x >= 3.0m` plus a wide→central y-zone check — with **no
  constraint on distance to the attacking goal**. A backward pass to your own goalkeeper 110m from the
  opponent's goal satisfies it identically to a genuine byline pull-back.
- `switch_of_play` (→ SWITCH_OF_PLAY) awards confidence from `lateral_change` alone, saturating to 1.0 well
  before `changed_side` (crossing the pitch's centre line) is even required to be true.
- `late_support` (→ OFF_BALL_RUN) fires whenever a player who touched the ball early receives again 12+ events
  later, with no displacement/velocity threshold distinguishing a purposeful attacking run from a center-back
  getting the ball back during circulation.

These four detectors saturate to confidence ≈1.0 almost immediately in **both** fixtures because both
possessions open with several minutes^H^H events of deep circulation among centre-backs, full-backs and the
goalkeeper before the ball ever approaches the box. Meanwhile the detector that *should* fire on the actual
decisive action — `box_arrival` — is capped at a flat confidence of `0.75` (`engine.py:228`) regardless of how
clear-cut the box entry is. In the possession-wide top-4-by-confidence selection, four low-stakes,
high-confidence defensive-third patterns systematically beat the one high-stakes, lower-confidence final-third
pattern. **The system is not biased toward wrong labels; it is biased toward the wrong events.**

This single mechanism explains every FAIL/WARN below in both fixtures. It is a selection-ranking defect, not a
labelling-vocabulary defect — the correct label (`CUTBACK` for Depay's real assist ball, `BOX_ARRIVAL` for
Locatelli's) already exists in the catalogue and was already detected; it just lost the cap.

## Per-episode findings

### Depay (match 3869117, possession 20) — goal at x=120

| Episode (original order) | Verdict | Why |
|---|---|---|
| BUILDUP | PASS | Makes no falsifiable claim; correctly scoped. |
| ISOLATION | **FAIL** | "Isolated attacker" is Andries Noppert, the Dutch **goalkeeper**, receiving a backward safety pass 112m from goal. Not an attacking isolation. |
| OFF_BALL_RUN | WARN | "Run" is Van Dijk's minor lateral drift while recycling possession in the defensive third; no meaningful displacement into relevant space. |
| SWITCH_OF_PLAY | **FAIL (objective)** | The episode's own evidence states `changed_side: false`. `lateral_change=32.4m` alone triggered it. This is progression to the right flank, not a switch of the point of attack. |
| CUTBACK | **FAIL** | Decisive pass ends at Andries Noppert, the goalkeeper, **111m from the opponent's goal** — inside Netherlands' own penalty area, not the opponent's. `backward_x=18.0` satisfied the detector on pure geometry with zero zone constraint. |
| FINISH | WARN | Technically true, but its 37-event span silently swallows the real mechanism (Gakpo's carry + Dumfries' box-entry pass to Depay) without surfacing it. |

**The real, undetected cutback**: Dumfries' pass `(108.7, 68.3) → (104.9, 43.7)`, `backward_x=3.8`, from a wide
zone, landing in the box, immediately received by the scorer. It satisfies both `cutback_candidate`
(confidence 0.64) and `box_arrival` (confidence 0.75) — but lost the confidence-ranked cap to the four
defensive-third patterns above.

### Locatelli (match 3788754, possession 40) — goal at x=120

| Episode (original order) | Verdict | Why |
|---|---|---|
| BUILDUP | PASS | Same as Depay. |
| ISOLATION | **FAIL** | Same defect: "isolated attacker" is Bonucci receiving a routine goalkeeper distribution pass 103m from goal. |
| CUTBACK | **FAIL** | Decisive pass `(41.7,72.1)→(25.9,49.9)` is Di Lorenzo passing back to Bonucci in midfield, 94m from goal. Same zone-blind detector defect as Depay. |
| SWITCH_OF_PLAY | WARN (downgrade, not FAIL) | Unlike Depay, `changed_side=true` here — internally consistent — but the pass happens between two central defenders still in Italy's own half with negligible goal-distance progress. Technically a switch, tactically inert. |
| OFF_BALL_RUN | WARN | Same defect as Depay's: -5.7m net goal-distance change: circulation, not a run into space. |
| FINISH | WARN | Swallows the real mechanism (Locatelli's switch to Berardi + Berardi's box-entry carry + return pass) without surfacing it. |

**The real, undetected mechanism**: Berardi's carry `(74.3,79.6)→(117.4,55.5)` **does** satisfy `box_arrival`
(confidence 0.75) but lost the cap to the same four defensive-third pattern types. His return pass to Locatelli
`(117.4,55.5)→(116.2,39.2)` narrowly **fails** `cutback_candidate`'s own thresholds (`backward_x=1.2 < 3.0`,
`from_wide_zone: |55.5-40|=15.5 < 22`) — a real, tactically legible cutback that the geometric definition is
too rigid to catch. This is a second, independent defect worth flagging even though it did not produce a wrong
label here: the thresholds were tuned against generic geometry, not against what a "byline pull-back" actually
looks like when the carry that precedes it already crosses into the box.

## Causal transitions

No `CREATES/ENABLES/FORCES/OPENS/ATTRACTS/RELEASES/EXPLOITS/FINISHES` vocabulary exists anywhere in the
codebase prior to this audit (confirmed by exhaustive grep) — it is new terminology defined fresh for this
sprint, not a reconciliation against prior art. Running `validate_causal_transition()` against every adjacent
pair in **both original sequences** rejects all of them: every `evidence` field on a `TacticalEpisode`
describes only that episode's own internal pattern, never how it caused the *next* episode's outcome. The
original sequences' apparent causal flow is chronology only.

For the two corrected sequences, exactly one defensible causal edge exists per fixture with real, checkable
evidence: `CUTBACK → FINISH` for Depay and `BOX_ARRIVAL → FINISH` for Locatelli, both backed by "pass/carry
ends inside the box" + "immediately followed by the shot." The preceding `BUILDUP → …` edge is retained only
as a low-confidence `ENABLES` ("possession wasn't lost"), which is necessary but tactically thin. See
`causal_graph.json`.

## Identity bridge

`src/identity_bridge.py` adds a four-state contract (`AUTHENTICATED_TRACK`, `OBSERVATION_ONLY`,
`AMBIGUOUS_TRACK_SET`, `UNRESOLVED`) without touching reconstruction. Applied to every tactically selected
defender in both fixtures (`identity_bridge_audit.json`):

- Every `primary_actor_id` resolves to `AUTHENTICATED_TRACK` (raw StatsBomb `player_id`, persistent for the
  match).
- Every `relevant_defender_id` resolves to `OBSERVATION_ONLY` (`recon:{event_id}:{idx}`, single-freeze-frame
  scoped) — this is already disclosed via `TacticalEpisode.limitations`, so it is a WARN, not a FAIL, in the
  automated validator run.
- No `AMBIGUOUS_TRACK_SET` or `UNRESOLVED` case is ever produced, **not because ambiguity doesn't exist**, but
  because `nearest_defender()` always forces a single pick. `audit_trace.json` shows this concretely: several
  "defender controlling the passing lane" entries are retained at `relevance_score: 0.0` (SWITCH_OF_PLAY,
  CUTBACK in Depay) — a zero score is the system finding *no* signal, yet still emitting a specific defender id
  and reason text as if it had. The bridge's `AMBIGUOUS_TRACK_SET`/`UNRESOLVED` states exist so a future caller
  can represent that honestly instead of fabricating a single confident pick.

## Render grounding

`render_grounding_audit.json` runs 7 checks per scene. Actor visibility and defender visibility pass
everywhere they apply (the renderer does correctly show who the episode names). The systematic failures are:
`primary_overlay_matches_episode_evidence` (FAILs on Depay's SWITCH_OF_PLAY — the switch-arrow overlay draws a
mechanism the evidence contradicts) and `claimed_tactical_concept_is_visually_observable`, which inherits every
episode's semantic-validity finding — a scene cannot visually ground a claim the underlying evidence does not
support, no matter how correctly the overlay itself renders. `tactically_relevant_space_in_viewport` is
reported as WARN, not PASS, throughout: `camera_intent` is a symbolic label, not a numeric viewport bound, so
pixel-level containment is not deterministically checkable from the scene plan alone — this audit does not
claim certainty it cannot support.

## Captions

Every caption in both fixtures is a **static per-episode-type template string**
(`src/tactical_episodes/engine.py:_TEMPLATES`), looked up by `episode_type` and never computed from the
instance's own evidence (confirmed in `src/scene_direction/engine.py`: `caption_intent = f"{episode.cause}
{episode.created_advantage}"`, both pulled from the same fixed dict). This means every FAIL/WARN episode above
produces a caption that reads as a specific, instance-grounded tactical claim while actually being boilerplate.
`caption_evidence_audit.json` traces each caption and flags `overstates_evidence` for every FAIL/WARN episode.

## Corrected sequences

See `corrected_episode_sequences.json` for full detail.

- **Depay**: `BUILDUP → ISOLATION → OFF_BALL_RUN → SWITCH_OF_PLAY → CUTBACK → FINISH` →
  **`BUILDUP → CUTBACK → FINISH`** (the CUTBACK re-anchored on Dumfries' actual assist ball).
- **Locatelli**: `BUILDUP → ISOLATION → CUTBACK → SWITCH_OF_PLAY → OFF_BALL_RUN → FINISH` →
  **`BUILDUP → BOX_ARRIVAL → FINISH`** (the BOX_ARRIVAL re-anchored on Berardi's carry).

Both corrections use only episode types already in `EPISODE_TYPES` and evidence already computed by existing
detectors (`box_arrival`, `cutback_candidate`) — no new tactical concept was introduced, per this sprint's
constraint. They are recommendations for the episode-selection ranking logic to reach next sprint, not applied
to the pipeline in this read-only audit.

## Di Maria

`select_source_documents()` rejects Di Maria (match 3869685, possession 52) with `SRC_EVENT_INDEX_INVALID`,
confirmed by direct execution against the pinned Open Data revision (not merely by reading the docs, which
elsewhere in the repo cite a different rejection code for the same fixture — worth a documentation fix, out of
scope here). This is Di Maria's existing negative-fixture contract
(`tests/test_action_graph.py::test_locatelli_and_depay_succeed_and_di_maria_fails_before_action_graph`); per
instructions it was not bypassed. No tactical episodes exist for Di Maria, so none of the validators in this
audit ran against it.

## What this audit did not do

- Did not modify any detector, template, camera/overlay logic, or the episode cap.
- Did not add a new tactical concept, episode type, overlay, or camera feature.
- Did not attempt to make `camera containment` a hard PASS/FAIL claim without a numeric viewport model to back
  it (reported WARN with the limitation stated).
- Did not perform broad caption copywriting; `caption_evidence_audit.json` states corrected *intent* only.
