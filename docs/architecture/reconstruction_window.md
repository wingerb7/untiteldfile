# Reconstruction Window

**Status:** Permanent architecture specification  
**Audience:** Contributors, maintainers, AI agents, and data-provider integrators

This document defines the boundary between reconstruction and every higher layer
of the system. A Reconstruction Window is the fundamental unit of football
understanding. Higher layers consume Reconstruction Windows; they do not consume
raw provider events directly.

## Motivation

Football event feeds and event-attached spatial observations are sparse. They
record selected moments, not a continuous measurement of every player and the
ball. Reconstructing an entire match—or usually even an entire possession—from
such evidence creates long intervals in which the system must either report
`UNKNOWN` or invent positions, identities, movement, and continuity.

The possession-length reconstruction benchmark demonstrated why continuous
reconstruction was rejected. Depending on the sequence, approximately 49–59%
of active track states were `UNKNOWN`; two possessions produced 73 and 78 tracks
despite there being at most 22 players on the pitch; anonymous track re-entry
created implausible movement; and a period-boundary case displayed stale state
for roughly a minute. The output was deterministic and traceable, but it was not
a credible continuous replay.

The event-window benchmark tested short, event-anchored segments instead. It
admitted 18 of 20 selected windows and reduced the mean `UNKNOWN` rate among
admitted windows to about 11.8%. These results do not guarantee that every short
window is usable. They establish the architectural point: reconstruction quality
tracks the local density and continuity of source evidence, so the reconstruction
boundary should be placed around supported actions rather than an assumed
continuous match state.

An event anchor supplies a factual reason for a segment to exist. A short bound
keeps interpolation between nearby observations, exposes gaps instead of hiding
them, and permits rejection when the source cannot support a faithful result.
This matches sparse event-plus-spatial data on its own terms.

## Definition

> A Reconstruction Window is a deterministic, bounded, source-supported segment
> of play that can be reconstructed without inventing football.

The terms are normative:

- **Deterministic** means identical normalized inputs, configuration, and
  reconstruction version produce the same canonical artifact and digest. It
  does not mean two providers must encode identical evidence.
- **Bounded** means the segment has explicit start and end times, lies wholly
  within one period, and is intentionally short. No state may silently leak in
  from an unbounded possession or match history.
- **Source-supported** means every event, identity, coordinate, transition, and
  inference is linked to evidence or is explicitly marked as a constrained
  derivation. Absence of support becomes `UNKNOWN` or rejection.
- **Segment of play** means one football action or a short chronological sequence
  of closely related actions. It is a local evidence unit, not a narrative unit.
- **Reconstruction** means producing a validated temporal representation of
  actors, ball, actions, positions, visibility, confidence, and provenance. It
  does not include tactical interpretation or editorial judgment.

“Without inventing football” is the governing test. Interpolation is allowed
only inside declared evidence, time, identity, period, and physical-motion gates.
It must never be presented as a direct observation.

## Scope

A window represents either:

- one football action, such as a pass, carry, or shot; or
- one short sequence of causally or temporally close actions, such as pass and
  reception, pass and carry, or carry and shot.

A full possession is normally outside scope. Possessions can span changing
camera regions, sparse observations, restarts, substitutions, identity gaps, and
long uneventful intervals. Possession membership is semantic metadata; it is not
evidence that every intervening state is observable or safely interpolated. A
possession may therefore yield zero, one, or several independent windows.

Window boundaries are evidence boundaries, not storytelling cuts. Adjacent
windows must not be merged merely to improve visual continuity.

## Lifecycle

```text
Discovery
    ↓
Selection
    ↓
Admission
    ↓
Reconstruction
    ↓
Validation
    ↓
World Model
    ↓
Recognition
    ↓
Tactical Analysis
    ↓
Editorial
    ↓
Rendering
```

1. **Discovery** locates provider records and candidate action anchors. It may
   index raw provider data but makes no claim that a candidate is reconstructable.
2. **Selection** chooses an anchor or short related sequence and proposes exact
   temporal and period bounds. Selection is deterministic and preserves source
   references.
3. **Admission** checks whether the proposed window has supported action types,
   sufficient observation, a valid period boundary, and adequate identity
   continuity. It records a defined admission state and reasons.
4. **Reconstruction** converts admitted, normalized evidence into canonical
   temporal state. It applies only bounded, declared derivations and represents
   unsupported state as `UNKNOWN`.
5. **Validation** verifies schema, timing, identity, motion, provenance,
   determinism, and digest integrity. A selected window is not a consumable
   accepted artifact until reconstruction validation passes.
6. **World Model** exposes the validated window as provider-neutral football
   entities and state. It is read-only with respect to reconstruction.
7. **Recognition** identifies football concepts present in the world model. It
   may not rewrite reconstructed facts or fill unknown state.
8. **Tactical Analysis** relates recognized concepts and explains football
   significance. Its conclusions remain separate, derived artifacts.
9. **Editorial** decides what is relevant, interesting, and publishable. It may
   select or arrange windows but cannot alter their factual content.
10. **Rendering** presents accepted reconstruction and optional downstream
    overlays. Presentation devices for uncertainty must remain visibly distinct
    and must never flow back into reconstruction or the world model.

Stages may produce separate artifacts. Whatever the packaging, their ownership
and dependency direction must remain as shown. At fixture scope, discovery and
admission outcomes are indexed by the [Window Manifest](#window-manifest).

## Window Contract

The canonical contract must contain the following fields. Implementations may
add versioned fields, but must not weaken these meanings.

| Field | Requirement and meaning |
|---|---|
| `window_id` | Stable, unique identifier derived or assigned under a documented scheme. It identifies the logical window, not a render or analysis. |
| `fixture_id` | Provider-neutral fixture identifier, with provider identifiers retained in provenance where needed. |
| `competition` | Normalized competition identity or descriptor, including season/edition when available; absence must be explicit. |
| `period` | The single match period containing the complete window. A window must never cross a period boundary. |
| `start_time` | Inclusive start on the canonical period-relative match clock. Its precision and source are preserved. |
| `end_time` | Inclusive or explicitly defined terminal bound on the same clock and in the same period as `start_time`. |
| `duration` | Non-negative `end_time - start_time`, in a declared unit. It is derived deterministically and must agree with the bounds. |
| `selected_events` | Ordered, normalized event references selected for the window. Each includes enough source identity and provenance to audit the selection. These are evidence, not a provider payload escape hatch for higher layers. |
| `supported_actions` | Ordered provider-neutral actions justified by `selected_events`; unsupported provider event types are not silently translated. |
| `reconstruction` | Canonical temporal state for actors, ball, action boundaries, visibility, observation status, and `UNKNOWN` values. It is populated only for admitted and validated output; rejected windows use an absent or null value rather than fabricated state. |
| `provenance` | Trace from every factual or derived reconstruction element to provider records, normalization/version information, and derivation method. |
| `confidence` | Structured reconstruction confidence and limitations, including its scale and basis. It expresses evidence quality, not tactical certainty, and never converts `UNKNOWN` into known state. |
| `admission` | Exactly one admission state from the closed set below. It governs whether higher layers may consume `reconstruction`. |
| `rejection_reason` | Null for fully accepted windows; otherwise a stable, machine-readable reason or ordered reasons with optional human explanation. Accepted-with-limitations windows record their limitations here or through an equivalently explicit limitations field. |
| `reconstruction_sha256` | SHA-256 of the canonical reconstruction representation under a documented serialization. It is present for a materialized, validated reconstruction and absent/null for a rejected, non-reconstructed window. |

Contract-level identifiers, times, enumerations, and provenance must be normalized
before crossing this boundary. Raw provider payloads may be retained inside
provenance for audit, but no higher layer may depend on their shape or semantics.

## Window Manifest

A football match is not represented as one continuous reconstruction. It is
represented by independently admitted or rejected Reconstruction Windows,
indexed at fixture scope:

```text
Fixture
    ↓
Window Discovery
    ↓
Candidate Windows
    ↓
Admission
    ↓
Accepted Windows
    ↓
Rejected Windows
    ↓
Window Manifest
```

The Window Manifest is the canonical reconstruction index for one fixture. It
does not contain football state. It indexes every Reconstruction Window generated
for that fixture, including accepted and rejected windows, while each window
remains an independent artifact governed by the Window Contract.

The Manifest is the primary fixture-level interface consumed by the Editorial
Engine, Recognition batch processing, Tactical batch analysis, benchmark
validation, and content generation. These consumers use it to enumerate and
resolve windows without depending on provider discovery output or scanning raw
events.

### Manifest Contract

A canonical Window Manifest contains at least:

| Field | Requirement and meaning |
|---|---|
| `fixture_id` | Provider-neutral identifier of the fixture whose windows are indexed. |
| `provider` | Source-provider identity and, where relevant, source dataset or revision reference. It is metadata, not a provider-specific interface for consumers. |
| `reconstruction_version` | Version of the reconstruction implementation and contract used by the referenced artifacts. |
| `discovery_version` | Version of the deterministic discovery and candidate-selection policy. |
| `generated_at` | Timestamp at which this immutable manifest artifact was generated. It is metadata and must not affect deterministic window contents. |
| `candidate_window_count` | Total number of candidate windows considered for admission. |
| `accepted_window_count` | Number of candidates with an accepted admission state, including accepted-with-limitations where policy defines it as consumable. |
| `rejected_window_count` | Number of candidates with a rejected admission state. Counts must reconcile with the candidate total. |
| `accepted_window_ids` | Deterministically ordered identifiers of accepted independent Reconstruction Window artifacts. |
| `rejected_window_ids` | Deterministically ordered identifiers of rejected independent Reconstruction Window audit artifacts. |
| `aggregate_metrics` | Fixture-level summaries derived from all indexed outcomes, with definitions and calculation versions preserved. They do not alter admission or window facts. |
| `benchmark_metrics` | Optional, explicitly versioned validation and comparison measurements. Absence is explicit and does not affect the indexed artifacts. |
| `manifest_sha256` | SHA-256 of the canonical manifest representation under a documented serialization, excluding or canonically handling the digest field itself. |

The Manifest references windows; it does not embed or redefine their football
state. Every Reconstruction Window remains independently addressable,
provenance-preserving, and digestible. Modifying, replacing, adding, or removing
one referenced window produces a new manifest version and digest. Existing
manifests remain immutable audit records.

### Architectural Purpose

The Manifest provides deterministic fixture indexing, reproducible batch input,
benchmark comparison, provider-independent discovery output, and an immutable
audit trail. It lets higher layers process a fixture as a stable collection while
preserving admission outcomes and the independence of each window.

The Manifest is to Reconstruction Windows what a Git tree is to commits. It
organises them. It does not redefine them.

## Admission

Admission is an explicit outcome, never an implicit truthiness check:

- **`ACCEPTED`** — source evidence, identity continuity, timing, supported actions,
  and validation satisfy the reconstruction policy without a material declared
  limitation. Higher layers may consume the validated reconstruction.
- **`ACCEPTED_WITH_LIMITATIONS`** — the window remains truthful and usable, but
  has material explicit limitations such as elevated `UNKNOWN` coverage or
  reduced identity certainty. Consumers must preserve those limitations and may
  impose stricter policies for a particular use.
- **`REJECTED_INSUFFICIENT_OBSERVATION`** — source coverage is too sparse or too
  discontinuous to reconstruct the bounded action faithfully.
- **`REJECTED_IDENTITY_FRAGMENTATION`** — actor continuity cannot be maintained
  within policy without merging, duplicating, or authenticating identities
  beyond the evidence.
- **`REJECTED_PERIOD_BOUNDARY`** — the proposed bounds cross match periods or
  would require temporal/state continuity across a period boundary.
- **`REJECTED_UNSUPPORTED_ACTION`** — the anchor or sequence contains no action
  the reconstruction implementation can represent under the current contract.

Rejected windows remain valuable audit records, but their reconstruction must
not enter the world model, recognition, tactical, editorial, or rendering path.
Admission policy can become stricter over time; state meanings must remain stable.

## Reconstruction Guarantees

For an `ACCEPTED` or `ACCEPTED_WITH_LIMITATIONS` window whose validation passed,
higher layers may assume:

- deterministic selection and reconstruction for identical normalized inputs,
  configuration, and versions;
- explicit, internally consistent period-relative timing and window bounds;
- chronological selected events and supported actions within those bounds;
- provenance for every visible factual object and every derived state;
- a clear distinction between observed, bounded-interpolated, and `UNKNOWN`
  state;
- interpolation bounded by declared evidence, time-gap, period, identity, and
  physical-speed gates;
- no implied motion through a failed speed or continuity gate;
- stable track identities within the accepted window to the degree stated by
  identity status and confidence; anonymous identities remain anonymous;
- no duplicate claim to the same authenticated identity at one time;
- explicit limitations and confidence, preserved by all consumers;
- a canonical reconstruction digest that detects changes to reconstructed truth;
  and
- no dependency on recognition, tactical analysis, editorial selection, or
  rendering decisions.

`ACCEPTED_WITH_LIMITATIONS` provides the same truthfulness guarantees, not the
same completeness. Consumers must inspect its limitations.

## Explicit Non-Guarantees

Reconstruction intentionally does **not** promise:

- continuous player or ball tracking;
- complete match or possession reconstruction;
- knowledge of off-camera or otherwise unobserved movement;
- authenticated identity for anonymous observations;
- continuity between anonymous observations unless supported within policy;
- exact trajectories or ball physics between sparse observations;
- that every player is visible, located, or represented at every instant;
- equivalence of confidence values across independently calibrated providers;
- tactical meaning, intent, causality, pressure, formation, or football concept;
- story selection, editorial importance, captions, or publishability;
- visual continuity or a broadcast-like replay;
- continuity across periods, windows, fixtures, or provider revisions; or
- that every discovered candidate will be admitted.

No higher layer may infer one of these properties merely because a window was
accepted.

## Separation of Responsibilities

Reconstruction answers: **“What happened, to the extent supported by source
evidence?”**

Recognition answers: **“What football concept is present?”**

Storytelling and editorial answer: **“What is interesting enough to publish?”**

These are independent layers. Reconstruction must not use a desired tactical
finding or story to choose coordinates, identities, timing, or admission.
Recognition must not repair reconstruction or treat `UNKNOWN` as negative
evidence. Editorial and rendering may select and present derived material, but
must preserve the underlying reconstruction, provenance, admission, confidence,
and uncertainty. Feedback from a higher layer may trigger a new reconstruction
request; it may never mutate an existing canonical window.

## Data Provider Independence

The contract describes football evidence, not a StatsBomb schema. Provider
adapters are responsible for discovery, validation, and normalization into the
contract’s identifiers, clocks, actions, observations, identities, and
provenance.

The same Reconstruction Window abstraction applies to StatsBomb, API-Football,
Opta, Wyscout, optical or wearable tracking providers, and future sources. A
provider with dense tracking may produce more observed state, lower uncertainty,
and richer provenance. A provider with event-only data may reject more windows
or reconstruct only actions with defensible endpoints. Those are implementation
and evidence-quality differences, not reasons to change the boundary.

Provider replacement may change adapters, reconstruction algorithms, confidence
calibration, and optional extensions. The interface consumed by World Model and
higher layers must remain stable. Provider-specific fields may appear only under
namespaced provenance or versioned extensions and must not become required input
to higher layers. Fixture-level provider output is exposed through the
[Window Manifest](#window-manifest), while the evolution rules for both public
interfaces are defined by [Contract Stability](#contract-stability).

## Examples

### Pass, receipt, shot

```text
PASS
  ↓
BALL_RECEIPT
  ↓
SHOT
```

This can form one window when the three events are close in time, remain in one
period, share source-supported actor/ball continuity, and the observations cover
the pass, reception, and shot without unsafe gaps. The window states only the
sequence. Whether it is a line break, chance creation, or compelling story is a
downstream question.

### Carry, pass, cross

```text
CARRY
  ↓
PASS
  ↓
CROSS
```

This can form one window when the carry leads directly into the pass and the
provider represents the cross as a supported action or supported pass subtype.
Temporal proximity alone is insufficient: action support, identity continuity,
and observation gates must also pass. Otherwise the actions become separate
windows or the candidate is rejected.

### Pass and reception

```text
PASS
  ↓
BALL_RECEIPT
```

This is a natural window when both endpoints are evidenced and the short interval
between them can be represented within motion limits. Missing off-ball locations
remain `UNKNOWN`; they are not required to invent a full team shape.

### Carry and shot

```text
CARRY
  ↓
SHOT
```

This is one window only when ball ownership and actor continuity are supported
through the transition. A long gap, identity break, or period boundary prevents
the merge regardless of narrative appeal.

## Future Extensions

The contract can be extended with richer tracking samples, player identity,
ball physics, optical tracking, probabilistic uncertainty, multi-camera evidence,
calibration metadata, or provider-fusion provenance. These additions improve the
implementation’s observations, association, interpolation, and confidence.

They do not redefine a Reconstruction Window. New data must still be bounded,
source-supported, provenance-preserving, deterministic under declared inputs,
and explicit about uncertainty. Extensions must be versioned, additive where
possible, and ignorable by consumers that implement the base contract. A future
implementation may admit windows that current evidence forces the system to
reject; it may not retroactively turn unsupported claims into facts.

## Contract Stability

The Reconstruction Window is a versioned public contract. The Window Manifest
is a versioned public fixture-level index of those contracts. Their stability
separates what higher layers may rely on from how reconstruction happens.

The following rules apply:

- Existing semantics must never silently change.
- New fields should be additive whenever possible.
- Existing fields may be deprecated but not repurposed.
- Breaking semantic changes require a new contract version.
- World Model, Recognition, Tactical Analysis, and Editorial consume the public
  contract rather than implementation details.
- Provider adapters may evolve independently as long as the public contract
  remains valid.

This separation prevents improvements in evidence ingestion or reconstruction
from propagating as unrelated changes through higher architectural layers.
StatsBomb improvements and integrations with API-Football, Opta, Wyscout, or
tracking data may increase observation density, identity quality, confidence,
and window admission. They must not force World Model, Recognition, Tactical
Analysis, or Editorial to depend on a new provider schema or reconstruction
implementation. When a genuinely new meaning is required, it is introduced
explicitly through contract versioning rather than hidden behind an existing
field.

## Architectural Principles

The following are long-term project rules:

1. **Never invent football.**
2. **Reject rather than fabricate.**
3. **Reconstruction precedes recognition.**
4. **Truth precedes storytelling.**
5. **Every visible factual object has provenance.**
6. **Observed, derived, and unknown state remain distinguishable.**
7. **Uncertainty remains explicit at every higher layer.**
8. **Interpolation is bounded by evidence and physical plausibility.**
9. **Period, identity, and source gaps are hard boundaries unless evidence proves continuity.**
10. **Higher layers consume Reconstruction Windows, never raw provider events.**
11. **Higher layers never mutate canonical reconstruction.**
12. **Provider changes alter adapters and implementation, not the architectural contract.**

Any design that violates these principles must be treated as an architecture
change, not a local implementation detail.
