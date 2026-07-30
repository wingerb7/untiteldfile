# Tactical Intelligence Conformance Suite

## Corpus Version 0.1.0 — Structure Draft

> Applicable specification: `SPEC.md` version `0.1.0`
>
> Applicable profile: `offline-statsbomb-goal-analysis`
>
> Status: test protocol defined; official golden corpus not yet published

## 1. Purpose

This document defines how an implementation demonstrates conformance with `SPEC.md`. It contains no tactical detection requirements. Those belong exclusively to the specification.

Conformance answers one question: given an official input fixture and immutable configuration, did the implementation produce the required observable artifacts?

## 2. Corpus layout

The official machine-readable corpus SHALL use this layout:

```text
conformance/
  manifest.json
  configuration/
    v0.1.0.json
  schemas/
  fixtures/
    locatelli/
      manifest.json
      events.json
      three_sixty.json
    depay/
      manifest.json
      events.json
      three_sixty.json
    di_maria/
      manifest.json
      events.json
      three_sixty.json
  golden/
    locatelli/
      normalized.json
      synchronized.json
      world_model.json
      perception.json
      primitives.json
      patterns.json
      hypotheses_generated.json
      hypotheses_evaluated.json
      causal_chain.json
      explanation_model.json
      communication_plan.json
      scene_plan.json
      frame_manifest.json
    depay/
    di_maria/
  tolerances/
    v0.1.0.json
  reports/
```

Until these files are published with validated hashes, the suite is a structure draft and no implementation can claim full v0.1 conformance.

## Implemented Chapters 5–9 production slice

The repository implements the single production route in `src/source_selection.py`, `src/normalization.py`, `src/synchronization.py`, `src/world_model.py`, and `src/perception/engine.py`. It is exercised by `tests/test_production_chain.py` and the Locatelli integration in `tests/test_perception.py`.

Implemented and tested requirements include deterministic selection, 105×68 normalization, explicit `SOURCE_POSITION_OUT_OF_BOUNDS` availability, exact event/360 attachment, observation-scoped identity, World Model validation, direct-input authentication, byte-stable canonical serialization, and validated World-to-Perception gating. The Locatelli canonical fixture identity is StatsBomb match `3788754`, possession `40`, Open Data revision `b0bc9f22dd77c206ddedc1d742893b3bbe64baec`.

Repository-generated hashes are recorded in `audit/locatelli/perception_diagnostic.json`. They are regression evidence only. The official authenticated golden corpus and normative expected hashes remain unpublished, so this implementation does not claim complete Chapters 5–9 conformance.

Known limitation: Chapter-9 candidate materialization is large. Observation-scoped players are candidate-eligible only in their unique `OBSERVED` origin state; using them in `UNKNOWN` or `TERMINATED` states would contradict their state-scoped identity and creates an impractical cross-state candidate expansion.

## Implemented Chapter-10 first Recognition slice

The authenticated `PerceptionDataset -> RecognitionDataset` route is implemented in `src/recognition/` and tested by `tests/test_recognition.py`. The exact first catalog contains `PLAYER_MOVING`, `PLAYER_STATIONARY`, `PLAYER_NEAREST_BALL`, `PASSING_CORRIDOR_EXISTS`, and `PASSING_CORRIDOR_OBSTRUCTED`. It consumes no World Model, source, synchronized, rendering, or narrative data.

Fixture evidence is recorded in `audit/recognition/recognition_diagnostic.json`: Locatelli produces 44 RecognitionFrames and Depay 59; the pinned Di María document is rejected upstream and Recognition is not executed. Repository-generated Recognition hashes are deterministic regression evidence, not normative golden hashes. `BALL_CONTROLLED`, `BALL_FREE`, and receiver reachability remain undefined until canonical Perception evidence exists.

## Implemented Chapter-11 first Action Graph slice

The authenticated `RecognitionDataset -> ActionGraphDataset` route is implemented in `src/action_graph/` and tested by `tests/test_action_graph.py`. It maps only the five positive Recognition concepts to objective state nodes and emits `STATE_CONTINUATION` only for an identical action type and ordered participant list in immediately adjacent frames. It has no direct Perception dependency and imports no source, World Model, legacy intelligence, narrative, scene-planning, or rendering code.

Fixture evidence is recorded in `audit/action_graph/action_graph_diagnostic.json`. Locatelli and Depay execute through validated Action Graph deterministically. Di María retains its upstream fail-closed source rejection, and Action Graph is not executed. Pass, receipt, carry, shot, actor-recipient, same-player football continuation, tactical patterns, causality, confidence, narrative, and renderer instructions remain deliberately unsupported.

## 3. Root manifest

`conformance/manifest.json` SHALL contain:

```json
{
  "corpus_version": "0.1.0",
  "specification_version": "0.1.0",
  "profile": "offline-statsbomb-goal-analysis",
  "configuration_version": "0.1.0",
  "fixture_order": ["locatelli", "depay", "di_maria"],
  "fixtures": [],
  "files": []
}
```

Each `files` entry SHALL contain a relative POSIX path, media type, byte length, and lowercase SHA-256 digest. The manifest SHALL list every normative file except itself. A runner SHALL verify all entries before executing a test.

## 4. Fixture manifest

Each fixture manifest SHALL contain:

```json
{
  "fixture_id": "locatelli",
  "title": "string",
  "match_id": "string",
  "possession_id": "string",
  "profile": "offline-statsbomb-goal-analysis",
  "mandatory": true,
  "source_license": "string",
  "source_files": [],
  "expected_artifacts": [],
  "expected_execution_status": "SUCCEEDED"
}
```

Every expected artifact SHALL declare `stage`, `path`, `contract_version`, `comparison_class`, and either `sha256` or a named equivalence/tolerance rule.

## 5. Official fixtures

The first conformance corpus SHALL contain these three mandatory fixtures:

| Fixture | Case | Class | Purpose |
| --- | --- | --- | --- |
| `locatelli` | Locatelli attacking possession ending in a goal | Positive | Line break, continuation, return action, and causal-chain construction |
| `depay` | Depay attacking possession ending in a goal | Positive | Generalization beyond the first development case |
| `di_maria` | Di María, Argentina possession 52 | Negative | Phase classification: official source declares `From Counter` |

Fixture labels are informative. Machine identity SHALL come from the fixture manifest, match identifier, possession identifier, and hashes.

Before corpus publication, each fixture SHALL be audited to confirm that it meets every v0.1 scope condition. A case failing a scope condition SHALL be moved to the negative-fixture set and SHALL NOT be silently adjusted. The Di María case is such a case and SHALL expect `UNSUPPORTED_INPUT` with `SRC_UNSUPPORTED_PHASE`; it is not a mandatory positive fixture under profile v0.1.

The published suite SHALL additionally include negative fixtures for at least:

- malformed Events input;
- malformed 360 input;
- missing required 360 association;
- non-goal possession;
- set-piece possession;
- transition or counterattack;
- insufficient objective evidence.

## 6. Comparison procedures

### 6.1 Byte-identical artifacts

The runner SHALL apply the canonical JSON procedure from `SPEC.md`, compute SHA-256, and compare it with the manifest digest. Explanation Models SHALL use this class.

### 6.2 Structural artifacts

Structural comparison is allowed only when the manifest names a versioned executable comparator. The comparator SHALL return a Boolean result plus JSON Pointer paths for every difference. Human judgment is not a comparator.

Communication Plans and Scene Plans SHALL initially be `BYTE_IDENTICAL`. They MAY move to `STRUCTURAL` only after their equivalence relations have been normatively defined and published.

### 6.3 Tolerance artifacts

The tolerance file SHALL name every permitted deviation. Unnamed deviations have a tolerance of zero.

The renderer tolerance schema SHALL eventually define at least:

- frame count and duration;
- presentation timestamp;
- geometry in pixels;
- color difference and color space;
- font identity, shaping, bounds, and rasterization policy;
- alpha and compositing;
- frame-level perceptual metric;
- codec, pixel format, bitrate, and container metadata.

No numeric tolerance is normative until Rendering Contract Step 8 is approved.

## 7. Test execution

A conforming runner SHALL execute these steps in order:

1. validate the root manifest schema;
2. verify all file hashes and byte lengths;
3. select fixtures matching the claimed profile;
4. run each fixture in manifest order from a clean process state;
5. capture every required pipeline-boundary artifact;
6. canonicalize artifacts as required;
7. execute the declared comparison procedure;
8. record every requirement and artifact result;
9. emit one conformance report;
10. return failure if any mandatory assertion fails.

The runner SHALL NOT update golden outputs. Golden-output publication is a separate, reviewed corpus-version operation.

## 8. Conformance report

The report SHALL contain:

```json
{
  "specification_version": "0.1.0",
  "profile": "offline-statsbomb-goal-analysis",
  "configuration_version": "0.1.0",
  "corpus_version": "0.1.0",
  "implementation": {
    "name": "string",
    "version": "string",
    "revision": "string"
  },
  "started_at": "RFC 3339 timestamp",
  "finished_at": "RFC 3339 timestamp",
  "fixtures": [],
  "requirements": [],
  "result": "PASS | FAIL"
}
```

Runtime timestamps are report metadata and SHALL NOT participate in determinism comparisons.

## 9. Pass and claim rules

An implementation passes only if:

- all corpus integrity checks pass;
- all mandatory positive fixtures return `SUCCEEDED`;
- all mandatory negative fixtures return the exact expected status and error code;
- all required intermediate and final artifacts pass their declared comparison;
- all applicable requirement assertions pass;
- the second execution of every determinism fixture produces identical canonical artifacts.

A public conformance claim SHALL state the complete tuple:

```text
Tactical Intelligence Specification 0.1.0
profile offline-statsbomb-goal-analysis
configuration 0.1.0
conformance corpus 0.1.0
```

“Compatible with,” “based on,” or passing only selected fixtures is not a conformance claim.

## 10. Regression and corpus changes

Golden artifacts SHALL change only through a reviewed corpus release. Every change SHALL include:

- the affected specification requirement;
- the reason for the change;
- old and new hashes;
- expected effect on existing implementations;
- corpus version increment.

A code change in the reference implementation SHALL NOT by itself justify changing a golden artifact.
