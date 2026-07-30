# Tactical Intelligence Specification

## Version 0.1.0 — Working Draft

> Status: Step 2 in progress — Chapter 5 normative; Chapters 6–8 pending
>
> Specification profile: `offline-statsbomb-goal-analysis`

## 1. Scope

### 1.1 Purpose

This specification defines the observable behavior of a system that transforms a supported StatsBomb attacking possession into an evidence-based tactical explanation and a rendered MP4 video.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **NOT RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be interpreted as described in BCP 14 when, and only when, they appear in capitals.

### 1.2 Implementation independence

This specification defines observable behavior, interfaces, contracts, algorithms, and conformance requirements. It intentionally does not prescribe programming language, software architecture below the interface level, in-memory data structures, optimization strategies, or implementation techniques unless they affect observable behavior.

A conforming implementation MAY be written in any programming language and MAY use any internal architecture. Internal choices MUST NOT change the artifacts observable at a specified pipeline boundary.

### 1.3 Specification completeness

> If two reasonable engineers can make observably different choices while implementing the same requirement, that requirement is not yet complete.

A normative requirement is complete only when its inputs, outputs, algorithm, parameters, ordering, error behavior, and conformance procedure are defined. Text marked **Informative** does not create a conformance requirement.

### 1.4 Supported profile

Version 0.1 defines exactly one capability profile: `offline-statsbomb-goal-analysis`.

An implementation claiming this profile SHALL support only the following normative analysis domain:

| Dimension | Required value |
| --- | --- |
| Source data | StatsBomb Events plus StatsBomb 360 |
| Execution | Offline, finite-input processing |
| Unit of analysis | One possession |
| Possession team | The attacking team |
| Phase | Positional attack |
| Outcome | Possession ending in a goal |
| Primary artifact | Canonical Explanation Model JSON |
| Planning artifacts | Canonical Communication Plan JSON and Scene Plan JSON |
| Presentation artifact | MP4 video |

The profile SHALL accept a possession only if every condition above can be established from the input contract. Failure to meet a condition SHALL produce the specified `UNSUPPORTED_INPUT` result; it SHALL NOT produce a tactical explanation.

### 1.5 Explicit non-goals

Version 0.1 does not specify:

- live or streaming analysis;
- defending possessions as the primary analysis perspective;
- transitions, counterattacks, corners, free kicks, throw-ins, or penalties;
- possessions not ending in a goal;
- player tracking reconstructed from broadcast video;
- optical tracking feeds;
- audio, commentary, or broadcast-video ingestion;
- machine-learning or probabilistic-model requirements;
- large language models;
- natural-language generation outside the controlled vocabulary;
- interactive, web, dashboard, or report output;
- counterfactual recommendations;
- performance requirements for real-time execution.

An implementation MAY contain such capabilities, but they are outside this specification and MUST NOT affect results produced under the v0.1 profile.

### 1.6 Source of truth

For observable system behavior, `SPEC.md` is normative. `CONFORMANCE.md` defines the official verification procedure and corpus. `REFERENCE-IMPLEMENTATION.md` is informative. `MASTERPLAN.md` provides vision and architectural rationale.

If these documents conflict on observable behavior, precedence SHALL be:

1. `SPEC.md`;
2. `CONFORMANCE.md` for test execution details explicitly delegated by this specification;
3. `REFERENCE-IMPLEMENTATION.md`;
4. `MASTERPLAN.md`.

An implementation defect does not amend this specification. A specification change requires a new specification version.

## 2. Conventions and normative language

### 2.1 Requirement identifiers

Every testable requirement SHALL have a stable identifier of the form `TIP-<SECTION>-<NUMBER>`. Identifiers SHALL NOT be reused after removal.

- **TIP-CONF-001:** A claimed profile SHALL be named explicitly.
- **TIP-CONF-002:** A conforming implementation SHALL pass every mandatory fixture for its claimed specification version and profile.
- **TIP-DET-001:** Repeated execution with identical input, configuration, and specification version SHALL produce identical canonical artifacts.
- **TIP-PROV-001:** Every derived tactical claim SHALL reference the evidence from which it was derived.
- **TIP-SEP-001:** A downstream stage SHALL NOT introduce a tactical claim absent from its upstream input.

### 2.2 Data representation

Unless a later section states otherwise:

- interchange artifacts SHALL be UTF-8 encoded JSON;
- JSON member names SHALL use `snake_case`;
- identifiers SHALL be case-sensitive strings;
- arrays whose order is specified SHALL preserve that order;
- timestamps SHALL be decimal seconds from the start of the relevant match period;
- durations SHALL be decimal seconds;
- confidence SHALL be a number in the closed interval `[0, 1]`;
- source coordinates SHALL use the StatsBomb coordinate system: nominal length `120`, nominal width `80`, origin at the upper-left of the attacking-left-to-right view; finite source locations outside those nominal bounds follow Sections 5.6 and 6.7;
- unavailable values SHALL be represented by JSON `null`, never by an empty string or sentinel number;
- non-finite numbers are forbidden;
- duplicate JSON member names are forbidden.

Metric quantities derived from pitch coordinates SHALL first convert coordinates using `x_m = x * 105 / 120` and `y_m = y * 68 / 80`.

### 2.3 Canonical JSON

Where byte identity is required, an artifact SHALL be canonicalized before comparison as follows:

1. encode as UTF-8 without a byte-order mark;
2. sort object member names lexicographically by Unicode code point;
3. preserve array order;
4. emit no insignificant whitespace;
5. encode `true`, `false`, and `null` in lowercase;
6. round calculated decimal values to six digits after the decimal point using round-half-to-even;
7. serialize integral values without a decimal point;
8. terminate without a trailing newline.

Source values explicitly designated as opaque SHALL NOT be numerically transformed.

### 2.4 Deterministic ordering and tie-breaking

Unless a stage defines a more specific ordering, records SHALL be ordered by:

1. canonical timestamp ascending;
2. source event index ascending;
3. source identifier ascending by Unicode code point.

Ranking ties SHALL be resolved by evidence confidence descending, then earliest supporting event, then canonical identifier ascending. Implementations SHALL NOT use input hash-map order, thread scheduling, random selection, or platform locale as a tie-breaker.

### 2.5 Controlled status vocabulary

Every pipeline execution SHALL end in exactly one status:

| Status | Meaning |
| --- | --- |
| `SUCCEEDED` | Every mandatory stage completed and all required artifacts were emitted. |
| `INVALID_INPUT` | Input failed schema or integrity validation. |
| `UNSUPPORTED_INPUT` | Input was valid but outside the claimed capability profile. |
| `INSUFFICIENT_EVIDENCE` | Input was supported, but the minimum evidence contract was not met. |
| `PROCESSING_ERROR` | A conforming result could not be produced because execution failed. |

Only `SUCCEEDED` SHALL include an Explanation Model, Communication Plan, Scene Plan, and MP4 result.

## 3. Conformance model

### 3.1 Conformance target

Conformance applies to an implementation plus an immutable tuple of:

```text
(specification_version, profile, configuration_version, conformance_corpus_version)
```

Claims lacking any tuple member are invalid.

### 3.2 Conformance levels

Artifacts use exactly one comparison class:

| Class | Requirement |
| --- | --- |
| `BYTE_IDENTICAL` | Canonical bytes and SHA-256 hash SHALL match. |
| `STRUCTURAL` | The normative equivalence algorithm SHALL return true. |
| `TOLERANCE` | Every named measurement SHALL remain within its declared tolerance. |

“Semantically identical” is not a valid test condition unless an executable equivalence algorithm is versioned in the conformance corpus.

### 3.3 Required conformance boundaries

The official corpus SHALL be capable of observing the output of every boundary:

1. source validation;
2. normalization;
3. synchronization;
4. World Model construction;
5. perception;
6. primitive recognition;
7. pattern recognition;
8. hypothesis generation;
9. hypothesis evaluation;
10. causal-chain construction;
11. Explanation Model construction;
12. Communication Plan construction;
13. Scene Plan construction;
14. rendering.

An implementation MAY combine stages internally, but SHALL expose each boundary in conformance mode.

### 3.4 Conformance statement

A conforming implementation SHALL satisfy every mandatory requirement in this specification and SHALL pass every official conformance fixture applicable to the claimed specification version and capability profile. Canonical Explanation Models SHALL be byte-identical after the specified canonicalization procedure. Communication Plans and Scene Plans SHALL satisfy their formally defined equivalence relations. Rendered outputs MAY differ only within explicitly defined temporal, geometric, chromatic, typographic, encoding, and perceptual tolerances. Any deviation outside these requirements constitutes non-conformance.

## 4. End-to-end processing contract

### 4.1 Normative pipeline

A `SUCCEEDED` execution SHALL process data in this logical order:

```text
StatsBomb Events + StatsBomb 360
              |
              v
      Source Validation
              |
              v
          Normalizer
              |
              v
       Synchronization
              |
              v
         World Model
              |
              v
          Perception
              |
              v
    Primitive Recognition
              |
              v
     Pattern Recognition
              |
              v
   Hypothesis Generation
              |
              v
   Hypothesis Evaluation
              |
              v
 Causal Chain Construction
              |
              v
      Explanation Model
              |
              v
     Communication Plan
              |
              v
          Scene Plan
              |
              v
           Renderer
              |
              v
             MP4
```

The arrows define information dependency, not process or deployment boundaries.

### 4.2 Stage contract

Every stage SHALL:

1. validate its complete input before deriving output;
2. consume only its declared input contract and immutable configuration;
3. emit exactly one versioned output contract or one defined error;
4. attach provenance to every derived value;
5. preserve upstream identifiers without reinterpretation;
6. refrain from modifying an upstream artifact;
7. behave deterministically;
8. emit stage name, contract version, configuration version, and execution status.

### 4.3 Separation requirements

- **TIP-PIPE-001:** Normalization SHALL translate source representation but SHALL NOT infer tactical meaning.
- **TIP-PIPE-002:** Synchronization SHALL align observations in canonical time but SHALL NOT recognize tactics.
- **TIP-PIPE-003:** The World Model SHALL represent entities, state, space, and relationships but SHALL NOT rank explanations.
- **TIP-PIPE-004:** Perception SHALL emit objective geometric, temporal, and relational features but SHALL NOT emit tactical labels.
- **TIP-PIPE-005:** Primitive Recognition SHALL classify atomic tactical actions from perception evidence.
- **TIP-PIPE-006:** Pattern Recognition SHALL classify temporal compositions of primitives and state transitions.
- **TIP-PIPE-007:** Hypothesis Generation SHALL produce candidate explanations and SHALL NOT select a winner.
- **TIP-PIPE-008:** Hypothesis Evaluation SHALL score support, contradiction, completeness, and uncertainty.
- **TIP-PIPE-009:** Causal Chain Construction SHALL connect evaluated hypotheses into an ordered explanation and SHALL NOT add unsupported findings.
- **TIP-PIPE-010:** The Explanation Model SHALL be the sole tactical input to Communication Planning.
- **TIP-PIPE-011:** The Communication Plan SHALL select and sequence content but SHALL NOT define pixels or frames.
- **TIP-PIPE-012:** The Scene Plan SHALL define audiovisual execution but SHALL NOT add tactical claims.
- **TIP-PIPE-013:** The Renderer SHALL render only the Scene Plan and referenced source facts.

### 4.4 Execution envelope

An execution request SHALL contain:

```json
{
  "specification_version": "0.1.0",
  "profile": "offline-statsbomb-goal-analysis",
  "configuration_version": "string",
  "source_dataset": "statsbomb-open-data",
  "source_revision": "b0bc9f22dd77c206ddedc1d742893b3bbe64baec",
  "match_id": 3869685,
  "possession_id": 52,
  "events": "StatsBomb Events document",
  "three_sixty": "StatsBomb 360 document"
}
```

An execution result SHALL contain:

```json
{
  "specification_version": "0.1.0",
  "profile": "offline-statsbomb-goal-analysis",
  "configuration_version": "string",
  "status": "SUCCEEDED | INVALID_INPUT | UNSUPPORTED_INPUT | INSUFFICIENT_EVIDENCE | PROCESSING_ERROR",
  "artifacts": [],
  "errors": []
}
```

Artifact entries SHALL contain `stage`, `contract_version`, `media_type`, `sha256`, and a caller-resolvable `location`. Error entries SHALL contain `code`, `stage`, `message`, and an ordered array of `source_references`.

### 4.5 Failure propagation

Stages SHALL fail closed. If a mandatory upstream stage does not emit a valid artifact, downstream stages SHALL NOT execute. Partial diagnostic artifacts MAY be retained but SHALL be marked `non_conforming_diagnostic` and SHALL NOT appear as successful outputs.

## 5. Source Input Contract

> **Editorial status:** Normative in Working Draft 0.1.0.

### 5.1 Purpose

This chapter defines the sole source representation accepted by profile `offline-statsbomb-goal-analysis`. It defines source identity, consumed fields, structural validation, possession selection, Events-to-360 relations, scope classification, and source-stage errors.

The source stage SHALL validate and select data. It SHALL NOT rename provider fields, convert timestamps or coordinates, infer missing values, associate observations in time, identify unlabelled players, calculate geometry, or infer tactical meaning.

### 5.2 Supported source and revision

The only normative source dataset is:

| Property | Required value |
| --- | --- |
| Dataset | StatsBomb Open Data |
| Repository | `https://github.com/statsbomb/open-data.git` |
| Git commit | `b0bc9f22dd77c206ddedc1d742893b3bbe64baec` |
| Commit date | `2026-05-26T15:59:55+01:00` |
| Events path | `data/events/<match_id>.json` |
| 360 path | `data/three-sixty/<match_id>.json` |

StatsBomb Open Data does not embed a separately versioned JSON schema in these documents. For v0.1, the full Git commit identifier is therefore the source schema and dataset revision.

- **TIP-SRC-001:** The request `source_dataset` SHALL equal `statsbomb-open-data`.
- **TIP-SRC-002:** The request `source_revision` SHALL equal the full commit identifier above.
- **TIP-SRC-003:** Input obtained through `statsbombpy`, a dataframe, an API, a transformed possession file, or any other adapter is not a normative source document. Such input MAY be accepted only if an adapter first emits byte-equivalent values for every consumed field and identifies the pinned Open Data revision.
- **TIP-SRC-004:** A different Open Data revision SHALL return `UNSUPPORTED_INPUT` with `SRC_UNSUPPORTED_REVISION`; an implementation SHALL NOT assume schema compatibility from repository history or a branch name such as `master`.

### 5.3 Inputs

The source stage consumes the following members from the execution request defined in Section 4.4:

| Member | Type | Required | Constraint |
| --- | --- | --- | --- |
| `source_dataset` | string | yes | Exact value from Section 5.2. |
| `source_revision` | string | yes | Forty lowercase hexadecimal characters; exact value from Section 5.2. |
| `match_id` | integer | yes | Positive and equal to the filename stem represented by both documents. |
| `possession_id` | integer | yes | Positive. |
| `events` | JSON array | yes | Complete pinned `data/events/<match_id>.json` document. |
| `three_sixty` | JSON array | yes | Complete pinned `data/three-sixty/<match_id>.json` document. |

The documents SHALL be supplied as decoded JSON values without preprocessing. Unknown object members are permitted and SHALL be ignored. Implementations SHALL NOT reject an object solely because it contains a field not listed in this chapter.

### 5.4 Consumed Events fields

Only Events records whose top-level `possession` equals the requested `possession_id` participate in profile and record selection. Fields marked conditional are required only for the named event type.

| JSON path | Type | Presence | Consumed meaning |
| --- | --- | --- | --- |
| `id` | string | required | Globally unique source event identifier. |
| `index` | integer | required | Source ordering key, positive. |
| `period` | integer | required | Match period, one of `1`, `2`, `3`, `4`. |
| `timestamp` | string | required | Period-relative time, exact grammar `HH:MM:SS.sss`. |
| `minute` | integer | required | Non-negative source display minute; preserved for audit only. |
| `second` | integer | required | Integer in `[0,59]`; preserved for audit only. |
| `duration` | number | optional | Non-negative event duration in seconds. Absence is distinct from zero. |
| `type.id` | integer | required | Provider event-type identifier. |
| `type.name` | string | required | Provider event-type name. |
| `possession` | integer | required | Provider possession identifier. |
| `possession_team.id` | integer | required | Possession-team identifier. |
| `possession_team.name` | string | required | Display label; not identity-bearing. |
| `play_pattern.id` | integer | required | Provider play-pattern identifier. |
| `play_pattern.name` | string | required | Used for v0.1 scope classification. |
| `team.id` | integer | required | Acting-team identifier. |
| `team.name` | string | required | Display label; not identity-bearing. |
| `player.id` | integer | required for retained types | Acting-player identifier. |
| `player.name` | string | required for retained types | Display label; not identity-bearing. |
| `location` | array[number] | required for retained types | Exactly two finite coordinates `[x,y]`. |
| `pass.recipient.id` | integer | Pass | Intended recipient identifier. |
| `pass.recipient.name` | string | Pass | Display label. |
| `pass.end_location` | array[number] | Pass | Exactly two finite coordinates `[x,y]`. |
| `pass.outcome.id` | integer | optional, Pass | Provider outcome identifier. Absence denotes a completed pass under the pinned source semantics. |
| `pass.outcome.name` | string | optional, Pass | Provider outcome label. |
| `carry.end_location` | array[number] | Carry | Exactly two finite coordinates `[x,y]`. |
| `shot.end_location` | array[number] | Shot | Two or three finite coordinates `[x,y]` or `[x,y,z]`. |
| `shot.outcome.id` | integer | Shot | Provider shot-outcome identifier. |
| `shot.outcome.name` | string | Shot | Provider shot-outcome label. |
| `shot.statsbomb_xg` | number | Shot | Finite number in `[0,1]`. |

The retained event types are exactly:

| `type.id` | `type.name` |
| ---: | --- |
| 30 | `Pass` |
| 42 | `Ball Receipt*` |
| 43 | `Carry` |
| 16 | `Shot` |

All possession events, including non-retained types, SHALL be inspected when validating possession identity, ordering, team consistency, phase, and terminal outcome. Only retained types SHALL be emitted by the source stage.

The following existing source values are explicitly not consumed in v0.1: pass length, angle, height, body part and type; shot body part, technique, type, key-pass link and embedded shot freeze frame; event tactics, under-pressure flags, related events and provider-derived metrics other than `shot.statsbomb_xg`. An implementation SHALL NOT let an unconsumed value affect a v0.1 artifact.

### 5.5 Consumed StatsBomb 360 fields

Each top-level 360 record consumes:

| JSON path | Type | Presence | Constraint |
| --- | --- | --- | --- |
| `event_uuid` | string | required | References exactly one Events `id` from the same match document. |
| `visible_area` | array[number] | required | Even number of finite values, at least six, interpreted as ordered `[x1,y1,...,xn,yn]`. |
| `freeze_frame` | array[object] | required | May be empty at source-contract level. |

Each `freeze_frame` element consumes:

| JSON path | Type | Presence | Constraint |
| --- | --- | --- | --- |
| `location` | array[number] | required | Exactly two finite coordinates `[x,y]`. |
| `teammate` | boolean | required | Relative to the event actor. |
| `actor` | boolean | required | Whether this observation represents the event actor. |
| `keeper` | boolean | required | Whether this observation represents a goalkeeper. |

StatsBomb 360 freeze-frame elements in the pinned source do not contain stable player identifiers. The source stage SHALL NOT create identities for non-actor observations. An observation with `actor=true` MAY later inherit the retained event's `player.id`, but that operation belongs to the Normalized Data Model algorithm in Section 6.

### 5.6 Coordinate and scalar validation

- Every Event and freeze-frame location SHALL contain exactly two numeric finite values. A finite value outside the nominal `[0,120]` by `[0,80]` source pitch is structurally valid and SHALL be preserved unchanged for Chapter 6 availability classification.
- Shot `z`, when present, SHALL be finite and non-negative.
- Visible-area coordinate pairs SHALL contain numeric finite values. Nominal-pitch availability is classified only by Chapter 6.
- Booleans SHALL be JSON booleans, not `0`, `1`, or strings.
- Integers SHALL be JSON numbers with no fractional component; booleans are not integers.
- Numeric strings are invalid.
- Names SHALL be non-empty strings after no transformation; whitespace SHALL be preserved.

Source precision SHALL be preserved at this stage. Rounding and metric conversion are forbidden.

### 5.7 Invariants and relationships

- **TIP-SRC-010:** Every Events `id` SHALL be non-empty and unique across the complete Events document.
- **TIP-SRC-011:** Every Events `index` SHALL be unique across the complete Events document.
- **TIP-SRC-012:** Sorting the complete Events document by `index` SHALL produce non-decreasing `(period,timestamp)` order. Equal timestamps are valid.
- **TIP-SRC-013:** Every selected possession event SHALL have the same `possession_team.id` and `possession_team.name`.
- **TIP-SRC-014:** Every retained event SHALL have `team.id` equal to `possession_team.id`. An opponent action inside the possession may exist but is not retained.
- **TIP-SRC-015:** Every 360 `event_uuid` SHALL reference exactly one Events `id` in the supplied Events document.
- **TIP-SRC-016:** A 360 `event_uuid` SHALL occur at most once. Duplicate records SHALL NOT be merged.
- **TIP-SRC-017:** A non-empty 360 freeze frame SHALL contain exactly one element with `actor=true`.
- **TIP-SRC-018:** The actor observation's `teammate` SHALL be `true`.
- **TIP-SRC-019:** The actor observation and referenced event location are distinct source observations. Both SHALL be preserved even when their numeric values differ; the source stage SHALL NOT reconcile or average them.
- **TIP-SRC-020:** Missing 360 records are permitted and SHALL be represented as absence, not as an empty fabricated record. Their later sufficiency and synchronization behavior are defined in Sections 7 and 8.
- **TIP-SRC-021:** `visible_area` SHALL describe a closed polygon: its first coordinate pair SHALL equal its last coordinate pair.
- **TIP-SRC-022:** The retained sequence SHALL contain at least one Pass, at least one Shot, and exactly one terminal goal Shot.
- **TIP-SRC-023:** The terminal goal Shot is the last retained event by source `index`; it SHALL have `shot.outcome.id=97` and `shot.outcome.name="Goal"`.

### 5.8 Profile classification

After structural validation, the selected possession SHALL meet all of these v0.1 conditions:

1. every selected possession event has `play_pattern.id=1` and `play_pattern.name="Regular Play"`;
2. no selected possession event has a set-piece event type or a set-piece play pattern;
3. the retained terminal event satisfies TIP-SRC-023;
4. at least one retained event has an associated non-empty 360 freeze frame;
5. the possession team performs every retained action.

For v0.1, `Regular Play` is the complete source-level operational definition of an eligible positional-attack candidate. Recognition of positional tactical structures is downstream and SHALL NOT change source eligibility. `From Counter` and every other play-pattern value are unsupported.

Failure of a structurally valid input to meet a profile condition SHALL return `UNSUPPORTED_INPUT`, not `INVALID_INPUT`. Lack of enough 360 evidence for reasoning beyond the minimum in item 4 SHALL be evaluated downstream and MAY return `INSUFFICIENT_EVIDENCE`.

### 5.9 Validation and selection algorithm

The source stage SHALL execute exactly these steps and stop at the first error:

1. verify `source_dataset` and `source_revision`;
2. parse both documents as UTF-8 JSON and require array roots;
3. validate complete-document event identifiers and indices;
4. validate the type and constraints of every consumed field that is present;
5. validate every 360 record and its reference to Events;
6. select all Events records with `possession == possession_id`;
7. fail if the selection is empty;
8. validate possession-wide identity, ordering, team, play-pattern, and terminal-outcome invariants;
9. retain only the four event types in Section 5.4;
10. order retained events by `index` ascending;
11. select 360 records whose `event_uuid` references a retained event;
12. preserve the selected 360 records in their source-array order;
13. emit the Source Selection output.

Unknown event types SHALL NOT cause an error. A record claiming a supported `type.id` with a different name, or a supported name with a different ID, is invalid.

### 5.10 Output

On success, the source stage SHALL emit a `SourceSelection` containing:

```json
{
  "contract_version": "0.1.0",
  "source_dataset": "statsbomb-open-data",
  "source_revision": "b0bc9f22dd77c206ddedc1d742893b3bbe64baec",
  "match_id": 3869685,
  "possession_id": 40,
  "events": [],
  "three_sixty": [],
  "source_event_count": 0,
  "retained_event_count": 0,
  "associated_360_count": 0
}
```

`events` and `three_sixty` SHALL contain exact deep copies of selected source objects, including unknown members. Count fields SHALL be integers. `source_event_count` counts all selected possession events; `retained_event_count` counts emitted supported event types; `associated_360_count` counts emitted 360 records.

### 5.11 Default parameters

The source contract has no configurable thresholds, tolerances, aliases, fallback source, or default values. Every required request member SHALL be supplied explicitly. Missing optional source members remain absent; they SHALL NOT be defaulted.

### 5.12 Failure behavior and error codes

Source errors SHALL use stage `source_validation`. When multiple defects exist, the validation order in Section 5.9 determines the reported primary error.

| Code | Execution status | Condition |
| --- | --- | --- |
| `SRC_UNSUPPORTED_DATASET` | `UNSUPPORTED_INPUT` | `source_dataset` is not the exact supported value. |
| `SRC_UNSUPPORTED_REVISION` | `UNSUPPORTED_INPUT` | `source_revision` is absent, malformed, or not the pinned revision. |
| `SRC_JSON_INVALID` | `INVALID_INPUT` | Either document is not valid UTF-8 JSON. |
| `SRC_ROOT_INVALID` | `INVALID_INPUT` | Either JSON root is not an array. |
| `SRC_EVENT_ID_INVALID` | `INVALID_INPUT` | Event ID is absent, empty, or duplicated. |
| `SRC_EVENT_INDEX_INVALID` | `INVALID_INPUT` | Event index is absent, invalid, duplicated, or conflicts with time order. |
| `SRC_FIELD_INVALID` | `INVALID_INPUT` | A consumed field violates its type, presence, enum pair, or scalar constraint. |
| `SRC_COORDINATE_INVALID` | `INVALID_INPUT` | A consumed coordinate or visible-area polygon is invalid. |
| `SRC_360_REFERENCE_INVALID` | `INVALID_INPUT` | A 360 UUID is absent, orphaned, or duplicated. |
| `SRC_360_ACTOR_INVALID` | `INVALID_INPUT` | A non-empty frame violates an actor invariant. |
| `SRC_POSSESSION_NOT_FOUND` | `INVALID_INPUT` | No event matches the requested possession. |
| `SRC_POSSESSION_INCONSISTENT` | `INVALID_INPUT` | Selected events disagree on possession team or violate retained-team rules. |
| `SRC_UNSUPPORTED_PHASE` | `UNSUPPORTED_INPUT` | Play pattern is not exactly Regular Play or indicates a set piece. |
| `SRC_UNSUPPORTED_OUTCOME` | `UNSUPPORTED_INPUT` | The possession does not have exactly one terminal goal Shot. |
| `SRC_360_UNAVAILABLE` | `UNSUPPORTED_INPUT` | No retained event has a non-empty associated 360 frame. |

Error `source_references` SHALL use the form `<document>#<JSON Pointer>`, where document is `events` or `three_sixty`, for example `events#/1165/play_pattern`. References SHALL be ordered by document name and array index. Messages are diagnostic and SHALL NOT be used for machine decisions.

### 5.13 Worked fixture

The locally available StatsBomb Open Data source for match `3869685`, possession `52` validates structurally and contains thirteen retained events with thirteen associated non-empty 360 records. Its selected Events records declare `play_pattern.id=6` and `play_pattern.name="From Counter"`.

The required result is therefore:

```json
{
  "status": "UNSUPPORTED_INPUT",
  "errors": [
    {
      "code": "SRC_UNSUPPORTED_PHASE",
      "stage": "source_validation",
      "message": "Possession 52 uses unsupported play pattern From Counter.",
      "source_references": ["events#/1165/play_pattern"]
    }
  ]
}
```

The array index in the pointer is zero-based and is illustrative of the pinned match document. This case SHALL NOT be a positive v0.1 fixture while the profile excludes counterattacks.

### 5.14 Conformance tests

The conformance corpus SHALL test at least:

| Test ID | Mutation or fixture | Expected result |
| --- | --- | --- |
| `SRC-C001` | Untouched pinned Locatelli Regular Play goal fixture | `SourceSelection`, `SUCCEEDED` at source stage |
| `SRC-C002` | Untouched pinned Depay Regular Play goal fixture | `SourceSelection`, `SUCCEEDED` at source stage |
| `SRC-C003` | Di María match 3869685, possession 52 | `SRC_UNSUPPORTED_PHASE` |
| `SRC-C004` | Unsupported revision | `SRC_UNSUPPORTED_REVISION` |
| `SRC-C005` | Duplicate Events ID | `SRC_EVENT_ID_INVALID` |
| `SRC-C006` | Equal timestamps with distinct indices | success; output ordered by index |
| `SRC-C007` | Duplicate 360 UUID | `SRC_360_REFERENCE_INVALID` |
| `SRC-C008` | Orphan 360 UUID | `SRC_360_REFERENCE_INVALID` |
| `SRC-C009` | Missing 360 for one retained non-terminal event | success with absent association |
| `SRC-C010` | Empty or absent 360 coverage for all retained events | `SRC_360_UNAVAILABLE` |
| `SRC-C011` | Two actor observations in one frame | `SRC_360_ACTOR_INVALID` |
| `SRC-C012` | Coordinate outside pitch bounds | `SRC_COORDINATE_INVALID` |
| `SRC-C013` | Non-goal terminal Shot | `SRC_UNSUPPORTED_OUTCOME` |
| `SRC-C014` | Unknown unconsumed member added | unchanged canonical downstream input |
| `SRC-C015` | Unconsumed pass angle changed | unchanged canonical downstream artifacts |

Each mutation test SHALL identify one pristine parent fixture and apply one machine-readable JSON Patch. The corpus SHALL store the patch, not a manually edited duplicate source document.

## 6. Normalized Data Model

> **Editorial status:** Normative in Working Draft 0.1.0.

### 6.1 Purpose

Normalization converts one valid `SourceSelection` artifact into one provider-independent canonical representation. Normalization changes representation and SHALL NOT change meaning.

Normalization SHALL perform only these operations:

1. rename fields;
2. wrap source identifiers in canonical namespaces;
3. map supported provider enums to canonical enums;
4. parse source timestamps;
5. convert pitch coordinates to canonical metric coordinates;
6. express source absence as a specified JSON `null`;
7. attach deterministic field-level provenance;
8. order records according to this chapter.

Normalization SHALL NOT infer tactical meaning, infer player continuity, synchronize observations, interpolate, create World State, detect football concepts, calculate geometric features, estimate confidence, repair source data, or reason about football.

- **TIP-NORM-001:** Every normalized value SHALL be reproducible from the `SourceSelection` and the rules in this chapter alone.
- **TIP-NORM-002:** A normalized artifact SHALL contain no provider field name or provider numeric enum except where this chapter explicitly preserves source identity metadata.
- **TIP-NORM-003:** Normalization SHALL NOT consume an unvalidated raw StatsBomb document.

### 6.2 Input

The sole accepted input is the `SourceSelection` artifact emitted by Section 5.10 with `contract_version="0.1.0"`.

The normalizer SHALL reject:

- a raw Events or 360 array;
- an execution request from Section 4.4;
- a `SourceSelection` with another contract version;
- a `SourceSelection` whose canonical bytes do not match its upstream artifact hash;
- a partial or diagnostic source artifact.

The normalizer SHALL treat the input as immutable. It SHALL NOT modify the input value or reuse a mutable input object as output.

The input object SHALL contain exactly the ten fields declared in Section 5.10: `contract_version`, `source_dataset`, `source_revision`, `match_id`, `possession_id`, `events`, `three_sixty`, `source_event_count`, `retained_event_count`, and `associated_360_count`. Unknown members remain permitted inside the deep-copied Events and 360 source objects under Section 5.3; unknown members are forbidden at the `SourceSelection` root.

The count relations SHALL be:

```text
source_event_count >= retained_event_count
retained_event_count = events.length
associated_360_count = three_sixty.length
```

All three counts SHALL be non-negative integers. Under the supported profile, `retained_event_count` and `associated_360_count` SHALL be positive.

### 6.3 Output

Successful normalization SHALL emit exactly one `NormalizedDataset` JSON artifact with media type `application/vnd.tip.normalized-dataset+json` and `contract_version="0.1.0"`.

The artifact SHALL contain only the fields defined in Section 6.4. Every object schema in this chapter has `additionalProperties=false`. A field marked non-nullable SHALL be present. A nullable field SHALL be present and SHALL contain either its declared value type or JSON `null`. Fields SHALL never be omitted from normalized records.

The artifact SHALL be serialized using Section 2.3 after all numeric calculations in this chapter have been completed.

### 6.4 Canonical schemas

#### 6.4.1 Common scalar types

| Type | JSON representation | Constraint |
| --- | --- | --- |
| `CanonicalId` | string | Non-empty ASCII matching `^[a-z][a-z0-9_]*(?::[A-Za-z0-9._-]+)+$`. |
| `CanonicalEnum` | string | One exact uppercase value declared by the containing field. |
| `Seconds` | number | Finite and non-negative; unit seconds. |
| `Metres` | number | Finite; unit metres. |
| `SourceIndex` | integer | Non-negative. |
| `SourcePath` | string | Exact pointer into the input artifact with form `source_selection#<JSON Pointer>`. |

Strings SHALL preserve Unicode code points from the source. Unicode normalization, case conversion, whitespace trimming, transliteration, and locale transformation are forbidden.

#### 6.4.2 `NormalizedDataset`

| Field | Type | Nullable | Units | Meaning | Source | Provenance |
| --- | --- | --- | --- | --- | --- | --- |
| `schema_id` | string | no | — | Exact value `tip.normalized_dataset`. | constant | `CONSTANT` |
| `contract_version` | string | no | — | Exact value `0.1.0`. | constant | `CONSTANT` |
| `source_dataset` | string | no | — | Audited source dataset identity. | `SourceSelection.source_dataset` | `COPIED` |
| `source_revision` | string | no | — | Audited source revision. | `SourceSelection.source_revision` | `COPIED` |
| `match_id` | `CanonicalId` | no | — | Canonical match identity. | `SourceSelection.match_id` | `WRAPPED_IDENTIFIER` |
| `possession_id` | `CanonicalId` | no | — | Canonical possession identity. | `SourceSelection.possession_id` and `match_id` | `WRAPPED_IDENTIFIER` |
| `period_ids` | array[`CanonicalId`] | no | — | Distinct periods represented by normalized events. | event periods | `DERIVED_DETERMINISTICALLY` |
| `events` | array[`NormalizedEvent`] | no | — | All normalized retained Events records. | `SourceSelection.events` | `DERIVED_DETERMINISTICALLY`; records carry field provenance |
| `freeze_frames` | array[`NormalizedFreezeFrame`] | no | — | All normalized associated 360 records. | `SourceSelection.three_sixty` | `DERIVED_DETERMINISTICALLY`; records carry field provenance |
| `provenance` | `ProvenanceMap` | no | — | Field provenance owned by this record. | all scalar dataset fields | not self-provenanced |

`events` SHALL be non-empty. `freeze_frames` SHALL be non-empty under the profile conditions in Section 5.8. `period_ids` SHALL contain no duplicate.

#### 6.4.3 `NormalizedEvent`

| Field | Type | Nullable | Units | Meaning | Source | Provenance |
| --- | --- | --- | --- | --- | --- | --- |
| `schema_id` | string | no | — | Exact value `tip.normalized_event`. | constant | `CONSTANT` |
| `event_id` | `CanonicalId` | no | — | Canonical event identity. | Events `id` | `WRAPPED_IDENTIFIER` |
| `source_record_id` | `CanonicalId` | no | — | Identity of the source Events record. | source identity plus Events `id` | `WRAPPED_IDENTIFIER` |
| `source_index` | `SourceIndex` | no | — | Provider Events ordering index. | Events `index` | `RENAMED` |
| `event_order` | integer | no | — | Zero-based position in normalized event order. | sorted retained Events | `DERIVED_DETERMINISTICALLY` |
| `period_id` | `CanonicalId` | no | — | Canonical period identity. | Events `period` and match identity | `WRAPPED_IDENTIFIER` |
| `period_number` | integer | no | — | Source match period, one of `1`, `2`, `3`, `4`. | Events `period` | `RENAMED` |
| `period_time_seconds` | `Seconds` | no | seconds | Elapsed time from the start of the period. | Events `timestamp` | `PARSED` |
| `match_time_seconds` | `Seconds` | no | seconds | Elapsed canonical match time. | period plus parsed timestamp | `CONVERTED` |
| `duration_seconds` | `Seconds` | yes | seconds | Source event duration. | Events `duration` | `RENAMED` or `SOURCE_ABSENT` |
| `possession_id` | `CanonicalId` | no | — | Canonical possession identity. | Events `possession` and match identity | `WRAPPED_IDENTIFIER` |
| `possession_team_id` | `CanonicalId` | no | — | Canonical possession-team identity. | Events `possession_team.id` | `WRAPPED_IDENTIFIER` |
| `possession_team_name` | string | no | — | Source display name. | Events `possession_team.name` | `RENAMED` |
| `team_id` | `CanonicalId` | no | — | Canonical acting-team identity. | Events `team.id` | `WRAPPED_IDENTIFIER` |
| `team_name` | string | no | — | Source acting-team display name. | Events `team.name` | `RENAMED` |
| `actor_player_id` | `CanonicalId` | no | — | Canonical acting-player identity. | Events `player.id` | `WRAPPED_IDENTIFIER` |
| `actor_player_name` | string | no | — | Source acting-player display name. | Events `player.name` | `RENAMED` |
| `event_type` | enum | no | — | One of `PASS`, `BALL_RECEIPT`, `CARRY`, `SHOT`. | Events `type` pair | `ENUM_MAPPED` |
| `play_pattern` | enum | no | — | Exact value `REGULAR_PLAY`. | Events `play_pattern` pair | `ENUM_MAPPED` |
| `start_position` | `CanonicalPosition` | no | metres | Event start location. | Events `location` | field-level conversion provenance |
| `end_position` | `CanonicalPosition` | yes | metres | Event end location; null only for `BALL_RECEIPT`. | type-specific end location | field-level conversion or absence provenance |
| `recipient_player_id` | `CanonicalId` | yes | — | Intended pass recipient. | `pass.recipient.id` | `WRAPPED_IDENTIFIER` or `NOT_APPLICABLE` |
| `recipient_player_name` | string | yes | — | Intended pass-recipient display name. | `pass.recipient.name` | `RENAMED` or `NOT_APPLICABLE` |
| `outcome` | enum | yes | — | `COMPLETED`, `INCOMPLETE`, or `GOAL`; null where not applicable. | type-specific outcome | `ENUM_MAPPED` or `NOT_APPLICABLE` |
| `shot_xg` | number | yes | probability | Source StatsBomb xG in `[0,1]`; null for non-Shot events. | `shot.statsbomb_xg` | `RENAMED` or `NOT_APPLICABLE` |
| `provenance` | `ProvenanceMap` | no | — | Every leaf field owned by this record. | Events record | not self-provenanced |

`start_position` and non-null `end_position` SHALL contain no fields other than `x_m`, `y_m`, and `z_m`.

#### 6.4.4 `CanonicalPosition`

| Field | Type | Nullable | Units | Meaning | Source | Provenance |
| --- | --- | --- | --- | --- | --- | --- |
| `availability` | enum | no | — | `AVAILABLE` or `UNAVAILABLE`. | source location bounds | `DERIVED_DETERMINISTICALLY` |
| `x_m` | `Metres` | yes | metres | Converted x when available; null when unavailable. | source `x` | `COORDINATE_CONVERTED` or `SOURCE_UNAVAILABLE` |
| `y_m` | `Metres` | yes | metres | Converted y when available; null when unavailable. | source `y` | `COORDINATE_CONVERTED` or `SOURCE_UNAVAILABLE` |
| `z_m` | `Metres` | yes | metres | Height when available and applicable; otherwise null. | source `z` | `RENAMED`, `SOURCE_ABSENT`, `NOT_APPLICABLE`, or `SOURCE_UNAVAILABLE` |
| `unavailable_reason` | enum | yes | — | Null when available; otherwise `SOURCE_POSITION_OUT_OF_BOUNDS`. | source location bounds | `NOT_APPLICABLE` or `SOURCE_UNAVAILABLE` |

The exact original numeric location SHALL remain in position provenance. An out-of-bounds source location SHALL NOT be clamped, changed, discarded, or converted. It SHALL produce `availability="UNAVAILABLE"`, null `x_m`, `y_m`, and `z_m`, and `unavailable_reason="SOURCE_POSITION_OUT_OF_BOUNDS"`.

#### 6.4.5 `NormalizedFreezeFrame`

| Field | Type | Nullable | Units | Meaning | Source | Provenance |
| --- | --- | --- | --- | --- | --- | --- |
| `schema_id` | string | no | — | Exact value `tip.normalized_freeze_frame`. | constant | `CONSTANT` |
| `freeze_frame_id` | `CanonicalId` | no | — | Canonical 360-record identity. | match identity plus `event_uuid` | `WRAPPED_IDENTIFIER` |
| `source_record_id` | `CanonicalId` | no | — | Identity of the source 360 record. | source identity plus `event_uuid` | `WRAPPED_IDENTIFIER` |
| `source_index` | `SourceIndex` | no | — | Zero-based array index in `SourceSelection.three_sixty`. | location of 360 object in normalizer input | `DERIVED_DETERMINISTICALLY` |
| `event_id` | `CanonicalId` | no | — | Referenced canonical event identity. | 360 `event_uuid` | `WRAPPED_IDENTIFIER` |
| `visible_area` | `NormalizedVisibleArea` | no | metres | Provider-observed visible polygon. | 360 `visible_area` | child record carries provenance |
| `observations` | array[`NormalizedPlayerObservation`] | no | — | Source-order player observations. | 360 `freeze_frame` | `DERIVED_DETERMINISTICALLY`; child records carry field provenance |
| `provenance` | `ProvenanceMap` | no | — | Scalar field provenance owned by this record. | 360 record | not self-provenanced |

The freeze frame SHALL contain no timestamp. Its reference to an event SHALL NOT be interpreted as temporal synchronization by normalization.

#### 6.4.6 `NormalizedPlayerObservation`

| Field | Type | Nullable | Units | Meaning | Source | Provenance |
| --- | --- | --- | --- | --- | --- | --- |
| `schema_id` | string | no | — | Exact value `tip.normalized_player_observation`. | constant | `CONSTANT` |
| `observation_id` | `CanonicalId` | no | — | Canonical identity of this one source observation. | freeze-frame identity and source element index | `DERIVED_DETERMINISTICALLY` |
| `source_record_id` | `CanonicalId` | no | — | Source 360 record containing the observation. | parent 360 record | `COPIED` |
| `source_index` | `SourceIndex` | no | — | Zero-based index in source `freeze_frame`. | source element location | `DERIVED_DETERMINISTICALLY` |
| `player_id` | `CanonicalId` | yes | — | Actor identity; null for every non-actor observation. | referenced Event actor plus `actor` | `DERIVED_DETERMINISTICALLY` or `SOURCE_UNIDENTIFIED` |
| `player_name` | string | yes | — | Actor display name; null for every non-actor observation. | referenced Event actor plus `actor` | `DERIVED_DETERMINISTICALLY` or `SOURCE_UNIDENTIFIED` |
| `team_id` | `CanonicalId` | yes | — | Possession-team identity for teammate observations; null for opponent observations. | `teammate` plus referenced Event possession team | `DERIVED_DETERMINISTICALLY` or `SOURCE_UNIDENTIFIED` |
| `team_relation` | enum | no | — | `TEAMMATE` or `OPPONENT`, relative to the event actor. | 360 `teammate` | `ENUM_MAPPED` |
| `actor` | boolean | no | — | Source actor flag. | 360 `actor` | `COPIED` |
| `goalkeeper` | boolean | no | — | Source keeper flag. | 360 `keeper` | `RENAMED` |
| `visible` | boolean | no | — | Exact value `true`; inclusion in a source freeze frame is an observed visible presence. | membership in 360 `freeze_frame` | `DERIVED_DETERMINISTICALLY` |
| `position` | `CanonicalPosition` | no | metres | Source observation location with `z_m=null`. | 360 `location` | field-level conversion provenance |
| `provenance` | `ProvenanceMap` | no | — | Every leaf field owned by this record. | observation and referenced Event where declared | not self-provenanced |

Normalization SHALL NOT assign a player identity to a non-actor observation. Equal coordinates, source order, names in other events, team relation, and goalkeeper status SHALL NOT be used for identity assignment.

#### 6.4.7 `NormalizedVisibleArea`

| Field | Type | Nullable | Units | Meaning | Source | Provenance |
| --- | --- | --- | --- | --- | --- | --- |
| `schema_id` | string | no | — | Exact value `tip.normalized_visible_area`. | constant | `CONSTANT` |
| `visible_area_id` | `CanonicalId` | no | — | Canonical identity of this polygon. | freeze-frame identity | `DERIVED_DETERMINISTICALLY` |
| `points` | array[`CanonicalPosition`] | no | metres | Closed polygon vertices in source order; every `z_m` is null. | consecutive 360 `visible_area` pairs | `DERIVED_DETERMINISTICALLY` plus point-level conversion provenance |
| `provenance` | `ProvenanceMap` | no | — | Every leaf field owned by this record. | 360 visible area | not self-provenanced |

Normalization SHALL preserve all polygon vertices, including the repeated closing vertex. It SHALL NOT simplify, orient, repair, clip, triangulate, or calculate properties of the polygon.

#### 6.4.8 `ProvenanceMap`

A `ProvenanceMap` SHALL be a JSON object. Each member name SHALL be a JSON Pointer relative to the record containing the map. Each member value SHALL be one `FieldProvenance`. The map SHALL contain exactly one entry for every non-provenance scalar field, null field, and array field owned by that record. Paths for object-valued fields SHALL NOT appear because their owned fields carry provenance separately. Array entries SHALL describe collection membership and order; nested record fields and scalar array elements SHALL additionally have their declared field-level or indexed paths. Keys SHALL be serialized in lexicographic order under Section 2.3.

`FieldProvenance` contains exactly:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `class` | enum | no | One provenance class from Section 6.10. |
| `operation` | enum | no | One operation from Section 6.10. |
| `sources` | array[`ProvenanceSource`] | no | Ordered source dependencies; empty only for `CONSTANT`. |

`ProvenanceSource` contains exactly:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `source_record_id` | `CanonicalId` | no | Canonical source-record identity. |
| `source_path` | `SourcePath` | no | Exact source field or record path. |

Sources SHALL be ordered by `source_record_id`, then `source_path`, both ascending by Unicode code point. Duplicate sources are forbidden.

### 6.5 Canonical identifiers

Canonical identifiers SHALL be constructed by exact string concatenation. Decimal integers SHALL contain no sign and no leading zero. Source string identifiers SHALL be preserved byte-for-byte after JSON string decoding.

| Identifier | Construction |
| --- | --- |
| `match_id` | `match:statsbomb:<source match_id>` |
| `period_id` | `<match_id>:period:<period_number>` |
| `possession_id` | `<match_id>:possession:<source possession_id>` |
| `team_id` | `team:statsbomb:<source team id>` |
| `player_id` | `player:statsbomb:<source player id>` |
| `event_id` | `event:statsbomb:<source Events id>` |
| `freeze_frame_id` | `<event_id>:freeze_frame:statsbomb360` |
| `visible_area_id` | `<freeze_frame_id>:visible_area` |
| `observation_id` | `<freeze_frame_id>:observation:<zero-based freeze_frame index>` |
| Events `source_record_id` | `source:statsbomb_open_data:<source_revision>:events:<match_id integer>:<source Events id>` |
| 360 `source_record_id` | `source:statsbomb_open_data:<source_revision>:three_sixty:<match_id integer>:<event_uuid>` |
| SourceSelection metadata identity | `source:statsbomb_open_data:<source_revision>:selection:<match_id integer>:<possession_id integer>` |

- **TIP-NORM-ID-001:** StatsBomb identifiers SHALL be wrapped, not replaced, hashed, parsed, lowercased, or generated anew.
- **TIP-NORM-ID-002:** Repeated normalization of the same input SHALL produce identical identifiers.
- **TIP-NORM-ID-003:** Two normalized records SHALL NOT share an identifier unless the schema explicitly uses that identifier as a reference.
- **TIP-NORM-ID-004:** An identifier collision SHALL fail normalization; suffixing, randomization, and last-write-wins behavior are forbidden.

### 6.6 Canonical temporal model

#### 6.6.1 Timestamp parsing

The source timestamp grammar is `HH:MM:SS.sss`, with two decimal digits for hours and minutes, two decimal digits for seconds, and three fractional digits. It SHALL be parsed as:

```text
period_time_seconds = HH * 3600 + MM * 60 + SS + sss / 1000
```

Decimal arithmetic SHALL be exact through this calculation. Binary floating-point approximation SHALL NOT be rounded before canonical serialization.

#### 6.6.2 Match time

`match_time_seconds` SHALL equal `period_offset_seconds + period_time_seconds`, using:

| Period | Offset seconds |
| ---: | ---: |
| 1 | 0 |
| 2 | 2700 |
| 3 | 5400 |
| 4 | 6300 |

This mapping is a representation conversion. It SHALL NOT align an event with a 360 observation or any other source. No `NormalizedFreezeFrame` or `NormalizedPlayerObservation` receives a time value during normalization.

#### 6.6.3 Event ordering

Normalized events SHALL be ordered by this total key:

```text
(period_number ascending,
 period_time_seconds ascending,
 source Events index ascending,
 source Events id ascending by Unicode code point)
```

`event_order` SHALL be assigned after sorting, beginning with zero. Equal timestamps SHALL remain distinct events. They SHALL NOT be combined, offset, or reordered by event type.

`period_ids` SHALL be the distinct `period_id` values encountered in normalized event order.

#### 6.6.4 Temporal precision and nulls

`period_time_seconds`, `match_time_seconds`, and non-null `duration_seconds` SHALL serialize to at most six fractional digits under Section 2.3. A missing source `duration` SHALL map to null. It SHALL NOT be calculated from the next event.

### 6.7 Canonical coordinate model

The normalized coordinate system SHALL be metric and attack-relative:

| Property | Canonical value |
| --- | --- |
| Pitch length | `105.000000` metres |
| Pitch width | `68.000000` metres |
| Origin | Own goal line at the lower touchline in canonical attacking view |
| Positive x-axis | Toward the opponent goal |
| Positive y-axis | From lower touchline toward upper touchline |
| Attacking direction | Left to right, along `+x` |

Every in-bounds StatsBomb `[x,y]` pair SHALL be converted by:

```text
x_m = x * 105 / 120
y_m = (80 - y) * 68 / 80
```

The third component of a Shot end location SHALL be represented unchanged as `z_m`. The pinned source expresses this component in metres. When the source contains no third component, `z_m` SHALL be null.

Calculations SHALL use decimal arithmetic with at least fifteen significant decimal digits. Values SHALL be rounded only by canonical serialization to six fractional digits using round-half-to-even. Negative zero SHALL serialize as zero.

- **TIP-NORM-COORD-001:** Original StatsBomb coordinates SHALL NOT be stored as normalized geometry.
- **TIP-NORM-COORD-002:** Provenance for every `x_m`, `y_m`, and non-null `z_m` SHALL reference the exact source array component.
- **TIP-NORM-COORD-003:** Normalization SHALL NOT clamp, interpolate, average, compare, reconcile, or infer coordinates.
- **TIP-NORM-COORD-004:** Event and actor-observation positions SHALL remain separate converted observations when their source values differ.

### 6.8 Event normalization

#### 6.8.1 Common mapping

Every retained source Event SHALL produce exactly one `NormalizedEvent`. The following mapping applies to all four event types:

| Source | Normalized target | Operation |
| --- | --- | --- |
| record identity | `source_record_id`, `source_index` | source wrapping and rename of Events `index` |
| `id` | `event_id` | identifier wrapping |
| `index` | `event_order` input | total ordering; source value remains represented by `source_index` only through provenance and ordering |
| `period` | `period_number`, `period_id`, `match_time_seconds` | rename, identifier wrapping, offset conversion |
| `timestamp` | `period_time_seconds`, `match_time_seconds` | parse and offset conversion |
| `minute` | no output field | validated audit value redundant with timestamp; discarded |
| `second` | no output field | validated audit value redundant with timestamp; discarded |
| `duration` | `duration_seconds` | rename or null on source absence |
| `type.id`, `type.name` | `event_type` | enum mapping |
| `possession` | `possession_id` | identifier wrapping |
| `possession_team.id` | `possession_team_id` | identifier wrapping |
| `possession_team.name` | `possession_team_name` | rename |
| `play_pattern.id`, `play_pattern.name` | `play_pattern` | enum mapping to `REGULAR_PLAY` |
| `team.id` | `team_id` | identifier wrapping |
| `team.name` | `team_name` | rename |
| `player.id` | `actor_player_id` | identifier wrapping |
| `player.name` | `actor_player_name` | rename |
| `location[0]`, `location[1]` | `start_position.x_m`, `start_position.y_m` | metric conversion |
| absent source z | `start_position.z_m` | null with `NOT_APPLICABLE` |

`source_index` SHALL preserve Events `index`. The position of the Events object inside `SourceSelection.events` SHALL be used only in provenance `source_path` values and SHALL NOT become domain data.

#### 6.8.2 Enum mappings

Only these mappings are supported:

| Source pair or condition | Canonical value |
| --- | --- |
| `(30, "Pass")` | `PASS` |
| `(42, "Ball Receipt*")` | `BALL_RECEIPT` |
| `(43, "Carry")` | `CARRY` |
| `(16, "Shot")` | `SHOT` |
| `(1, "Regular Play")` | `REGULAR_PLAY` |
| Pass `outcome` absent | `COMPLETED` |
| Pass outcome `(9, "Incomplete")` | `INCOMPLETE` |
| Shot outcome `(97, "Goal")` | `GOAL` |

Any present provider pair not listed above SHALL fail with `NORM_UNSUPPORTED_MAPPING`. Names or IDs SHALL NOT be mapped independently.

#### 6.8.3 `PASS`

| Target | Source or value |
| --- | --- |
| `end_position.x_m`, `end_position.y_m` | converted `pass.end_location[0:2]` |
| `end_position.z_m` | null, `NOT_APPLICABLE` |
| `recipient_player_id` | wrapped `pass.recipient.id` |
| `recipient_player_name` | `pass.recipient.name` |
| `outcome` | `COMPLETED` when `pass.outcome` is absent; otherwise mapped pair |
| `shot_xg` | null, `NOT_APPLICABLE` |

#### 6.8.4 `BALL_RECEIPT`

`end_position`, `recipient_player_id`, `recipient_player_name`, `outcome`, and `shot_xg` SHALL all be null with provenance class `NOT_APPLICABLE`. No end position SHALL be copied from a preceding Pass.

#### 6.8.5 `CARRY`

| Target | Source or value |
| --- | --- |
| `end_position.x_m`, `end_position.y_m` | converted `carry.end_location[0:2]` |
| `end_position.z_m` | null, `NOT_APPLICABLE` |
| `recipient_player_id` | null, `NOT_APPLICABLE` |
| `recipient_player_name` | null, `NOT_APPLICABLE` |
| `outcome` | null, `NOT_APPLICABLE` |
| `shot_xg` | null, `NOT_APPLICABLE` |

#### 6.8.6 `SHOT`

| Target | Source or value |
| --- | --- |
| `end_position.x_m`, `end_position.y_m` | converted `shot.end_location[0:2]` |
| `end_position.z_m` | `shot.end_location[2]` when present; otherwise null with `SOURCE_ABSENT` |
| `recipient_player_id` | null, `NOT_APPLICABLE` |
| `recipient_player_name` | null, `NOT_APPLICABLE` |
| `outcome` | mapped `shot.outcome` pair; v0.1 permits only `GOAL` |
| `shot_xg` | copied numeric value from `shot.statsbomb_xg` |

#### 6.8.7 Normative mapping matrix

This matrix is the exhaustive field disposition for the `SourceSelection` contract. Each source field pattern occurs exactly once. A comma-separated canonical target list is one mapping disposition, not multiple matrix entries.

The `Action` column uses exactly these values:

| Action | Meaning |
| --- | --- |
| `COPIED` | Source value is emitted without value transformation. |
| `RENAMED` | Source value is emitted unchanged under a canonical field name. |
| `TRANSFORMED` | Source value participates in deterministic identifier construction, enum mapping, collection construction, null classification, or ordering. |
| `CONVERTED` | Source numeric or temporal representation is converted to canonical units or representation. |
| `DISCARDED` | Source field has no canonical output and SHALL NOT affect output bytes. |

The `Provenance` column names the required provenance class. `—` means that no normalized provenance entry is permitted because the field is discarded.

##### SourceSelection envelope

| Source field | Canonical field | Action | Provenance |
| --- | --- | --- | --- |
| `contract_version` | `contract_version` | `TRANSFORMED` | `CONSTANT` after input-version validation |
| `source_dataset` | `source_dataset` | `COPIED` | `COPIED` |
| `source_revision` | `source_revision` | `COPIED` | `COPIED` |
| `match_id` | `match_id`; component of `period_id`, `possession_id`, freeze-frame and source-record identifiers | `TRANSFORMED` | `WRAPPED_IDENTIFIER` |
| `possession_id` | `possession_id` | `TRANSFORMED` | `WRAPPED_IDENTIFIER` |
| `events` | `events` collection membership | `TRANSFORMED` | `DERIVED_DETERMINISTICALLY` |
| `three_sixty` | `freeze_frames` collection membership | `TRANSFORMED` | `DERIVED_DETERMINISTICALLY` |
| `source_event_count` | no output field | `DISCARDED` | — |
| `retained_event_count` | validation of `events.length`; no output field | `DISCARDED` | — |
| `associated_360_count` | validation of `freeze_frames.length`; no output field | `DISCARDED` | — |

Discarded count fields SHALL be validated under Section 6.2 before removal. Their values SHALL NOT be copied into `NormalizedDataset`.

##### Retained Events records

| Source field | Canonical field | Action | Provenance |
| --- | --- | --- | --- |
| Events object membership | `source_record_id` | `TRANSFORMED` | `WRAPPED_IDENTIFIER` |
| `id` | `event_id`; identifier component of related normalized records | `TRANSFORMED` | `WRAPPED_IDENTIFIER` |
| `index` | `source_index`; input to `event_order` | `RENAMED` for `source_index`; `TRANSFORMED` for order | `RENAMED`; `DERIVED_DETERMINISTICALLY` |
| `period` | `period_number`, `period_id`, `match_time_seconds`, `period_ids` | `TRANSFORMED` | `RENAMED`, `WRAPPED_IDENTIFIER`, `CONVERTED`, `DERIVED_DETERMINISTICALLY` |
| `timestamp` | `period_time_seconds`, `match_time_seconds`; input to `event_order` | `CONVERTED` | `PARSED`, `CONVERTED`, `DERIVED_DETERMINISTICALLY` |
| `minute` | no output field | `DISCARDED` | — |
| `second` | no output field | `DISCARDED` | — |
| `duration` | `duration_seconds` | `RENAMED` | `RENAMED` or `SOURCE_ABSENT` |
| `type.id` plus `type.name` | `event_type`; type-dependent null dispositions | `TRANSFORMED` | `ENUM_MAPPED`; `NOT_APPLICABLE` where declared |
| `possession` | event `possession_id` | `TRANSFORMED` | `WRAPPED_IDENTIFIER` |
| `possession_team.id` | `possession_team_id`; teammate-observation `team_id` | `TRANSFORMED` | `WRAPPED_IDENTIFIER`; `DERIVED_DETERMINISTICALLY` |
| `possession_team.name` | `possession_team_name` | `RENAMED` | `RENAMED` |
| `play_pattern.id` plus `play_pattern.name` | `play_pattern` | `TRANSFORMED` | `ENUM_MAPPED` |
| `team.id` | `team_id` | `TRANSFORMED` | `WRAPPED_IDENTIFIER` |
| `team.name` | `team_name` | `RENAMED` | `RENAMED` |
| `player.id` | `actor_player_id`; actor-observation `player_id` | `TRANSFORMED` | `WRAPPED_IDENTIFIER`; `DERIVED_DETERMINISTICALLY` |
| `player.name` | `actor_player_name`; actor-observation `player_name` | `RENAMED` | `RENAMED`; `DERIVED_DETERMINISTICALLY` |
| `location[0]` | `start_position.x_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `location[1]` | `start_position.y_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `pass.recipient.id` | Pass `recipient_player_id` | `TRANSFORMED` | `WRAPPED_IDENTIFIER` |
| `pass.recipient.name` | Pass `recipient_player_name` | `RENAMED` | `RENAMED` |
| `pass.end_location[0]` | Pass `end_position.x_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `pass.end_location[1]` | Pass `end_position.y_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| absent `pass.outcome` | Pass `outcome=COMPLETED` | `TRANSFORMED` | `ENUM_MAPPED` |
| `pass.outcome.id` plus `pass.outcome.name` | Pass `outcome=INCOMPLETE` | `TRANSFORMED` | `ENUM_MAPPED` |
| `carry.end_location[0]` | Carry `end_position.x_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `carry.end_location[1]` | Carry `end_position.y_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `shot.end_location[0]` | Shot `end_position.x_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `shot.end_location[1]` | Shot `end_position.y_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| optional `shot.end_location[2]` | Shot `end_position.z_m` | `RENAMED` | `COORDINATE_CONVERTED` with `COPY_Z_METRES`, or `SOURCE_ABSENT` |
| `shot.outcome.id` plus `shot.outcome.name` | Shot `outcome=GOAL` | `TRANSFORMED` | `ENUM_MAPPED` |
| `shot.statsbomb_xg` | `shot_xg` | `RENAMED` | `RENAMED` |

##### StatsBomb 360 records

| Source field | Canonical field | Action | Provenance |
| --- | --- | --- | --- |
| 360 object position in `SourceSelection.three_sixty` | `source_index`; component of `source_record_id` | `TRANSFORMED` | `DERIVED_DETERMINISTICALLY`; `WRAPPED_IDENTIFIER` |
| `event_uuid` | `event_id`, `freeze_frame_id`, `visible_area_id`; source-record identifier component | `TRANSFORMED` | `WRAPPED_IDENTIFIER`; `DERIVED_DETERMINISTICALLY` |
| `visible_area` array membership and pair order | `visible_area.points` | `TRANSFORMED` | `DERIVED_DETERMINISTICALLY` |
| `visible_area[2i]` | `visible_area.points[i].x_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `visible_area[2i+1]` | `visible_area.points[i].y_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `freeze_frame` array membership and order | `observations` | `TRANSFORMED` | `DERIVED_DETERMINISTICALLY` |
| `freeze_frame[i].location[0]` | `observations[i].position.x_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `freeze_frame[i].location[1]` | `observations[i].position.y_m` | `CONVERTED` | `COORDINATE_CONVERTED` |
| `freeze_frame[i].teammate` | `team_relation`; input to `team_id` | `TRANSFORMED` | `ENUM_MAPPED`; `DERIVED_DETERMINISTICALLY` or `SOURCE_UNIDENTIFIED` |
| `freeze_frame[i].actor` | `actor`; input to `player_id` and `player_name` | `TRANSFORMED` | `COPIED`; `DERIVED_DETERMINISTICALLY` or `SOURCE_UNIDENTIFIED` |
| `freeze_frame[i].keeper` | `goalkeeper` | `RENAMED` | `RENAMED` |
| source membership of `freeze_frame[i]` | `visible=true`, `observation_id`, observation `source_index`, observation `source_record_id` | `TRANSFORMED` | `DERIVED_DETERMINISTICALLY`; `COPIED` for parent source-record identity |

##### Explicitly discarded provider fields

The following field patterns are present in the pinned provider schema but unsupported by the v0.1 canonical profile. They SHALL be discarded whether present or absent:

| Source field pattern | Canonical field | Action | Provenance |
| --- | --- | --- | --- |
| `pass.length` | no output field | `DISCARDED` | — |
| `pass.angle` | no output field | `DISCARDED` | — |
| `pass.height` | no output field | `DISCARDED` | — |
| `pass.body_part` | no output field | `DISCARDED` | — |
| `pass.type` | no output field | `DISCARDED` | — |
| `pass.assisted_shot_id` | no output field | `DISCARDED` | — |
| `pass.goal_assist` | no output field | `DISCARDED` | — |
| `shot.body_part` | no output field | `DISCARDED` | — |
| `shot.technique` | no output field | `DISCARDED` | — |
| `shot.type` | no output field | `DISCARDED` | — |
| `shot.key_pass_id` | no output field | `DISCARDED` | — |
| `shot.first_time` | no output field | `DISCARDED` | — |
| `shot.freeze_frame` | no output field | `DISCARDED` | — |
| `tactics` | no output field | `DISCARDED` | — |
| `under_pressure` | no output field | `DISCARDED` | — |
| `related_events` | no output field | `DISCARDED` | — |
| provider metric other than `shot.statsbomb_xg` | no output field | `DISCARDED` | — |
| any unknown Events or 360 object member permitted by Section 5.3 | no output field | `DISCARDED` | — |

Unknown members are covered by the final row and SHALL NOT require a specification revision merely to be discarded. An unknown member SHALL fail with `NORM_UNSUPPORTED_MAPPING` only when an implementation attempts to map or emit it.

- **TIP-NORM-MAP-001:** Every source field declared by Sections 5.10, 5.4, and 5.5 SHALL match exactly one source-field row in this matrix.
- **TIP-NORM-MAP-002:** A source field SHALL have exactly one primary action: `COPIED`, `RENAMED`, `TRANSFORMED`, `CONVERTED`, or `DISCARDED`.
- **TIP-NORM-MAP-003:** One matrix row MAY produce multiple canonical fields only when every target is listed in that row.
- **TIP-NORM-MAP-004:** A field with action `DISCARDED` SHALL produce no canonical field and no provenance entry.
- **TIP-NORM-MAP-005:** A field not matched by a named row SHALL match the applicable unknown-member row and SHALL be discarded.
- **TIP-NORM-MAP-006:** No mapping, alias, fallback, passthrough, or field disposition exists outside this matrix.

### 6.9 Freeze-frame normalization

Every source 360 record in `SourceSelection.three_sixty` SHALL produce exactly one `NormalizedFreezeFrame`.

The normalizer SHALL locate the referenced normalized event by exact equality between 360 `event_uuid` and the source Events `id` wrapped by that event. It SHALL use this relation only for identifiers and actor metadata. It SHALL NOT assign, adjust, or compare timestamps.

For each source freeze-frame element at zero-based index `i`:

1. create one observation with identifier suffix `:observation:<i>`;
2. preserve array order and set `source_index=i`;
3. map `teammate=true` to `TEAMMATE`, otherwise `OPPONENT`;
4. copy `actor`;
5. rename `keeper` to `goalkeeper`;
6. set `visible=true`;
7. convert the element's location independently;
8. if `actor=true`, copy the referenced normalized event's actor player ID and name;
9. if `actor=false`, set player ID and name to null with `SOURCE_UNIDENTIFIED`;
10. if `teammate=true`, copy the referenced normalized event's possession-team ID; otherwise set team ID to null with `SOURCE_UNIDENTIFIED`.

For the visible area, consecutive source values `(0,1)`, `(2,3)`, through `(n-2,n-1)` SHALL each produce one `CanonicalPosition` in the same order. Every point `z_m` SHALL be null with `NOT_APPLICABLE`.

Normalization SHALL NOT:

- create an observation for an absent 360 record;
- create a player not present in `freeze_frame`;
- merge observations at equal locations;
- associate non-actor observations across frames;
- infer an opponent team identity;
- infer whether an unobserved player is outside the visible area;
- interpret `visible_area` as player visibility beyond the explicit included observations.

### 6.10 Provenance

The allowed provenance classes and operations are exact:

| Class | Required operation | Meaning |
| --- | --- | --- |
| `COPIED` | `COPY` | Value is unchanged. |
| `RENAMED` | `RENAME` | Value is unchanged under a canonical field name. |
| `WRAPPED_IDENTIFIER` | `WRAP_ID` | Source identity is preserved inside a canonical namespace. |
| `ENUM_MAPPED` | `MAP_ENUM` | Validated source pair or source absence maps through Section 6.8.2. |
| `PARSED` | `PARSE_TIMESTAMP` | Timestamp string maps to decimal period seconds. |
| `CONVERTED` | `ADD_PERIOD_OFFSET` | Parsed period time receives the fixed period offset. |
| `COORDINATE_CONVERTED` | `SCALE_X_METRES`, `INVERT_SCALE_Y_METRES`, or `COPY_Z_METRES` | Coordinate maps through Section 6.7. |
| `DERIVED_DETERMINISTICALLY` | `ASSIGN_ORDER`, `BUILD_COLLECTION`, `INHERIT_ACTOR`, `INHERIT_TEAM`, or `SET_VISIBLE_TRUE` | Non-tactical deterministic construction declared by this chapter. |
| `SOURCE_ABSENT` | `SET_NULL_SOURCE_ABSENT` | Optional source member is absent and target is null. |
| `SOURCE_UNIDENTIFIED` | `SET_NULL_SOURCE_UNIDENTIFIED` | Source intentionally supplies no identity and target is null. |
| `NOT_APPLICABLE` | `SET_NULL_NOT_APPLICABLE` | Field has no meaning for this record type and is null. |
| `CONSTANT` | `SET_SCHEMA_CONSTANT` | Specification constant with an empty source list. |

Provenance SHALL NOT contain confidence, tactical labels, explanatory text, implementation names, runtime timestamps, memory addresses, or code locations.

Where a normalized value depends on another normalized value, provenance SHALL reference the original source dependencies, not the intermediate normalized path. `match_time_seconds` SHALL reference both Events `period` and `timestamp`. Actor identity inherited by a 360 observation SHALL reference both the observation `actor` flag and the referenced Events player field.

- **TIP-NORM-PROV-001:** Every owned non-provenance leaf SHALL have exactly one provenance entry.
- **TIP-NORM-PROV-002:** No provenance entry SHALL target an absent field, an object-valued field, or the provenance map itself. Array-valued fields SHALL have one collection provenance entry.
- **TIP-NORM-PROV-003:** Every source path SHALL resolve in the input, except a `SOURCE_ABSENT` path, which SHALL name the exact absent optional member.
- **TIP-NORM-PROV-004:** Changing an unconsumed source member SHALL NOT change the normalized artifact or its provenance.

### 6.11 Missing-value policy

Null is permitted only as follows:

| Field | Null condition | Required class |
| --- | --- | --- |
| `duration_seconds` | source Events `duration` is absent | `SOURCE_ABSENT` |
| `end_position` | event type is `BALL_RECEIPT` | `NOT_APPLICABLE` |
| position `z_m` | start position, Pass end, Carry end, visible-area point, or player observation | `NOT_APPLICABLE` |
| Shot end `z_m` | source Shot end location has two components | `SOURCE_ABSENT` |
| `recipient_player_id`, `recipient_player_name` | event type is not `PASS` | `NOT_APPLICABLE` |
| `outcome` | event type is `BALL_RECEIPT` or `CARRY` | `NOT_APPLICABLE` |
| `shot_xg` | event type is not `SHOT` | `NOT_APPLICABLE` |
| observation `player_id`, `player_name` | observation `actor=false` | `SOURCE_UNIDENTIFIED` |
| observation `team_id` | observation `team_relation=OPPONENT` | `SOURCE_UNIDENTIFIED` |

Canonical position coordinates are additionally nullable exactly when `availability="UNAVAILABLE"`; in that case all coordinate members SHALL be null and `unavailable_reason` SHALL equal `SOURCE_POSITION_OUT_OF_BOUNDS`. No other normalized field is nullable. Empty string, zero, empty object, omitted member, `NaN`, infinity, and sentinel identifiers SHALL NOT substitute for null.

An optional source member that is present with JSON null is not absent. Because Section 5 does not permit null for a present consumed field, such an input cannot be a valid `SourceSelection`; normalization SHALL report `NORM_INPUT_SCHEMA_INVALID` if encountered.

### 6.12 Output ordering

All output order is normative:

1. `events` SHALL follow Section 6.6.3;
2. `period_ids` SHALL follow first occurrence in ordered events;
3. `freeze_frames` SHALL be sorted by referenced event `event_order`, then 360 `source_index`, then `freeze_frame_id` by Unicode code point;
4. observations SHALL remain in source `freeze_frame` array order;
5. visible-area points SHALL remain in source pair order;
6. provenance sources SHALL follow Section 6.4.8;
7. JSON object members SHALL follow canonical serialization in Section 2.3.

Input object-member order, hash-map order, filesystem order, thread completion order, platform locale, and source 360 array order SHALL NOT override these rules.

### 6.13 Normalization algorithm

The normalizer SHALL execute these steps and stop at the first failure:

1. verify artifact identity, hash, media type, and SourceSelection contract version;
2. validate the complete `SourceSelection` schema and count fields;
3. precompute source-record identities, SourceSelection array positions, and preserved Events indices;
4. construct canonical match, possession, team, player, event, period, and source-record identifiers;
5. reject identifier collisions;
6. map each retained Event by Section 6.8 in input order;
7. reject an unsupported enum mapping or illegal transformed value;
8. order events and assign `event_order`;
9. construct `period_ids`;
10. map each 360 record and its visible area and observations by Section 6.9;
11. order freeze frames by Section 6.12;
12. construct and validate every provenance map;
13. validate every invariant in Section 6.15;
14. canonicalize the completed artifact under Section 2.3;
15. emit the artifact and its SHA-256 digest.

No step has a configurable parameter or fallback.

### 6.14 Default parameters

Normalization has no default parameters and no configuration surface. Pitch dimensions, period offsets, identifier namespaces, enum mappings, precision, null rules, ordering, and provenance operations are fixed contract values. An implementation SHALL reject any request to override them during a conformance execution with `NORM_INPUT_ARTIFACT_INVALID`.

### 6.15 Invariants

- **TIP-NORM-010:** One input retained Event SHALL map to exactly one normalized event and vice versa.
- **TIP-NORM-011:** One input 360 record SHALL map to exactly one normalized freeze frame and vice versa.
- **TIP-NORM-012:** One input freeze-frame element SHALL map to exactly one normalized observation and vice versa.
- **TIP-NORM-013:** Every normalized record and observation identifier SHALL be deterministic and unique in its identifier class.
- **TIP-NORM-014:** Every normalized coordinate SHALL use metres and the coordinate system in Section 6.7.
- **TIP-NORM-015:** Every time value SHALL use seconds and the temporal model in Section 6.6.
- **TIP-NORM-016:** Every normalized leaf SHALL have complete provenance under Section 6.10.
- **TIP-NORM-017:** No unconsumed or unknown source field SHALL appear in the output or influence output bytes.
- **TIP-NORM-018:** No persistent player identity SHALL be assigned to a non-actor 360 observation.
- **TIP-NORM-019:** No normalized field SHALL encode synchronization, interpolation, lifecycle, confidence, tactics, perception, hypotheses, or rendering.
- **TIP-NORM-020:** Event, frame, observation, point, source, and object-member ordering SHALL be total and deterministic.
- **TIP-NORM-021:** Counts SHALL satisfy `events.length=retained_event_count` and `freeze_frames.length=associated_360_count` from the input.
- **TIP-NORM-022:** Every freeze-frame `event_id` SHALL resolve to exactly one normalized event.
- **TIP-NORM-023:** Normalization SHALL preserve the source distinction between absence, unidentified identity, and non-applicability through provenance classes.

### 6.16 Failure behavior

Normalization errors SHALL use stage `normalization`, execution status `PROCESSING_ERROR`, and an empty successful-artifacts array. A partial normalized artifact SHALL NOT be emitted.

| Code | Condition |
| --- | --- |
| `NORM_INPUT_ARTIFACT_INVALID` | Input is not the authenticated successful SourceSelection artifact. |
| `NORM_INPUT_VERSION_UNSUPPORTED` | SourceSelection contract version is not `0.1.0`. |
| `NORM_INPUT_SCHEMA_INVALID` | SourceSelection structure, count, required value, or deep-copied source record violates its declared upstream schema. |
| `NORM_IDENTIFIER_COLLISION` | Two constructed identifiers collide. |
| `NORM_UNSUPPORTED_MAPPING` | A provider enum pair or present source state has no mapping in this chapter. |
| `NORM_TIMESTAMP_INVALID` | Timestamp cannot be represented by Section 6.6. |
| `NORM_TRANSFORM_INVALID` | A converted number is non-finite, outside canonical bounds, or cannot meet required precision. |
| `NORM_PROVENANCE_INCOMPLETE` | Provenance is missing, extra, duplicated, unresolved, or incorrectly ordered. |
| `NORM_ORDERING_INVALID` | Required total order cannot be constructed or output violates it. |
| `NORM_INVARIANT_VIOLATION` | Any remaining invariant in Section 6.15 fails. |
| `NORM_SERIALIZATION_FAILED` | Canonical JSON bytes cannot be produced under Section 2.3. |

Errors SHALL be selected deterministically by algorithm step, then source document order `events` before `three_sixty`, then source array index, then source JSON Pointer lexicographically, then error code lexicographically. The normalizer SHALL stop after selecting the first error.

`source_references` SHALL reference original source paths where available. An artifact-level error SHALL reference `source_selection#/`. Normalization SHALL NOT reuse or emit a `SRC_*` code.

### 6.17 Worked fixture

The following validated source Events record is the first retained event of the Locatelli possession. Its Events `index` is `1043` and its position in `SourceSelection.events` is zero.

```json
{
  "id": "f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
  "index": 1043,
  "period": 1,
  "timestamp": "00:24:24.046",
  "minute": 24,
  "second": 24,
  "type": {"id": 43, "name": "Carry"},
  "possession": 40,
  "possession_team": {"id": 914, "name": "Italy"},
  "play_pattern": {"id": 1, "name": "Regular Play"},
  "team": {"id": 914, "name": "Italy"},
  "player": {"id": 7036, "name": "Gianluigi Donnarumma"},
  "location": [9.5, 22.8],
  "duration": 1.416717,
  "carry": {"end_location": [8.8, 26.7]}
}
```

It SHALL normalize to this `NormalizedEvent`. Provenance paths address the input `SourceSelection` artifact.

```json
{
  "schema_id": "tip.normalized_event",
  "event_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
  "source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
  "source_index": 1043,
  "event_order": 0,
  "period_id": "match:statsbomb:3788754:period:1",
  "period_number": 1,
  "period_time_seconds": 1464.046,
  "match_time_seconds": 1464.046,
  "duration_seconds": 1.416717,
  "possession_id": "match:statsbomb:3788754:possession:40",
  "possession_team_id": "team:statsbomb:914",
  "possession_team_name": "Italy",
  "team_id": "team:statsbomb:914",
  "team_name": "Italy",
  "actor_player_id": "player:statsbomb:7036",
  "actor_player_name": "Gianluigi Donnarumma",
  "event_type": "CARRY",
  "play_pattern": "REGULAR_PLAY",
  "start_position": {"x_m": 8.3125, "y_m": 48.62, "z_m": null},
  "end_position": {"x_m": 7.7, "y_m": 45.305, "z_m": null},
  "recipient_player_id": null,
  "recipient_player_name": null,
  "outcome": null,
  "shot_xg": null,
  "provenance": {
    "/actor_player_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/player/id"}]},
    "/actor_player_name": {"class": "RENAMED", "operation": "RENAME", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/player/name"}]},
    "/duration_seconds": {"class": "RENAMED", "operation": "RENAME", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/duration"}]},
    "/end_position/x_m": {"class": "COORDINATE_CONVERTED", "operation": "SCALE_X_METRES", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/carry/end_location/0"}]},
    "/end_position/y_m": {"class": "COORDINATE_CONVERTED", "operation": "INVERT_SCALE_Y_METRES", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/carry/end_location/1"}]},
    "/end_position/z_m": {"class": "NOT_APPLICABLE", "operation": "SET_NULL_NOT_APPLICABLE", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/carry"}]},
    "/event_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/id"}]},
    "/event_order": {"class": "DERIVED_DETERMINISTICALLY", "operation": "ASSIGN_ORDER", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/id"}, {"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/index"}, {"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/period"}, {"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/timestamp"}]},
    "/event_type": {"class": "ENUM_MAPPED", "operation": "MAP_ENUM", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/type"}]},
    "/match_time_seconds": {"class": "CONVERTED", "operation": "ADD_PERIOD_OFFSET", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/period"}, {"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/timestamp"}]},
    "/outcome": {"class": "NOT_APPLICABLE", "operation": "SET_NULL_NOT_APPLICABLE", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/type"}]},
    "/period_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/period"}]},
    "/period_number": {"class": "RENAMED", "operation": "RENAME", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/period"}]},
    "/period_time_seconds": {"class": "PARSED", "operation": "PARSE_TIMESTAMP", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/timestamp"}]},
    "/play_pattern": {"class": "ENUM_MAPPED", "operation": "MAP_ENUM", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/play_pattern"}]},
    "/possession_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/possession"}]},
    "/possession_team_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/possession_team/id"}]},
    "/possession_team_name": {"class": "RENAMED", "operation": "RENAME", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/possession_team/name"}]},
    "/recipient_player_id": {"class": "NOT_APPLICABLE", "operation": "SET_NULL_NOT_APPLICABLE", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/type"}]},
    "/recipient_player_name": {"class": "NOT_APPLICABLE", "operation": "SET_NULL_NOT_APPLICABLE", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/type"}]},
    "/schema_id": {"class": "CONSTANT", "operation": "SET_SCHEMA_CONSTANT", "sources": []},
    "/shot_xg": {"class": "NOT_APPLICABLE", "operation": "SET_NULL_NOT_APPLICABLE", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/type"}]},
    "/source_index": {"class": "RENAMED", "operation": "RENAME", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/index"}]},
    "/source_record_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/id"}]},
    "/start_position/x_m": {"class": "COORDINATE_CONVERTED", "operation": "SCALE_X_METRES", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/location/0"}]},
    "/start_position/y_m": {"class": "COORDINATE_CONVERTED", "operation": "INVERT_SCALE_Y_METRES", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/location/1"}]},
    "/start_position/z_m": {"class": "NOT_APPLICABLE", "operation": "SET_NULL_NOT_APPLICABLE", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/location"}]},
    "/team_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/team/id"}]},
    "/team_name": {"class": "RENAMED", "operation": "RENAME", "sources": [{"source_record_id": "source:statsbomb_open_data:b0bc9f22dd77c206ddedc1d742893b3bbe64baec:events:3788754:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "source_selection#/events/0/team/name"}]}
  }
}
```

The source `minute`, `second`, `position`, and `related_events` members do not occur in the normalized record. The first two are explicitly discarded by Section 6.8.1; the latter two are unconsumed under Section 5.4. Their presence SHALL NOT change any normalized byte.

### 6.18 Conformance tests

Every test in this section is normative and SHALL have a machine-readable fixture or JSON Patch.

| Test ID | Input or mutation | Required assertion |
| --- | --- | --- |
| **TIP-NORM-C001** | Untouched Locatelli positive `SourceSelection` | Canonical `NormalizedDataset` hash equals golden hash. |
| **TIP-NORM-C002** | Untouched Depay positive `SourceSelection` | Canonical `NormalizedDataset` hash equals golden hash. |
| **TIP-NORM-C003** | All four supported event types | Every type-specific field and null follows Section 6.8. |
| **TIP-NORM-C004** | Normalize the same artifact twice in fresh processes | All identifiers and canonical bytes are identical. |
| **TIP-NORM-C005** | StatsBomb points `[0,80]`, `[60,40]`, `[120,0]` | Results are `[0,0]`, `[52.5,34]`, `[105,68]` metres. |
| **TIP-NORM-C006** | Locatelli first Carry | Start is `(8.3125,48.62,null)` and end is `(7.7,45.305,null)`. |
| **TIP-NORM-C007** | Equal event timestamps with reversed input array order | Output follows period, timestamp, Events index, then Events ID. |
| **TIP-NORM-C008** | Add unknown source members at every nesting level | Output and hash remain unchanged. |
| **TIP-NORM-C009** | Change unconsumed pass angle | Output and hash remain unchanged. |
| **TIP-NORM-C010** | Remove optional Events duration | `duration_seconds=null` with `SOURCE_ABSENT`. |
| **TIP-NORM-C011** | Set optional Events duration to JSON null | `NORM_INPUT_SCHEMA_INVALID`. |
| **TIP-NORM-C012** | Non-actor 360 observation | Player ID and name are null with `SOURCE_UNIDENTIFIED`; no identity is synthesized. |
| **TIP-NORM-C013** | Opponent 360 observation | Team ID is null with `SOURCE_UNIDENTIFIED`. |
| **TIP-NORM-C014** | Actor location differs from event location | Both positions are converted independently and remain unequal. |
| **TIP-NORM-C015** | Visible-area polygon | Vertex count, closing vertex, and source order are preserved. |
| **TIP-NORM-C016** | Unsupported present Pass outcome pair | `NORM_UNSUPPORTED_MAPPING`. |
| **TIP-NORM-C017** | Force two constructed event identifiers to collide | `NORM_IDENTIFIER_COLLISION`; no partial artifact. |
| **TIP-NORM-C018** | Delete one required provenance entry | `NORM_PROVENANCE_INCOMPLETE`. |
| **TIP-NORM-C019** | Add provenance for an object-valued field path | `NORM_PROVENANCE_INCOMPLETE`. |
| **TIP-NORM-C020** | Shuffle source 360 records and execute normalization | Freeze-frame output order remains defined by Section 6.12. |
| **TIP-NORM-C021** | Input raw Events array instead of SourceSelection | `NORM_INPUT_ARTIFACT_INVALID`. |
| **TIP-NORM-C022** | SourceSelection with unknown contract version | `NORM_INPUT_VERSION_UNSUPPORTED`. |
| **TIP-NORM-C023** | Output with an unspecified normalized field | Schema validation fails. |
| **TIP-NORM-C024** | Output with an omitted nullable field | Schema validation fails. |
| **TIP-NORM-C025** | Canonical serialize golden dataset | Bytes and SHA-256 equal the published golden artifact. |
| **TIP-NORM-C026** | Timestamp `00:24:24.046`, period 1 | Period and match time both equal `1464.046` seconds. |
| **TIP-NORM-C027** | Identical timestamp in periods 1 and 2 | Match times differ by exactly `2700` seconds; no synchronization occurs. |
| **TIP-NORM-C028** | Shot end `[120,40,0.5]` | Canonical end is `(105,34,0.5)` metres with component-level provenance. |
| **TIP-NORM-C029** | Enumerate every field matched by the Chapter 5 input contract | Every field matches exactly one Section 6.8.7 matrix row. |
| **TIP-NORM-C030** | Mutate each explicitly discarded provider field independently | Canonical output bytes and hash remain unchanged. |
| **TIP-NORM-C031** | Instrument Synchronization input reads | Only canonical `NormalizedDataset` fields are read; every provider-specific read fails the test. |
| **TIP-NORM-C032** | Replace source provenance strings while preserving canonical records | Downstream branching behavior and non-provenance output remain unchanged. |

The golden artifact for each positive fixture SHALL validate against every schema in Section 6.4, satisfy every invariant in Section 6.15, contain complete provenance, and serialize under Section 2.3 before its hash is accepted.

### 6.19 Provider Independence Guarantee

Any downstream stage conforming to this specification SHALL consume only canonical normalized records and SHALL NOT depend on provider-specific schemas, field names, numeric enums, identifier formats, coordinate systems, document structures, repository layouts, dataset revisions, or source-library behavior.

- **TIP-NORM-PI-001:** `NormalizedDataset` is the sole data input permitted to the Synchronization stage.
- **TIP-NORM-PI-002:** A stage after normalization SHALL NOT read `SourceSelection`, raw Events, raw 360, a StatsBomb file, a StatsBomb dataframe, or a StatsBomb API response.
- **TIP-NORM-PI-003:** A stage after normalization SHALL NOT branch on `source_dataset`, `source_revision`, a provider-prefixed `source_record_id`, or provider information contained in provenance.
- **TIP-NORM-PI-004:** Downstream stages MAY retain and emit canonical provenance references but SHALL treat their provider-specific contents as opaque strings.
- **TIP-NORM-PI-005:** Adding a second provider SHALL require a provider adapter that emits this exact `NormalizedDataset` contract. It SHALL NOT change a downstream interface or observable downstream algorithm.
- **TIP-NORM-PI-006:** A downstream artifact or diagnostic SHALL use canonical terminology. The terms `StatsBomb location`, `StatsBomb freeze frame`, and raw provider field names are forbidden outside source provenance and source-validation diagnostics.
- **TIP-NORM-PI-007:** Conformance tests SHALL instrument downstream input access. Any read of a provider-specific source artifact or provider field after successful normalization constitutes non-conformance.

## 7. Synchronization

> **Editorial status:** Normative in Working Draft 0.1.0.

### 7.1 Purpose

Synchronization converts one valid `NormalizedDataset` into one deterministic canonical timeline. Synchronization changes temporal organization only. It SHALL NOT change semantic meaning.

Synchronization SHALL perform only these operations:

1. validate normalized temporal relations;
2. calculate deterministic period spans and canonical period starts;
3. assign canonical timeline timestamps;
4. construct a total record order;
5. attach each normalized freeze frame to its referenced normalized event;
6. preserve normalized payloads and normalized provenance byte-for-byte;
7. append synchronization provenance for synchronization-owned fields;
8. serialize one `SynchronizedDataset`.

Synchronization SHALL NOT create a World Model, infer identity over time, interpolate positions, estimate confidence, calculate football features, detect tactical concepts, create tracking, infer ball possession, reason about football, or modify canonical geometry.

- **TIP-SYNC-001:** Every synchronization-owned value SHALL be reproducible from the `NormalizedDataset` and this chapter alone.
- **TIP-SYNC-002:** Synchronization SHALL modify temporal organization and SHALL NOT modify an input payload value.
- **TIP-SYNC-003:** Synchronization SHALL NOT read `SourceSelection`, raw provider documents, provider dataframes, or provider APIs.

### 7.2 Input

The sole accepted input is a successful `NormalizedDataset` artifact produced by Chapter 6 with:

| Property | Required value |
| --- | --- |
| Media type | `application/vnd.tip.normalized-dataset+json` |
| `schema_id` | `tip.normalized_dataset` |
| `contract_version` | `0.1.0` |
| Integrity | Canonical bytes match the authenticated SHA-256 artifact digest |

The synchronizer SHALL reject a raw source artifact, `SourceSelection`, partial normalized artifact, diagnostic artifact, or normalized artifact with an unknown contract version.

The input SHALL satisfy every schema and invariant in Chapter 6 before synchronization begins. The synchronizer SHALL treat the input as immutable.

### 7.3 Output

Successful synchronization SHALL emit exactly one `SynchronizedDataset` JSON artifact with media type `application/vnd.tip.synchronized-dataset+json` and `contract_version="0.1.0"`.

The artifact SHALL contain only the fields defined in Section 7.4. Every synchronization schema has `additionalProperties=false`. Every field SHALL be present. Nullable fields SHALL contain their declared type or JSON `null`.

The artifact SHALL be serialized using Section 2.3. Synchronization SHALL emit the canonical artifact bytes and their lowercase SHA-256 digest.

### 7.4 Canonical schemas

#### 7.4.1 `SynchronizedDataset`

| Field | Type | Nullable | Units | Meaning |
| --- | --- | --- | --- | --- |
| `schema_id` | string | no | — | Exact value `tip.synchronized_dataset`. |
| `contract_version` | string | no | — | Exact value `0.1.0`. |
| `input_contract_version` | string | no | — | Exact copied value `0.1.0`. |
| `normalized_dataset_sha256` | string | no | — | Lowercase SHA-256 digest of canonical input bytes. |
| `source_dataset` | string | no | — | Opaque copy from `NormalizedDataset`; downstream stages SHALL NOT branch on it. |
| `source_revision` | string | no | — | Opaque copy from `NormalizedDataset`; downstream stages SHALL NOT branch on it. |
| `match_id` | `CanonicalId` | no | — | Copied canonical match identity. |
| `possession_id` | `CanonicalId` | no | — | Copied canonical possession identity. |
| `periods` | array[`SynchronizedPeriod`] | no | — | Canonical period timing records in period-number order. |
| `timeline_origin_seconds` | `Seconds` | no | seconds | Exact value `0`; canonical origin at the start of period 1. |
| `timeline` | array[`SynchronizedRecord`] | no | — | Total canonical timeline. |
| `normalized_provenance` | `ProvenanceMap` | no | — | Byte-identical copy of input dataset-level provenance. |
| `synchronization_provenance` | `ProvenanceMap` | no | — | Provenance for synchronization-owned dataset fields. |

`periods` and `timeline` SHALL be non-empty.

#### 7.4.2 `SynchronizedPeriod`

| Field | Type | Nullable | Units | Meaning |
| --- | --- | --- | --- | --- |
| `schema_id` | string | no | — | Exact value `tip.synchronized_period`. |
| `period_id` | `CanonicalId` | no | — | Copied normalized period identity when represented by an event; otherwise deterministically constructed from `match_id` and `period_number`. |
| `period_number` | integer | no | — | One of `1`, `2`, `3`, `4`. |
| `nominal_span_seconds` | `Seconds` | no | seconds | Fixed regulation span from Section 7.5. |
| `observed_span_seconds` | `Seconds` | no | seconds | Maximum observed event boundary in this period, or zero when no event exists. |
| `canonical_span_seconds` | `Seconds` | no | seconds | Maximum of nominal and observed span. |
| `canonical_start_seconds` | `Seconds` | no | seconds | Sum of canonical spans of all preceding periods. |
| `canonical_end_seconds` | `Seconds` | no | seconds | Start plus canonical span. |
| `synchronization_provenance` | `ProvenanceMap` | no | — | Provenance for every non-provenance field. |

#### 7.4.3 `SynchronizedRecord`

| Field | Type | Nullable | Units | Meaning |
| --- | --- | --- | --- | --- |
| `schema_id` | string | no | — | Exact value `tip.synchronized_record`. |
| `timeline_index` | integer | no | — | Unique zero-based position in `timeline`. |
| `record_kind` | enum | no | — | `EVENT` or `FREEZE_FRAME`. |
| `canonical_time_seconds` | `Seconds` | no | seconds | Canonical position in elapsed timeline time. |
| `period_id` | `CanonicalId` | no | — | Period containing the referenced event. |
| `period_number` | integer | no | — | Period containing the referenced event. |
| `period_time_seconds` | `Seconds` | no | seconds | Immutable normalized event period time. |
| `event_id` | `CanonicalId` | no | — | Referenced normalized event identity. |
| `attachment_event_id` | `CanonicalId` | yes | — | Referenced event for `FREEZE_FRAME`; null for `EVENT`. |
| `event_start_seconds` | `Seconds` | yes | seconds | Canonical event start for `EVENT`; null for `FREEZE_FRAME`. |
| `event_end_seconds` | `Seconds` | yes | seconds | Canonical event end when normalized duration exists; otherwise null. Always null for `FREEZE_FRAME`. |
| `boundary_kind` | enum | no | — | `INTERVAL`, `INSTANT`, or `ATTACHMENT`. |
| `normalized_event` | `NormalizedEvent` | yes | — | Byte-identical normalized event payload for `EVENT`; null otherwise. |
| `normalized_freeze_frame` | `NormalizedFreezeFrame` | yes | — | Byte-identical normalized freeze-frame payload for `FREEZE_FRAME`; null otherwise. |
| `normalized_provenance` | `ProvenanceMap` | no | — | Byte-identical copy of the payload provenance. |
| `synchronization_provenance` | `ProvenanceMap` | no | — | Provenance for synchronization-owned fields. |

The record-kind constraints are exact:

| Field | `EVENT` | `FREEZE_FRAME` |
| --- | --- | --- |
| `attachment_event_id` | null | equals `event_id` |
| `event_start_seconds` | equals `canonical_time_seconds` | null |
| `event_end_seconds` | start plus duration, or null | null |
| `boundary_kind` | `INTERVAL` when duration is non-null; otherwise `INSTANT` | `ATTACHMENT` |
| `normalized_event` | non-null | null |
| `normalized_freeze_frame` | null | non-null |
| `normalized_provenance` | exact event provenance | exact freeze-frame provenance |

`normalized_event` and `normalized_freeze_frame` are Chapter 6 records carried as immutable payloads. Their inclusion SHALL NOT create a new semantic entity or alter their schemas.

#### 7.4.4 Synchronization provenance

Synchronization provenance SHALL use the `ProvenanceMap`, `FieldProvenance`, and `ProvenanceSource` structures in Section 6.4.8. It SHALL use only these additional synchronization operations:

| Class | Operation | Meaning |
| --- | --- | --- |
| `COPIED` | `COPY_NORMALIZED` | Canonical normalized value is unchanged. |
| `CONVERTED` | `ADD_CANONICAL_PERIOD_START` | Period-local time receives its synchronized period start. |
| `DERIVED_DETERMINISTICALLY` | `CALCULATE_PERIOD_SPAN` | Period span follows Section 7.5. |
| `DERIVED_DETERMINISTICALLY` | `ASSIGN_TIMELINE_INDEX` | Unique record position follows Section 7.7. |
| `DERIVED_DETERMINISTICALLY` | `ATTACH_FREEZE_FRAME` | Freeze frame is attached by exact event identity. |
| `DERIVED_DETERMINISTICALLY` | `CALCULATE_EVENT_BOUNDARY` | Event boundary follows Section 7.6. |
| `DERIVED_DETERMINISTICALLY` | `BUILD_TIMELINE` | Collection membership and total order follow Section 7.7. |
| `CONSTANT` | `SET_SYNC_CONSTANT` | Specification constant with an empty source list. |
| `NOT_APPLICABLE` | `SET_NULL_SYNC_NOT_APPLICABLE` | Synchronization field does not apply to this record kind. |

Synchronization provenance sources SHALL reference canonical normalized record identifiers and paths with form `normalized_dataset#<JSON Pointer>`. Sources SHALL follow the ordering rules in Section 6.4.8.

### 7.5 Canonical timeline

#### 7.5.1 Origin and period coverage

The canonical timeline origin SHALL be `0` seconds at the start of match period 1. The synchronizer SHALL create `SynchronizedPeriod` records for every integer period from `1` through the highest period represented by normalized events. A period without an input event SHALL have `observed_span_seconds=0` and SHALL retain its nominal span.

For a period containing an event, `period_id` SHALL equal that event's normalized `period_id`. For a period without an event, it SHALL equal `<match_id>:period:<period_number>` under the identifier grammar in Section 6.5. Construction of an absent period record is temporal organization and SHALL NOT create a semantic match-state entity.

Nominal spans are fixed:

| Period | Nominal span seconds |
| ---: | ---: |
| 1 | 2700 |
| 2 | 2700 |
| 3 | 900 |
| 4 | 900 |

Periods outside `1` through `4` SHALL fail with `SYNC_UNSUPPORTED_PERIOD`.

#### 7.5.2 Observed and canonical period spans

For each event, its observed boundary SHALL be:

```text
event_observed_boundary = period_time_seconds + duration_seconds
```

when duration is non-null, and:

```text
event_observed_boundary = period_time_seconds
```

when duration is null.

For period `p`:

```text
observed_span[p] = maximum event_observed_boundary for p
observed_span[p] = 0 when p contains no event
canonical_span[p] = max(nominal_span[p], observed_span[p])
canonical_start[1] = 0
canonical_start[p] = sum(canonical_span[k]) for every integer k where 1 <= k < p
canonical_end[p] = canonical_start[p] + canonical_span[p]
```

This calculation incorporates observed stoppage time when an event boundary exceeds the nominal period span. It SHALL NOT insert half-time, interval, broadcast, or wall-clock duration.

#### 7.5.3 Canonical record timestamp

For an `EVENT` record:

```text
canonical_time_seconds = canonical_start[period_number] + period_time_seconds
```

For a `FREEZE_FRAME` record, `canonical_time_seconds`, `period_id`, `period_number`, and `period_time_seconds` SHALL equal those of its attached `EVENT` record.

The normalized `period_time_seconds` and `match_time_seconds` inside immutable payloads SHALL NOT be changed. `canonical_time_seconds` is a synchronization-owned value. The normalized `match_time_seconds` SHALL NOT be used to order synchronized records.

#### 7.5.4 Precision and rounding

All temporal calculations SHALL use decimal arithmetic with at least fifteen significant decimal digits. No intermediate value SHALL be rounded. Canonical serialization SHALL round to six fractional digits using Section 2.3. Negative zero SHALL serialize as zero.

Two canonical timestamps are equal when their exact pre-serialization decimal values are equal. Equality SHALL NOT use a tolerance.

#### 7.5.5 Period transitions and stoppage time

The first record in period `p>1` SHALL have a canonical time greater than or equal to `canonical_start[p]`. Every record in a later period SHALL sort after every record in an earlier period, including when normalized nominal match times overlap because of stoppage time.

Period 2 begins after the canonical span of period 1. Period 3 begins after the canonical spans of periods 1 and 2. Period 4 begins after the canonical spans of periods 1 through 3. Extra time is supported only through periods 3 and 4. A penalty-shootout period is unsupported.

### 7.6 Event boundaries

Every normalized event SHALL produce one synchronized `EVENT` record.

Its start boundary SHALL equal `canonical_time_seconds`. When `duration_seconds` is non-null, its end boundary SHALL equal:

```text
event_end_seconds = event_start_seconds + duration_seconds
```

and `boundary_kind` SHALL equal `INTERVAL`.

When `duration_seconds` is null, `event_end_seconds` SHALL be null and `boundary_kind` SHALL equal `INSTANT`. Synchronization SHALL NOT estimate an end from the next event, attached freeze frame, period boundary, event type, or any other record.

Event intervals MAY overlap. An overlap SHALL NOT change ordering and SHALL NOT cause clipping, splitting, merging, or failure. An event end after `canonical_end_seconds` indicates an invalid period-span calculation and SHALL fail with `SYNC_TIMESTAMP_INCONSISTENT`.

### 7.7 Synchronization algorithm and record ordering

The synchronizer SHALL execute exactly these steps and stop at the first failure:

1. authenticate the input artifact and verify media type and contract version;
2. validate Chapter 6 object schemas, field types, null rules, canonical identifier grammar, and normalized provenance; defer ordering, uniqueness, attachment, and temporal-relation checks to the following synchronization steps;
3. index normalized events by `event_id` and reject duplicate identities;
4. validate that normalized `event_order` values are the consecutive integers from zero through `events.length-1`;
5. index normalized freeze frames by `freeze_frame_id` and reject duplicate identities;
6. resolve every freeze-frame `event_id` to exactly one normalized event;
7. reject a second freeze frame resolving to an event that already has an attachment;
8. calculate period observed spans, canonical spans, starts, and ends;
9. process normalized events in ascending `event_order`;
10. emit one `EVENT` record for the current event;
11. when the current event has an attachment, emit its `FREEZE_FRAME` record immediately after the `EVENT` record;
12. assign `timeline_index` values consecutively from zero in emission order;
13. construct and validate synchronization provenance;
14. validate every invariant in Section 7.11;
15. canonicalize under Section 2.3 and emit the artifact and digest.

The total order is therefore:

```text
(normalized event_order ascending,
 record_kind_rank ascending)

record_kind_rank(EVENT) = 0
record_kind_rank(FREEZE_FRAME) = 1
```

No other tie-breaker is required because Chapter 6 event identities and event-order values are unique and Section 7.8 permits at most one freeze-frame attachment per event. If these preconditions do not hold, synchronization SHALL fail instead of inventing an order.

Input array order, object-member order, hash-map order, filesystem order, locale, thread completion order, memory address, and random state SHALL NOT affect the timeline.

Equal canonical timestamps SHALL remain equal. They SHALL NOT receive an epsilon, offset, artificial duration, or reordered timestamp. `timeline_index` SHALL provide their unique total position.

### 7.8 Freeze-frame attachment

A normalized freeze frame SHALL attach to a normalized event only when their canonical `event_id` strings are exactly equal.

- **TIP-SYNC-ATT-001:** Every normalized freeze frame SHALL attach to exactly one normalized event.
- **TIP-SYNC-ATT-002:** A normalized event SHALL have zero or one attached freeze frame.
- **TIP-SYNC-ATT-003:** An event without a freeze frame SHALL emit only its `EVENT` record. No empty frame or observation SHALL be created.
- **TIP-SYNC-ATT-004:** An attached freeze frame SHALL emit exactly one `FREEZE_FRAME` record immediately after its event record.
- **TIP-SYNC-ATT-005:** Attachment SHALL NOT change, add, remove, reorder, merge, or identify any normalized observation.
- **TIP-SYNC-ATT-006:** Freeze-frame source order SHALL NOT determine timeline order.
- **TIP-SYNC-ATT-007:** A duplicate attachment SHALL fail; first-write-wins, last-write-wins, merging, and selection are forbidden.
- **TIP-SYNC-ATT-008:** A missing attachment is valid and SHALL NOT reduce, estimate, or annotate confidence.

The attachment relation SHALL be represented by `attachment_event_id`, synchronization provenance operation `ATTACH_FREEZE_FRAME`, adjacency in the timeline, and equality of the event and freeze-frame canonical timestamps.

### 7.9 Provenance preservation

Synchronization SHALL preserve every input provenance map exactly:

1. `NormalizedDataset.provenance` SHALL be copied to `SynchronizedDataset.normalized_provenance` without adding, deleting, reordering, or changing a member;
2. each event payload SHALL be an exact deep copy of its normalized event, including its provenance;
3. an `EVENT` record's `normalized_provenance` SHALL equal the payload provenance;
4. each freeze-frame payload SHALL be an exact deep copy of the complete normalized freeze frame, including visible-area and observation provenance;
5. a `FREEZE_FRAME` record's `normalized_provenance` SHALL equal the freeze-frame record-level provenance; child provenance remains inside the payload;
6. synchronization provenance SHALL be stored separately and SHALL NOT be inserted into a normalized provenance map.

Synchronization-owned provenance SHALL cover every synchronization-owned scalar, null, and array field. Payload object paths SHALL NOT receive synchronization provenance. `normalized_event` and `normalized_freeze_frame` SHALL be proven by their authenticated input record identity and input artifact digest, not by duplicating child provenance into the synchronization map.

- **TIP-SYNC-PROV-001:** No normalized provenance entry SHALL be removed or rewritten.
- **TIP-SYNC-PROV-002:** Every timeline index, canonical timestamp, period calculation, boundary, null disposition, collection order, and attachment SHALL have synchronization provenance.
- **TIP-SYNC-PROV-003:** Synchronization provenance SHALL contain no tactical, confidence, lifecycle, geometry, or identity-continuity assertion.

### 7.10 Missing values and duplicate handling

Null is permitted only as follows:

| Field | Null condition |
| --- | --- |
| `attachment_event_id` | record kind is `EVENT` |
| `event_start_seconds` | record kind is `FREEZE_FRAME` |
| `event_end_seconds` | record kind is `FREEZE_FRAME`, or event normalized duration is null |
| `normalized_event` | record kind is `FREEZE_FRAME` |
| `normalized_freeze_frame` | record kind is `EVENT` |

No other synchronization-owned field is nullable. Missing normalized freeze frames do not create a null payload field on a separate record because no `FREEZE_FRAME` record is emitted.

Duplicate normalized event IDs, freeze-frame IDs, event-order values, timeline indices, or attachments are invalid. Duplicate timestamps are valid. Duplicate payload bytes with distinct valid identifiers are valid and remain distinct records.

### 7.11 Temporal invariants

- **TIP-SYNC-010:** Every normalized event maps to exactly one `EVENT` record and vice versa.
- **TIP-SYNC-011:** Every normalized freeze frame maps to exactly one `FREEZE_FRAME` record and vice versa.
- **TIP-SYNC-012:** Every synchronized record has exactly one canonical timestamp and one unique timeline index.
- **TIP-SYNC-013:** Timeline indices are the consecutive integers from zero through `timeline.length-1`.
- **TIP-SYNC-014:** Timeline canonical timestamps are non-decreasing in timeline-index order.
- **TIP-SYNC-015:** Records in a later period follow every record in an earlier period.
- **TIP-SYNC-016:** Equal timestamps preserve total order through normalized event order and record-kind rank.
- **TIP-SYNC-017:** Event and freeze-frame payloads are semantically and byte-wise unchanged from normalized input records.
- **TIP-SYNC-018:** Every freeze-frame record is adjacent to and immediately follows its attached event record.
- **TIP-SYNC-019:** Every event has at most one freeze-frame attachment.
- **TIP-SYNC-020:** Every synchronization-owned field has complete synchronization provenance.
- **TIP-SYNC-021:** Every normalized provenance field is preserved.
- **TIP-SYNC-022:** Canonical timestamps and timeline indices contain no inferred, interpolated, or tolerance-adjusted time.
- **TIP-SYNC-023:** Synchronization output contains no newly introduced identity, state, tracking, lifecycle, confidence, geometry, football feature, tactical concept, or explanation.
- **TIP-SYNC-024:** Repeated synchronization of identical canonical input bytes produces identical canonical output bytes.
- **TIP-SYNC-025:** After synchronization, `canonical_time_seconds`, event boundaries, period spans, period starts, period ends, and timeline indices are immutable downstream.

### 7.12 Default parameters

Synchronization has no configuration surface and no default parameters. Nominal period spans, timeline origin, decimal precision, attachment key, ordering, record-kind rank, null rules, and provenance operations are fixed contract values.

An implementation SHALL reject a request to override a synchronization contract value during conformance execution with `SYNC_INPUT_ARTIFACT_INVALID`.

### 7.13 Failure behavior

Synchronization errors SHALL use stage `synchronization`, execution status `PROCESSING_ERROR`, and an empty successful-artifacts array. A partial synchronized artifact SHALL NOT be emitted.

| Code | Condition |
| --- | --- |
| `SYNC_INPUT_ARTIFACT_INVALID` | Input is not an authenticated successful NormalizedDataset or includes a synchronization override. |
| `SYNC_INPUT_VERSION_UNSUPPORTED` | NormalizedDataset contract version is not `0.1.0`. |
| `SYNC_INPUT_SCHEMA_INVALID` | Input violates a Chapter 6 schema, ordering rule, or non-temporal invariant. |
| `SYNC_DUPLICATE_EVENT` | Event identity occurs more than once. |
| `SYNC_DUPLICATE_FREEZE_FRAME` | Freeze-frame identity occurs more than once. |
| `SYNC_EVENT_ORDER_INVALID` | Event-order values are duplicated, missing, non-consecutive, or inconsistent with input order. |
| `SYNC_ATTACHMENT_TARGET_MISSING` | Freeze-frame event identity resolves to no event. |
| `SYNC_DUPLICATE_ATTACHMENT` | More than one freeze frame resolves to the same event. |
| `SYNC_UNSUPPORTED_PERIOD` | Period is outside `1` through `4`. |
| `SYNC_TIMESTAMP_INCONSISTENT` | Period time, duration, boundary, span, canonical time, or period transition violates Section 7.5 or 7.6. |
| `SYNC_UNSUPPORTED_TEMPORAL_RELATION` | Input requires a temporal relation not defined by this chapter. |
| `SYNC_ORDERING_IMPOSSIBLE` | A unique total timeline order cannot be constructed. |
| `SYNC_PROVENANCE_INCOMPLETE` | Normalized provenance is changed or synchronization provenance is missing, extra, unresolved, or incorrectly ordered. |
| `SYNC_INVARIANT_VIOLATION` | Any remaining invariant in Section 7.11 fails. |
| `SYNC_SERIALIZATION_FAILED` | Canonical JSON bytes cannot be produced under Section 2.3. |

The synchronizer SHALL select the first error by:

1. algorithm step in Section 7.7;
2. normalized event order;
3. record-kind rank;
4. normalized source index;
5. normalized record identifier by Unicode code point;
6. normalized JSON Pointer by Unicode code point;
7. error code by Unicode code point.

An unavailable ordering-key component SHALL sort before an available component. Errors at artifact scope SHALL precede record errors within the same algorithm step.

Error `source_references` SHALL use `normalized_dataset#<JSON Pointer>`. Synchronization SHALL NOT emit a `SRC_*` or `NORM_*` error code.

### 7.14 Worked fixture

This worked fixture contains two normalized events with equal timestamps. The first event has one normalized freeze frame; the second event has none. Payload bodies are abbreviated as authenticated immutable records because synchronization does not transform their fields.

```json
{
  "schema_id": "tip.normalized_dataset",
  "contract_version": "0.1.0",
  "match_id": "match:statsbomb:3788754",
  "possession_id": "match:statsbomb:3788754:possession:40",
  "events": [
    {
      "event_id": "event:statsbomb:event-a",
      "event_order": 0,
      "period_id": "match:statsbomb:3788754:period:1",
      "period_number": 1,
      "period_time_seconds": 1464.046,
      "match_time_seconds": 1464.046,
      "duration_seconds": 1.416717,
      "provenance": {"/event_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": []}}
    },
    {
      "event_id": "event:statsbomb:event-b",
      "event_order": 1,
      "period_id": "match:statsbomb:3788754:period:1",
      "period_number": 1,
      "period_time_seconds": 1464.046,
      "match_time_seconds": 1464.046,
      "duration_seconds": null,
      "provenance": {"/event_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": []}}
    }
  ],
  "freeze_frames": [
    {
      "freeze_frame_id": "event:statsbomb:event-a:freeze_frame:statsbomb360",
      "event_id": "event:statsbomb:event-a",
      "provenance": {"/event_id": {"class": "WRAPPED_IDENTIFIER", "operation": "WRAP_ID", "sources": []}}
    }
  ]
}
```

The resulting temporal structure SHALL be:

```json
{
  "periods": [
    {
      "period_number": 1,
      "nominal_span_seconds": 2700,
      "observed_span_seconds": 1465.462717,
      "canonical_span_seconds": 2700,
      "canonical_start_seconds": 0,
      "canonical_end_seconds": 2700
    }
  ],
  "timeline": [
    {
      "timeline_index": 0,
      "record_kind": "EVENT",
      "canonical_time_seconds": 1464.046,
      "event_id": "event:statsbomb:event-a",
      "attachment_event_id": null,
      "event_start_seconds": 1464.046,
      "event_end_seconds": 1465.462717,
      "boundary_kind": "INTERVAL",
      "normalized_event": "byte-identical event-a payload",
      "normalized_freeze_frame": null,
      "synchronization_provenance": {
        "/canonical_time_seconds": {
          "class": "CONVERTED",
          "operation": "ADD_CANONICAL_PERIOD_START",
          "sources": [{"source_record_id": "event:statsbomb:event-a", "source_path": "normalized_dataset#/events/0/period_time_seconds"}]
        },
        "/timeline_index": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "ASSIGN_TIMELINE_INDEX",
          "sources": [{"source_record_id": "event:statsbomb:event-a", "source_path": "normalized_dataset#/events/0/event_order"}]
        }
      }
    },
    {
      "timeline_index": 1,
      "record_kind": "FREEZE_FRAME",
      "canonical_time_seconds": 1464.046,
      "event_id": "event:statsbomb:event-a",
      "attachment_event_id": "event:statsbomb:event-a",
      "event_start_seconds": null,
      "event_end_seconds": null,
      "boundary_kind": "ATTACHMENT",
      "normalized_event": null,
      "normalized_freeze_frame": "byte-identical attached payload",
      "synchronization_provenance": {
        "/attachment_event_id": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "ATTACH_FREEZE_FRAME",
          "sources": [
            {"source_record_id": "event:statsbomb:event-a", "source_path": "normalized_dataset#/events/0/event_id"},
            {"source_record_id": "event:statsbomb:event-a:freeze_frame:statsbomb360", "source_path": "normalized_dataset#/freeze_frames/0/event_id"}
          ]
        },
        "/timeline_index": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "ASSIGN_TIMELINE_INDEX",
          "sources": [{"source_record_id": "event:statsbomb:event-a:freeze_frame:statsbomb360", "source_path": "normalized_dataset#/freeze_frames/0/freeze_frame_id"}]
        }
      }
    },
    {
      "timeline_index": 2,
      "record_kind": "EVENT",
      "canonical_time_seconds": 1464.046,
      "event_id": "event:statsbomb:event-b",
      "attachment_event_id": null,
      "event_start_seconds": 1464.046,
      "event_end_seconds": null,
      "boundary_kind": "INSTANT",
      "normalized_event": "byte-identical event-b payload",
      "normalized_freeze_frame": null,
      "synchronization_provenance": {
        "/canonical_time_seconds": {
          "class": "CONVERTED",
          "operation": "ADD_CANONICAL_PERIOD_START",
          "sources": [{"source_record_id": "event:statsbomb:event-b", "source_path": "normalized_dataset#/events/1/period_time_seconds"}]
        },
        "/timeline_index": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "ASSIGN_TIMELINE_INDEX",
          "sources": [{"source_record_id": "event:statsbomb:event-b", "source_path": "normalized_dataset#/events/1/event_order"}]
        }
      }
    }
  ]
}
```

The complete conformance fixture SHALL contain every required schema field and complete provenance. The abbreviated payload strings and partial provenance maps above specify temporal results only and SHALL NOT be used as schema-valid golden artifacts.

### 7.15 Conformance tests

Every test in this section is normative and SHALL use a machine-readable fixture or JSON Patch.

| Test ID | Input or mutation | Required assertion |
| --- | --- | --- |
| **TIP-SYNC-C001** | Untouched Locatelli `NormalizedDataset` | Canonical `SynchronizedDataset` hash equals golden hash. |
| **TIP-SYNC-C002** | Untouched Depay `NormalizedDataset` | Canonical `SynchronizedDataset` hash equals golden hash. |
| **TIP-SYNC-C003** | Two events with equal timestamps | Timestamps remain equal; records follow event order. |
| **TIP-SYNC-C004** | Two equal-time events, first with a frame | Order is first event, its frame, second event. |
| **TIP-SYNC-C005** | Event without a freeze frame | One event record and no fabricated frame record. |
| **TIP-SYNC-C006** | Process valid normalized freeze frames through reversed internal enumeration | Attachments and timeline bytes remain unchanged because output follows event identity and event order. |
| **TIP-SYNC-C007** | Two freeze frames reference one event | `SYNC_DUPLICATE_ATTACHMENT`. |
| **TIP-SYNC-C008** | Duplicate freeze-frame identity | `SYNC_DUPLICATE_FREEZE_FRAME`. |
| **TIP-SYNC-C009** | Freeze frame references unknown event | `SYNC_ATTACHMENT_TARGET_MISSING`. |
| **TIP-SYNC-C010** | Event duration absent | Instant boundary with null event end; no estimated duration. |
| **TIP-SYNC-C011** | Event duration present | End equals canonical start plus exact duration. |
| **TIP-SYNC-C012** | Period 1 observed boundary `2760` | Period 1 canonical span is `2760`; period 2 start is `2760`. |
| **TIP-SYNC-C013** | Periods 1 and 2 with nominal overlap in normalized match time | Canonical timeline remains non-decreasing and period ordered. |
| **TIP-SYNC-C014** | Period 3 event | Periods 1 and 2 exist in `periods`; canonical start is their span sum. |
| **TIP-SYNC-C015** | Period 5 event | `SYNC_UNSUPPORTED_PERIOD`. |
| **TIP-SYNC-C016** | Duplicate event order | `SYNC_EVENT_ORDER_INVALID`. |
| **TIP-SYNC-C017** | Gap in event order | `SYNC_EVENT_ORDER_INVALID`. |
| **TIP-SYNC-C018** | Normalize and synchronize twice in fresh processes | Canonical timeline bytes and digest are identical. |
| **TIP-SYNC-C019** | Shuffle object members and execute concurrently | Canonical output bytes remain unchanged. |
| **TIP-SYNC-C020** | Input normalized provenance | Every map and entry is byte-identical in synchronized output. |
| **TIP-SYNC-C021** | Delete one synchronization provenance entry | `SYNC_PROVENANCE_INCOMPLETE`. |
| **TIP-SYNC-C022** | Change a normalized payload byte during synchronization | `SYNC_INVARIANT_VIOLATION`. |
| **TIP-SYNC-C023** | Raw SourceSelection supplied as input | `SYNC_INPUT_ARTIFACT_INVALID`. |
| **TIP-SYNC-C024** | Unknown NormalizedDataset contract version | `SYNC_INPUT_VERSION_UNSUPPORTED`. |
| **TIP-SYNC-C025** | Multiple defects in different algorithm steps | Error selected by Section 7.13 ordering. |
| **TIP-SYNC-C026** | Duplicate timestamps with distinct event IDs | Both events and attachments remain distinct. |
| **TIP-SYNC-C027** | Canonical serialization of golden synchronized data | Bytes and SHA-256 equal published golden artifact. |
| **TIP-SYNC-C028** | Instrument synchronization input access | No provider artifact or provider field is read. |

### 7.16 Synchronized Data Boundary

Any downstream stage conforming to this specification SHALL consume only `SynchronizedDataset` and SHALL NOT consume `NormalizedDataset` directly.

- **TIP-SYNC-BOUND-001:** The World Model stage SHALL accept `SynchronizedDataset` as its sole data input.
- **TIP-SYNC-BOUND-002:** A stage after synchronization SHALL NOT read a normalized artifact outside immutable normalized payloads carried by synchronized records.
- **TIP-SYNC-BOUND-003:** A downstream stage SHALL use `canonical_time_seconds` and `timeline_index` for temporal organization. It SHALL NOT reorder records using normalized `match_time_seconds`, normalized `event_order`, source indices, payload array order, or provenance.
- **TIP-SYNC-BOUND-004:** Downstream stages MAY preserve normalized and synchronization provenance but SHALL treat provenance content as non-semantic audit data.
- **TIP-SYNC-BOUND-005:** Any downstream read that bypasses the synchronized timeline constitutes non-conformance.

## 8. World Model

> **Editorial status:** Normative in Working Draft 0.1.0.

### 8.1 Purpose

The World Model represents the canonical football world at synchronized instants. It is a state representation only.

The World Model SHALL:

1. construct immutable entity identities from synchronized canonical records;
2. represent direct event and freeze-frame observations without reconciliation;
3. represent visibility and absence explicitly;
4. apply the deterministic lifecycle in Section 8.12;
5. express only factual identity, membership, observation, visibility, location, ownership-knowledge, and temporal relations;
6. emit one `WorldState` for every synchronized `EVENT` record.

The World Model SHALL NOT perform football reasoning, detect tactical concepts, calculate tactical features, infer intent, explain an event, interpolate, estimate motion, create tracking, infer anonymous identity continuity, select a preferred conflicting position, or assign confidence.

- **TIP-WORLD-001:** A World Model value SHALL be reproducible from one authenticated `SynchronizedDataset` and this chapter alone.
- **TIP-WORLD-002:** The absence of an observation SHALL NOT be converted into a spatial fact.
- **TIP-WORLD-003:** Multiple direct observations of one entity at one instant SHALL remain distinct observations.

### 8.2 Input and output

The sole input is a successful `SynchronizedDataset` artifact produced by Chapter 7 with media type `application/vnd.tip.synchronized-dataset+json`, `schema_id="tip.synchronized_dataset"`, and `contract_version="0.1.0"`.

The World Model stage SHALL NOT read `NormalizedDataset`, `SourceSelection`, raw provider data, or provider-specific provenance content. Immutable normalized payloads carried inside synchronized records are part of the synchronized input and SHALL be treated as canonical records.

Successful construction SHALL emit exactly one `WorldModelDataset` artifact with media type `application/vnd.tip.world-model+json` and `contract_version="0.1.0"`.

Every schema in this chapter has `additionalProperties=false`. Every field SHALL be present. A nullable field SHALL contain its declared type or JSON `null`; omission is forbidden. The output SHALL use canonical serialization under Section 2.3.

### 8.3 `WorldModelDataset`

#### 8.3.1 Purpose

`WorldModelDataset` is the immutable container for the entity catalog and ordered instantaneous states of one synchronized possession dataset.

#### 8.3.2 Schema

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.world_model_dataset`. |
| `contract_version` | string | no | Exact value `0.1.0`. |
| `input_contract_version` | string | no | Exact value `0.1.0`. |
| `synchronized_dataset_sha256` | string | no | Lowercase SHA-256 of canonical synchronized input bytes. |
| `match_id` | `CanonicalId` | no | Copied canonical match identity. |
| `possession_id` | `CanonicalId` | no | Copied canonical possession identity. |
| `pitch` | `Pitch` | no | One canonical pitch entity. |
| `possession` | `Possession` | no | One canonical possession entity. |
| `ball` | `Ball` | no | One canonical ball entity. |
| `teams` | array[`Team`] | no | Complete team catalog. |
| `players` | array[`Player`] | no | Complete player catalog. |
| `world_states` | array[`WorldState`] | no | Ordered instantaneous states. |
| `input_provenance` | `InputProvenanceBundle` | no | Exact synchronized dataset normalized and synchronization provenance, copied without interpretation. |
| `world_provenance` | `ProvenanceMap` | no | Provenance for World Model-owned fields and collections. |

No field is optional. `teams`, `players`, and `world_states` SHALL be non-empty.

`InputProvenanceBundle` contains exactly:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `normalized_provenance` | `ProvenanceMap` | no | Exact `SynchronizedDataset.normalized_provenance`. |
| `synchronization_provenance` | `ProvenanceMap` | no | Exact `SynchronizedDataset.synchronization_provenance`. |

#### 8.3.3 Identity and lifecycle

The dataset identity is the tuple `(contract_version, synchronized_dataset_sha256)`. The dataset itself has no lifecycle state. Contained entities follow Sections 8.5 through 8.12.

#### 8.3.4 Invariants and failure

The dataset SHALL contain exactly one pitch, one possession, and one ball. A violation SHALL fail with `WORLD_MANDATORY_ENTITY_MISSING` or `WORLD_DUPLICATE_BALL` as applicable. Catalog identifiers SHALL be unique across their entity type and SHALL satisfy Section 8.11.

#### 8.3.5 Provenance

Every scalar and collection owned by the dataset SHALL have World Model provenance. Entity and state objects carry their own provenance. Provider-specific input provenance SHALL be copied as opaque audit data and SHALL NOT affect construction.

### 8.4 `WorldState`

#### 8.4.1 Purpose

A `WorldState` represents exactly one synchronized event instant. It SHALL be anchored to one and only one synchronized `EVENT` record and its optional immediately adjacent `FREEZE_FRAME` record.

Two `EVENT` records with equal `canonical_time_seconds` SHALL produce two distinct WorldStates. They SHALL retain event order through `world_state_index`.

#### 8.4.2 Schema

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.world_state`. |
| `world_state_id` | `CanonicalId` | no | Deterministic state identity. |
| `world_state_index` | integer | no | Unique zero-based state order. |
| `anchor_timeline_index` | integer | no | Timeline index of the anchoring event. |
| `canonical_time_seconds` | `Seconds` | no | Exact synchronized event time. |
| `period_id` | `CanonicalId` | no | Exact synchronized period identity. |
| `period_number` | integer | no | Exact synchronized period number. |
| `period_time_seconds` | `Seconds` | no | Exact synchronized period-local time. |
| `anchor_event_id` | `CanonicalId` | no | Event anchoring this state. |
| `pitch_id` | `CanonicalId` | no | Reference to the sole Pitch. |
| `possession_id` | `CanonicalId` | no | Reference to the sole Possession. |
| `ball_state` | `BallState` | no | Ball state at this instant. |
| `team_states` | array[`TeamState`] | no | State of every catalog team. |
| `player_states` | array[`PlayerState`] | no | State of every catalog player. |
| `observations` | array[`Observation`] | no | Direct observations assigned to this instant. |
| `relationships` | array[`Relationship`] | no | Factual relationships valid at this instant. |
| `world_provenance` | `ProvenanceMap` | no | Provenance for every state-owned field and collection. |

No field is optional or nullable.

#### 8.4.3 Identity rules

```text
world_state_id = world_state:<match_id>:<possession_id source integer>:<anchor event_id source suffix>
```

The canonical possession source integer and event source suffix SHALL be extracted only by the canonical identifier grammar in Section 6.5. Failure to match that grammar SHALL produce `WORLD_IDENTITY_INVALID`.

`world_state_index` SHALL equal the zero-based order of synchronized `EVENT` records. `anchor_timeline_index` SHALL equal that event record's `timeline_index`.

#### 8.4.4 Lifecycle rules

A WorldState is immutable after construction. WorldStates have no lifecycle enum. Temporal succession is represented by `TEMPORALLY_FOLLOWS` relationships and state order.

#### 8.4.5 Invariants and failure

A WorldState SHALL have exactly one timestamp, one ball state, one pitch reference, one possession reference, one anchor event, and one state entry for every catalog team and player. Duplicate state entries SHALL produce `WORLD_DUPLICATE_ENTITY_STATE`. A timestamp mismatch with the anchor SHALL produce `WORLD_TIMESTAMP_INCONSISTENT`.

#### 8.4.6 Provenance

Time, period, event, and timeline fields SHALL reference the synchronized anchor record. Collection membership and order SHALL use World Model construction provenance. No state provenance SHALL assert a tactical interpretation.

### 8.5 `Player` and `PlayerState`

#### 8.5.1 Purpose

`Player` defines immutable entity identity and team membership. `PlayerState` defines observation, visibility, and lifecycle at one WorldState.

#### 8.5.2 `Player` schema

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.player`. |
| `player_id` | `CanonicalId` | no | Immutable World Model player identity. |
| `identity_kind` | enum | no | `IDENTIFIED` or `OBSERVATION_SCOPED`. |
| `display_name` | string | yes | Canonical source display name; null for observation-scoped identity. |
| `team_id` | `CanonicalId` | no | Immutable membership reference. |
| `origin_observation_id` | `CanonicalId` | yes | Non-null only for `OBSERVATION_SCOPED`. |
| `world_provenance` | `ProvenanceMap` | no | Complete field provenance. |

#### 8.5.3 `PlayerState` schema

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.player_state`. |
| `player_id` | `CanonicalId` | no | Reference to one catalog Player. |
| `lifecycle` | enum | no | One lifecycle state from Section 8.12. |
| `visibility` | enum | no | `VISIBLE`, `NOT_VISIBLE`, or `UNKNOWN`. |
| `observation_ids` | array[`CanonicalId`] | no | All direct player observations in this WorldState. |
| `position_observation_ids` | array[`CanonicalId`] | no | Observation references containing direct positions. |
| `world_provenance` | `ProvenanceMap` | no | Complete field and collection provenance. |

Position is represented only through observations. `PlayerState` SHALL NOT contain a selected, averaged, interpolated, predicted, or preferred position.

Every WorldState SHALL contain a PlayerState for every catalog Player, including `UNKNOWN` and `TERMINATED` catalog entries. `TERMINATED` states remain in the catalog for deterministic lifecycle history and SHALL have empty observation-reference arrays.

#### 8.5.4 Required and nullable fields

All Player and PlayerState fields are required. `display_name` and `origin_observation_id` are the only nullable fields. For `IDENTIFIED`, `display_name` SHALL be non-null and `origin_observation_id` SHALL be null. For `OBSERVATION_SCOPED`, `display_name` SHALL be null and `origin_observation_id` SHALL be non-null.

#### 8.5.5 Identity rules

An identified player preserves the Chapter 6 `player_id` unchanged.

An unidentified non-actor freeze-frame observation SHALL produce exactly one observation-scoped Player:

```text
player_id = player:observation_scoped:<normalized observation_id>
origin_observation_id = observation:world:<normalized observation_id>
```

Observation-scoped identities SHALL NOT be compared or joined across observations. Equal position, team relation, goalkeeper flag, timestamp, source order, or later appearance SHALL NOT create shared identity.

A normalized freeze-frame observation with non-null `player_id` SHALL resolve to the identified Player with that exact ID. It SHALL NOT create an observation-scoped Player. A normalized freeze-frame observation with null `player_id` SHALL create the observation-scoped Player defined above and SHALL NOT resolve to any identified Player. These two branches are exhaustive.

#### 8.5.6 Team membership rules

An identified event actor SHALL belong to the event `team_id`. An identified pass recipient SHALL belong to the event `possession_team_id`. An identified player appearing in both roles SHALL have the same team ID or construction SHALL fail with `WORLD_ILLEGAL_TEAM_MEMBERSHIP`.

A pass-recipient reference creates catalog identity and membership only. It SHALL NOT create an Observation, set lifecycle to `OBSERVED`, establish visibility, or establish a position.

A teammate freeze-frame observation with identified actor identity SHALL use the actor's identified team. An observation-scoped teammate SHALL belong to the event possession team. An observation-scoped opponent SHALL belong to the single `UNIDENTIFIED_OPPONENT` Team defined in Section 8.7.

Every Player SHALL belong to exactly one Team. Team membership is immutable.

#### 8.5.7 Lifecycle and visibility

Player lifecycle SHALL follow Section 8.12. A player with at least one direct observation in the state is `OBSERVED`. An identified player previously observed but not directly observed is `MISSING`. An identified player before its first direct observation is `UNKNOWN`. An observation-scoped player is `UNKNOWN` before its origin state, `OBSERVED` in its origin state, and `TERMINATED` after it.

Visibility SHALL be `VISIBLE` when at least one current observation has `visibility=VISIBLE`. It SHALL be `UNKNOWN` otherwise. `NOT_VISIBLE` SHALL be emitted only from an explicit canonical negative-visibility observation. The v0.1 synchronized input contains no such observation; v0.1 construction therefore SHALL NOT emit `NOT_VISIBLE`.

#### 8.5.8 Invariants, failure, and provenance

Player IDs and membership SHALL be immutable. Every observation reference SHALL resolve and name the same player. Violations SHALL produce `WORLD_IDENTITY_COLLISION`, `WORLD_ILLEGAL_TEAM_MEMBERSHIP`, or `WORLD_RELATIONSHIP_INVALID`.

Identified values SHALL trace to synchronized normalized payloads. Observation-scoped identity SHALL trace to exactly one normalized observation. Lifecycle and visibility SHALL trace to ordered state observations and the transition table.

### 8.6 `Ball` and `BallState`

#### 8.6.1 Purpose

`Ball` defines the sole ball identity in the analysis scope. `BallState` represents direct event-location observation and ownership knowledge at one WorldState.

#### 8.6.2 Schemas

`Ball` contains exactly:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.ball`. |
| `ball_id` | `CanonicalId` | no | Sole ball identity. |
| `world_provenance` | `ProvenanceMap` | no | Identity provenance. |

`BallState` contains exactly:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.ball_state`. |
| `ball_id` | `CanonicalId` | no | Reference to the sole Ball. |
| `lifecycle` | enum | no | `OBSERVED` for every v0.1 state. |
| `visibility` | enum | no | Exact value `UNKNOWN`; event location does not assert camera visibility. |
| `ownership_status` | enum | no | Exact value `UNKNOWN`. |
| `owner_player_id` | `CanonicalId` | yes | Always null in v0.1. |
| `observation_id` | `CanonicalId` | no | Direct event-ball Observation. |
| `position_observation_id` | `CanonicalId` | no | Same value as `observation_id`. |
| `world_provenance` | `ProvenanceMap` | no | Complete field provenance. |

#### 8.6.3 Identity, lifecycle, and invariants

```text
ball_id = ball:<match_id>:analysis_scope:1
```

Exactly one Ball SHALL exist. It SHALL be referenced by every WorldState. Every synchronized event start position SHALL produce one direct ball observation. The World Model SHALL NOT infer control or ownership from an actor, event type, proximity, or possession metadata.

`owner_player_id` SHALL remain null and `ownership_status` SHALL remain `UNKNOWN`. A second ball identity SHALL produce `WORLD_DUPLICATE_BALL`. A missing event-ball observation SHALL produce `WORLD_MANDATORY_ENTITY_MISSING`.

Ball identity traces to the match and analysis scope. BallState position traces to the anchor event start-position fields. Ownership null traces to the prohibition on ownership inference.

### 8.7 `Team` and `TeamState`

#### 8.7.1 Purpose

`Team` represents immutable team identity. `TeamState` represents lifecycle and catalog membership at one WorldState. It SHALL NOT represent formation, shape, width, depth, compactness, lines, or organization.

#### 8.7.2 Schemas

`Team` contains exactly:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.team`. |
| `team_id` | `CanonicalId` | no | Immutable team identity. |
| `identity_kind` | enum | no | `IDENTIFIED` or `UNIDENTIFIED_OPPONENT`. |
| `display_name` | string | yes | Non-null for identified team; null otherwise. |
| `world_provenance` | `ProvenanceMap` | no | Complete field provenance. |

`TeamState` contains exactly:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.team_state`. |
| `team_id` | `CanonicalId` | no | Team reference. |
| `lifecycle` | enum | no | Lifecycle from Section 8.12. |
| `player_ids` | array[`CanonicalId`] | no | Every catalog Player belonging to this team. |
| `observed_player_ids` | array[`CanonicalId`] | no | Members with lifecycle `OBSERVED` in this state. |
| `world_provenance` | `ProvenanceMap` | no | Complete field and collection provenance. |

#### 8.7.3 Identity and membership

Identified team IDs and names SHALL be copied from normalized event payloads. Equal IDs with unequal names SHALL fail with `WORLD_IDENTITY_COLLISION`.

When at least one opponent freeze-frame observation lacks a canonical team ID, the catalog SHALL contain exactly one scoped team:

```text
team_id = team:unidentified_opponent:<possession_id>
identity_kind = UNIDENTIFIED_OPPONENT
display_name = null
```

This identity asserts only that its members are opponents relative to the possession team in this dataset. It SHALL NOT be joined to an identified team in this or another dataset.

#### 8.7.4 Lifecycle, invariants, failure, and provenance

A Team is `OBSERVED` when at least one member is observed in the state. After its first observed state, it is `MISSING` when no member is observed. Before its first observed state it is `UNKNOWN`. Team lifecycle never becomes `TERMINATED` in v0.1.

Every player ID SHALL occur in exactly one TeamState `player_ids` array. `observed_player_ids` SHALL be the ordered subset whose PlayerState lifecycle is `OBSERVED`. Illegal or duplicate membership SHALL produce `WORLD_ILLEGAL_TEAM_MEMBERSHIP`.

Identified team provenance traces to synchronized event metadata. The unidentified-opponent team traces to all opponent relation flags that require it. Membership traces to Section 8.5.6.

### 8.8 `Possession`

#### 8.8.1 Purpose and schema

`Possession` represents the immutable analysis scope selected upstream. It SHALL NOT infer event-level ball ownership.

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.possession`. |
| `possession_id` | `CanonicalId` | no | Copied canonical possession identity. |
| `possession_team_id` | `CanonicalId` | no | Unique possession-team identity shared by all anchor events. |
| `first_world_state_id` | `CanonicalId` | no | First state in ordered scope. |
| `last_world_state_id` | `CanonicalId` | no | Last state in ordered scope. |
| `lifecycle` | enum | no | Exact value `OBSERVED` for the represented scope. |
| `world_provenance` | `ProvenanceMap` | no | Complete field provenance. |

#### 8.8.2 Identity, lifecycle, invariants, failure, and provenance

The possession ID SHALL remain unchanged from synchronized input. Every anchor event SHALL reference the same normalized possession ID and possession-team ID. A disagreement SHALL produce `WORLD_POSSESSION_INCONSISTENT`.

The possession is observed throughout the finite analysis scope. Dataset exhaustion SHALL NOT create a football termination assertion; lifecycle SHALL remain `OBSERVED`.

The possession and its team trace to every anchor event. First and last state references trace to ordered WorldState construction.

### 8.9 `Pitch`

#### 8.9.1 Purpose and schema

`Pitch` defines the canonical spatial domain. It SHALL NOT contain zones, channels, dangerous areas, passing lanes, tactical regions, or calculated space.

| Field | Type | Nullable | Units | Meaning |
| --- | --- | --- | --- | --- |
| `schema_id` | string | no | — | Exact value `tip.pitch`. |
| `pitch_id` | `CanonicalId` | no | — | Sole pitch identity. |
| `length_m` | number | no | metres | Exact value `105`. |
| `width_m` | number | no | metres | Exact value `68`. |
| `origin` | enum | no | — | Exact value `OWN_GOAL_LOWER_TOUCHLINE`. |
| `positive_x` | enum | no | — | Exact value `TOWARD_OPPONENT_GOAL`. |
| `positive_y` | enum | no | — | Exact value `TOWARD_UPPER_TOUCHLINE`. |
| `lifecycle` | enum | no | — | Exact value `OBSERVED`. |
| `world_provenance` | `ProvenanceMap` | no | — | Specification-constant provenance. |

#### 8.9.2 Identity, lifecycle, invariants, failure, and provenance

```text
pitch_id = pitch:<match_id>:canonical:105x68
```

Exactly one Pitch SHALL exist and every WorldState SHALL reference it. Every Observation position SHALL be inside inclusive bounds `0<=x_m<=105`, `0<=y_m<=68`, and non-negative `z_m` when non-null. An out-of-bounds value SHALL produce `WORLD_SPATIAL_VALUE_INVALID`; it SHALL NOT be clamped.

Pitch fields derive only from the canonical coordinate contract in Section 6.7 and SHALL use constant provenance.

### 8.10 `Observation`, visibility, and factual relationships

#### 8.10.1 `Observation` purpose and schema

An Observation records one direct canonical assertion assigned to one WorldState. It SHALL NOT merge source assertions.

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.world_observation`. |
| `observation_id` | `CanonicalId` | no | Deterministic observation identity. |
| `world_state_id` | `CanonicalId` | no | Owning state. |
| `subject_kind` | enum | no | `PLAYER` or `BALL`. |
| `subject_id` | `CanonicalId` | no | Player or Ball reference. |
| `observation_kind` | enum | no | `EVENT_ACTOR`, `EVENT_BALL`, or `FREEZE_FRAME`. |
| `position` | `CanonicalPosition` | no | Direct canonical position. |
| `visibility` | enum | no | `VISIBLE` or `UNKNOWN`. |
| `anchor_event_id` | `CanonicalId` | no | State anchor event. |
| `source_timeline_index` | integer | no | Event or attachment timeline index. |
| `normalized_observation_id` | `CanonicalId` | yes | Non-null only for `FREEZE_FRAME`. |
| `world_provenance` | `ProvenanceMap` | no | Complete field provenance. |

Event observation identities are:

```text
observation:world:<event_id>:actor
observation:world:<event_id>:ball
```

Freeze-frame observation identity is:

```text
observation:world:<normalized observation_id>
```

An event actor observation uses event `start_position`, visibility `UNKNOWN`, and the event timeline index. An event ball observation uses the same direct event start position, visibility `UNKNOWN`, and event timeline index. Each normalized freeze-frame observation produces one World Observation with unchanged position, visibility `VISIBLE`, and the attachment timeline index.

The event actor and ball sharing a source position SHALL remain two observations because they assert positions of different subjects. An actor freeze-frame position differing from its event actor position SHALL remain a second observation of the same player.

#### 8.10.2 Visibility

Visibility is epistemic state, not geometry. `VISIBLE` requires direct inclusion in a normalized freeze frame. `NOT_VISIBLE` requires an explicit canonical negative observation. `UNKNOWN` means neither assertion exists. Polygon membership SHALL NOT determine entity visibility.

#### 8.10.3 `Relationship` schema

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.world_relationship`. |
| `relationship_id` | `CanonicalId` | no | Deterministic relationship identity. |
| `world_state_id` | `CanonicalId` | no | State in which relation is asserted. |
| `relationship_type` | enum | no | One exact type below. |
| `subject_id` | `CanonicalId` | no | Relationship subject. |
| `object_id` | `CanonicalId` | yes | Relationship object where applicable. |
| `observation_id` | `CanonicalId` | yes | Supporting observation where applicable. |
| `world_provenance` | `ProvenanceMap` | no | Complete field provenance. |

Only these relationship types are permitted:

| Type | Subject | Object | Observation | Meaning |
| --- | --- | --- | --- | --- |
| `PLAYER_MEMBER_OF_TEAM` | Player | Team | null | Immutable catalog membership. |
| `POSSESSION_ASSIGNED_TO_TEAM` | Possession | Team | null | Upstream possession-team fact. |
| `ENTITY_OBSERVED_AT` | Player or Ball | null | required | Subject has the observation position. |
| `ENTITY_VISIBLE` | Player | null | required | Supporting freeze-frame observation asserts visibility. |
| `BALL_OWNERSHIP_UNKNOWN` | Ball | null | null | No ownership fact is asserted. |
| `TEMPORALLY_FOLLOWS` | current WorldState | previous WorldState | null | Immediate state succession. |
| `SAME_SYNCHRONIZED_INSTANT` | Observation | anchor event | required | Observation belongs to the anchor instant. |

Relationship identity SHALL be:

```text
relationship:<world_state_id>:<relationship_type lowercase>:<subject_id>:<object-or-observation suffix>
```

The suffix SHALL be `none` when both object and observation are null, the object ID when object is non-null, and the observation ID when observation is non-null. A relationship type not listed above SHALL produce `WORLD_RELATIONSHIP_INVALID`.

Spatial relationships are limited to `ENTITY_OBSERVED_AT`. Temporal relationships are limited to `TEMPORALLY_FOLLOWS` and `SAME_SYNCHRONIZED_INSTANT`. Distance, adjacency, reachability, pressure, lane, line, zone, superiority, occupation, freedom, danger, and tactical relationships are forbidden.

The v0.1 World Model SHALL NOT construct a discrete `Space` entity. Spatial state consists exactly of the Pitch, direct Observation positions, and `ENTITY_OBSERVED_AT` relationships. Any subdivision or calculated characterization of the Pitch belongs downstream.

Each WorldState SHALL contain exactly these relationship instances:

1. one `PLAYER_MEMBER_OF_TEAM` for every catalog Player;
2. one `POSSESSION_ASSIGNED_TO_TEAM` for the dataset Possession;
3. one `ENTITY_OBSERVED_AT` for every Observation;
4. one `ENTITY_VISIBLE` for every Observation whose `subject_kind=PLAYER` and `visibility=VISIBLE`;
5. one `BALL_OWNERSHIP_UNKNOWN` for the sole Ball;
6. one `TEMPORALLY_FOLLOWS` when `world_state_index>0`, referencing the immediately preceding WorldState, and none for index zero;
7. one `SAME_SYNCHRONIZED_INSTANT` for every Observation.

No other Relationship SHALL be emitted. Multiple observations of one subject SHALL produce separate `ENTITY_OBSERVED_AT` and `SAME_SYNCHRONIZED_INSTANT` relationships. Multiple visible observations of one player SHALL produce separate `ENTITY_VISIBLE` relationships.

#### 8.10.4 Invariants, failure, and provenance

Every Observation SHALL resolve to one state and one subject. Every Relationship SHALL resolve its required references in the same dataset. Observation IDs and relationship IDs SHALL be unique. Violations SHALL produce `WORLD_OBSERVATION_INVALID` or `WORLD_RELATIONSHIP_INVALID`.

Observation provenance traces to exact synchronized payload positions and timeline records. Relationship provenance traces only to the facts used by its declared type.

### 8.11 Entity identity

Entity identity is deterministic, immutable, case-sensitive, and scope-explicit.

| Entity | Identity source |
| --- | --- |
| WorldState | Possession scope plus anchor event |
| identified Player | Canonical normalized player ID |
| observation-scoped Player | One normalized freeze-frame observation ID |
| identified Team | Canonical normalized team ID |
| unidentified opponent Team | Possession scope |
| Ball | Match plus analysis-scope singleton |
| Possession | Canonical synchronized possession ID |
| Pitch | Match plus canonical pitch contract |
| Observation | Anchor event role or normalized observation ID |
| Relationship | State, type, subject, and applicable object or observation |

- **TIP-WORLD-ID-001:** Identity SHALL NOT depend on coordinate equality, temporal proximity, names alone, array memory identity, hash-map order, process ID, random value, or heuristic matching.
- **TIP-WORLD-ID-002:** An entity identifier SHALL NOT change between WorldStates.
- **TIP-WORLD-ID-003:** One identifier SHALL resolve to one immutable entity definition.
- **TIP-WORLD-ID-004:** Equal display names SHALL NOT imply equal identity.
- **TIP-WORLD-ID-005:** An observation-scoped identity SHALL terminate after its source state and SHALL NOT be reused.

Identity construction SHALL occur before state construction. A collision or conflicting immutable definition SHALL produce `WORLD_IDENTITY_COLLISION`.

### 8.12 Entity lifecycle

#### 8.12.1 States

The canonical lifecycle enum contains exactly:

| State | Meaning |
| --- | --- |
| `UNKNOWN` | Entity is cataloged but has not yet received a direct observation in this dataset. |
| `OBSERVED` | Entity has at least one direct observation in the current WorldState, or is a scope entity explicitly present by contract. |
| `MISSING` | Identified entity was observed in an earlier WorldState and has no direct observation in the current state. |
| `TERMINATED` | Observation-scoped entity's sole valid observation instant has passed. |

`MISSING` does not mean invisible, absent from the pitch, substituted, dismissed, injured, or outside the frame. `TERMINATED` applies only to observation-scoped Player identities in v0.1.

#### 8.12.2 Transition table

Only these transitions are legal:

| Previous | Current | Condition |
| --- | --- | --- |
| start | `UNKNOWN` | Catalog entity has no observation in first state. |
| start | `OBSERVED` | Entity is directly observed or contract-observed in first state. |
| `UNKNOWN` | `UNKNOWN` | No direct observation. |
| `UNKNOWN` | `OBSERVED` | First direct observation occurs. |
| `OBSERVED` | `OBSERVED` | Direct observation exists in next state. |
| `OBSERVED` | `MISSING` | Identified entity lacks direct observation in next state. |
| `OBSERVED` | `TERMINATED` | Observation-scoped Player advances beyond origin state. |
| `MISSING` | `MISSING` | Identified entity remains unobserved. |
| `MISSING` | `OBSERVED` | Identified entity is directly observed again. |
| `TERMINATED` | `TERMINATED` | Later state retains terminated catalog status. |

Every transition not listed is illegal and SHALL produce `WORLD_ILLEGAL_LIFECYCLE_TRANSITION`.

Ball, Pitch, and Possession lifecycle SHALL be `OBSERVED` in every state or entity record where declared. Identified Teams and Players follow observation transitions. Observation-scoped Players follow `UNKNOWN -> OBSERVED -> TERMINATED` according to state position.

The lifecycle applicability matrix is exact:

| Entity kind | Permitted lifecycle values |
| --- | --- |
| Pitch | `OBSERVED` only |
| Possession | `OBSERVED` only |
| Ball | `OBSERVED` only |
| identified Team | `UNKNOWN`, `OBSERVED`, `MISSING` |
| unidentified-opponent Team | `UNKNOWN`, `OBSERVED`, `MISSING` |
| identified Player | `UNKNOWN`, `OBSERVED`, `MISSING` |
| observation-scoped Player | `UNKNOWN`, `OBSERVED`, `TERMINATED` |

An entity kind using a lifecycle value outside this matrix SHALL produce `WORLD_ILLEGAL_LIFECYCLE_TRANSITION`.

### 8.13 World Model provenance

World Model provenance SHALL use the structures in Section 6.4.8 and source paths of form `synchronized_dataset#<JSON Pointer>`. Input provenance is opaque and SHALL NOT be used as a construction source.

Only these class and operation pairs are permitted:

| Class | Operation | Meaning |
| --- | --- | --- |
| `COPIED` | `COPY_SYNCHRONIZED` | Canonical synchronized value is unchanged. |
| `WRAPPED_IDENTIFIER` | `WORLD_BUILD_ID` | World entity or relation identity follows this chapter. |
| `DERIVED_DETERMINISTICALLY` | `WORLD_BUILD_COLLECTION` | Collection membership and order follow this chapter. |
| `DERIVED_DETERMINISTICALLY` | `WORLD_ASSIGN_STATE_INDEX` | WorldState order follows event-record order. |
| `DERIVED_DETERMINISTICALLY` | `WORLD_LIFECYCLE_TRANSITION` | Lifecycle follows Section 8.12. |
| `DERIVED_DETERMINISTICALLY` | `WORLD_VISIBILITY_STATE` | Visibility follows direct observations. |
| `DERIVED_DETERMINISTICALLY` | `WORLD_TEAM_MEMBERSHIP` | Membership follows Section 8.5.6. |
| `DERIVED_DETERMINISTICALLY` | `WORLD_CREATE_OBSERVATION` | Observation follows one synchronized assertion. |
| `DERIVED_DETERMINISTICALLY` | `WORLD_CREATE_RELATIONSHIP` | Relationship follows Section 8.10.3. |
| `DERIVED_DETERMINISTICALLY` | `WORLD_UNKNOWN_OWNERSHIP` | Ownership remains unasserted under Section 8.6. |
| `CONSTANT` | `WORLD_SET_CONSTANT` | Specification constant with an empty source list. |
| `SOURCE_UNIDENTIFIED` | `WORLD_SET_NULL_UNIDENTIFIED` | Canonical input supplies no identity. |
| `NOT_APPLICABLE` | `WORLD_SET_NULL_NOT_APPLICABLE` | Field does not apply under its entity schema. |

Every World Model-owned scalar, null, and array field SHALL have exactly one provenance entry. Object-valued fields carry their own maps. Collection paths SHALL describe membership and order; indexed scalar elements SHALL have indexed provenance entries. Provenance entries SHALL be ordered under Section 6.4.8.

- **TIP-WORLD-PROV-001:** Every source path SHALL resolve in the authenticated SynchronizedDataset.
- **TIP-WORLD-PROV-002:** Every construction dependency SHALL be listed; unrelated sources are forbidden.
- **TIP-WORLD-PROV-003:** No provenance value SHALL contain confidence, tactical interpretation, implementation detail, or heuristic rationale.
- **TIP-WORLD-PROV-004:** Changing opaque provider provenance without changing synchronized facts SHALL NOT change World Model fields other than the exact copied `input_provenance` value and resulting artifact digest.

### 8.14 Construction algorithm and deterministic ordering

The World Model stage SHALL execute exactly these steps and stop at the first failure:

1. authenticate the SynchronizedDataset, media type, contract version, and digest;
2. validate every Chapter 7 schema and invariant;
3. select synchronized `EVENT` records in timeline order and validate optional adjacent attachments;
4. construct the Pitch, Possession, and sole Ball identities;
5. scan immutable event payloads for identified teams, actors, and pass recipients;
6. scan freeze-frame payloads for observation-scoped players and the requirement for an unidentified-opponent Team;
7. construct immutable Team and Player catalogs and reject collisions or membership conflicts;
8. construct one WorldState per event record in event timeline order;
9. create event actor, event ball, and attached freeze-frame observations for the state;
10. determine lifecycle and visibility from the ordered observation history and Section 8.12;
11. construct BallState, TeamStates, and PlayerStates;
12. construct every required factual relationship in Section 8.10.3;
13. construct World Model provenance;
14. validate every invariant in Section 8.15;
15. canonicalize under Section 2.3 and emit the artifact and digest.

Ordering SHALL be:

| Collection | Total order |
| --- | --- |
| `teams` | `team_id` ascending by Unicode code point |
| `players` | `player_id` ascending by Unicode code point |
| `world_states` | `world_state_index` ascending |
| `team_states` | referenced `team_id` ascending |
| `player_states` | referenced `player_id` ascending |
| `observations` | `source_timeline_index`, then observation-kind rank, then `observation_id` |
| `relationships` | relationship type, subject ID, null-first object ID, null-first observation ID, relationship ID |
| `player_ids`, `observed_player_ids`, observation-reference arrays | identifier ascending by Unicode code point |

Observation-kind rank SHALL be `EVENT_BALL=0`, `EVENT_ACTOR=1`, `FREEZE_FRAME=2`.

No input object order, hash-map order, locale, thread schedule, memory address, or random state SHALL affect output ordering.

### 8.15 World invariants

- **TIP-WORLD-010:** Every WorldState represents exactly one synchronized event instant.
- **TIP-WORLD-011:** WorldState timestamps and indices are immutable and strictly traceable to synchronized records.
- **TIP-WORLD-012:** Exactly one Ball, one Pitch, and one Possession exist in the dataset.
- **TIP-WORLD-013:** Every Player belongs to exactly one Team.
- **TIP-WORLD-014:** Every WorldState contains exactly one state entry for every catalog Player and Team.
- **TIP-WORLD-015:** Entity identifiers and immutable definitions never change.
- **TIP-WORLD-016:** Every lifecycle transition is listed in Section 8.12.2.
- **TIP-WORLD-017:** Every Observation maps to exactly one synchronized factual assertion and one WorldState.
- **TIP-WORLD-018:** Every relationship is one permitted factual relation and has valid cardinality.
- **TIP-WORLD-019:** Ball ownership remains unknown in v0.1.
- **TIP-WORLD-020:** Conflicting direct positions remain separate observations.
- **TIP-WORLD-021:** No observation-scoped Player identity crosses its origin instant.
- **TIP-WORLD-022:** Every position remains inside canonical Pitch bounds.
- **TIP-WORLD-023:** Output contains no velocity, acceleration, tracking, confidence, inferred intent, calculated space, tactical feature, tactical concept, hypothesis, explanation, or rendering instruction.
- **TIP-WORLD-024:** Repeated construction from identical canonical synchronized bytes produces identical canonical World Model bytes.

### 8.16 Default parameters

The World Model has no configuration surface and no default parameters. Identity grammars, singleton counts, lifecycle states, transitions, ordering, visibility rules, observation construction, membership, relationship vocabulary, pitch definition, and null behavior are fixed contract values.

An override request during conformance execution SHALL fail with `WORLD_INPUT_ARTIFACT_INVALID`.

### 8.17 Failure behavior

World Model errors SHALL use stage `world_model`, execution status `PROCESSING_ERROR`, and an empty successful-artifacts array. Partial world artifacts SHALL NOT be emitted.

| Code | Condition |
| --- | --- |
| `WORLD_INPUT_ARTIFACT_INVALID` | Input is not an authenticated successful SynchronizedDataset or requests an override. |
| `WORLD_INPUT_VERSION_UNSUPPORTED` | SynchronizedDataset contract version is not `0.1.0`. |
| `WORLD_INPUT_SCHEMA_INVALID` | Input violates a Chapter 7 schema or non-World invariant. |
| `WORLD_IDENTITY_INVALID` | Canonical input identity cannot be used under Section 8.11. |
| `WORLD_IDENTITY_COLLISION` | One identifier resolves to conflicting entity definitions or two constructed entities collide. |
| `WORLD_DUPLICATE_BALL` | More than one Ball is constructed or referenced. |
| `WORLD_MANDATORY_ENTITY_MISSING` | Ball, Pitch, Possession, required Team, required Player, anchor, or direct event observation is missing. |
| `WORLD_DUPLICATE_ENTITY_STATE` | A WorldState contains duplicate state entries for one entity. |
| `WORLD_ILLEGAL_TEAM_MEMBERSHIP` | Player has zero, multiple, or conflicting team memberships. |
| `WORLD_ILLEGAL_LIFECYCLE_TRANSITION` | Lifecycle transition is absent from Section 8.12.2. |
| `WORLD_TIMESTAMP_INCONSISTENT` | WorldState time, period, order, anchor, or attachment disagrees with synchronization. |
| `WORLD_POSSESSION_INCONSISTENT` | Possession identity or possession-team identity differs across anchor events. |
| `WORLD_OBSERVATION_INVALID` | Observation identity, subject, source, position, visibility, or cardinality is invalid. |
| `WORLD_RELATIONSHIP_INVALID` | Relationship type, identity, reference, cardinality, or evidence is invalid. |
| `WORLD_SPATIAL_VALUE_INVALID` | Position is non-finite or outside Pitch bounds. |
| `WORLD_PROVENANCE_INCOMPLETE` | Input provenance is altered or World provenance is incomplete, extra, unresolved, or misordered. |
| `WORLD_INVARIANT_VIOLATION` | Any remaining Section 8.15 invariant fails. |
| `WORLD_SERIALIZATION_FAILED` | Canonical JSON serialization fails. |

Errors SHALL be selected by construction-algorithm step, world-state index, entity-kind rank, entity identifier, observation identifier, relationship identifier, JSON Pointer, and error code, in that order. String keys use Unicode code-point order and unavailable keys sort first.

Entity-kind rank SHALL be `PITCH=0`, `POSSESSION=1`, `BALL=2`, `TEAM=3`, `PLAYER=4`, `OBSERVATION=5`, `RELATIONSHIP=6`, `WORLD_STATE=7`.

Error references SHALL use `synchronized_dataset#<JSON Pointer>`. World construction SHALL NOT emit `SRC_*`, `NORM_*`, or `SYNC_*` codes.

### 8.18 Worked example

The synchronized instant contains one event actor and one attached freeze-frame observation of that actor at a slightly different direct position. The required WorldState preserves both observations.

```json
{
  "schema_id": "tip.world_state",
  "world_state_id": "world_state:match:statsbomb:3788754:40:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
  "world_state_index": 0,
  "anchor_timeline_index": 0,
  "canonical_time_seconds": 1464.046,
  "period_id": "match:statsbomb:3788754:period:1",
  "period_number": 1,
  "period_time_seconds": 1464.046,
  "anchor_event_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
  "pitch_id": "pitch:match:statsbomb:3788754:canonical:105x68",
  "possession_id": "match:statsbomb:3788754:possession:40",
  "ball_state": {
    "schema_id": "tip.ball_state",
    "ball_id": "ball:match:statsbomb:3788754:analysis_scope:1",
    "lifecycle": "OBSERVED",
    "visibility": "UNKNOWN",
    "ownership_status": "UNKNOWN",
    "owner_player_id": null,
    "observation_id": "observation:world:event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:ball",
    "position_observation_id": "observation:world:event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:ball",
    "world_provenance": {
      "/owner_player_id": {"class": "CONSTANT", "operation": "WORLD_SET_CONSTANT", "sources": []}
    }
  },
  "team_states": [
    {
      "schema_id": "tip.team_state",
      "team_id": "team:statsbomb:914",
      "lifecycle": "OBSERVED",
      "player_ids": ["player:statsbomb:7036"],
      "observed_player_ids": ["player:statsbomb:7036"],
      "world_provenance": {
        "/lifecycle": {"class": "DERIVED_DETERMINISTICALLY", "operation": "WORLD_LIFECYCLE_TRANSITION", "sources": [{"source_record_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "synchronized_dataset#/timeline/0/event_id"}]}
      }
    }
  ],
  "player_states": [
    {
      "schema_id": "tip.player_state",
      "player_id": "player:statsbomb:7036",
      "lifecycle": "OBSERVED",
      "visibility": "VISIBLE",
      "observation_ids": [
        "observation:world:event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:actor",
        "observation:world:event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:freeze_frame:statsbomb360:observation:0"
      ],
      "position_observation_ids": [
        "observation:world:event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:actor",
        "observation:world:event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:freeze_frame:statsbomb360:observation:0"
      ],
      "world_provenance": {
        "/lifecycle": {"class": "DERIVED_DETERMINISTICALLY", "operation": "WORLD_LIFECYCLE_TRANSITION", "sources": [{"source_record_id": "player:statsbomb:7036", "source_path": "synchronized_dataset#/timeline/0/normalized_event/actor_player_id"}]},
        "/visibility": {"class": "DERIVED_DETERMINISTICALLY", "operation": "WORLD_VISIBILITY_STATE", "sources": [{"source_record_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:freeze_frame:statsbomb360:observation:0", "source_path": "synchronized_dataset#/timeline/1/normalized_freeze_frame/observations/0/visible"}]}
      }
    }
  ],
  "observations": [
    {
      "schema_id": "tip.world_observation",
      "observation_id": "observation:world:event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:ball",
      "world_state_id": "world_state:match:statsbomb:3788754:40:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
      "subject_kind": "BALL",
      "subject_id": "ball:match:statsbomb:3788754:analysis_scope:1",
      "observation_kind": "EVENT_BALL",
      "position": {"x_m": 8.3125, "y_m": 48.62, "z_m": null},
      "visibility": "UNKNOWN",
      "anchor_event_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
      "source_timeline_index": 0,
      "normalized_observation_id": null,
      "world_provenance": {
        "/position/x_m": {"class": "COPIED", "operation": "COPY_SYNCHRONIZED", "sources": [{"source_record_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "synchronized_dataset#/timeline/0/normalized_event/start_position/x_m"}]}
      }
    },
    {
      "schema_id": "tip.world_observation",
      "observation_id": "observation:world:event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:actor",
      "world_state_id": "world_state:match:statsbomb:3788754:40:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
      "subject_kind": "PLAYER",
      "subject_id": "player:statsbomb:7036",
      "observation_kind": "EVENT_ACTOR",
      "position": {"x_m": 8.3125, "y_m": 48.62, "z_m": null},
      "visibility": "UNKNOWN",
      "anchor_event_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
      "source_timeline_index": 0,
      "normalized_observation_id": null,
      "world_provenance": {
        "/position/x_m": {"class": "COPIED", "operation": "COPY_SYNCHRONIZED", "sources": [{"source_record_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "synchronized_dataset#/timeline/0/normalized_event/start_position/x_m"}]}
      }
    },
    {
      "schema_id": "tip.world_observation",
      "observation_id": "observation:world:event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:freeze_frame:statsbomb360:observation:0",
      "world_state_id": "world_state:match:statsbomb:3788754:40:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
      "subject_kind": "PLAYER",
      "subject_id": "player:statsbomb:7036",
      "observation_kind": "FREEZE_FRAME",
      "position": {"x_m": 8.3125, "y_m": 48.620001, "z_m": null},
      "visibility": "VISIBLE",
      "anchor_event_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
      "source_timeline_index": 1,
      "normalized_observation_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:freeze_frame:statsbomb360:observation:0",
      "world_provenance": {
        "/position/x_m": {"class": "COPIED", "operation": "COPY_SYNCHRONIZED", "sources": [{"source_record_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:freeze_frame:statsbomb360:observation:0", "source_path": "synchronized_dataset#/timeline/1/normalized_freeze_frame/observations/0/position/x_m"}]}
      }
    }
  ],
  "relationships": [
    {
      "schema_id": "tip.world_relationship",
      "relationship_id": "relationship:world_state:match:statsbomb:3788754:40:f3761d40-7236-4128-9ce5-a6e84d2e0dc8:player_member_of_team:player:statsbomb:7036:team:statsbomb:914",
      "world_state_id": "world_state:match:statsbomb:3788754:40:f3761d40-7236-4128-9ce5-a6e84d2e0dc8",
      "relationship_type": "PLAYER_MEMBER_OF_TEAM",
      "subject_id": "player:statsbomb:7036",
      "object_id": "team:statsbomb:914",
      "observation_id": null,
      "world_provenance": {
        "/object_id": {"class": "DERIVED_DETERMINISTICALLY", "operation": "WORLD_TEAM_MEMBERSHIP", "sources": [{"source_record_id": "player:statsbomb:7036", "source_path": "synchronized_dataset#/timeline/0/normalized_event/team_id"}]}
      }
    }
  ],
  "world_provenance": {
    "/canonical_time_seconds": {"class": "COPIED", "operation": "COPY_SYNCHRONIZED", "sources": [{"source_record_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "synchronized_dataset#/timeline/0/canonical_time_seconds"}]},
    "/world_state_index": {"class": "DERIVED_DETERMINISTICALLY", "operation": "WORLD_ASSIGN_STATE_INDEX", "sources": [{"source_record_id": "event:statsbomb:f3761d40-7236-4128-9ce5-a6e84d2e0dc8", "source_path": "synchronized_dataset#/timeline/0/timeline_index"}]}
  }
}
```

The complete conformance artifact SHALL include all catalog entities, all required factual relationships, and one provenance entry for every owned field. The worked state demonstrates the required preservation of unequal direct actor positions and SHALL NOT be interpreted as a schema-valid replacement for the complete dataset artifact.

### 8.19 Conformance tests

Every test is normative and SHALL use a machine-readable fixture or JSON Patch.

| Test ID | Input or mutation | Required assertion |
| --- | --- | --- |
| **TIP-WORLD-C001** | Untouched Locatelli SynchronizedDataset | Canonical WorldModelDataset hash equals golden hash. |
| **TIP-WORLD-C002** | Untouched Depay SynchronizedDataset | Canonical WorldModelDataset hash equals golden hash. |
| **TIP-WORLD-C003** | Repeat construction in fresh processes | All identities and canonical bytes are identical. |
| **TIP-WORLD-C004** | Two events with equal canonical time | Two ordered WorldStates with equal time and distinct indices. |
| **TIP-WORLD-C005** | Identified player observed, absent, then observed | Lifecycle is `OBSERVED`, `MISSING`, `OBSERVED`. |
| **TIP-WORLD-C006** | Observation-scoped player across three states | Lifecycle is `UNKNOWN`, `OBSERVED`, `TERMINATED`. |
| **TIP-WORLD-C007** | Attempt `TERMINATED` to `OBSERVED` | `WORLD_ILLEGAL_LIFECYCLE_TRANSITION`. |
| **TIP-WORLD-C008** | Two catalog Ball identities | `WORLD_DUPLICATE_BALL`. |
| **TIP-WORLD-C009** | Player assigned to two teams | `WORLD_ILLEGAL_TEAM_MEMBERSHIP`. |
| **TIP-WORLD-C010** | Equal player ID with unequal names | `WORLD_IDENTITY_COLLISION`. |
| **TIP-WORLD-C011** | Non-actor observations at equal positions | Distinct observation-scoped Player identities. |
| **TIP-WORLD-C012** | Actor event and frame positions differ | Both direct Observations remain unchanged. |
| **TIP-WORLD-C013** | Event without attached frame | Actor and ball observations exist; no freeze-frame observations. |
| **TIP-WORLD-C014** | Opponent anonymous observation | Membership uses one scoped unidentified-opponent Team. |
| **TIP-WORLD-C015** | Ball ownership field set from event actor | World invariant validation fails. |
| **TIP-WORLD-C016** | Observation outside Pitch bounds | `WORLD_SPATIAL_VALUE_INVALID`. |
| **TIP-WORLD-C017** | WorldState timestamp changed from anchor | `WORLD_TIMESTAMP_INCONSISTENT`. |
| **TIP-WORLD-C018** | Relationship uses unknown subject | `WORLD_RELATIONSHIP_INVALID`. |
| **TIP-WORLD-C019** | Add tactical relationship type | `WORLD_RELATIONSHIP_INVALID`. |
| **TIP-WORLD-C020** | Shuffle internal catalog construction | Catalog, state, observation, relationship, and output order remain unchanged. |
| **TIP-WORLD-C021** | Remove mandatory PlayerState | `WORLD_MANDATORY_ENTITY_MISSING`. |
| **TIP-WORLD-C022** | Duplicate PlayerState in one state | `WORLD_DUPLICATE_ENTITY_STATE`. |
| **TIP-WORLD-C023** | Delete World provenance entry | `WORLD_PROVENANCE_INCOMPLETE`. |
| **TIP-WORLD-C024** | Modify copied input provenance | `WORLD_PROVENANCE_INCOMPLETE`. |
| **TIP-WORLD-C025** | Multiple simultaneous defects | Error selection follows Section 8.17. |
| **TIP-WORLD-C026** | Canonical serialization of golden World Model | Bytes and SHA-256 equal published golden artifact. |
| **TIP-WORLD-C027** | Instrument World Model input access | Only SynchronizedDataset canonical records are read. |
| **TIP-WORLD-C028** | Scan output schema and controlled enums | No forbidden field or tactical concept occurs. |

### 8.20 World Model Boundary

Downstream Perception SHALL consume only `WorldModelDataset` and SHALL NOT bypass WorldStates to reinterpret synchronized or normalized payloads.

- **TIP-WORLD-BOUND-001:** Perception SHALL treat entity identities, lifecycle, observations, visibility, membership, positions, factual relationships, state time, and state order as immutable World Model facts.
- **TIP-WORLD-BOUND-002:** Perception MAY calculate objective features from World Model facts. Such features SHALL NOT be written back into the World Model.
- **TIP-WORLD-BOUND-003:** A downstream stage SHALL NOT add an entity, repair an identity, rewrite lifecycle, select a preferred source position, or change a WorldState.
- **TIP-WORLD-BOUND-004:** Tactical concepts SHALL first appear only in Recognition or later chapters; they are forbidden in World Model artifacts.

## 9. Perception Layer

> **Editorial status:** Normative in Working Draft 0.1.0.

### 9.1 Purpose

Perception transforms one canonical `WorldModelDataset` into one deterministic `PerceptionDataset`. Perception derives objective measurable properties only. Semantic interpretation SHALL occur only in Recognition or later.

Perception answers only which canonical facts and measurements exist. It SHALL NOT determine danger, intelligence, desirability, causation, intent, tactical meaning, opportunity, or recommended action.

Perception SHALL NOT perform football reasoning, recognize tactical concepts, infer intent, explain events, generate hypotheses, modify World Model facts, interpolate missing positions, infer identity continuity, or feed a derived result back into the World Model.

- **TIP-PER-001:** Every available feature value SHALL follow one exact definition in Section 9.9.
- **TIP-PER-002:** Insufficient objective input SHALL produce an unavailable feature record; it SHALL NOT produce an estimate.
- **TIP-PER-003:** A feature name, value, description, or status SHALL NOT encode a tactical label.

### 9.2 Input

The sole input is a successful `WorldModelDataset` artifact produced by Chapter 8 with:

| Property | Required value |
| --- | --- |
| Media type | `application/vnd.tip.world-model+json` |
| `schema_id` | `tip.world_model_dataset` |
| `contract_version` | `0.1.0` |
| Integrity | Canonical bytes match the authenticated SHA-256 digest |

Perception SHALL consume only canonical WorldStates, entity catalogs, Observations, lifecycle, visibility, membership, Pitch, and factual World relationships. It SHALL NOT access `SynchronizedDataset`, `NormalizedDataset`, `SourceSelection`, raw provider data, or provider-specific provenance content.

The input SHALL be immutable and SHALL satisfy every Chapter 8 schema and invariant.

### 9.3 Output

Successful perception SHALL emit exactly one `PerceptionDataset` artifact with media type `application/vnd.tip.perception-dataset+json`, `schema_id="tip.perception_dataset"`, and `contract_version="0.1.0"`.

The output SHALL contain exactly the schemas and controlled values defined in this chapter. Every field SHALL be present. Nullable fields SHALL contain their declared type or JSON `null`; omission is forbidden. Every schema has `additionalProperties=false`.

The artifact SHALL be canonicalized under Section 2.3 and emitted with its lowercase SHA-256 digest.

### 9.4 Canonical feature model

#### 9.4.1 `PerceptionDataset`

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.perception_dataset`. |
| `contract_version` | string | no | Exact value `0.1.0`. |
| `input_contract_version` | string | no | Exact value `0.1.0`. |
| `world_model_sha256` | string | no | Lowercase SHA-256 of canonical input bytes. |
| `match_id` | `CanonicalId` | no | Copied World Model match identity. |
| `possession_id` | `CanonicalId` | no | Copied World Model possession identity. |
| `feature_definitions` | array[`FeatureDefinition`] | no | Exact feature catalog from Section 9.9. |
| `frames` | array[`PerceptionFrame`] | no | One frame per WorldState. |
| `input_provenance` | `PerceptionInputProvenance` | no | Exact copied World Model input and world provenance, treated as opaque. |
| `perception_provenance` | `ProvenanceMap` | no | Provenance for dataset-owned fields and collections. |

`feature_definitions` and `frames` SHALL be non-empty.

`PerceptionInputProvenance` contains exactly:

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `input_provenance` | `InputProvenanceBundle` | no | Exact `WorldModelDataset.input_provenance`. |
| `world_provenance` | `ProvenanceMap` | no | Exact `WorldModelDataset.world_provenance`. |

#### 9.4.2 `PerceptionFrame`

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.perception_frame`. |
| `perception_frame_id` | `CanonicalId` | no | Deterministic frame identity. |
| `world_state_id` | `CanonicalId` | no | Originating WorldState. |
| `world_state_index` | integer | no | Exact WorldState index. |
| `canonical_time_seconds` | `Seconds` | no | Exact WorldState timestamp. |
| `features` | array[`PerceptionFeature`] | no | Complete candidate feature set for this frame. |
| `perception_provenance` | `ProvenanceMap` | no | Provenance for frame-owned fields and collection order. |

```text
perception_frame_id = perception_frame:<world_state_id>
```

#### 9.4.3 `FeatureDefinition`

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.feature_definition`. |
| `feature_code` | enum | no | Exact code from Section 9.9. |
| `feature_name` | string | no | Exact name from Section 9.9. |
| `description` | string | no | Exact objective description from Section 9.9. |
| `category` | enum | no | `SPATIAL`, `MOTION`, `BALL`, `VISIBILITY`, `REACHABILITY`, `DENSITY`, `PASSING_GEOMETRY`, or `TEMPORAL`. |
| `candidate_scope` | enum | no | `OBSERVATION`, `ENTITY`, `ORDERED_ENTITY_PAIR`, `UNORDERED_ENTITY_PAIR`, `TEAM`, `WORLD_STATE`, or `FEATURE_INSTANCE`. |
| `output_type` | enum | no | One `FeatureValue` type. |
| `unit` | enum | no | One unit from Section 9.4.6. |
| `valid_min` | number | yes | Inclusive numeric minimum; null for non-numeric or unbounded output. |
| `valid_max` | number | yes | Inclusive numeric maximum; null for non-numeric or unbounded output. |
| `precision_decimals` | integer | no | Exact value `6` for real-valued and geometric output and `0` for integer, Boolean, enum, and entity-reference output. |
| `dependency_codes` | array[enum] | no | Direct feature dependencies in evaluation order. |
| `definition_version` | string | no | Exact value `0.1.0`. |
| `perception_provenance` | `ProvenanceMap` | no | Specification-constant provenance. |

Feature definitions SHALL be ordered by category rank from Section 9.11, then `feature_code` by Unicode code point.

#### 9.4.4 `PerceptionFeature`

| Field | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `schema_id` | string | no | Exact value `tip.perception_feature`. |
| `feature_id` | `CanonicalId` | no | Deterministic feature identity. |
| `feature_code` | enum | no | Reference to one FeatureDefinition. |
| `feature_name` | string | no | Exact copied definition name. |
| `category` | enum | no | Exact copied definition category. |
| `world_state_id` | `CanonicalId` | no | Originating WorldState. |
| `world_state_index` | integer | no | Originating WorldState index. |
| `canonical_time_seconds` | `Seconds` | no | Originating WorldState timestamp. |
| `subject_ids` | array[`CanonicalId`] | no | Ordered feature subjects. |
| `input_observation_ids` | array[`CanonicalId`] | no | Ordered direct position or visibility inputs. |
| `dependency_feature_ids` | array[`CanonicalId`] | no | Ordered direct feature dependencies. |
| `status` | enum | no | `AVAILABLE` or `UNAVAILABLE`. |
| `unavailable_reason` | enum | yes | Null when available; one reason from Section 9.6 otherwise. |
| `value` | `FeatureValue` | yes | Non-null when available; null otherwise. |
| `unit` | enum | no | Exact copied definition unit. |
| `perception_provenance` | `ProvenanceMap` | no | Complete feature provenance. |

#### 9.4.5 Feature identity

Feature identity SHALL be constructed as:

```text
feature_id = feature:<world_state_id>:<feature_code lowercase>:<candidate_key>
```

Candidate keys are exact:

| Scope | Candidate key |
| --- | --- |
| `OBSERVATION` | observation ID |
| `ENTITY` | entity ID |
| `ORDERED_ENTITY_PAIR` | `<first entity ID>:to:<second entity ID>` |
| `UNORDERED_ENTITY_PAIR` | lexicographically smaller entity ID, `:and:`, larger entity ID |
| `TEAM` | team ID |
| `WORLD_STATE` | world-state ID |
| `FEATURE_INSTANCE` | dependency feature ID |

When one feature code emits multiple records for the same subjects because distinct direct observations exist, `candidate_key` SHALL append `:observations:` followed by the input observation IDs in declared order joined with `:and:`.

#### 9.4.6 `FeatureValue`

`FeatureValue` contains exactly these nullable fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `scalar` | number | Scalar numeric output. |
| `integer` | integer | Count or index output. |
| `boolean` | boolean | Boolean output. |
| `enum_value` | string | Controlled non-tactical state. |
| `entity_id` | `CanonicalId` | One referenced entity. |
| `entity_ids` | array[`CanonicalId`] | Ordered referenced entities. |
| `vector2` | object `{x,y}` | Two-dimensional vector. |
| `position2` | object `{x_m,y_m}` | Canonical pitch position. |
| `polygon2` | array[object `{x_m,y_m}`] | Ordered closed polygon. |
| `polyline2` | array[object `{x_m,y_m}`] | Ordered non-closed point sequence. |
| `circle2` | object `{center_x_m,center_y_m,radius_m}` | Closed circular region. |

Exactly one field SHALL be non-null in an available value. Every field SHALL be null in no object because unavailable features have `value=null`.

Units are exactly: `NONE`, `BOOLEAN`, `ENUM`, `ENTITY_ID`, `ENTITY_IDS`, `COUNT`, `METRES`, `SQUARE_METRES`, `METRES_PER_SECOND`, `METRES_PER_SECOND_SQUARED`, `RADIANS`, `RADIANS_PER_SECOND`, `SECONDS`, `RATIO`, `PLAYERS_PER_SQUARE_METRE`, `POSITION_METRES`, `VECTOR_METRES`, `VECTOR_METRES_PER_SECOND`, `VECTOR_METRES_PER_SECOND_SQUARED`, `POLYGON_METRES`, `POLYLINE_METRES`, and `CIRCLE_METRES`.

### 9.5 Candidate generation and position eligibility

Perception SHALL generate every candidate required by the feature's `candidate_scope`:

1. `OBSERVATION`: every Observation meeting the feature's subject-kind rule;
2. `ENTITY`: every catalog entity of the declared kind;
3. `ORDERED_ENTITY_PAIR`: every ordered pair of distinct eligible catalog entities;
4. `UNORDERED_ENTITY_PAIR`: every unordered pair of distinct eligible catalog entities;
5. `TEAM`: every catalog Team;
6. `WORLD_STATE`: the current WorldState;
7. `FEATURE_INSTANCE`: every available dependency feature instance named by the definition.

Catalog ordering SHALL NOT suppress a candidate. A missing input SHALL create an unavailable record for that candidate.

An entity has a unique current position only when its current state references exactly one valid position Observation. Zero position observations produces `POSITION_MISSING`. More than one produces `POSITION_AMBIGUOUS`. Perception SHALL NOT select between multiple positions.

Motion eligibility additionally requires the same identified entity to have a unique position in the immediately preceding WorldState and a strictly positive timestamp delta. Observation-scoped Players are never motion-eligible because their identity SHALL NOT cross WorldStates.

### 9.6 Availability and missing input

Unavailable reasons are exact:

| Reason | Condition |
| --- | --- |
| `POSITION_MISSING` | Required entity has no current direct position. |
| `POSITION_AMBIGUOUS` | Required entity has multiple current direct positions. |
| `PREVIOUS_STATE_MISSING` | Required preceding WorldState does not exist. |
| `PREVIOUS_POSITION_MISSING` | Required prior unique position does not exist. |
| `ZERO_TIME_DELTA` | Required timestamps are equal. |
| `ENTITY_NOT_IDENTIFIED` | Feature requires persistent identified identity. |
| `DEPENDENCY_UNAVAILABLE` | A direct feature dependency is unavailable. |
| `INSUFFICIENT_SAMPLE_COUNT` | Exact minimum sample count is not met. |
| `WORLD_INPUT_ABSENT` | World Model does not contain the required factual input class. |
| `DEGENERATE_GEOMETRY` | Required denominator, direction, segment, polygon, or hull is mathematically degenerate. |
| `NO_FINITE_SOLUTION` | A defined equation has no finite non-negative solution. |
| `NO_ELIGIBLE_ENTITY` | A deterministic selection has no eligible entity. |

If multiple reasons apply, the table order above determines the emitted reason. An unavailable feature SHALL have `value=null`, retain its definition unit, list every input entity known for the candidate, list available input observations, and list direct dependency feature IDs.

### 9.7 Mathematical conventions

Coordinates are canonical metres from Chapter 6. For points `a=(ax,ay)` and `b=(bx,by)`:

```text
delta(a,b) = (bx-ax, by-ay)
distance(a,b) = sqrt((bx-ax)^2 + (by-ay)^2)
bearing(a,b) = atan2(by-ay, bx-ax)
```

Angles SHALL be radians in interval `(-pi,pi]`. An exact `-pi` result SHALL be represented as `pi`. Angular difference SHALL be wrapped into `(-pi,pi]`.

Vector magnitude uses Euclidean norm. Dot and cross products use canonical Cartesian definitions. A point is inside a polygon or corridor when it is inside or on its boundary.

All calculations SHALL use IEEE 754 binary64 operations with round-to-nearest, ties-to-even, in the exact operation order stated by each definition. Fused multiply-add SHALL NOT be used. Transcendental functions `sqrt`, `atan2`, and `pi` SHALL use correctly rounded binary64 results. Each final numeric leaf SHALL then be rounded to six decimal places using decimal round-half-to-even before Section 2.3 serialization. Negative zero SHALL become zero.

### 9.8 Feature dependencies

A feature MAY depend only on the current WorldState, earlier WorldStates, immutable entity catalogs, direct World observations, factual World relationships, or feature codes earlier in the dependency order in Section 9.9.

The dependency graph SHALL be acyclic. A feature SHALL list every direct feature dependency in its definition and every concrete dependency instance in its record. Recognition output, hypotheses, explanations, renderer state, provider data, and implementation caches are forbidden dependencies.

Evaluation SHALL follow the Section 9.9 table order. Dependency cycles SHALL fail with `TIP-PER-DEPENDENCY-CYCLE`.

### 9.9 Normative feature catalog

The tables in this section are the complete v0.1 feature catalog. The row order is the dependency evaluation order. `P` means Player, `B` means Ball, `T` means Team, `O` means Observation, and `S` means WorldState. Numeric ranges are inclusive. A blank bound is unbounded.

For each row, `feature_name` is the text before the em dash and `description` is the text after it. `candidate_scope` is the uppercase scope token in the Scope column. `output_type` is the uppercase form of the first token in the Type column and `unit` is the second token. Output types are exactly `SCALAR`, `INTEGER`, `BOOLEAN`, `ENUM_VALUE`, `ENTITY_ID`, `ENTITY_IDS`, `VECTOR2`, `POSITION2`, `POLYGON2`, `POLYLINE2`, and `CIRCLE2`. Numeric range endpoints populate `valid_min` and `valid_max`; an unbounded or non-numeric endpoint is null. Angle definitions SHALL store `valid_min=-3.141593` and `valid_max=3.141593`, while the value-level invariant continues to exclude exact `-pi`. `dependency_codes` is the listed dependency sequence and is empty when the table says `none`.

`precision_decimals` SHALL equal `6` for `SCALAR`, `VECTOR2`, `POSITION2`, `POLYGON2`, `POLYLINE2`, and `CIRCLE2`; it SHALL equal `0` for every other output type.

#### 9.9.1 Spatial features

| Code | Name and objective description | Scope and subjects | Type; unit; range | Dependencies | Exact definition |
| --- | --- | --- | --- | --- | --- |
| `OBSERVATION_POSITION` | Observation Position — direct canonical position. | `OBSERVATION`; O of P or B | `position2`; `POSITION_METRES`; pitch bounds | none | Copy Observation `position.x_m,y_m`. |
| `ABSOLUTE_POSITION` | Absolute Position — unique current entity position. | `ENTITY`; P or B | `position2`; `POSITION_METRES`; pitch bounds | `OBSERVATION_POSITION` | Available only with one current position observation; copy that position. |
| `PAIR_DISTANCE` | Pair Distance — Euclidean separation. | `UNORDERED_ENTITY_PAIR`; distinct P or B | `scalar`; `METRES`; `[0,125.095963]` | `ABSOLUTE_POSITION` | `distance(a,b)`. |
| `RELATIVE_POSITION` | Relative Position — vector from first subject to second. | `ORDERED_ENTITY_PAIR`; distinct P or B | `vector2`; `VECTOR_METRES`; unbounded | `ABSOLUTE_POSITION` | `delta(a,b)`. |
| `BEARING` | Bearing — angle from first subject to second. | `ORDERED_ENTITY_PAIR`; distinct P or B | `scalar`; `RADIANS`; `(-pi,pi]` | `RELATIVE_POSITION` | `atan2(vector.y,vector.x)`; zero vector is degenerate. |
| `PITCH_CELL` | Pitch Cell — fixed rectangular grid address of one Observation. | `OBSERVATION`; O of P or B | `enum_value`; `ENUM`; — | `OBSERVATION_POSITION` | `X<x_index>_Y<y_index>` under Section 9.10.1. |
| `BODY_ORIENTATION` | Body Orientation — directly observed body axis. | `ENTITY`; P | `scalar`; `RADIANS`; `(-pi,pi]` | none | Always unavailable with `WORLD_INPUT_ABSENT` in v0.1. |
| `TEAM_CENTROID` | Team Centroid — arithmetic mean of unique current member positions. | `TEAM`; T | `position2`; `POSITION_METRES`; pitch bounds | `ABSOLUTE_POSITION` | Section 9.10.2; minimum one positioned member. |
| `TEAM_CONVEX_HULL` | Team Convex Hull — minimal convex polygon around unique current member positions. | `TEAM`; T | `polygon2`; `POLYGON_METRES`; — | `ABSOLUTE_POSITION` | Section 9.10.3; minimum three non-collinear positions. |
| `TEAM_WIDTH` | Team Width — current lateral coordinate range. | `TEAM`; T | `scalar`; `METRES`; `[0,68]` | `ABSOLUTE_POSITION` | `max(y)-min(y)`; minimum one positioned member. |
| `TEAM_DEPTH` | Team Depth — current longitudinal coordinate range. | `TEAM`; T | `scalar`; `METRES`; `[0,105]` | `ABSOLUTE_POSITION` | `max(x)-min(x)`; minimum one positioned member. |
| `TEAM_DISPERSION` | Team Dispersion — root mean square distance to team centroid. | `TEAM`; T | `scalar`; `METRES`; `[0,125.095963]` | `TEAM_CENTROID`, `ABSOLUTE_POSITION` | `sqrt(sum(distance(pi,c)^2)/n)`. |
| `TEAM_COMPACTNESS` | Team Compactness — convex-hull area divided by width-depth envelope area. | `TEAM`; T | `scalar`; `RATIO`; `[0,1]` | `TEAM_CONVEX_HULL`, `TEAM_WIDTH`, `TEAM_DEPTH` | `hull_area/(width*depth)`; zero denominator is degenerate. |

#### 9.9.2 Motion features

| Code | Name and objective description | Scope and subjects | Type; unit; range | Dependencies | Exact definition |
| --- | --- | --- | --- | --- | --- |
| `ENTITY_VELOCITY` | Entity Velocity — backward finite-difference position vector. | `ENTITY`; identified P or B | `vector2`; `VECTOR_METRES_PER_SECOND`; unbounded | `ABSOLUTE_POSITION` | `(position_i-position_i-1)/(time_i-time_i-1)`. |
| `ENTITY_SPEED` | Entity Speed — velocity magnitude. | `ENTITY`; identified P or B | `scalar`; `METRES_PER_SECOND`; `[0,]` | `ENTITY_VELOCITY` | Euclidean magnitude. |
| `MOTION_HEADING` | Motion Heading — direction of non-zero velocity. | `ENTITY`; identified P or B | `scalar`; `RADIANS`; `(-pi,pi]` | `ENTITY_VELOCITY` | `atan2(vy,vx)`; zero speed is degenerate. |
| `ENTITY_ACCELERATION` | Entity Acceleration — backward finite difference of velocity. | `ENTITY`; identified P or B | `vector2`; `VECTOR_METRES_PER_SECOND_SQUARED`; unbounded | `ENTITY_VELOCITY` | `(velocity_i-velocity_i-1)/(time_i-time_i-1)`. |
| `SPEED_CHANGE_RATE` | Speed Change Rate — signed speed derivative. | `ENTITY`; identified P or B | `scalar`; `METRES_PER_SECOND_SQUARED`; unbounded | `ENTITY_SPEED` | `(speed_i-speed_i-1)/(time_i-time_i-1)`. |
| `DECELERATION` | Deceleration — non-negative magnitude of decreasing speed. | `ENTITY`; identified P or B | `scalar`; `METRES_PER_SECOND_SQUARED`; `[0,]` | `SPEED_CHANGE_RATE` | `max(0,-speed_change_rate)`. |
| `ANGULAR_VELOCITY` | Angular Velocity — wrapped heading change per second. | `ENTITY`; identified P or B | `scalar`; `RADIANS_PER_SECOND`; unbounded | `MOTION_HEADING` | `wrapped(heading_i-heading_i-1)/(time_i-time_i-1)`. |
| `RELATIVE_VELOCITY` | Relative Velocity — second subject velocity minus first subject velocity. | `ORDERED_ENTITY_PAIR`; distinct identified P or B | `vector2`; `VECTOR_METRES_PER_SECOND`; unbounded | `ENTITY_VELOCITY` | `velocity_b-velocity_a`. |
| `CLOSING_SPEED` | Closing Speed — positive radial approach rate. | `ORDERED_ENTITY_PAIR`; distinct identified P or B | `scalar`; `METRES_PER_SECOND`; unbounded | `RELATIVE_POSITION`, `RELATIVE_VELOCITY`, `PAIR_DISTANCE` | `-dot(relative_position,relative_velocity)/pair_distance`; zero distance is degenerate. |
| `SEPARATION_SPEED` | Separation Speed — positive radial separation rate. | `ORDERED_ENTITY_PAIR`; distinct identified P or B | `scalar`; `METRES_PER_SECOND`; unbounded | `CLOSING_SPEED` | `-closing_speed`. |

#### 9.9.3 Ball features

| Code | Name and objective description | Scope and subjects | Type; unit; range | Dependencies | Exact definition |
| --- | --- | --- | --- | --- | --- |
| `BALL_POSITION` | Ball Position — unique current direct ball position. | `ENTITY`; B | `position2`; `POSITION_METRES`; pitch bounds | `ABSOLUTE_POSITION` | Copy Ball absolute position. |
| `BALL_VELOCITY` | Ball Velocity — measured backward finite-difference vector. | `ENTITY`; B | `vector2`; `VECTOR_METRES_PER_SECOND`; unbounded | `ENTITY_VELOCITY` | Copy Ball entity velocity. |
| `BALL_SPEED` | Ball Speed — Ball velocity magnitude. | `ENTITY`; B | `scalar`; `METRES_PER_SECOND`; `[0,]` | `ENTITY_SPEED` | Copy Ball entity speed. |
| `BALL_DIRECTION` | Ball Direction — direction of non-zero Ball velocity. | `ENTITY`; B | `scalar`; `RADIANS`; `(-pi,pi]` | `MOTION_HEADING` | Copy Ball motion heading. |
| `BALL_ACCELERATION` | Ball Acceleration — measured backward finite-difference vector. | `ENTITY`; B | `vector2`; `VECTOR_METRES_PER_SECOND_SQUARED`; unbounded | `ENTITY_ACCELERATION` | Copy Ball entity acceleration. |
| `BALL_TRAJECTORY` | Ball Trajectory — ordered sequence of unique direct Ball positions through current state. | `ENTITY`; B | `polyline2`; `POLYLINE_METRES`; — | `BALL_POSITION` | Append one position per state from index zero through current; all states SHALL be available; minimum two. |
| `BALL_TRAVEL_DISTANCE` | Ball Travel Distance — cumulative trajectory segment length. | `ENTITY`; B | `scalar`; `METRES`; `[0,]` | `BALL_TRAJECTORY` | Sum consecutive polyline segment distances. |
| `BALL_LIFECYCLE` | Ball Lifecycle — canonical World lifecycle value. | `ENTITY`; B | `enum_value`; `ENUM`; — | none | Copy BallState lifecycle. |
| `BALL_OWNERSHIP_STATUS` | Ball Ownership Status — canonical World ownership knowledge. | `ENTITY`; B | `enum_value`; `ENUM`; — | none | Copy BallState ownership status; v0.1 value is `UNKNOWN`. |
| `BALL_OWNER_REFERENCE` | Ball Owner Reference — canonical owner when asserted. | `ENTITY`; B | `entity_id`; `ENTITY_ID`; — | none | Available only when BallState owner is non-null; otherwise `WORLD_INPUT_ABSENT`. |
| `BALL_VISIBILITY` | Ball Visibility — canonical World visibility value. | `ENTITY`; B | `enum_value`; `ENUM`; — | none | Copy BallState visibility. |

#### 9.9.4 Visibility features

| Code | Name and objective description | Scope and subjects | Type; unit; range | Dependencies | Exact definition |
| --- | --- | --- | --- | --- | --- |
| `ENTITY_VISIBILITY` | Entity Visibility — canonical visibility state. | `ENTITY`; P or B | `enum_value`; `ENUM`; — | none | Copy current PlayerState or BallState visibility. |
| `VISIBLE_TEAMMATE_COUNT` | Visible Teammate Count — visible same-team Players excluding subject. | `ENTITY`; P | `integer`; `COUNT`; `[0,]` | `ENTITY_VISIBILITY` | Count catalog Players with same team, distinct ID, and `VISIBLE`. |
| `VISIBLE_OPPONENT_COUNT` | Visible Opponent Count — visible different-team Players. | `ENTITY`; P | `integer`; `COUNT`; `[0,]` | `ENTITY_VISIBILITY` | Count catalog Players with different team and `VISIBLE`. |
| `VISIBLE_BALL` | Visible Ball — whether Ball visibility is explicitly visible. | `WORLD_STATE`; S | `boolean`; `BOOLEAN`; — | `BALL_VISIBILITY` | True only for `VISIBLE`; false only for `NOT_VISIBLE`; `UNKNOWN` makes feature unavailable with `WORLD_INPUT_ABSENT`. |
| `OBSERVATION_COMPLETENESS` | Observation Completeness — observed non-terminated Player fraction. | `WORLD_STATE`; S | `scalar`; `RATIO`; `[0,1]` | none | observed PlayerState count divided by non-terminated PlayerState count; zero denominator is degenerate. |
| `LINE_OF_SIGHT` | Line of Sight — direct visibility segment assertion. | `ORDERED_ENTITY_PAIR`; distinct P or B | `boolean`; `BOOLEAN`; — | none | Always unavailable with `WORLD_INPUT_ABSENT` in v0.1. |
| `OCCLUSION_STATUS` | Occlusion Status — direct occlusion assertion. | `ORDERED_ENTITY_PAIR`; distinct P or B | `enum_value`; `ENUM`; — | none | Always unavailable with `WORLD_INPUT_ABSENT` in v0.1. |

#### 9.9.5 Reachability features

| Code | Name and objective description | Scope and subjects | Type; unit; range | Dependencies | Exact definition |
| --- | --- | --- | --- | --- | --- |
| `ARRIVAL_TIME` | Arrival Time — straight-line distance divided by current subject speed. | `ORDERED_ENTITY_PAIR`; first identified P, second distinct P or B | `scalar`; `SECONDS`; `[0,]` | `PAIR_DISTANCE`, `ENTITY_SPEED` | `distance/speed_first`; zero speed is degenerate. |
| `TIME_TO_BALL` | Time To Ball — Arrival Time from Player to Ball. | `ORDERED_ENTITY_PAIR`; identified P to B | `scalar`; `SECONDS`; `[0,]` | `ARRIVAL_TIME` | Copy matching Arrival Time. |
| `REACHABLE_REGION_1S` | Reachable Region 1s — constant-current-speed circle over one second. | `ENTITY`; identified P | `circle2`; `CIRCLE_METRES`; — | `ABSOLUTE_POSITION`, `ENTITY_SPEED` | Center current position; radius `speed*1`. |
| `REACHABILITY_SCORE` | Reachability Score — monotonic normalization of Time To Ball. | `ORDERED_ENTITY_PAIR`; identified P to B | `scalar`; `RATIO`; `[0,1]` | `TIME_TO_BALL` | `1/(1+time_to_ball)`. |
| `INTERCEPTION_TIME` | Interception Time — first constant-velocity Player–Ball separation of one metre. | `ORDERED_ENTITY_PAIR`; identified P to B | `scalar`; `SECONDS`; `[0,]` | `ABSOLUTE_POSITION`, `ENTITY_VELOCITY`, `BALL_POSITION`, `BALL_VELOCITY` | Section 9.10.6. |
| `CLOSEST_REACHABLE_PLAYER` | Closest Reachable Player — minimum available Time To Ball. | `WORLD_STATE`; S | `entity_id`; `ENTITY_ID`; — | `TIME_TO_BALL` | Minimum value; ties by Player ID; none produces `NO_ELIGIBLE_ENTITY`. |

These reachability features are kinematic measurements under their stated constant-velocity formulas. They SHALL NOT assert future position, intent, success, control, or tactical availability.

#### 9.9.6 Density features

| Code | Name and objective description | Scope and subjects | Type; unit; range | Dependencies | Exact definition |
| --- | --- | --- | --- | --- | --- |
| `NEIGHBOR_COUNT_5M` | Neighbor Count 5m — positioned Players within five metres. | `ENTITY`; P | `integer`; `COUNT`; `[0,]` | `PAIR_DISTANCE` | Count distinct other Players with available distance `<=5`. |
| `LOCAL_PLAYER_COUNT_10M` | Local Player Count 10m — positioned Players within ten metres. | `ENTITY`; P | `integer`; `COUNT`; `[0,]` | `PAIR_DISTANCE` | Count distinct other Players with available distance `<=10`. |
| `LOCAL_TEAMMATE_COUNT_10M` | Local Teammate Count 10m — same-team subset of local count. | `ENTITY`; P | `integer`; `COUNT`; `[0,]` | `PAIR_DISTANCE` | Count same-team distinct Players with distance `<=10`. |
| `LOCAL_OPPONENT_COUNT_10M` | Local Opponent Count 10m — different-team subset of local count. | `ENTITY`; P | `integer`; `COUNT`; `[0,]` | `PAIR_DISTANCE` | Count different-team Players with distance `<=10`. |
| `LOCAL_PLAYER_DENSITY_10M` | Local Player Density 10m — local count per circle area. | `ENTITY`; P | `scalar`; `PLAYERS_PER_SQUARE_METRE`; `[0,]` | `LOCAL_PLAYER_COUNT_10M` | `count/(pi*100)`. |
| `TEAM_OCCUPANCY_AREA` | Team Occupancy Area — observed team convex-hull area. | `TEAM`; T | `scalar`; `SQUARE_METRES`; `[0,7140]` | `TEAM_CONVEX_HULL` | Polygon shoelace area. |
| `VORONOI_FREE_SPACE_AREA` | Voronoi Free-Space Area — pitch-clipped nearest-position cell area. | `ENTITY`; P | `scalar`; `SQUARE_METRES`; `[0,7140]` | `ABSOLUTE_POSITION` | Section 9.10.4. |

#### 9.9.7 Passing-geometry features

| Code | Name and objective description | Scope and subjects | Type; unit; range | Dependencies | Exact definition |
| --- | --- | --- | --- | --- | --- |
| `CONNECTION_DISTANCE` | Connection Distance — distance between ordered same-team Player positions. | `ORDERED_ENTITY_PAIR`; distinct same-team P | `scalar`; `METRES`; `[0,126.589889]` | `PAIR_DISTANCE` | Copy pair distance. |
| `CONNECTION_ANGLE` | Connection Angle — bearing from first Player to second. | `ORDERED_ENTITY_PAIR`; distinct same-team P | `scalar`; `RADIANS`; `(-pi,pi]` | `BEARING` | Copy ordered bearing. |
| `CONNECTION_CORRIDOR` | Connection Corridor — closed two-metre-wide rectangle around directed segment. | `ORDERED_ENTITY_PAIR`; distinct same-team P | `polygon2`; `POLYGON_METRES`; — | `ABSOLUTE_POSITION`, `CONNECTION_DISTANCE` | Section 9.10.5; zero distance is degenerate. |
| `CORRIDOR_WIDTH` | Corridor Width — fixed full width of Connection Corridor. | `ORDERED_ENTITY_PAIR`; distinct same-team P | `scalar`; `METRES`; `[2,2]` | `CONNECTION_CORRIDOR` | Exact value `2`. |
| `CORRIDOR_OCCUPANCY` | Corridor Occupancy — uniquely positioned opponent Players inside corridor. | `ORDERED_ENTITY_PAIR`; distinct same-team P | `integer`; `COUNT`; `[0,]` | `CONNECTION_CORRIDOR`, `ABSOLUTE_POSITION` | Count different-team Players inside or on polygon. |
| `CORRIDOR_OBSTRUCTED` | Corridor Obstructed — whether corridor occupancy is non-zero. | `ORDERED_ENTITY_PAIR`; distinct same-team P | `boolean`; `BOOLEAN`; — | `CORRIDOR_OCCUPANCY` | `occupancy>0`. |
| `RECEIVER_APERTURE_ANGLE` | Receiver Aperture Angle — angle at second Player from sender direction to positive x-axis. | `ORDERED_ENTITY_PAIR`; distinct same-team P | `scalar`; `RADIANS`; `(-pi,pi]` | `ABSOLUTE_POSITION` | Wrapped difference `0-bearing(receiver,sender)`. |

These records describe connection geometry only. They SHALL NOT assert pass existence, pass feasibility, pass desirability, progression, line breaking, or danger.

#### 9.9.8 Temporal features

| Code | Name and objective description | Scope and subjects | Type; unit; range | Dependencies | Exact definition |
| --- | --- | --- | --- | --- | --- |
| `STATE_DELTA_TIME` | State Delta Time — elapsed time since immediately preceding WorldState. | `WORLD_STATE`; S | `scalar`; `SECONDS`; `[0,]` | none | Current minus previous canonical time; first state unavailable with `PREVIOUS_STATE_MISSING`. |
| `LIFECYCLE_PERSISTENCE` | Lifecycle Persistence — elapsed time since current lifecycle value began. | `ENTITY`; P, B, or T | `scalar`; `SECONDS`; `[0,]` | none | Current time minus first state time in current consecutive lifecycle run. |
| `VISIBILITY_PERSISTENCE` | Visibility Persistence — elapsed time since current visibility value began. | `ENTITY`; P or B | `scalar`; `SECONDS`; `[0,]` | none | Current time minus first state time in current consecutive visibility run. |
| `PAIR_DISTANCE_TREND` | Pair Distance Trend — backward derivative of pair distance. | `UNORDERED_ENTITY_PAIR`; distinct identified P or B | `scalar`; `METRES_PER_SECOND`; unbounded | `PAIR_DISTANCE`, `STATE_DELTA_TIME` | `(distance_i-distance_i-1)/delta_time`. |
| `RELATIVE_MOVEMENT` | Relative Movement — backward derivative of relative-position vector. | `ORDERED_ENTITY_PAIR`; distinct identified P or B | `vector2`; `VECTOR_METRES_PER_SECOND`; unbounded | `RELATIVE_POSITION`, `STATE_DELTA_TIME` | `(relative_position_i-relative_position_i-1)/delta_time`. |
| `POSITION_STABILITY_3` | Position Stability 3 — RMS distance to centroid over three consecutive positions. | `ENTITY`; identified P or B | `scalar`; `METRES`; `[0,125.095963]` | `ABSOLUTE_POSITION` | Section 9.10.7; exactly current and two preceding states. |

`PAIR_DISTANCE_TREND` and `RELATIVE_MOVEMENT` SHALL be unavailable with `ZERO_TIME_DELTA` when `STATE_DELTA_TIME` equals zero.

### 9.10 Exact geometric and temporal procedures

#### 9.10.1 Pitch cell

The Pitch SHALL be partitioned into six equal longitudinal bands and five equal lateral bands:

```text
x_index = min(floor(x_m / 17.5), 5)
y_index = min(floor(y_m / 13.6), 4)
```

The resulting enum is `X<x_index>_Y<y_index>`. Lower bounds are inclusive. Internal upper bounds belong to the next band. Pitch maximum coordinates belong to the final band.

#### 9.10.2 Team position set and centroid

The team position set SHALL contain each current Team member with lifecycle `OBSERVED` and exactly one position Observation. `UNKNOWN`, `MISSING`, and `TERMINATED` members SHALL be excluded. If an observed member has multiple position Observations, every aggregate Team feature SHALL be unavailable with `POSITION_AMBIGUOUS`.

Positions SHALL be ordered by Player ID. Centroid is:

```text
cx = sum(x_i)/n
cy = sum(y_i)/n
```

An empty position set produces `INSUFFICIENT_SAMPLE_COUNT`.

#### 9.10.3 Convex hull

Duplicate coordinate pairs SHALL be reduced to one point after Player-ID ordering. Points SHALL then be sorted by `x_m`, then `y_m`, both ascending. The hull SHALL use the monotonic-chain definition:

1. build the lower sequence from left to right;
2. while its final three points have cross product `<=0`, remove the middle of those three;
3. build the upper sequence by the same rule from right to left;
4. concatenate lower and upper without their duplicate terminal points;
5. emit vertices counter-clockwise beginning with the lexicographically smallest `(x_m,y_m)`;
6. repeat the first vertex as the final vertex.

Fewer than three unique points or zero polygon area produces `DEGENERATE_GEOMETRY`. Polygon area SHALL use the absolute shoelace sum divided by two.

#### 9.10.4 Pitch-clipped Voronoi area

For subject position `p`, begin with closed Pitch polygon `(0,0),(105,0),(105,68),(0,68),(0,0)`. For every other Player with an available unique position `q`, ordered by Player ID, intersect the current polygon with the closed half-plane:

```text
2*(q.x-p.x)*x + 2*(q.y-p.y)*y <= q.x^2 + q.y^2 - p.x^2 - p.y^2
```

Half-plane intersection SHALL process polygon edges in current vertex order. A boundary intersection SHALL be calculated by linear interpolation of the two endpoint signed half-plane values. Exact boundary points are inside. Consecutive duplicate vertices SHALL be removed. The result SHALL be counter-clockwise, begin at its lexicographically smallest vertex, and repeat that vertex at the end.

For signed half-plane function `f`, each directed polygon edge from `s` to `e` SHALL be processed as follows: when `f(s)<=0` and `f(e)<=0`, emit `e`; when `f(s)<=0` and `f(e)>0`, emit only intersection `s+t*(e-s)`; when `f(s)>0` and `f(e)<=0`, emit that intersection followed by `e`; otherwise emit nothing. For a crossing edge, `t=f(s)/(f(s)-f(e))`. The denominator SHALL be non-zero by the crossing condition.

The feature value is the absolute shoelace area. An empty result produces scalar zero. A subject without a unique position produces its position availability reason. Other Players without unique positions SHALL be excluded; their absence SHALL be recorded in provenance and SHALL NOT make the subject feature unavailable.

#### 9.10.5 Connection corridor

For sender point `a`, receiver point `b`, distance `d>0`, unit direction `u=(b-a)/d`, and left normal `n=(-u.y,u.x)`, the closed full-width two-metre corridor is:

```text
a+n, b+n, b-n, a-n, a+n
```

The polygon SHALL NOT be clipped to the Pitch. Opponent occupancy SHALL evaluate each opponent with exactly one current position. Opponents without a unique position SHALL be excluded and recorded in provenance. Boundary points count as occupied.

The corridor vertex order above is clockwise. Point `p` is inside or on the corridor exactly when the four values `cross(vertex[i+1]-vertex[i], p-vertex[i])` are all `<=0` for `i=0..3`. No geometric tolerance SHALL be used.

#### 9.10.6 Interception time

Let `r=ball_position-player_position`, `v=ball_velocity-player_velocity`, and interception radius `R=1` metre. Solve:

```text
a = dot(v,v)
b = 2*dot(r,v)
c = dot(r,r)-R^2
```

If `c<=0`, result is zero. Otherwise, if `a=0`, result is unavailable with `NO_FINITE_SOLUTION`. Calculate `D=b^2-4*a*c`. If `D<0`, result is unavailable with `NO_FINITE_SOLUTION`. Otherwise calculate both roots `(-b-sqrt(D))/(2*a)` and `(-b+sqrt(D))/(2*a)` and emit the smallest root `>=0`. If neither root is non-negative, emit `NO_FINITE_SOLUTION`.

This value is a constant-velocity geometric intersection time. It SHALL NOT assert an actual future interception.

#### 9.10.7 Three-state position stability

The sample SHALL contain exactly the unique entity positions at current state and its two immediate predecessors. All three timestamps SHALL be distinct and increasing. Let `c` be their arithmetic centroid. The value is:

```text
sqrt((distance(p0,c)^2 + distance(p1,c)^2 + distance(p2,c)^2)/3)
```

Missing or ambiguous positions use their specific availability reason. Fewer than three states produces `INSUFFICIENT_SAMPLE_COUNT`.

### 9.11 Ordering and evaluation

Category rank is:

```text
SPATIAL=0
MOTION=1
BALL=2
VISIBILITY=3
REACHABILITY=4
DENSITY=5
PASSING_GEOMETRY=6
TEMPORAL=7
```

The Perception Layer SHALL execute exactly:

1. authenticate WorldModelDataset media type, version, and digest;
2. validate every Chapter 8 schema and invariant;
3. construct the exact FeatureDefinition catalog in Section 9.9;
4. process WorldStates by `world_state_index` ascending;
5. generate candidates for each definition in catalog order;
6. construct feature identities and reject collisions;
7. resolve direct World inputs and dependency instances;
8. determine availability under Sections 9.5 and 9.6;
9. calculate available values using Sections 9.7, 9.9, and 9.10;
10. validate type, unit, range, precision, and entity references;
11. construct feature provenance;
12. order features and frames;
13. validate Section 9.14 invariants;
14. canonicalize and emit artifact bytes and digest.

Within a frame, features SHALL be ordered by category rank, `feature_code`, `subject_ids` lexicographically as arrays, `input_observation_ids` lexicographically as arrays, `dependency_feature_ids` lexicographically as arrays, then `feature_id`, all ascending. Candidate entity enumeration uses catalog identifier order. Ordered pair direction SHALL be preserved. Unordered pair subjects SHALL be lexicographically sorted.

No hash-map order, object-member input order, filesystem order, locale, thread schedule, vectorized reduction order, memory address, or random state SHALL affect evaluation or output.

### 9.12 Feature provenance

Perception provenance SHALL use Section 6.4.8 structures with source paths `world_model_dataset#<JSON Pointer>`. Feature dependencies SHALL additionally reference dependency feature IDs and their canonical paths in the in-construction PerceptionDataset.

Allowed class and operation pairs are exactly:

| Class | Operation | Meaning |
| --- | --- | --- |
| `COPIED` | `PER_COPY_WORLD_FACT` | World fact is unchanged. |
| `WRAPPED_IDENTIFIER` | `PER_BUILD_ID` | Perception identity follows Section 9.4.5. |
| `DERIVED_DETERMINISTICALLY` | `PER_GENERATE_CANDIDATE` | Candidate follows Section 9.5. |
| `DERIVED_DETERMINISTICALLY` | `PER_CALCULATE_FEATURE` | Value follows one catalog definition. |
| `DERIVED_DETERMINISTICALLY` | `PER_BUILD_COLLECTION` | Collection membership and order are normative. |
| `DERIVED_DETERMINISTICALLY` | `PER_MARK_UNAVAILABLE` | Availability follows Section 9.6. |
| `CONSTANT` | `PER_SET_DEFINITION_CONSTANT` | Feature-definition or contract constant with empty sources. |
| `NOT_APPLICABLE` | `PER_SET_NULL_NOT_APPLICABLE` | Nullable field does not apply to current availability state. |

Every feature SHALL trace to its originating WorldState, timestamp, subjects, input Observations, World facts, and direct dependency features. An available calculated value SHALL reference every numeric input. An unavailable record SHALL reference every available prerequisite used to determine the reason.

Input World provenance SHALL be copied as opaque data and SHALL NOT be reinterpreted, flattened, or substituted for Perception provenance.

- **TIP-PER-PROV-001:** Every Perception-owned scalar, null, and collection field SHALL have exactly one provenance entry.
- **TIP-PER-PROV-002:** Every provenance source SHALL resolve to the authenticated World Model or an earlier concrete dependency feature.
- **TIP-PER-PROV-003:** Tactical labels, inferred intent, confidence, implementation details, and provider fields are forbidden in provenance.
- **TIP-PER-PROV-004:** A value derived by a reduction SHALL list inputs in the same normative order as the reduction.

### 9.13 Determinism and serialization

Feature calculations SHALL follow Section 9.7 numeric semantics. Reductions SHALL execute left-to-right in their normatively ordered input sequence. Implementations SHALL NOT reassociate arithmetic.

All feature arrays, polygon vertices, polylines, entity lists, dependency lists, and provenance sources SHALL follow their declared total order. Canonical JSON SHALL follow Section 2.3.

Two conforming implementations receiving identical canonical WorldModelDataset bytes SHALL produce byte-identical PerceptionDataset artifacts and identical SHA-256 digests.

### 9.14 Perception invariants

- **TIP-PER-010:** Perception never changes an entity identity, WorldState identity, timestamp, lifecycle, visibility value, coordinate, membership, or World relationship.
- **TIP-PER-011:** Perception introduces no football-world entity and deletes no input entity.
- **TIP-PER-012:** Every WorldState produces exactly one PerceptionFrame.
- **TIP-PER-013:** Every required feature candidate produces exactly one available or unavailable feature record.
- **TIP-PER-014:** Every feature references existing canonical entities, states, observations, and dependencies only.
- **TIP-PER-015:** Every available value matches its definition type, unit, range, precision, and algorithm.
- **TIP-PER-016:** Every unavailable value is null and has exactly one valid unavailable reason.
- **TIP-PER-017:** Available features have null unavailable reason; unavailable features have no value.
- **TIP-PER-018:** Feature dependencies are acyclic and point only to earlier definition codes.
- **TIP-PER-019:** Perception contains no provider data, recognition result, hypothesis, explanation, confidence, or implementation-dependent value.
- **TIP-PER-020:** Multiple source observations are never reconciled into a preferred entity position.
- **TIP-PER-021:** Repeated execution from identical canonical input produces identical canonical output.

### 9.15 Default contract constants

Perception has no configurable parameters. These constants are normative:

| Constant | Value |
| --- | ---: |
| Pitch grid | 6 longitudinal by 5 lateral cells |
| Neighbor radius | 5 metres |
| Local-density radius | 10 metres |
| Connection-corridor full width | 2 metres |
| Reachable-region horizon | 1 second |
| Interception radius | 1 metre |
| Position-stability sample count | 3 states |
| Numeric output precision | 6 decimal places |

An override request SHALL fail with `TIP-PER-INPUT-ARTIFACT-INVALID`.

### 9.16 Failure behavior

Perception errors SHALL use stage `perception`, execution status `PROCESSING_ERROR`, and an empty successful-artifacts array. No partial PerceptionDataset SHALL be emitted.

| Error code | Condition |
| --- | --- |
| `TIP-PER-INPUT-ARTIFACT-INVALID` | Input is not an authenticated successful WorldModelDataset or requests an override. |
| `TIP-PER-INPUT-VERSION-UNSUPPORTED` | WorldModelDataset contract version is not `0.1.0`. |
| `TIP-PER-INPUT-SCHEMA-INVALID` | Input violates a Chapter 8 schema or invariant. |
| `TIP-PER-FEATURE-DEFINITION-INVALID` | Catalog definition differs from Section 9.9. |
| `TIP-PER-IDENTIFIER-COLLISION` | Two feature or frame identities collide. |
| `TIP-PER-DEPENDENCY-MISSING` | Required dependency definition or concrete candidate is absent. |
| `TIP-PER-DEPENDENCY-CYCLE` | Feature dependency graph is cyclic. |
| `TIP-PER-ENTITY-REFERENCE-INVALID` | Subject or referenced entity does not resolve. |
| `TIP-PER-OBSERVATION-REFERENCE-INVALID` | Input observation does not resolve or has wrong subject. |
| `TIP-PER-TIMESTAMP-INVALID` | Required state times are invalid, decreasing, or inconsistent. |
| `TIP-PER-GEOMETRY-INVALID` | Available geometry is non-finite, out of range, malformed, or contradicts its definition. |
| `TIP-PER-VALUE-INVALID` | Available value has wrong type, unit, range, or precision. |
| `TIP-PER-AVAILABILITY-INVALID` | Status, reason, inputs, or null disposition violates Section 9.6. |
| `TIP-PER-PROVENANCE-INCOMPLETE` | Input provenance is changed or Perception provenance is incomplete, extra, unresolved, or misordered. |
| `TIP-PER-ORDERING-INVALID` | Required candidate, feature, definition, frame, or value ordering is violated. |
| `TIP-PER-INVARIANT-VIOLATION` | Any remaining Section 9.14 invariant fails. |
| `TIP-PER-SERIALIZATION-FAILED` | Canonical JSON serialization fails. |

Errors SHALL be selected by algorithm step, WorldState index, category rank, feature code, candidate subject IDs, input observation IDs, dependency feature IDs, JSON Pointer, and error code, in that order. Arrays compare lexicographically, strings use Unicode code-point order, and unavailable keys sort first.

Error references SHALL use `world_model_dataset#<JSON Pointer>`. Perception SHALL NOT emit `SRC_*`, `NORM_*`, `SYNC_*`, or `WORLD_*` codes.

### 9.17 Worked example

At WorldState time `10`, identified teammate Players `player:worked:p1` and `player:worked:p2` have unique positions `(10,20)` and `(13,24)`. Identified opponent `player:worked:p3` has unique position `(12,22)`. Ball `ball:worked:b1` has unique position `(16,20)`. In the preceding WorldState at time `9`, `player:worked:p1` is at `(9,20)` and `ball:worked:b1` is at `(14,20)`.

The required representative records are:

```json
{
  "schema_id": "tip.perception_frame",
  "perception_frame_id": "perception_frame:world_state:worked:1",
  "world_state_id": "world_state:worked:1",
  "world_state_index": 1,
  "canonical_time_seconds": 10,
  "features": [
    {
      "schema_id": "tip.perception_feature",
      "feature_id": "feature:world_state:worked:1:pair_distance:player:worked:p1:and:player:worked:p2",
      "feature_code": "PAIR_DISTANCE",
      "feature_name": "Pair Distance",
      "category": "SPATIAL",
      "world_state_id": "world_state:worked:1",
      "world_state_index": 1,
      "canonical_time_seconds": 10,
      "subject_ids": [
        "player:worked:p1",
        "player:worked:p2"
      ],
      "input_observation_ids": [
        "observation:worked:player:worked:p1:1",
        "observation:worked:player:worked:p2:1"
      ],
      "dependency_feature_ids": [
        "feature:world_state:worked:1:absolute_position:player:worked:p1",
        "feature:world_state:worked:1:absolute_position:player:worked:p2"
      ],
      "status": "AVAILABLE",
      "unavailable_reason": null,
      "value": {
        "scalar": 5,
        "integer": null,
        "boolean": null,
        "enum_value": null,
        "entity_id": null,
        "entity_ids": null,
        "vector2": null,
        "position2": null,
        "polygon2": null,
        "polyline2": null,
        "circle2": null
      },
      "unit": "METRES",
      "perception_provenance": {
        "/value/scalar": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "PER_CALCULATE_FEATURE",
          "sources": [
            {
              "source_record_id": "observation:worked:player:worked:p1:1",
              "source_path": "world_model_dataset#/world_states/1/observations/0/position"
            },
            {
              "source_record_id": "observation:worked:player:worked:p2:1",
              "source_path": "world_model_dataset#/world_states/1/observations/1/position"
            }
          ]
        }
      }
    },
    {
      "schema_id": "tip.perception_feature",
      "feature_id": "feature:world_state:worked:1:entity_velocity:player:worked:p1",
      "feature_code": "ENTITY_VELOCITY",
      "feature_name": "Entity Velocity",
      "category": "MOTION",
      "world_state_id": "world_state:worked:1",
      "world_state_index": 1,
      "canonical_time_seconds": 10,
      "subject_ids": [
        "player:worked:p1"
      ],
      "input_observation_ids": [
        "observation:worked:player:worked:p1:0",
        "observation:worked:player:worked:p1:1"
      ],
      "dependency_feature_ids": [
        "feature:world_state:worked:0:absolute_position:player:worked:p1",
        "feature:world_state:worked:1:absolute_position:player:worked:p1"
      ],
      "status": "AVAILABLE",
      "unavailable_reason": null,
      "value": {
        "scalar": null,
        "integer": null,
        "boolean": null,
        "enum_value": null,
        "entity_id": null,
        "entity_ids": null,
        "vector2": {
          "x": 1,
          "y": 0
        },
        "position2": null,
        "polygon2": null,
        "polyline2": null,
        "circle2": null
      },
      "unit": "VECTOR_METRES_PER_SECOND",
      "perception_provenance": {
        "/value/vector2": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "PER_CALCULATE_FEATURE",
          "sources": [
            {
              "source_record_id": "observation:worked:player:worked:p1:0",
              "source_path": "world_model_dataset#/world_states/0/observations/0/position"
            },
            {
              "source_record_id": "observation:worked:player:worked:p1:1",
              "source_path": "world_model_dataset#/world_states/1/observations/0/position"
            }
          ]
        }
      }
    },
    {
      "schema_id": "tip.perception_feature",
      "feature_id": "feature:world_state:worked:1:line_of_sight:player:worked:p1:to:player:worked:p2",
      "feature_code": "LINE_OF_SIGHT",
      "feature_name": "Line of Sight",
      "category": "VISIBILITY",
      "world_state_id": "world_state:worked:1",
      "world_state_index": 1,
      "canonical_time_seconds": 10,
      "subject_ids": [
        "player:worked:p1",
        "player:worked:p2"
      ],
      "input_observation_ids": [],
      "dependency_feature_ids": [],
      "status": "UNAVAILABLE",
      "unavailable_reason": "WORLD_INPUT_ABSENT",
      "value": null,
      "unit": "BOOLEAN",
      "perception_provenance": {
        "/status": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "PER_MARK_UNAVAILABLE",
          "sources": [
            {
              "source_record_id": "world_state:worked:1",
              "source_path": "world_model_dataset#/world_states/1"
            }
          ]
        }
      }
    },
    {
      "schema_id": "tip.perception_feature",
      "feature_id": "feature:world_state:worked:1:arrival_time:player:worked:p1:to:ball:worked:b1",
      "feature_code": "ARRIVAL_TIME",
      "feature_name": "Arrival Time",
      "category": "REACHABILITY",
      "world_state_id": "world_state:worked:1",
      "world_state_index": 1,
      "canonical_time_seconds": 10,
      "subject_ids": [
        "player:worked:p1",
        "ball:worked:b1"
      ],
      "input_observation_ids": [
        "observation:worked:player:worked:p1:1",
        "observation:worked:ball:worked:b1:1"
      ],
      "dependency_feature_ids": [
        "feature:world_state:worked:1:entity_speed:player:worked:p1",
        "feature:world_state:worked:1:pair_distance:ball:worked:b1:and:player:worked:p1"
      ],
      "status": "AVAILABLE",
      "unavailable_reason": null,
      "value": {
        "scalar": 6,
        "integer": null,
        "boolean": null,
        "enum_value": null,
        "entity_id": null,
        "entity_ids": null,
        "vector2": null,
        "position2": null,
        "polygon2": null,
        "polyline2": null,
        "circle2": null
      },
      "unit": "SECONDS",
      "perception_provenance": {
        "/value/scalar": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "PER_CALCULATE_FEATURE",
          "sources": [
            {
              "source_record_id": "observation:worked:ball:worked:b1:1",
              "source_path": "world_model_dataset#/world_states/1/observations/3/position"
            },
            {
              "source_record_id": "observation:worked:player:worked:p1:1",
              "source_path": "world_model_dataset#/world_states/1/observations/0/position"
            }
          ]
        }
      }
    },
    {
      "schema_id": "tip.perception_feature",
      "feature_id": "feature:world_state:worked:1:time_to_ball:player:worked:p1:to:ball:worked:b1",
      "feature_code": "TIME_TO_BALL",
      "feature_name": "Time To Ball",
      "category": "REACHABILITY",
      "world_state_id": "world_state:worked:1",
      "world_state_index": 1,
      "canonical_time_seconds": 10,
      "subject_ids": [
        "player:worked:p1",
        "ball:worked:b1"
      ],
      "input_observation_ids": [
        "observation:worked:player:worked:p1:1",
        "observation:worked:ball:worked:b1:1"
      ],
      "dependency_feature_ids": [
        "feature:world_state:worked:1:arrival_time:player:worked:p1:to:ball:worked:b1"
      ],
      "status": "AVAILABLE",
      "unavailable_reason": null,
      "value": {
        "scalar": 6,
        "integer": null,
        "boolean": null,
        "enum_value": null,
        "entity_id": null,
        "entity_ids": null,
        "vector2": null,
        "position2": null,
        "polygon2": null,
        "polyline2": null,
        "circle2": null
      },
      "unit": "SECONDS",
      "perception_provenance": {
        "/value/scalar": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "PER_CALCULATE_FEATURE",
          "sources": [
            {
              "source_record_id": "feature:world_state:worked:1:arrival_time:player:worked:p1:to:ball:worked:b1",
              "source_path": "perception_dataset#/frames/1/features/3/value/scalar"
            }
          ]
        }
      }
    },
    {
      "schema_id": "tip.perception_feature",
      "feature_id": "feature:world_state:worked:1:corridor_occupancy:player:worked:p1:to:player:worked:p2",
      "feature_code": "CORRIDOR_OCCUPANCY",
      "feature_name": "Corridor Occupancy",
      "category": "PASSING_GEOMETRY",
      "world_state_id": "world_state:worked:1",
      "world_state_index": 1,
      "canonical_time_seconds": 10,
      "subject_ids": [
        "player:worked:p1",
        "player:worked:p2"
      ],
      "input_observation_ids": [
        "observation:worked:player:worked:p1:1",
        "observation:worked:player:worked:p2:1",
        "observation:worked:player:worked:p3:1"
      ],
      "dependency_feature_ids": [
        "feature:world_state:worked:1:connection_corridor:player:worked:p1:to:player:worked:p2"
      ],
      "status": "AVAILABLE",
      "unavailable_reason": null,
      "value": {
        "scalar": null,
        "integer": 1,
        "boolean": null,
        "enum_value": null,
        "entity_id": null,
        "entity_ids": null,
        "vector2": null,
        "position2": null,
        "polygon2": null,
        "polyline2": null,
        "circle2": null
      },
      "unit": "COUNT",
      "perception_provenance": {
        "/value/integer": {
          "class": "DERIVED_DETERMINISTICALLY",
          "operation": "PER_CALCULATE_FEATURE",
          "sources": [
            {
              "source_record_id": "observation:worked:player:worked:p3:1",
              "source_path": "world_model_dataset#/world_states/1/observations/2/position"
            }
          ]
        }
      }
    }
  ],
  "perception_provenance": {
    "/canonical_time_seconds": {
      "class": "COPIED",
      "operation": "PER_COPY_WORLD_FACT",
      "sources": [
        {
          "source_record_id": "world_state:worked:1",
          "source_path": "world_model_dataset#/world_states/1/canonical_time_seconds"
        }
      ]
    }
  }
}
```

The pair distance is `sqrt(3^2+4^2)=5`. Player `player:worked:p1` speed is one metre per second. Player-to-Ball distance is six metres, producing Time To Ball `6`. Opponent `player:worked:p3` lies on the directed corridor center segment and produces occupancy `1`. Line of Sight remains unavailable because the World Model supplies no direct line-of-sight fact.

The official worked fixture SHALL additionally contain every candidate record required by Section 9.5 and complete field provenance. The records above are the complete normative calculations for the displayed candidates and SHALL NOT suppress any undisplayed candidate in a conforming artifact.

### 9.18 Conformance tests

| Test ID | Input or mutation | Required assertion |
| --- | --- | --- |
| **TIP-PER-C001** | Untouched Locatelli WorldModelDataset | Canonical PerceptionDataset hash equals golden hash. |
| **TIP-PER-C002** | Untouched Depay WorldModelDataset | Canonical PerceptionDataset hash equals golden hash. |
| **TIP-PER-C003** | Points `(0,0)` and `(3,4)` | Pair Distance `5`, both relative vectors, and exact bearings. |
| **TIP-PER-C004** | Pitch boundary and internal grid points | Pitch Cell follows Section 9.10.1. |
| **TIP-PER-C005** | Three non-collinear team positions | Centroid, hull, width, depth, dispersion, area, and compactness match golden values. |
| **TIP-PER-C006** | Entity moves `(1,0)` metre over one second | Velocity `(1,0)`, speed `1`, heading `0`. |
| **TIP-PER-C007** | Equal consecutive timestamps | Motion records unavailable with `ZERO_TIME_DELTA`. |
| **TIP-PER-C008** | Three positions with changing velocities | Acceleration, speed-change, deceleration, and angular velocity match golden values. |
| **TIP-PER-C009** | Two moving identified entities | Relative velocity, closing speed, separation speed, and relative movement match formulas. |
| **TIP-PER-C010** | Ball positions across three states | Ball trajectory, distance, velocity, direction, and acceleration match golden values. |
| **TIP-PER-C011** | World Ball ownership and visibility unknown | Exact enum records; owner and Visible Ball are unavailable. |
| **TIP-PER-C012** | Visible same-team and opponent Players | Visibility counts and completeness match exact catalog states. |
| **TIP-PER-C013** | Line-of-sight and occlusion candidates | Both unavailable with `WORLD_INPUT_ABSENT`. |
| **TIP-PER-C014** | Player speed `2`, target distance `6` | Arrival Time `3`; reachable-region radius `2`. |
| **TIP-PER-C015** | Constant-velocity interception cases | Zero, positive-root, negative-discriminant, and no-positive-root outcomes match Section 9.10.6. |
| **TIP-PER-C016** | Multiple available Time To Ball values with a tie | Closest Player chosen by lexicographic ID. |
| **TIP-PER-C017** | Players on density-radius boundaries | Boundary Players are included in all exact counts. |
| **TIP-PER-C018** | Voronoi positions including coincident points | Areas match ordered half-plane construction. |
| **TIP-PER-C019** | Directed same-team pair and opponents on corridor boundary | Corridor, occupancy, obstruction, distance, angle, and aperture match golden values. |
| **TIP-PER-C020** | Three-state lifecycle, visibility, distance, and positions | Persistence, trends, movement, and stability match definitions. |
| **TIP-PER-C021** | Entity has two current position observations | Entity-position features unavailable with `POSITION_AMBIGUOUS`; Observation Position records remain available. |
| **TIP-PER-C022** | Observation-scoped Player motion candidate | Unavailable with `ENTITY_NOT_IDENTIFIED`. |
| **TIP-PER-C023** | Delete dependency definition | `TIP-PER-DEPENDENCY-MISSING`. |
| **TIP-PER-C024** | Introduce dependency cycle | `TIP-PER-DEPENDENCY-CYCLE`. |
| **TIP-PER-C025** | Reference unknown entity | `TIP-PER-ENTITY-REFERENCE-INVALID`. |
| **TIP-PER-C026** | Delete or alter feature provenance | `TIP-PER-PROVENANCE-INCOMPLETE`. |
| **TIP-PER-C027** | Shuffle catalogs and execute concurrently | Feature and artifact ordering remain identical. |
| **TIP-PER-C028** | Repeat execution in fresh processes | Canonical bytes and digest are identical. |
| **TIP-PER-C029** | Available value outside declared range | `TIP-PER-VALUE-INVALID`. |
| **TIP-PER-C030** | Multiple defects | Error selection follows Section 9.16. |
| **TIP-PER-C031** | Canonical serialization of golden output | Bytes and SHA-256 equal published golden artifact. |
| **TIP-PER-C032** | Scan feature codes, names, descriptions, and values | No prohibited semantic output occurs. |

### 9.19 Explicit non-goals

Perception SHALL NOT produce these concepts or textual variants of them: `LINE_BREAK`, `THIRD_MAN`, `OVERLOAD`, `UNDERLOAD`, `ISOLATION`, `PRESS`, `COUNTER_ATTACK`, `POSITIONAL_ATTACK`, `BUILD_UP`, `TACTICAL_PHASE`, `DANGEROUS_SPACE`, `PROGRESSIVE_PASS`, `TACTICAL_OPPORTUNITY`, `THREAT_SCORE`, `EXPECTED_GOALS`, `NARRATIVE`, `EXPLANATION`, and `HYPOTHESIS`.

Perception SHALL NOT classify an event as a pass, shot, carry, action, phase, pattern, primitive, opportunity, or cause. Feature descriptions SHALL remain measurement definitions.

### 9.20 Perception boundary

#### 9.20.1 Semantic-foundation evidence rule

`PLAYER_BALL_DISTANCE` is a neutral Perception measurement with ordered subjects
`(Player, Ball)`. It is the Euclidean distance in metres between the unique
available Player position and unique available Ball position in the same
WorldState, uses the corresponding `PAIR_DISTANCE` record as its sole numeric
dependency, has range `[0, sqrt(105^2 + 68^2)]`, and uses the Chapter 9 numeric
precision. Every in-scope Player produces exactly one record per frame. If the
pair-distance dependency is unavailable, the record SHALL be unavailable with
`DEPENDENCY_UNAVAILABLE`; absence SHALL NOT be classified as distance, control,
freedom, or reachability. This catalogue addition has definition version
`0.1.0` and introduces no threshold.

No ownership, receipt, loss, recovery, action boundary, reachability result, or
temporal relation SHALL be emitted unless every required dependency and every
normative decision is explicitly defined.

Unavailable evidence SHALL produce unavailable output or no concept according
to the relevant contract. It SHALL NOT produce a negative classification unless
the negative is itself proven. In particular, unavailable evidence does not
prove `BALL_FREE`, `PLAYER_CANNOT_REACH_BALL`, or
`PASSING_CORRIDOR_CLOSED`.

The authenticated v0.1 route does not define a controller-selection rule,
control distance or relative-velocity condition, persistence window,
simultaneous-candidate resolution, aerial-ball rule, or sparse-observation
interpolation. It also does not expose source-declared event semantics through
the Perception-to-Recognition contract, and it defines no acceleration, maximum
speed, reaction time, prediction horizon, or ball-trajectory profile for
reachability. Consequently, `BALL_CONTROLLED`, `BALL_FREE`, `BALL_RECEIVED`,
`BALL_RELEASED`, `BALL_LOST`, `BALL_RECOVERED`, `PASS_START`, `PASS_END`,
`CARRY_START`, `CARRY_END`, `SHOT`, `PLAYER_CAN_REACH_BALL`, and
`PLAYER_CANNOT_REACH_BALL` SHALL NOT be emitted by Recognition or Action Graph
under this profile. `PASSING_CORRIDOR_EXISTS` and
`PASSING_CORRIDOR_OBSTRUCTED` retain their existing geometric state semantics;
they SHALL NOT be renamed to open or closed, because those names would assert
football availability beyond the measured corridor occupancy.

Recognition SHALL consume only `PerceptionDataset`. It SHALL NOT directly access WorldModelDataset, SynchronizedDataset, NormalizedDataset, SourceSelection, or raw provider data.

- **TIP-PER-BOUND-001:** Recognition SHALL treat feature values, availability, subjects, times, units, definitions, and provenance as immutable.
- **TIP-PER-BOUND-002:** Recognition SHALL NOT recalculate a Perception feature from World data.
- **TIP-PER-BOUND-003:** A later stage SHALL NOT write a label, score, hypothesis, or interpretation into PerceptionDataset.
- **TIP-PER-BOUND-004:** Any Recognition input read that bypasses PerceptionDataset constitutes non-conformance.

## 10. Primitive Recognition

> **Editorial status:** Not normative in this Working Draft. This chapter becomes normative in Step 4.

Each primitive SHALL define inputs, preconditions, exact detection algorithm, thresholds, confidence algorithm, evidence schema, deterministic identifier, tie-breaking, failure behavior, and fixtures.

## 11. Pattern Recognition

> **Editorial status:** Not normative in this Working Draft. This chapter becomes normative in Step 4.

A pattern SHALL be specified as an ordered or partially ordered composition of primitives, World Model states, and state transitions. Pattern detection SHALL NOT depend on narrative desirability.

## 12. Hypothesis Generation

> **Editorial status:** Not normative in this Working Draft. This chapter becomes normative in Step 5.

This chapter SHALL define candidate generation, admissibility, deduplication, identifiers, and maximum search boundaries.

## 13. Hypothesis Evaluation

> **Editorial status:** Not normative in this Working Draft. This chapter becomes normative in Step 5.

This chapter SHALL define supporting evidence, contradicting evidence, missing evidence, score calculation, ranking, rejection, and uncertainty propagation.

## 14. Causal Chain Construction

> **Editorial status:** Not normative in this Working Draft. This chapter becomes normative in Step 5.

This chapter SHALL define eligible nodes and edges, temporal and causal constraints, chain scoring, selection, ordering, and contradiction handling.

## 15. Explanation Model

> **Editorial status:** Not normative in this Working Draft. This chapter becomes normative in Step 6.

The complete schema, canonicalization rules, invariants, controlled vocabularies, and evidence graph SHALL be specified here. The Explanation Model SHALL contain no presentation instructions.

## 16. Communication Plan

> **Editorial status:** Not normative in this Working Draft. This chapter becomes normative in Step 7.

This chapter SHALL define content selection, learning objective, central question, narrative sequence, claim budget, controlled copy, and Explanation Model traceability.

## 17. Scene Plan

> **Editorial status:** Not normative in this Working Draft. This chapter becomes normative in Step 7.

This chapter SHALL define scenes, timing, cameras, layers, annotations, transitions, source references, and Communication Plan traceability.

## 18. Rendering Contract

> **Editorial status:** Not normative in this Working Draft. This chapter becomes normative in Step 8.

This chapter SHALL define accepted Scene Plan version, output dimensions, frame rate, color space, audio policy, MP4 container and codec requirements, deterministic frame timing, and rendering tolerances. It SHALL NOT prescribe a graphics library.

## 19. Error Handling and Observability

> **Editorial status:** Not normative beyond Sections 2.5, 4.2, 4.4, and 4.5 in this Working Draft.

The final chapter SHALL define the complete error taxonomy, diagnostics schema, stage metrics, provenance log, and prohibited disclosure of implementation-specific state.

## 20. Reproducibility

> **Editorial status:** Not normative in this Working Draft.

The final chapter SHALL define configuration identity, dependency disclosure, random-source prohibition or seeding, numerical environment disclosure, and artifact manifests.

## 21. Versioning and compatibility

Specification versions SHALL use semantic versioning. A change that can alter a conforming observable artifact for an existing fixture is breaking and SHALL increment the major version after version `1.0.0`. Before `1.0.0`, any normative change SHALL increment the minor version. Editorial changes SHALL increment the patch version.

Every artifact SHALL declare its contract version. Unknown major versions SHALL be rejected. Compatibility between different minor versions SHALL NOT be assumed unless explicitly specified.

## 22. Conformance requirements

The official corpus, manifests, comparison classes, tolerances, and reporting format are defined in `CONFORMANCE.md`. A fixture is normative only when its manifest declares this specification version and profile and its integrity hashes validate.

## Appendix A — Editorial completion sequence

This appendix is informative.

1. Scope and end-to-end pipeline — complete for Working Draft 0.1.0.
2. Input Contract — complete; Normalized Data Model, Synchronization, and World Model — pending.
3. Perception.
4. Primitive and Pattern Recognition.
5. Hypothesis Generation, Hypothesis Evaluation, and Causal Chain Construction.
6. Explanation Model.
7. Communication Plan and Scene Plan.
8. Renderer.
9. Acceptance tests and publication of conformance corpus 0.1.
