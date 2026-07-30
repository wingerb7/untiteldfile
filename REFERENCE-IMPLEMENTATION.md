# Tactical Intelligence Reference Implementation

## Implementation Note for Specification 0.1.0

> Status: Informative inventory of the current Python prototype
>
> This document is not normative.

## 1. Purpose

This document maps one concrete implementation to the pipeline defined by `SPEC.md`. It exists to demonstrate implementability, aid development, and identify gaps. It does not define conformance and does not override the specification.

The reference implementation MAY use Python-specific types, libraries, modules, caches, and optimizations. Other conforming implementations need not reproduce those internal choices.

## 2. Current implementation profile

| Property | Current value |
| --- | --- |
| Language | Python |
| Execution mode | Offline |
| Input family | StatsBomb-derived possession JSON and 360 freeze frames |
| Primary configuration | `config.yaml` |
| Current outputs | Analysis JSON, scene-plan JSON, diagnostic images, and MP4 |
| Conformance status | Not yet conforming; official v0.1 schemas and golden corpus are not published |

No conformance claim SHALL be inferred from the existence or quality of current rendered examples.

## 3. Repository mapping

The current code and artifacts map approximately as follows:

| Specification stage | Current repository location | Gap |
| --- | --- | --- |
| Source ingestion | `ingest.py`, `data/` | Chapter 5 is specified; pinned-revision validation and normative errors are not yet implemented. |
| Normalization | `analysis/normalize.py` | Output schema, error policy, canonicalization, and field contract require specification. |
| Synchronization | `analysis/synchronisation.py` | Only basic nearest-event and video-offset helpers exist. |
| World Model | domain and tracking code under `src/` and `analysis/` | Normative entity schemas and lifecycle rules require specification. |
| Perception | analysis/intelligence modules | Features are not yet published as a complete objective feature contract. |
| Recognition | analysis/intelligence modules | Primitive and pattern boundaries must be separated and specified. |
| Reasoning | analysis/intelligence modules | Generation, evaluation, and chain construction require separate contracts. |
| Explanation Model | JSON files under `renders/` | Current analysis JSON is developmental, not the canonical v0.1 schema. |
| Communication Plan | narrative-selection artifacts under `renders/` | Formal contract is absent. |
| Scene Plan | scene-plan artifacts under `renders/` | Formal contract and equivalence relation are absent. |
| Renderer | `render/`, rendering scripts | MP4 contract and tolerances are absent. |
| Tests | `tests/` | These are implementation tests, not the official conformance suite. |

## 4. Development fixtures already present

The repository contains developmental material for the proposed initial cases:

- Di María / Argentina possession 52: `data/possession_52.json` and related render artifacts;
- Depay: `data/depay_goal.json` and related render artifacts;
- Locatelli: current render and audit artifacts associated with the Italy case.

These assets SHALL NOT become official fixtures merely by being copied into `conformance/`. Each source must first be licensed, provenance-audited, scope-validated, minimized, assigned a fixture manifest, and hashed.

The current `ingest.py` supports both `statsbombpy` and a moving shallow clone of the Open Data repository. Neither behavior is conforming source acquisition for v0.1: a conformance run must use the exact Open Data commit pinned in `SPEC.md`. The implementation also currently flattens and enriches source records before formal validation; this must be separated into Source Validation and Normalization.

The Di María possession is useful development material but its official `play_pattern` is `From Counter`. It is therefore a negative source-scope fixture under v0.1, not a positive positional-attack fixture.

## 5. Reference implementation obligations

To become the official v0.1 reference implementation, this codebase must:

1. implement every normative v0.1 stage contract;
2. expose every conformance boundary without changing normal execution behavior;
3. validate all inputs and outputs against versioned schemas;
4. remove uncontrolled ordering and platform-dependent output;
5. emit canonical artifacts and provenance;
6. implement the official error taxonomy;
7. pass every mandatory positive and negative fixture twice;
8. publish a complete conformance report.

## 6. Configuration discipline

Current thresholds in `config.yaml` are implementation defaults, not specification values. A threshold affects observable behavior and therefore becomes normative only after it is defined in `SPEC.md`, assigned a configuration version, and covered by conformance fixtures.

The reference implementation SHALL eventually accept an immutable versioned conformance configuration. Local overrides MAY exist for experimentation but invalidate a conformance run.

## 7. Change discipline

Development SHALL follow this dependency order:

```text
Normative requirement
        -> schema and fixture
        -> implementation change
        -> implementation tests
        -> conformance run
```

Behavior discovered in code MAY motivate a specification proposal, but it does not become normative until the specification and conformance corpus are versioned accordingly.

## 8. Relationship to the Masterplan

`MASTERPLAN.md` explains the intended system, principles, and long-term architecture. This implementation realizes only the currently supported specification profile. Features described in the Masterplan but excluded from `SPEC.md` v0.1 are future work, not partial conformance failures.
