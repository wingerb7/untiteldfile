# Cinematography Layer

> Status: architecture proposal
>
> Position: after Reconstruction, before Renderer
>
> Objective: maximize immediate, first-view understanding of football action

## 1. Decision

Introduce a deterministic, semantic **Cinematography Layer** between the immutable
reconstruction artifact and the renderer.

```text
Reconstruction + admitted football semantics
                    |
                    v
            Cinematography Layer
       Beat Map -> Shot Plan -> Edit Decision List
                    |
                    v
          Render Instruction Stream
                    |
                    v
                 Renderer
```

The layer is a director, not a second reconstruction system and not a renderer.
It decides what the viewer must understand next, who should own attention, which
relationships must remain visible, and how much presentation time each moment
needs. The renderer remains a deterministic executor of camera, emphasis, and
timing instructions.

The current production camera answers only: **where is the ball?** It does this
reliably with a smoothed, slightly anticipated ball-following crop. It does not
answer: **who is about to receive it, why does that handoff matter, and which
player becomes the next protagonist?** Keeping an object in frame is therefore
not the same as communicating an action.

## 2. Boundary and invariants

The following upstream inputs are read-only and remain authoritative:

- World Model, Perception, Recognition, Football Action Graph;
- Reconstruction, Identity, and Tracking;
- authentication and the production pipeline;
- all existing renderer contracts.

The Cinematography Layer may transform presentation time and presentation
salience. It must never transform football state.

It must not:

- move a player or the ball in source time;
- invent a touch, run, receiver, passing lane, defender, or tactical claim;
- reorder football events;
- fill an unknown state with a guessed fact;
- change event identity, track identity, confidence, or reconstruction hashes;
- require the renderer to infer football meaning.

Every output instruction must trace to source event IDs, actor IDs, source-time
bounds, and planner rules. If required evidence is absent or below its confidence
threshold, the planner must use a conservative wide coverage shot with no
speculative emphasis.

## 3. What is fundamentally missing

The reconstruction describes **what exists over time**. The current camera
describes **where to crop over time**. Between them, no component describes
**what the viewer must notice over time**.

This missing representation causes four failures:

1. **No semantic segmentation.** A pass, its anticipation, its receipt, and the
   next action arrive as an undifferentiated continuous interval.
2. **No attention ownership.** Same-team markers have equal visual weight, so a
   viewer must discover the receiver and shooter unaided.
3. **No handoff grammar.** The focal subject changes only after the ball changes
   location. In a fast action this is perceptually late; in a multi-pass action
   it makes the viewer repeatedly reacquire the story.
4. **No editorial clock.** Source timestamps are treated as presentation
   timestamps even when a decisive receipt occupies too few frames to perceive.

This is why Goal 2 works: one protagonist and one direction allow the ball to
act as an accidental director. Goals 1 and 3 require intentional directing.

## 4. Inputs

The planner consumes immutable facts and admitted semantics; it does not run new
recognition logic.

### Required

- reconstructed, time-indexed ball and player state;
- ordered events with source timestamps and spatial endpoints;
- stable actor, receiver, team, and goalkeeper identities where available;
- ball state: controlled, travelling, contested, shot, out/goal, or unknown;
- pitch and goal geometry;
- confidence and provenance for every semantic input;
- output format, safe areas, duration policy, and renderer capability version.

### Optional, used only when already produced upstream

- expected next action or graph edge;
- causal or tactical importance;
- participating actors and protagonist chain;
- defensive pressure, nearby defenders, passing lanes, defensive line, and
  goalkeeper relation;
- phase labels such as counterattack, cross, combination, or line-breaking pass.

Optional inputs improve direction but do not become facts merely because the
planner wants them. The planner records whether a decision was evidence-backed,
rule-derived, or a conservative fallback.

## 5. Output contracts

Use three explicit artifacts rather than adding more heuristics to the renderer.

### 5.1 Beat Map

A beat is the smallest interval with one viewer comprehension objective.

```json
{
  "beat_id": "beat_04",
  "kind": "RECEIPT",
  "source_range": [2.18, 2.34],
  "anchor_event_ids": ["receipt-event-id"],
  "primary_actor_id": "receiver-id",
  "secondary_actor_ids": ["passer-id"],
  "attention_from": "passer-id",
  "attention_to": "receiver-id",
  "viewer_question": "Who received the pass?",
  "required_context": ["BALL", "RECEIVER", "NEAREST_DEFENDER", "GOAL"],
  "confidence": 0.94
}
```

Beat kinds form a small vocabulary:

- `ESTABLISH`: orient direction, goal, ball owner, and relevant structure;
- `ACTION_SETUP`: expose a runner, target zone, overload, or open lane;
- `PASS_RELEASE` or `CROSS_RELEASE`: show origin and intended destination;
- `TRAVEL`: preserve origin-to-destination relationship while attention moves;
- `RECEIVER_ANTICIPATION`: make the verified receiver visually available before
  the ball arrives;
- `RECEIPT`: make the change of possession immediately legible;
- `CONTROL` or `CARRY`: maintain actor-ball coupling and direction;
- `COMBINATION_HANDOFF`: preserve two or three linked protagonists;
- `SHOT_SETUP`: frame shooter, ball, goalkeeper, goal, and relevant defender;
- `SHOT`: prioritize ball trajectory without dropping shooter or goal context;
- `RESOLUTION`: show goal, save, miss, clearance, or turnover;
- `OUTCOME_HOLD`: allow the causal chain and outcome to register.

The planner creates only beats supported by upstream events. For example,
`RECEIVER_ANTICIPATION` is a presentation beat around a known future receipt,
not a claim that the player intended the pass before it was made.

### 5.2 Semantic Shot Plan

Each shot has a single primary intention and an explicit subject hierarchy.

```json
{
  "shot_id": "shot_03",
  "beat_ids": ["beat_03", "beat_04"],
  "intention": "TRANSFER_ATTENTION_TO_RECEIVER",
  "source_range": [1.82, 2.34],
  "presentation_range": [2.10, 2.78],
  "composition": {
    "primary": ["receiver-id", "BALL"],
    "secondary": ["passer-id", "GOAL"],
    "context": ["nearest-defender-id"],
    "screen_direction": "TOWARD_ATTACKING_GOAL",
    "lead_room": 0.30
  },
  "camera": {
    "mode": "TWO_SUBJECT_HANDOFF",
    "framing": "MEDIUM_ACTION",
    "transition": "MOTIVATED_PAN",
    "max_crop_velocity": 18.0
  },
  "attention": {
    "primary_actor_id": "receiver-id",
    "transition_start_source_time": 1.96,
    "transition_end_source_time": 2.24
  }
}
```

Camera modes are semantic execution primitives, not event classifiers:

- `CONTEXT_COVERAGE`: show action footprint and attacking direction;
- `OWNER_AND_OPTIONS`: ball owner plus relevant receivers/defenders;
- `TWO_SUBJECT_HANDOFF`: retain passer and receiver through attention transfer;
- `PROTAGONIST_TRACK`: follow a controlled carry with goal context;
- `BOX_RELATIONSHIP`: ball source, target attackers, defenders, goalkeeper, goal;
- `COMBINATION_COVERAGE`: preserve multiple verified protagonists in one stable
  composition until a motivated cut is safe;
- `FINISH_COVERAGE`: shooter-ball-goal triangle;
- `OUTCOME_HOLD`: stable result composition.

### 5.3 Edit Decision List and render instructions

The Edit Decision List maps monotonically increasing presentation time to
nondecreasing source time. It contains shot boundaries, transition durations,
speed segments, and holds. The compiled Render Instruction Stream contains only
capabilities the renderer understands: viewport bounds or targets, zoom,
transition curve, salience parameters, and source-time mapping.

The semantic plan is retained for explainability; the renderer receives no prose
such as “follow the important player.” Existing renderer inputs remain valid. A
versioned adapter compiles the new plan into additive, backward-compatible
instructions, and absence of a plan selects the current production behavior.

## 6. Planning stages

1. **Validate inputs.** Reject cross-possession identities, non-monotonic event
   time, unsupported renderer capabilities, and untraceable semantic claims.
2. **Build the action spine.** Select the admitted, ordered events from the
   presentation window and connect verified actor-to-receiver handoffs.
3. **Segment beats.** Place semantic boundaries around release, arrival, control,
   decisive action, and resolution; merge beats that would be too brief to read.
4. **Classify directing challenge.** Measure action footprint, actor count,
   direction changes, event density, crowding, and ball-background ambiguity.
5. **Assign attention ownership.** Produce a continuous protagonist schedule
   with pre-attention, joint-attention, and post-handoff intervals.
6. **Select shot strategy.** Use an event-family grammar, then solve framing for
   required subjects and screen continuity.
7. **Allocate presentation time.** Preserve event order and state, adding only
   bounded slowdowns or duplicate-frame holds.
8. **Compile and validate.** Emit renderer-native instructions and verify visual
   coverage, continuity, identity, time mapping, and provenance.

The planner should be deterministic for a fixed input, configuration, and
capability version. Optimize lexicographically: comprehension constraints first,
continuity second, aesthetic smoothness third. Never trade the visibility of the
decisive actor for smoother camera motion.

## 7. Beat-driven directing grammar

Rendering should be beat-driven, but not forced into one universal sequence.
`ESTABLISH -> PASS -> RECEIPT -> SHOT -> HOLD` is a useful grammar, not a fixed
template. Beats are generated from the actual action spine.

### Simple finish

`ESTABLISH -> SHOT_SETUP -> SHOT -> RESOLUTION -> OUTCOME_HOLD`

Use one stable finish composition when possible. Preserve shooter, ball, goal,
and goalkeeper; avoid a cut during foot-to-ball contact.

### Cross

`WIDE_SETUP -> CROSS_RELEASE -> BOX_FLIGHT -> TARGET_ARRIVAL -> FINISH -> RESOLUTION`

Begin wide enough to establish crosser and box occupation. During flight,
transfer attention toward the verified target area while retaining ball origin
briefly. Prefer box relationship framing over tight ball tracking.

### Line-breaking pass

`STRUCTURE_SETUP -> PASS_RELEASE -> LINE_TRANSIT -> RECEIVER_ANTICIPATION -> RECEIPT -> NEXT_ACTION`

The defensive line and receiver are required context when supplied upstream.
Show why the pass matters before tightening on the receiver. Do not draw or imply
a defensive line unless Recognition has provided it.

### Third-man combination

`TRIAD_SETUP -> FIRST_PASS -> LAYOFF_HANDOFF -> THIRD_MAN_ANTICIPATION -> RETURN_PASS -> NEXT_ACTION`

Keep the verified triad in a stable composition through the first handoff. Cut
or tighten only after the viewer has registered the third player. A generic ball
camera is specifically disallowed when it would remove one of the triad.

### Carry

`OWNER_SETUP -> CARRY -> PRESSURE_OR_SPACE_CHANGE -> SHOT_OR_PASS -> RESOLUTION`

Use protagonist tracking with forward lead room. Ball visibility reinforces the
owner rather than replacing the owner as the focal subject.

### Counterattack

`TURNOVER_OR_LAUNCH -> ADVANTAGE_ESTABLISH -> ADVANCE -> DECISION -> FINISH -> RESOLUTION`

Use wider, directional framing and fewer cuts. Preserve velocity, numerical
relationship, available space, and attacking direction. Editorial slowdowns are
more restricted because pace is part of the meaning.

## 8. Protagonist switching

Protagonist switching is an attention transition, not a camera snap.

For a verified `passer -> receiver` edge:

1. **Ownership:** passer is primary; receiver is contextual.
2. **Pre-attention:** shortly before or at release, composition creates space in
   the receiver's direction and raises the receiver from context to secondary.
3. **Joint attention:** while the ball travels, passer, ball path, and receiver
   remain readable. Salience transfers gradually.
4. **Handoff:** at receipt, receiver becomes primary; passer remains secondary
   only if needed for the combination.
5. **Commit:** after controlled receipt, camera may tighten or follow the new
   protagonist.

For `passer -> receiver -> shooter`, the same state machine chains without
resetting to neutral. A new switch may begin only when the current receiver is
perceptually established. If event density makes two clean handoffs impossible,
the planner uses stable multi-subject coverage instead of two rapid cuts.

Continuity rules:

- preserve attacking screen direction unless a motivated establishing shot
  explicitly resets it;
- do not cut inside the protected interval around release, first contact, or
  shot contact;
- do not change zoom and protagonist at maximum rate simultaneously;
- use hysteresis so small score changes cannot oscillate focus;
- keep the current protagonist until the successor exceeds the focus threshold
  for a minimum dwell time;
- prefer one understandable shot over several technically correct shots.

## 9. Editorial time

Presentation time should not remain strictly 1:1, but source time must remain
truthful, monotonic, and inspectable.

Allowed operations are bounded playback-rate changes and duplicate-frame holds:

- normal play: `1.0x`;
- dense receipt or shot setup: typically `0.75x-0.9x` for a short interval;
- pre-reception readability hold: up to about `120 ms` on the last source state
  before contact;
- receipt emphasis: up to about `180 ms`, or a short mild slowdown around it;
- shot emphasis: short slowdown around contact, never a fabricated ball path;
- outcome hold: typically `0.8-1.5 s` after the result is established.

These are starting policy bounds, not universal constants; benchmark them. A
hold repeats a valid reconstructed state. It does not interpolate a player into
a new location. Audio, if added later, must use an explicit retiming policy.

The Edit Decision List records, for every output frame, its source timestamp and
operation. Event order is invariant. The planner must cap total expansion so the
clip stays natural, and should use the least retiming that passes comprehension
constraints. Counterattacks and long ball flights receive stricter slowdown caps
than compressed box combinations.

## 10. Visual hierarchy

Visual hierarchy is a time-varying instruction, not a permanent player style.
Default priority is:

1. ball at release, travel, and shot;
2. current primary actor;
3. incoming receiver or next verified protagonist;
4. goalkeeper and nearest causally relevant defenders;
5. secondary attackers required to explain the action;
6. remaining players and pitch detail.

The ordering changes by beat: during receiver anticipation, the receiver can
temporarily equal the ball; during shot flight, ball and goal dominate; during a
carry, actor and ball operate as one focal unit.

Permitted guidance should remain diegetic and restrained:

- modest scale, luminance, edge, or halo lift for the primary actor;
- temporary receiver pre-emphasis that ramps in and out;
- controlled de-emphasis of nonessential players, never disappearance;
- depth/z-order guarantees so the ball is never painted beneath a player;
- composition, negative space, and motion as the primary guidance tools.

No names, labels, arrows, cones, or tactical diagram overlays are required for
the consumer output. QA renders may expose all planner decisions.

## 11. Ball visibility without diagram language

Ball visibility needs a layered policy rather than a permanently oversized dot:

- maintain minimum screen-space diameter and edge contrast after zoom;
- render the ball above player markers, with a subtle adaptive separation halo;
- adapt the halo to local luminance and crowding, not to team identity;
- use short motion persistence only during fast travel, constrained so it cannot
  imply a false trajectory or previous ball state;
- frame to create negative space ahead of travel whenever possible;
- avoid placing the ball on top of a player's high-contrast edge at decisive
  contact; when unavoidable, use contact emphasis for a few frames;
- retain the relevant actor-ball pair, not the ball alone;
- widen rather than chase when high-speed ball motion would cause disorienting
  camera acceleration.

The ball treatment should feel like broadcast legibility: subtle enough to be
unnoticed when successful. Its intensity decays after acquisition and is capped
to avoid becoming annotation.

## 12. One camera cannot solve every goal

Use one coherent visual language, not one camera behavior. The semantic situation
selects a directing strategy. A compact carry may need a stable protagonist
track; a crowded first-time finish needs receipt emphasis and finish coverage; a
multi-stage build-up needs deliberate handoffs or stable combination coverage.

The selector uses observable complexity, not only a goal-type label:

- number of protagonist changes;
- action footprint and required zoom;
- direction changes;
- event density and shortest inter-event interval;
- local player density at decisive touches;
- ball visibility risk;
- required context span;
- semantic confidence.

This prevents brittle templates. Two crosses can receive different shot plans if
one has an isolated target and the other has a crowded far-post contest.

## 13. Benchmark-specific first plans

### Goal 1: fast combination

- Start with passer, receiver, goal, and the decisive cluster in a compact action
  frame.
- Begin receiver pre-attention at pass release.
- Use a two-subject handoff through ball travel.
- Apply restrained ball separation and a brief receipt emphasis.
- Keep receipt and shot as distinct beats even if one camera shot covers both.
- Protect shot contact from a cut, then hold the goal outcome.

The key change is not more zoom; it is perceptually separating `RECEIPT` from
`SHOT`.

### Goal 2: carry goal

- Preserve the current stable behavior as the control strategy.
- Establish the receiver, then use protagonist tracking through carry and shot.
- Add only a modest outcome hold and conditional ball treatment.

This case is the non-regression reference: the new layer must not make an already
clear action busier.

### Goal 3: multi-stage build-up

- Establish the full first pass relationship and attacking direction.
- Execute a passer-to-first-receiver handoff before committing the camera move.
- Preserve first receiver and second receiver together during the next setup.
- Use a motivated transition at the second pass, not continuous generic ball
  following.
- Tighten only once the final receiver is established; finish in
  shooter-ball-goal coverage and hold the resolution.

The key change is a planned chain of attention ownership, not a faster camera.

## 14. Failure and fallback policy

The planner must fail soft without inventing football:

| Missing or uncertain input | Directing response |
|---|---|
| Receiver unknown | Keep owner, ball, destination region, and context wide; no receiver pre-emphasis |
| Actor identity uncertain | Use spatial subject reference for framing; no identity-specific highlight |
| Ball temporarily unknown | Hold contextual coverage; do not synthesize a trajectory |
| Tactical importance absent | Direct chronological action only; do not imply causal importance |
| Required subjects cannot fit | Prefer wider coverage; never crop the decisive actor or goal merely for style |
| Rapid conflicting handoffs | Use stable multi-subject coverage and fewer cuts |
| Planner validation fails | Invoke the existing production renderer unchanged and record the fallback reason |

## 15. Validation

### Contract tests

- input reconstruction bytes and hash are unchanged;
- all referenced events and identities exist upstream;
- source time is nondecreasing and stays within the admitted window;
- event order and reconstructed state at a source timestamp are unchanged;
- no unsupported renderer instruction is emitted;
- deterministic reruns produce identical plans and instruction streams;
- legacy rendering remains available when no cinematography plan is supplied.

### Automated readability proxies

For every decisive beat, measure:

- ball screen-space size, contrast, occlusion, and edge collisions;
- primary actor visibility and distance from frame boundary;
- joint visibility of passer-ball-receiver during handoff;
- shooter-ball-goal and goalkeeper coverage during finishes;
- camera velocity, acceleration, cut timing, and screen-direction continuity;
- focus switches per second and minimum protagonist dwell;
- duration in which all required subjects satisfy their framing constraints.

These are guardrails, not substitutes for viewer testing.

### Viewer benchmark

Run blinded, first-view tests using the same questions as the existing benchmark:
who has the ball, who receives, who shoots, why the pass matters, and how the move
ends. Compare comprehension accuracy and response time against the unchanged
production baseline.

Acceptance criteria for the first release:

- Goal 2 does not regress on comprehension, smoothness, or enjoyment;
- Goals 1 and 3 improve immediate understanding, especially receiver and shooter
  identification;
- no clip introduces a false football inference;
- gains persist with labels and QA overlays disabled;
- results generalize to held-out examples of each directing family.

Use ablations to isolate value: semantic framing only, attention hierarchy only,
editorial timing only, and the complete plan. Do not declare success from the
three benchmark goals alone.

## 16. Delivery sequence

1. Publish versioned Beat Map, Shot Plan, Edit Decision List, and render
   instruction schemas.
2. Add a read-only adapter from the current reconstruction and admitted event
   semantics.
3. Implement the planner first for simple finish, carry, fast combination, and
   multi-pass build-up, with explicit conservative fallback.
4. Extend the renderer only with generic execution primitives: planned viewport,
   salience envelope, transition, and time mapping.
5. Add trace and QA modes that visualize beat boundaries, attention ownership,
   required-subject bounds, and source-to-presentation time.
6. Re-run the current three-goal benchmark, then a held-out directing-family
   suite before making the layer the default.

The architectural test is simple: changing the football situation may change
the shot list, but changing the shot list can never change the football.
