# MASTERPLAN v1.0

## The Tactical Intelligence Platform

### Architecture, Vision & Engineering Specification

> Status: Complete Draft v1.0 — ready for formal review

---

## Part I — Foundation

### 1. Executive Summary

#### Purpose

The Tactical Intelligence Platform is an AI system designed to transform raw football match data into structured tactical knowledge.

Unlike conventional analytics systems, the platform is not intended to describe football events. Its primary objective is to explain why football events occur.

The system reconstructs the evolving state of a football match, identifies meaningful tactical interactions, evaluates competing explanations, and produces evidence-based narratives that describe the causal mechanisms behind successful and unsuccessful actions.

Video generation is one possible presentation layer. It is not the product itself.

The primary output of the platform is tactical understanding.

#### Problem Statement

Modern football data contains enormous amounts of information. Examples include:

- event feeds
- tracking data
- freeze frames
- broadcast video
- player positions
- ball trajectories
- expected goals
- passing networks

These systems answer questions such as:

- Who passed the ball?
- Where was the shot taken?
- What was the xG?

However, elite coaches rarely think in terms of isolated events. Instead, they think in terms of:

- manipulating defensive structures
- creating numerical superiority
- exploiting space
- triggering rotations
- attracting pressure
- opening passing lanes
- timing movements
- creating advantages

These concepts exist across multiple events and often involve several players acting over several seconds.

Current football analytics provides observations.

Elite analysts produce explanations.

The Tactical Intelligence Platform exists to bridge that gap.

#### Vision

The long-term vision is to build an artificial intelligence system capable of reasoning about football in a manner comparable to an elite tactical analyst.

Rather than detecting isolated football events, the platform continuously models the tactical state of the match and explains how that state evolves over time.

The platform should eventually be capable of answering questions such as:

- Why did this attack succeed?
- Which player created the decisive advantage?
- What defensive mistake enabled the chance?
- Which tactical principle was exploited?
- Which earlier actions made the goal inevitable?
- Which alternative decisions could have prevented the goal?

The objective is not merely prediction.

The objective is understanding.

#### Core Philosophy

The platform is built around one central belief:

> Football is a dynamic system of interacting players, spaces, and intentions—not a sequence of disconnected events.

Every architectural decision follows from this principle.

The system therefore models:

- persistent entities rather than isolated observations;
- evolving tactical states rather than static moments;
- causal relationships rather than chronological lists;
- explanations rather than descriptions.

#### System Overview

At the highest level, the platform consists of seven architectural layers:

```text
Football Match
      │
      ▼
Football World Model
      │
      ▼
Tactical Intelligence Engine
      │
      ▼
Causal Reasoning & Hypothesis Evaluation
      │
      ▼
Explanation Model
      │
      ▼
Didactic Engine
      │
      ▼
Renderer
```

Each layer has a single responsibility. No layer may assume responsibilities belonging to another.

This strict separation enables the independent development, testing, and future replacement of individual components.

#### Architectural Principles

##### Separation of Concerns

Each component performs exactly one class of responsibilities.

The Renderer renders.

The Didactic Engine plans.

The Tactical Intelligence Engine recognizes tactical concepts and patterns.

The Causal Reasoning & Hypothesis Evaluation layer determines which findings explain the outcome.

The Football World Model represents reality.

No component should perform work belonging to another layer.

##### Evidence-Based Reasoning

Every tactical conclusion must be supported by observable evidence.

The platform distinguishes between:

- observed facts;
- detected patterns;
- inferred relationships;
- hypothetical explanations.

Confidence must always reflect the strength of the available evidence.

##### Explainability First

Producing correct conclusions is insufficient. Every conclusion must also be explainable.

The platform therefore records not only what it concluded, but also why that conclusion was reached and which evidence supported it.

##### Deterministic Core

Where possible, the tactical reasoning pipeline should remain deterministic.

Deterministic reasoning improves:

- reproducibility;
- debugging;
- validation;
- scientific credibility.

Probabilistic or learned models may extend the platform but should not replace deterministic reasoning without demonstrable benefit.

##### Intelligence Before Presentation

Presentation is downstream of intelligence.

Visualizations must never introduce tactical conclusions that were not generated by the intelligence layer.

If the reasoning layers cannot explain an action, the Renderer must not invent an explanation.

#### Primary Artifact

A key architectural decision is that the primary product of the platform is not the rendered video.

Instead, the primary artifact is the Explanation Model.

The Explanation Model contains:

- tactical findings;
- causal chains;
- supporting evidence;
- competing hypotheses;
- confidence estimates;
- narrative structure.

Every downstream output—including videos, reports, dashboards, and interactive applications—must be derived exclusively from this artifact.

This guarantees consistency across all presentation formats.

#### Long-Term Scope

Although the initial implementation focuses on attacking possessions leading to goals, the architecture is intentionally designed for broader application.

Future extensions include:

- defensive organization;
- pressing systems;
- transition analysis;
- set pieces;
- player development;
- opponent scouting;
- recruitment support;
- automated coaching assistants;
- multimodal video reasoning;
- live tactical analysis.

These capabilities should emerge by extending existing architectural components rather than redesigning the platform.

#### Intended Audience

This document is written for:

- software architects;
- AI researchers;
- football analysts;
- data scientists;
- computer vision engineers;
- future contributors to the Tactical Intelligence Platform.

It defines the long-term architectural direction of the platform.

Implementation details, programming languages, frameworks, and optimization strategies are intentionally excluded unless they materially affect architectural decisions.

#### Document Status

This document serves as the architectural source of truth for the Tactical Intelligence Platform.

All future implementations should derive from the architecture described herein.

Where an implementation conflicts with the Masterplan, the Masterplan takes precedence until formally revised.

### 2. Terminology & Normative Language

#### Purpose

This chapter establishes the foundational vocabulary and normative language used throughout the Masterplan.

Terms defined here have one canonical meaning. Component-specific chapters may refine a term but MUST NOT contradict its definition here.

#### Foundational Terms

| Term | Canonical Meaning |
| --- | --- |
| Observation | A time-bound measurement or assertion received from a data source, accompanied by provenance and confidence. |
| Observable Fact | An observation, or a deterministic derivation from observations, represented without tactical interpretation. |
| Entity | A persistent object with identity and state, such as a player, ball, team, possession, or space. |
| State | The values and relationships that are true for a set of entities at a particular time. |
| World State | The coherent, time-indexed representation of match reality maintained by the Football World Model. |
| Evidence | One or more traceable facts used to support or contradict a tactical claim. |
| Tactical Concept | A canonically defined football idea within the Tactical Ontology. |
| Detection | A claim that available evidence satisfies the definition of a tactical concept. |
| Finding | A structured, evidence-linked result produced by a detector or reasoning process. |
| Hypothesis | A candidate explanation that connects findings and state transitions to an outcome. |
| Confidence | A calibrated expression of evidential support and uncertainty, never a substitute for evidence. |
| Causal Chain | An ordered dependency structure describing how state changes contributed to an outcome. |
| Explanation | The selected, evidence-supported account of why an outcome occurred, including uncertainty and alternatives. |
| Explanation Model | The immutable, authoritative knowledge artifact produced after causal reasoning and hypothesis evaluation. |
| Communication Plan | A presentation-neutral learning path derived from an Explanation Model by the Didactic Engine. |
| Scene Plan | A video-oriented serialization of a Communication Plan produced by the Scene Planner implementation. |
| Render Instructions | Deterministic visual execution instructions derived from a Scene Plan. |

#### Critical Distinctions

The following distinctions MUST remain explicit:

- An observation is not an interpretation.
- A detection is not an explanation.
- Confidence is not evidence.
- Chronology is not causality.
- A World State is not a tactical judgment.
- A Communication Plan or Scene Plan is not a source of tactical intelligence.
- A rendered output is not the authoritative knowledge artifact.

#### Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be interpreted as described by RFC 2119 when they appear in uppercase.

- **MUST** and **SHALL** define mandatory requirements.
- **MUST NOT** and **SHALL NOT** define absolute prohibitions.
- **SHOULD** defines a strong recommendation whose exceptions require documented rationale.
- **SHOULD NOT** defines a discouraged choice whose use requires documented rationale.
- **MAY** defines a permitted but optional capability.

Lowercase uses of these words are descriptive rather than normative.

#### Requirement Identification

Normative requirements SHOULD be testable through automated tests, schema validation, architectural checks, or documented review.

An exception to a normative requirement MUST be recorded as an Architectural Decision Record and MUST describe its scope, rationale, consequences, and intended resolution.

#### Chapter Summary

This terminology provides a stable language for representation, reasoning, explanation, and presentation.

By separating facts from interpretations and recommendations from requirements, the Masterplan remains precise, testable, and resistant to semantic drift.

### 3. Vision & Mission

#### Purpose

This chapter defines the long-term purpose of the Tactical Intelligence Platform.

It establishes why the platform exists, which problems it solves, and which design philosophy governs every architectural decision.

All subsequent chapters derive from the principles defined herein.

#### Vision

##### Long-Term Vision

The Tactical Intelligence Platform aims to become an artificial intelligence system capable of understanding football as a continuously evolving tactical system rather than as a sequence of isolated events.

The platform SHALL reconstruct the state of a football match, reason about the interactions between players and space, identify the tactical mechanisms that influence outcomes, and communicate those mechanisms through structured explanations.

Its ultimate objective is not merely to identify what happened, but to explain why it happened.

In doing so, the platform seeks to replicate the reasoning process of an elite tactical analyst while maintaining the consistency, scalability, and reproducibility of software.

##### Beyond Event Analytics

Most existing football analytics systems are fundamentally event-centric.

They answer questions such as:

- Who completed the pass?
- Where was possession lost?
- How many progressive carries occurred?
- What was the expected goals value?

These observations are valuable but inherently descriptive.

Elite tactical analysis operates at a different level of abstraction.

Analysts seek to understand:

- how defensive structures were manipulated;
- why numerical superiority emerged;
- which movement created space;
- which player attracted pressure;
- why passing lanes appeared;
- how multiple actions combined into a successful attack.

These explanations cannot be derived from individual events in isolation. They require reasoning across time, space, and relationships.

The Tactical Intelligence Platform is designed specifically to perform that reasoning.

#### Mission

The mission of the platform is to transform raw football data into explainable tactical knowledge.

This transformation occurs through four successive stages.

##### Stage 1 — Observe

Collect objective information from one or more data sources.

Examples include:

- event data;
- tracking data;
- freeze frames;
- broadcast video;
- future multimodal inputs.

No tactical interpretation occurs during this stage. The platform simply records observations.

##### Stage 2 — Understand

Construct a coherent representation of the current football state.

This includes:

- player positions;
- ball state;
- spatial occupation;
- team structure;
- relationships;
- temporal continuity.

The result is the Football World Model.

##### Stage 3 — Reason

Infer tactical meaning from the evolving world model.

Examples include:

- overloads;
- isolations;
- line-breaking actions;
- rotations;
- third-man combinations;
- pressing traps;
- defensive collapses;
- transition opportunities.

Multiple competing explanations may coexist during this stage.

Reasoning remains evidence-driven throughout.

##### Stage 4 — Explain

Generate a structured explanation describing:

- what happened;
- why it happened;
- which evidence supports the conclusion;
- which hypotheses were rejected;
- how the explanation should be communicated.

This Explanation Model becomes the authoritative output of the platform.

All presentation layers derive exclusively from this artifact.

#### Scope

The Tactical Intelligence Platform is intentionally designed as a general football reasoning system.

The architecture is not limited to:

- goals;
- assists;
- attacking possessions;
- professional football;
- StatsBomb data.

The same reasoning framework should eventually support:

- defensive analysis;
- pressing behavior;
- transition phases;
- counterattacks;
- build-up structures;
- set pieces;
- youth development;
- recruitment analysis;
- opponent scouting;
- training feedback;
- live tactical analysis.

The architecture therefore prioritizes generality over short-term optimization.

#### Non-Goals

Equally important is defining what the platform is not intended to become.

##### A Video Generator

Video production is a downstream presentation capability.

The Renderer is intentionally separated from tactical reasoning.

##### An Animation Engine

Animations communicate conclusions.

They do not generate conclusions.

##### An Event Detector

Event detection is one input into tactical reasoning.

It is not the end product.

##### A Statistics Dashboard

Statistics describe performance.

The platform explains tactical mechanisms.

##### A Large Language Model

Large language models may assist explanation generation in future iterations.

However, tactical understanding MUST originate from structured reasoning rather than language generation alone.

#### Fundamental Belief

Every architectural decision is derived from a single foundational assumption:

> Football is a continuously evolving system of interacting players, spaces, relationships, and intentions.

Consequently, football cannot be understood by analyzing isolated events.

Instead, understanding emerges from modeling how the state of the game evolves over time.

This principle governs every component of the architecture.

#### Design Objectives

The platform pursues several primary objectives.

##### Explainability

Every tactical conclusion SHALL be explainable.

The system MUST expose the evidence supporting each conclusion.

##### Transparency

The platform SHALL distinguish clearly between:

- observations;
- detections;
- inferences;
- hypotheses;
- explanations.

A conclusion MUST NOT conceal its level of certainty.

##### Reproducibility

Given identical input data, the platform SHALL produce identical reasoning outputs.

This enables:

- validation;
- debugging;
- benchmarking;
- scientific comparison.

##### Extensibility

New tactical concepts SHOULD be introduced by extending the ontology and reasoning engine rather than modifying unrelated architectural components.

##### Modularity

Each architectural component SHALL maintain a single, clearly defined responsibility.

Components SHOULD communicate exclusively through well-defined interfaces.

##### Domain Independence

Although the first implementation targets football, the underlying reasoning architecture SHOULD avoid assumptions that unnecessarily restrict future extensions.

Where possible, tactical reasoning SHOULD be expressed through generic concepts such as:

- entities;
- state transitions;
- spatial relationships;
- causal interactions;
- evidence aggregation.

Football-specific terminology SHOULD reside within the Tactical Ontology rather than the architectural foundation.

#### Success Definition

The platform succeeds when it can consistently generate explanations that a knowledgeable football analyst recognizes as:

- tactically correct;
- logically coherent;
- evidence-based;
- reproducible;
- more informative than a simple description of events.

Success is therefore measured by the quality of understanding rather than the sophistication of visualization.

#### Chapter Summary

The Vision and Mission establish the identity of the Tactical Intelligence Platform.

The platform exists to transform football data into structured tactical understanding through observation, world modeling, reasoning, and explanation.

Every subsequent architectural decision should reinforce this objective.

### 4. Guiding Principles

#### Purpose

The Guiding Principles define the immutable architectural philosophy of the Tactical Intelligence Platform.

Unlike implementation details, algorithms, or technologies, these principles are expected to remain stable throughout the lifetime of the platform.

Every architectural decision, implementation choice, research direction, and future extension SHOULD be evaluated against these principles.

If a proposed feature violates one or more Guiding Principles, the architecture—not the principle—should be reconsidered.

#### Principle 1 — Explain, Don't Describe

The platform exists to explain football.

It does not exist to enumerate events.

Descriptive systems answer questions such as:

- What happened?
- Who touched the ball?
- Where was the pass completed?

Explanatory systems answer questions such as:

- Why did this attack succeed?
- Which tactical advantage emerged?
- Which earlier action made the outcome possible?
- Which player created that advantage?

Descriptions are observations.

Explanations are causal models.

The Tactical Intelligence Platform prioritizes explanations.

#### Principle 2 — Intelligence Before Presentation

Understanding MUST always precede visualization.

The Renderer has no tactical knowledge.

The Didactic Engine has no tactical reasoning.

Presentation components communicate conclusions produced elsewhere. They never create conclusions.

This separation ensures that videos, reports, dashboards, and APIs all communicate exactly the same tactical understanding.

Presentation MUST NOT become a source of intelligence.

#### Principle 3 — Evidence Before Inference

Every conclusion MUST be traceable to evidence.

Evidence may include:

- observed player positions;
- verified tracking;
- event sequences;
- freeze-frame observations;
- temporal consistency;
- spatial relationships.

Inference begins only after evidence has been established.

The platform MUST NOT blur the distinction between observation and interpretation.

#### Principle 4 — States Over Events

Football is not fundamentally a sequence of events.

Football is the continuous evolution of a shared state.

Events merely reveal changes within that state.

For example:

```text
Pass
  ↓
Defensive shift
  ↓
Space opens
  ↓
Runner attacks
  ↓
Cutback
  ↓
Goal
```

The goal is not caused by the pass alone. It emerges from the evolution of the tactical state.

Consequently, the Football World Model represents continuously evolving states rather than isolated events.

#### Principle 5 — Causality Over Chronology

Chronological order does not imply tactical importance.

The platform therefore reconstructs causal chains rather than timelines.

Two consecutive events may be tactically unrelated. Conversely, an action occurring several seconds earlier may be the true origin of an attack.

Reasoning SHOULD therefore answer:

> Which actions changed the tactical state?

rather than:

> Which actions happened first?

#### Principle 6 — Explicit Uncertainty

Football is inherently uncertain.

The platform SHALL NOT present uncertain conclusions as established facts.

Every inference SHOULD expose:

- supporting evidence;
- confidence;
- competing explanations;
- unresolved ambiguity.

Users should always understand not only what the system believes, but also how strongly it believes it.

#### Principle 7 — Separation of Responsibilities

Each architectural component owns exactly one responsibility.

| Component | Responsibility |
| --- | --- |
| Football World Model | Represent reality |
| Tactical Intelligence Engine | Recognize tactical concepts and patterns |
| Causal Reasoning & Hypothesis Evaluation | Determine explanatory relevance |
| Explanation Model | Record understanding |
| Didactic Engine | Plan communication |
| Renderer | Produce visual output |

No component SHOULD duplicate the responsibility of another.

#### Principle 8 — Generic Before Hardcoded

The architecture SHOULD model tactical principles rather than specific football patterns.

Poor abstraction:

> Detect the Italy–Switzerland Locatelli goal.

Good abstraction:

> Detect a wide overload followed by a cutback into Zone 14.

Specific football situations SHOULD emerge naturally from generic reasoning.

This enables the platform to analyze:

- any team;
- any league;
- any tactical system;
- future tactical innovations.

#### Principle 9 — The World Exists Independently of the Explanation

The Football World Model represents objective reality.

It does not exist to support a particular explanation.

Multiple explanations may emerge from the same world state.

The Causal Reasoning & Hypothesis Evaluation layer evaluates these competing hypotheses before selecting the most plausible explanation.

Reality is independent of interpretation.

#### Principle 10 — Competing Hypotheses

The first plausible explanation is rarely sufficient.

The platform SHOULD actively generate alternative explanations.

For example, a goal may have been scored because of:

- **Hypothesis A:** a wide overload;
- **Hypothesis B:** a third-man combination;
- **Hypothesis C:** a defensive communication failure.

Each hypothesis SHOULD compete for the available evidence.

The selected explanation SHOULD be the one best supported by observable facts.

#### Principle 11 — Determinism by Default

Where practical, reasoning SHOULD remain deterministic.

Deterministic systems provide:

- reproducibility;
- explainability;
- benchmarkability;
- easier debugging.

Machine learning SHOULD augment deterministic reasoning rather than replace it without clear evidence of superior performance.

#### Principle 12 — Intelligence Is Domain Knowledge

The platform's intelligence resides in structured football knowledge.

Not in animations.

Not in prompts.

Not in rendering.

Knowledge SHOULD exist independently of any presentation format.

This allows the same understanding to power:

- coaching reports;
- scouting tools;
- educational videos;
- interactive applications;
- future AI assistants.

#### Principle 13 — Every Conclusion Must Be Reproducible

Given identical inputs, the platform SHALL produce identical outputs.

This includes:

- tactical findings;
- causal chains;
- confidence estimates;
- Explanation Models.

Scientific reproducibility is essential for trust and validation.

#### Principle 14 — The Explanation Model Is the Product

The Renderer is not the product.

The animation is not the product.

The graph is not the product.

The product is structured tactical understanding.

That understanding is formalized within the Explanation Model.

Every downstream representation MUST derive exclusively from that Model.

#### Principle 15 — Architecture Before Implementation

Implementation choices are temporary.

Architecture is long-lived.

Programming languages will change.

Libraries will change.

Rendering engines will change.

Reasoning algorithms will improve.

The architecture SHOULD remain sufficiently abstract to accommodate these changes without altering the conceptual model of the platform.

#### Principle 16 — Progressive Constraint Reduction

Every architectural layer reduces the decision space inherited by the next.

- The Football World Model reduces match reality to coherent, objective state.
- The Tactical Intelligence Engine reduces observable state to traceable tactical findings.
- Causal Reasoning & Hypothesis Evaluation reduces competing findings to supported explanations.
- The Explanation Model reduces reasoning into one consistent knowledge representation.
- The Didactic Engine reduces possible explanations into a deliberate learning path.
- The Renderer reduces an approved presentation plan into deterministic output.

Layers do not add uncontrolled complexity. They eliminate ambiguity by making decisions explicit and passing a richer but more constrained representation downstream.

A downstream component SHOULD receive enough resolved information to execute its responsibility without recreating upstream judgment.

#### Architectural Consequences

These principles imply several architectural constraints. The following statements are normative:

- The Renderer SHALL NOT perform tactical reasoning.
- The Didactic Engine SHALL NOT infer tactical concepts.
- The Football World Model SHALL NOT contain subjective interpretations.
- The Tactical Intelligence Engine SHALL operate exclusively on evidence provided by the Football World Model.
- Causal Reasoning & Hypothesis Evaluation SHALL operate exclusively on traceable tactical findings and their evidence.
- Every Explanation SHALL reference supporting evidence.
- Every inference SHALL expose uncertainty.
- Every presentation SHALL derive from the Explanation Model.

Violation of these constraints constitutes an architectural defect rather than an implementation detail.

#### Chapter Summary

The Guiding Principles define the philosophical foundation of the Tactical Intelligence Platform.

They ensure that future development remains consistent, explainable, and scientifically grounded, regardless of future implementation choices or technological advances.

Every subsequent chapter of this Masterplan assumes compliance with these principles.

### 5. Success Criteria

#### Purpose

This chapter defines what success means for the Tactical Intelligence Platform.

No single score can represent system quality. Success MUST be evaluated across the complete chain from reconstruction to communication.

#### Quality Dimensions

##### Reconstruction Quality

The Football World Model accurately represents match reality.

Measures include:

- player and ball localization error;
- identity continuity;
- possession continuity;
- relationship accuracy;
- temporal completeness;
- confidence calibration.

A tactically convincing explanation MUST NOT compensate for an incorrect World State.

##### Tactical Quality

Detected concepts and inferred mechanisms conform to the Tactical Ontology and available evidence.

Measures include:

- primitive precision and recall;
- pattern validity;
- hypothesis coverage;
- causal relevance;
- expert agreement;
- counterexample rejection.

##### Explanation Quality

The Explanation Model provides a coherent and defensible account of the outcome.

Measures include:

- completeness;
- parsimony;
- internal consistency;
- evidence traceability;
- treatment of competing hypotheses;
- uncertainty calibration.

##### Narrative Quality

The explanation can be communicated clearly without distorting its tactical meaning.

Measures include:

- conceptual clarity;
- ordering of decisive mechanisms;
- appropriate emphasis;
- audience suitability;
- information density;
- absence of unsupported claims.

##### Trustworthiness

Users can inspect, reproduce, challenge, and compare system outputs.

Measures include:

- deterministic reproducibility;
- provenance completeness;
- auditability;
- failure transparency;
- benchmark stability;
- expert-review outcomes.

#### Evaluation Matrix

| Dimension | Primary Artifact | Evaluation Method |
| --- | --- | --- |
| Reconstruction | World State | Geometric, temporal, and identity benchmarks |
| Tactical | Findings and hypotheses | Labeled examples, counterexamples, and expert review |
| Explanation | Explanation Model | Structural checks, causal review, and traceability audits |
| Narrative | Communication Plan and medium-specific derivative | Comprehension and fidelity review |
| Trustworthiness | Complete pipeline | Reproduction, calibration, provenance, and regression tests |

#### Acceptance Principle

A release MUST meet minimum thresholds in every quality dimension.

Strong rendering or narrative quality MUST NOT mask deficiencies in reconstruction, reasoning, or evidence.

Thresholds MAY evolve by release and use case, but their definitions, benchmark versions, and results MUST be recorded.

#### Chapter Summary

The platform succeeds when it produces tactically correct, evidence-based, reproducible explanations that communicate more understanding than a chronological description of events.

Quality is therefore multidimensional, independently measurable, and traceable to architectural artifacts.

---

## Part II — Core Architecture

### 6. System Architecture

#### Purpose

This chapter defines the high-level architecture of the Tactical Intelligence Platform.

It specifies the primary architectural components, their responsibilities, the direction of information flow, and the contractual boundaries between components.

The architecture is intentionally layered.

Each layer transforms information into a representation with a higher level of semantic understanding.

Raw observations become tactical knowledge through successive stages of interpretation.

#### Architectural Philosophy

The Tactical Intelligence Platform is designed as a pipeline of increasingly intelligent representations.

Each stage answers a different class of questions.

| Layer | Primary Question |
| --- | --- |
| Football Data | What was observed? |
| Football World Model | What is happening? |
| Tactical Intelligence Engine | Which tactical concepts and patterns are present? |
| Causal Reasoning & Hypothesis Evaluation | Which findings actually explain the outcome? |
| Explanation Model | What is the best explanation? |
| Didactic Engine | How should this be communicated? |
| Renderer | How should this be visualized? |

No component may answer questions belonging to another layer.

#### High-Level Architecture

```text
                    ┌─────────────────────────────┐
                    │        Football Data        │
                    │─────────────────────────────│
                    │ Events                      │
                    │ Tracking                    │
                    │ Freeze Frames               │
                    │ Broadcast Video             │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │    Football World Model     │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ Tactical Intelligence Engine│
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ Causal Reasoning &          │
                    │ Hypothesis Evaluation       │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │     Explanation Model      │
                    └──────────────┬──────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  │                                 │
                  ▼                                 ▼
            Didactic Engine                    Other Consumers
                  │                         Reports, APIs,
                  ▼                         Coaching Tools,
              Renderer                      and Dashboards
                  │
                  ▼
                Video
```

The architecture deliberately positions the Explanation Model as the central product of the platform.

All presentation layers consume this artifact. None generate tactical understanding themselves.

#### Information Hierarchy

Every architectural layer increases semantic abstraction.

```text
Raw Data
   ↓
Observed Facts
   ↓
World State
   ↓
Tactical Concepts
   ↓
Tactical Findings
   ↓
Candidate Hypotheses
   ↓
Evaluated Causal Chains
   ↓
Explanation
   ↓
Presentation
```

This hierarchy MUST NOT be reversed.

Presentation components MUST NOT introduce new tactical concepts.

#### Component Responsibilities

##### Football Data Layer

**Responsibility:** Acquire objective observations.

Examples include:

- event feeds;
- tracking coordinates;
- freeze frames;
- broadcast imagery;
- future sensor inputs.

This layer performs no tactical interpretation. It merely provides evidence.

##### Football World Model

**Responsibility:** Maintain the complete evolving state of the football match.

The Football World Model transforms observations into persistent entities.

Examples include:

- players;
- the ball;
- teams;
- space;
- formations;
- relationships;
- possession;
- temporal continuity.

The Football World Model answers:

> What is currently true?

It does not answer:

> Why?

##### Tactical Intelligence Engine

**Responsibility:** Recognize tactical concepts and patterns in the evolving world.

Its responsibilities include:

- tactical primitive detection;
- tactical state transitions;
- spatial reasoning;
- temporal reasoning;
- evidence-linked finding generation.

This component transforms objective evidence into structured tactical recognition.

##### Causal Reasoning & Hypothesis Evaluation

**Responsibility:** Determine which tactical findings materially explain the outcome.

Its responsibilities include:

- causal-importance estimation;
- hypothesis construction and competition;
- supporting and contradicting evidence evaluation;
- confidence estimation;
- narrative compression;
- accepted and rejected explanation selection.

This component transforms tactical recognition into tactical understanding.

##### Explanation Model

**Responsibility:** Record the platform's understanding.

The Explanation Model is immutable.

Once generated, it represents the official explanation of the analyzed possession.

It contains:

- findings;
- evidence;
- causal chains;
- rejected hypotheses;
- uncertainty;
- narrative intent.

No downstream component may modify tactical conclusions.

##### Didactic Engine

**Responsibility:** Transform understanding into communication.

Examples include:

- learning objectives;
- narrative ordering;
- emphasis and omission;
- pacing;
- audience adaptation;
- cognitive-load management.

The Didactic Engine receives tactical meaning but creates no tactical meaning.

##### Renderer

**Responsibility:** Convert a medium-specific presentation plan into output.

The Renderer performs:

- drawing;
- interpolation;
- animation;
- video encoding;
- compositing.

The Renderer has no knowledge of football.

#### Layer Interfaces

Every component communicates through explicit interfaces.

```text
Football Data
      ↓
World Model Object Graph
      ↓
Tactical Findings
      ↓
Evaluated Hypotheses and Causal Chains
      ↓
Explanation Model
      ↓
Communication Plan
      ↓
Scene Plan
      ↓
Render Instructions
```

Each interface forms a contractual boundary.

Replacing a component SHOULD NOT require modifying unrelated layers, provided that the interface contract remains unchanged.

#### Dependency Rules

Dependencies SHALL flow in one direction only.

```text
Renderer
  SHALL NOT call
      ↓
Tactical Intelligence Engine or Causal Reasoning

Didactic Engine
  SHALL NOT modify
      ↓
Explanation Model

Explanation Model
  SHALL NOT modify
      ↓
Football World Model
```

This prevents circular dependencies and ensures reproducibility.

#### Architectural Constraints

The following constraints are normative:

- The Football World Model SHALL NOT perform tactical reasoning.
- The Tactical Intelligence Engine SHALL NOT render.
- The Tactical Intelligence Engine SHALL produce traceable tactical findings rather than final explanations.
- Causal Reasoning & Hypothesis Evaluation SHALL consume only traceable tactical findings and their underlying evidence.
- The Explanation Model SHALL be immutable after publication.
- The Didactic Engine SHALL consume but never modify tactical understanding.
- The Renderer SHALL operate exclusively on Render Instructions derived from a medium-specific plan that traces back to a Communication Plan.
- Tactical conclusions SHALL NOT bypass the Explanation Model.

#### Design Rationale

The architecture intentionally places the Explanation Model between reasoning and presentation.

This decision offers several advantages.

##### Multiple Outputs

The same tactical understanding can produce:

- social media videos;
- coaching reports;
- scouting summaries;
- interactive dashboards;
- API responses;
- future conversational interfaces.

All remain consistent because they originate from a shared explanation.

##### Easier Validation

Reasoning can be validated independently of rendering.

Engineers may inspect Explanation Models without generating videos.

##### Easier Research

Researchers may improve tactical reasoning without modifying rendering.

Likewise, visual designers may improve presentation without risking tactical correctness.

##### Long-Term Evolution

New presentation formats can be added without altering the intelligence layer.

Similarly, future reasoning algorithms can improve explanations without requiring changes to downstream consumers.

#### Architectural Invariants

The following statements SHOULD remain true regardless of future implementation:

- Reality is represented by the Football World Model.
- Tactical recognition exists within the Tactical Intelligence Engine.
- Explanatory judgment exists within Causal Reasoning & Hypothesis Evaluation.
- Knowledge is formalized in the Explanation Model.
- Communication is planned by the Didactic Engine.
- Rendering produces pixels and nothing more.

These invariants define the identity of the platform.

Any future architecture that violates them SHOULD be considered a fundamentally different system rather than an evolution of the current platform.

#### Chapter Summary

The System Architecture establishes a layered pipeline in which each component owns a single responsibility and communicates through well-defined interfaces.

By treating the Explanation Model as the central artifact and enforcing strict separation between representation, reasoning, and presentation, the architecture remains modular, testable, extensible, and scientifically reproducible.

### 7. Football World Model

#### Purpose

The Football World Model is the authoritative digital representation of the current state of a football match.

It transforms fragmented observations originating from events, tracking data, freeze frames, and future data sources into a coherent representation of football reality.

The Football World Model is not an analysis.

It is not an explanation.

It is not an interpretation.

Its sole responsibility is to answer one question:

> What is currently true about the football match?

Every subsequent reasoning process depends exclusively on the accuracy and completeness of this representation.

#### Design Philosophy

Football is not a collection of events.

Football is a continuously evolving dynamic system.

At every instant, a current state exists consisting of:

- twenty-two players;
- one ball;
- available space;
- occupied space;
- team structures;
- player relationships;
- tactical constraints;
- temporal momentum.

Events merely expose changes in that state.

Consequently, the platform models the state itself rather than the events that generated it.

#### World State

At every timestamp, the Football World Model represents a complete snapshot of football reality.

Conceptually:

```text
World State(t)
    =
Players
    +
Ball
    +
Space
    +
Teams
    +
Relationships
    +
Possession
    +
Temporal Context
```

Each component evolves continuously over time.

Together, they define the complete tactical environment from which reasoning emerges.

#### Core Design Principle

The Football World Model represents facts.

Not opinions.

Not tactical conclusions.

Not explanations.

Examples of valid facts include:

- Player A occupies coordinate `(34.2, 18.9)`.
- Player B is the nearest defender.
- Team X controls possession.
- The distance between two players is `4.3 m`.
- A passing lane exists.

Examples of invalid interpretations include:

- A defensive overload was created.
- The movement was excellent.
- The player occupied a clever position.
- The attack was dangerous.

The latter belong to the Tactical Intelligence Engine.

#### World Entities

Everything represented within the Football World Model is an Entity.

Entities persist over time. They have identity, possess state, and evolve continuously.

The platform initially defines the following entity types.

##### Player

A Player represents a football player throughout the match.

Attributes include:

- unique identity;
- team;
- position;
- velocity;
- acceleration;
- orientation;
- visibility;
- confidence;
- lifecycle state.

A player remains the same entity even when temporarily invisible.

Identity is independent of observation.

##### Ball

The Ball represents the football.

Unlike players, the Ball possesses additional attributes such as:

- owner;
- velocity;
- trajectory;
- height in future implementations;
- possession uncertainty.

Future implementations may distinguish between controlled and uncontrolled ball states.

##### Team

A Team represents a collection of players acting collectively.

The Team entity stores:

- formation;
- shape;
- compactness;
- width;
- depth;
- defensive line;
- pressing height.

These values remain descriptive. No tactical interpretation occurs here.

##### Possession

Possession represents a continuous period during which one team controls the ball.

Possessions provide natural temporal boundaries for tactical reasoning.

Future implementations may support nested possessions:

```text
Possession
    ↓
Attacking Phase
    ↓
Combination
    ↓
Chance Creation
    ↓
Finish
```

##### Space

Space is treated as a first-class entity.

This is one of the defining architectural decisions of the platform.

Most football software models players. Elite analysts reason about space. The platform therefore models both.

Space is not merely the background against which players move. Players and the ball continuously alter its state by creating, closing, opening, contesting, and exploiting it.

Space may possess properties including:

- occupied;
- free;
- contested;
- accessible;
- hidden;
- reachable;
- threatened.

Later reasoning layers may interpret these properties tactically.

The Football World Model merely records them.

#### Relationships

Football cannot be understood through isolated entities.

The Football World Model therefore stores relationships explicitly.

Relationship types include:

- Player ↔ Ball;
- Player ↔ Player;
- Player ↔ Space;
- Team ↔ Space;
- Team ↔ Team;
- Ball ↔ Space.

Relationships evolve continuously.

Examples include:

- nearest teammate;
- nearest opponent;
- passing lane;
- marking distance;
- support distance;
- visibility;
- reachability.

Relationships remain objective. Interpretation occurs later.

#### Temporal Continuity

Football has memory.

The Football World Model therefore preserves continuity across time.

Entities do not disappear simply because a frame is missing. Instead, each entity maintains a lifecycle.

Possible lifecycle states include:

```text
Observed
    ↓
Predicted
    ↓
Temporarily Hidden
    ↓
Recovered
    ↓
Terminated
```

This architecture enables robust reasoning despite incomplete observations.

#### Confidence

Every observable fact carries confidence.

Importantly, confidence belongs to observations—not to tactical conclusions.

Examples include:

| Observation | Confidence |
| --- | ---: |
| Player position | 99% |
| Ball position | 96% |
| Receiver identity | 84% |
| Interpolated location | 71% |
| Missing observation | 32% |

This distinction prevents uncertainty from propagating incorrectly through the reasoning pipeline.

#### State Evolution

The Football World Model is not reconstructed independently for every frame. Instead, it evolves.

Conceptually:

```text
World State(t)
      +
New Observations
      ↓
World State(t+1)
```

This enables:

- continuity;
- interpolation;
- prediction;
- lifecycle management;
- temporal consistency.

#### Spatial Representation

The architecture intentionally avoids representing the football pitch as merely a coordinate system.

Instead, the pitch is treated as a semantic environment.

Rather than representing a position only as:

```text
(42.3, 18.6)
```

the Football World Model should eventually also recognize objective spatial descriptors such as:

- left half-space;
- central lane;
- wide channel;
- penalty area;
- build-up zone;
- zone between lines.

These remain objective spatial descriptors. They are not tactical conclusions.

#### Invariants

The following statements SHALL always remain true:

- The Football World Model SHALL contain only observable or derivable facts.
- The Football World Model SHALL NOT contain tactical interpretations.
- Entity identity SHALL persist independently of visibility.
- Space SHALL be represented explicitly.
- Relationships SHALL be first-class citizens.
- Temporal continuity SHALL be preserved.
- Confidence SHALL be attached to observations.

Violation of these invariants constitutes corruption of the Football World Model.

#### Design Consequences

Separating representation from interpretation provides several important advantages.

##### Reusability

The Football World Model becomes reusable.

Future reasoning engines can operate on the same representation.

##### Debuggability

Errors can be isolated to observation, representation, or reasoning rather than being intertwined.

##### Scientific Validation

Researchers can verify whether the Football World Model accurately represents football reality before evaluating tactical intelligence.

#### Chapter Summary

The Football World Model is the objective memory of the football match.

It stores persistent entities, spatial relationships, temporal continuity, and observable facts while remaining completely free of tactical interpretation.

It provides the foundation upon which all tactical reasoning is built.

### 8. Tactical Ontology

#### Purpose

The Tactical Ontology defines the vocabulary through which the Tactical Intelligence Platform understands football.

It establishes a common language shared by every reasoning component within the platform.

Without a shared ontology, tactical concepts become inconsistent, ambiguous, and impossible to validate.

The ontology therefore provides precise definitions for every tactical concept recognized by the system.

It answers the question:

> What does a tactical concept actually mean?

It intentionally does not answer:

> How is that concept detected?

Detection belongs to the Tactical Intelligence Engine.

#### Why an Ontology?

Football language is inherently ambiguous.

Different coaches may use different terminology for the same tactical behavior.

Examples include:

- Third-Man Run;
- Third-Player Combination;
- Wall Pass;
- Layoff Combination.

Likewise, the same term may describe different tactical ideas depending on the coach, league, or country.

Software cannot reason reliably using ambiguous language.

The platform therefore requires a formal vocabulary.

Every tactical concept SHALL possess a single canonical definition.

Alternative terminology may exist as aliases, but all reasoning refers to one canonical concept.

#### Ontology Design Philosophy

The ontology describes concepts, not algorithms.

For example, the ontology defines what constitutes a Line Break. It does not specify how a Line Break detector should identify one.

This separation ensures that improvements to detection algorithms do not alter the meaning of tactical concepts.

Concept definitions SHOULD remain stable over time.

Detection algorithms SHOULD evolve.

#### Hierarchical Organization

The ontology is organized into multiple conceptual layers.

```text
Football Concept
│
├── Tactical State
├── Tactical Action
├── Tactical Relationship
├── Tactical Transition
├── Tactical Pattern
├── Tactical Function
└── Tactical Outcome
```

This hierarchy reflects increasing levels of abstraction.

#### Tactical States

A Tactical State represents the current tactical condition of the football environment.

States persist over time.

Examples include:

- Compact Block;
- High Defensive Line;
- Numerical Equality;
- Numerical Superiority;
- Isolated Defender;
- Open Half-Space;
- Occupied Half-Space;
- Stable Possession;
- Transitional Phase;
- Rest Defense Established.

States describe the world. They do not describe actions.

#### Tactical Actions

Actions change the tactical state.

Examples include:

- Pass;
- Carry;
- Shot;
- Dribble;
- Cross;
- Clearance;
- Tackle;
- Press;
- Recovery Run.

Actions occur at specific moments.

Their tactical importance depends on how they influence state transitions.

#### Tactical Relationships

Relationships describe interactions between entities.

Examples include:

```text
Player supports Player
Player marks Player
Player pins Defender
Player attracts Defender
Player blocks Lane
Player creates Width
Team controls Space
Team overloads Zone
```

Relationships often persist across multiple actions.

#### Tactical Transitions

Football is fundamentally about changing one tactical state into another.

Transitions therefore occupy a central position within the ontology.

For example:

```text
Compact Defense
      ↓
Wide Overload
      ↓
Open Cutback Lane
```

or:

```text
Controlled Possession
      ↓
Counterpress
      ↓
Transition
      ↓
Chance
```

The platform reasons primarily through these transitions rather than through isolated events.

#### Tactical Patterns

Patterns describe recurring combinations of tactical transitions.

Examples include:

- Third-Man Combination;
- Switch of Play;
- Underlap;
- Overlap;
- Wall Pass;
- Positional Rotation;
- Blindside Run;
- Counterpress Trap.

Patterns emerge from multiple lower-level concepts. They are not primitive observations.

#### Tactical Functions

Every action serves one or more tactical functions.

The same football action may perform different functions in different contexts.

For example, a backward pass may function as:

- recycling possession;
- attracting pressure;
- changing the point of attack;
- increasing numerical superiority;
- delaying transition.

Likewise, a carry may function as:

- progressing the ball;
- fixing defenders;
- opening passing lanes;
- creating overloads;
- drawing pressure.

The ontology therefore separates:

> What happened?

from:

> Why did it happen?

#### Tactical Outcomes

Outcomes represent the consequences of tactical behavior.

Examples include:

- Chance Creation;
- Goal;
- Ball Progression;
- Defensive Recovery;
- Press Broken;
- Space Exploited;
- Defensive Collapse;
- Successful Escape;
- Loss of Control.

Outcomes terminate tactical chains. They do not explain them.

#### Canonical Concept Definition

Every tactical concept SHALL follow the same structure.

The following example defines a Wide Overload.

##### Concept

**Canonical name:** Wide Overload

**Definition:** A tactical state in which the attacking team establishes a local numerical superiority in a wide area of the pitch, increasing the probability of successful progression or penetration.

**Category:** Tactical State

**Preconditions:**

- ball under control;
- wide zone occupied;
- minimum one-player numerical advantage.

**Observable evidence:**

- player positions;
- team assignments;
- spatial occupation.

**Possible tactical functions:**

- create a crossing opportunity;
- isolate the fullback;
- open central space.

**Possible outcomes:**

- successful progression;
- cross;
- cutback;
- switch.

**Aliases:**

- Wing Overload;
- Wide Numerical Superiority.

Every concept follows exactly the same template.

#### Concept Dependencies

Many concepts depend on others.

For example:

```text
Wide Overload
      ↓
Isolated Fullback
      ↓
Defensive Shift
      ↓
Open Half-Space
      ↓
Cutback Lane
      ↓
Chance
```

These dependencies enable hierarchical reasoning.

Higher-level concepts are constructed from lower-level concepts.

#### Ontology Evolution

The ontology is expected to grow continuously.

New concepts SHALL be added by extending the ontology rather than modifying existing definitions.

Existing concept definitions SHOULD remain stable whenever possible.

This enables:

- backward compatibility;
- benchmark stability;
- reproducible research.

#### Architectural Constraints

The following statements are normative:

- The Tactical Ontology SHALL define concepts but SHALL NOT detect them.
- The Tactical Ontology SHALL contain canonical definitions.
- Every tactical concept SHALL belong to exactly one primary category.
- Every concept SHALL expose observable evidence.
- Every concept SHALL expose possible tactical functions.
- Every concept SHALL expose possible outcomes.
- Detection algorithms SHALL reference ontology concepts rather than embedding tactical definitions.

#### Chapter Summary

The Tactical Ontology provides the shared tactical vocabulary of the platform.

It separates definitions from detection, enables consistent reasoning, and ensures that every tactical conclusion is expressed using a formally defined and reusable language.

It forms the semantic foundation upon which the Tactical Intelligence Engine performs all higher-level reasoning.

### 9. Tactical Intelligence Engine

#### Purpose

The Tactical Intelligence Engine transforms objective World States into evidence-linked tactical recognition.

It detects ontology-defined primitives, identifies state transitions, and composes recurring tactical patterns.

It answers:

> Which tactical concepts and patterns are present?

It does not decide which findings explain the outcome. That judgment belongs to Causal Reasoning & Hypothesis Evaluation.

#### Design Philosophy

Football understanding cannot be reduced to a single detector or monolithic reasoning algorithm.

The Tactical Intelligence Engine is therefore a collection of specialized, cooperating reasoning modules. Each module answers a distinct class of questions while preserving a shared evidence model, ontology, and output contract.

This internal separation prevents the Engine from becoming a monolithic object and allows primitive detection, state-transition analysis, and pattern recognition to evolve independently.

#### Inputs and Outputs

The Engine consumes immutable World States, observation provenance, and Tactical Ontology definitions.

It produces:

- evidence-linked tactical findings;
- state transitions;
- detected tactical patterns;
- finding-level confidence;
- a versioned Tactical Findings package.

It MUST NOT modify the Football World Model or produce presentation instructions.

#### Perception Boundary

Objective feature extraction answers, “What can be derived from the reconstructed world?” Tactical reasoning answers, “What does that evidence mean?”

The first responsibility remains logically upstream of the Tactical Intelligence Engine. Player distances, movement vectors, occupied zones, passing-lane geometry, and other objective features SHOULD be exposed by the Football World Model or a dedicated non-interpretive Perception Layer.

This Perception Layer MAY become an explicit top-level component in a future architectural revision. Until then, it is a contractual boundary rather than a license for the Tactical Intelligence Engine to place interpretations inside the Football World Model.

#### Internal Architecture

```text
World States
     ↓
Objective Evidence Interface
     ↓
Tactical Primitive Engine
     ↓
State-Transition Analysis
     ↓
Tactical Pattern Engine
     ↓
Tactical Findings
```

Each stage has an explicit contract and SHOULD be testable independently.

#### Tactical Primitive Engine

Detectors determine whether evidence satisfies an ontology definition.

A detector output MUST include:

- canonical concept identifier;
- involved entities;
- temporal interval;
- supporting and contradicting evidence;
- observation provenance;
- confidence;
- detector version.

Detectors SHALL reference the Tactical Ontology and SHALL NOT embed competing definitions of concepts.

#### State-Transition Analysis

The Engine compares World States to identify meaningful changes in football reality.

Examples include:

- a passing lane opening or closing;
- numerical equality becoming superiority;
- a defender becoming isolated;
- team width expanding;
- possession changing control;
- a previously inaccessible space becoming reachable.

State changes are not automatically causal. They become causal candidates only when connected to evidence and an outcome.

#### Tactical Pattern Engine

Patterns combine primitives and transitions across time.

Pattern construction MUST preserve the lower-level evidence from which the pattern emerged.

The same primitive MAY contribute to multiple patterns, and multiple patterns MAY coexist without immediate selection.

Patterns remain descriptive structures. They do not by themselves establish intent or causality.

#### Evidence Traceability

Every finding preserves its complete derivation from World State facts through primitives and patterns.

The Engine MAY maintain a recognition graph connecting observations, primitives, transitions, and patterns. Causal edges, hypotheses, and explanation selection belong to the downstream Causal Reasoning & Hypothesis Evaluation layer.

#### Hierarchical Recognition

Recognition follows a traceable hierarchy:

```text
Observations
     ↓
Primitives
     ↓
State Transitions
     ↓
Patterns
     ↓
Tactical Findings
```

Higher-order findings SHALL NOT bypass the evidence and lower-order concepts on which they depend.

#### Future Evolution

Specialized recognition modules MAY extend the Engine without changing its external contract.

Candidate modules include defensive-structure recognition, set-piece recognition, pressing-pattern recognition, and player-role recognition.

Modules that infer intent, evaluate counterfactuals, or rank explanations belong downstream in Causal Reasoning & Hypothesis Evaluation.

#### Failure Behavior

The Engine MUST be able to abstain.

When available evidence cannot support a reliable detection, it SHOULD publish uncertainty rather than manufacture a finding.

Failure states include:

- insufficient evidence;
- conflicting observations;
- unsupported ontology concept;
- pattern below its acceptance threshold.

#### Architectural Constraints

- The Engine SHALL reason only over evidence exposed by the Football World Model.
- Every finding SHALL reference a canonical ontology concept.
- Higher-order reasoning SHALL depend on traceable lower-order evidence and concepts.
- Finding confidence SHALL remain explicit and calibrated.
- The Engine SHALL NOT plan scenes or render outputs.
- The Engine SHALL produce Tactical Findings and SHALL NOT publish final explanations.

#### Chapter Summary

The Tactical Intelligence Engine converts reconstructed reality into evidence-based tactical recognition.

Its intelligence emerges through composable detection, state-transition analysis, pattern recognition, and explicit uncertainty. Explanatory judgment remains a separate downstream responsibility.

### 10. Causal Reasoning & Hypothesis Evaluation

#### Purpose

Causal Reasoning & Hypothesis Evaluation transforms tactical recognition into tactical understanding.

It no longer asks which tactical concepts are present. It asks which findings materially influenced the outcome and which explanation is best supported.

The platform MUST distinguish causal dependence from temporal sequence and statistical association.

#### From Recognition to Understanding

A possession may contain many correct findings—such as a Line Break, Width Creation, Overlap, Third-Man Combination, Late Runner, Defensive Shift, and Open Half-Space—without all of them being explanatory.

This layer identifies the subset that mattered, preserves relevant contributing context, and rejects plausible but weakly supported narratives.

#### Causal Unit

The primary causal unit is a state transition, not an event.

An event becomes tactically relevant when it changes relationships, constraints, or accessible space.

```text
Pass
  ↓
Defensive block shifts
  ↓
Space opens
  ↓
Runner attacks the space
  ↓
Cutback lane becomes available
  ↓
Finish
```

Intermediate touches that do not materially alter tactical state MAY be omitted from the causal chain.

#### Causal Importance

Chronological prominence and causal importance are different dimensions.

| Action | Chronological Prominence | Potential Causal Importance |
| --- | --- | --- |
| Safe pass | High | Low |
| Dummy run | Low | High |
| Progressive carry | Medium | Medium |
| Decoy movement | Low | Very high |
| Finish | Final | Context-dependent |

Causal importance estimates how much a finding changed the conditions that enabled or prevented the outcome.

#### Causal Claims

Every causal claim MUST identify:

- a cause or enabling condition;
- the state before the change;
- the state after the change;
- the affected entities and relationships;
- supporting evidence;
- temporal bounds;
- confidence;
- plausible alternatives.

The platform distinguishes direct causes, enabling conditions, contributing factors, and contextual conditions.

#### Hypothesis Construction

Every hypothesis contains four elements:

1. **Claim** — the proposed explanation.
2. **Evidence** — observations, findings, and transitions that support it.
3. **Contradictions** — evidence that weakens or limits it.
4. **Expected consequences** — later state changes that should follow if the hypothesis is correct.

Failure of expected consequences to appear SHOULD reduce confidence.

#### Hypothesis Competition

Multiple hypotheses compete against the same outcome and evidence set.

Evaluation considers:

- explanatory completeness;
- supporting evidence;
- contradictory evidence;
- causal consistency;
- expected consequences;
- unsupported assumptions;
- unnecessary complexity.

Hypotheses MUST NOT be accepted merely because they are individually plausible.

#### Explanation Roles

The evaluated result distinguishes:

- **Primary Cause** — the mechanism with greatest explanatory power;
- **Contributing Factors** — independently supported mechanisms that materially assisted the outcome;
- **Contextual Factors** — conditions that shaped but did not directly drive the chain;
- **Rejected Factors** — candidates insufficiently supported by evidence.

This structure allows multiple valid mechanisms without reducing explanation to either a single winner or an unranked list.

#### Necessity and Sufficiency

Football mechanisms are rarely individually necessary or sufficient.

The Engine SHOULD therefore avoid claims that one action caused an outcome in isolation unless evidence supports that strength of claim.

Explanations SHOULD express contribution precisely: created, enabled, preserved, increased, prevented, or completed.

#### Temporal Scope

A causal chain MAY begin several actions before the visible outcome.

The Engine SHOULD search backward until additional states no longer materially improve the explanation, and SHOULD stop before irrelevant match history enters the chain.

#### Counterevidence and Alternatives

Causal reasoning MUST consider whether:

- the outcome could have occurred without the proposed cause;
- another mechanism explains the same transition;
- contradictory evidence weakens the chain;
- an omitted action better explains the outcome.

Counterfactual simulation MAY strengthen future causal analysis but is not required for initial causal attribution.

Initial implementations MAY approximate counterfactual importance by testing whether removal of a finding breaks necessary transitions in the reconstructed chain.

#### Chain Selection

The preferred chain SHOULD maximize evidential coverage and causal coherence while minimizing unsupported assumptions and unnecessary complexity.

Multiple chains MAY be retained when the evidence does not support a single dominant explanation.

#### Narrative Compression

The layer compresses long possessions into decisive tactical transitions.

Compression MAY remove redundant actions but MUST preserve causal integrity, supporting evidence, contradictory evidence, and uncertainty.

Narrative compression selects explanatory content; the downstream Didactic Engine still decides how that content is taught and communicated.

#### Failure Analysis

The same framework explains unsuccessful actions.

A chain may show that an overload opened a lane, a poor first touch removed the opportunity, and the resulting loss triggered a defensive transition.

Success and failure therefore use the same causal representation.

#### Architectural Constraints

- Chronology SHALL NOT be presented as causality without evidence of state change.
- Causal Reasoning & Hypothesis Evaluation SHALL consume only traceable Tactical Findings and their underlying evidence.
- Every causal edge SHALL reference supporting evidence.
- Every accepted hypothesis SHALL identify supporting and contradicting evidence.
- Uncertainty and alternative chains SHALL remain explicit.
- Causal reasoning SHALL operate on ontology-defined concepts and World State transitions.
- Counterfactual reasoning SHALL remain extensible without modifying recognition stages.
- Presentation components SHALL NOT create or modify causal claims.

#### Chapter Summary

Causal Reasoning & Hypothesis Evaluation transforms a sequence of recognized tactical findings into an explanation of changing tactical conditions.

Its purpose is not to identify what happened next, but to establish which changes made the outcome possible and why.

---

## Part III — Explanation

### 11. Explanation Model

#### Purpose

The Explanation Model is the authoritative knowledge artifact of the Tactical Intelligence Platform.

It records what the platform concluded, why it reached that conclusion, how certain it is, and which alternatives were rejected.

It is the platform's canonical intermediate representation of tactical understanding and its primary output.

#### Design Philosophy

The Explanation Model plays a role comparable to an Abstract Syntax Tree in a compiler.

A compiler does not translate source text directly into every possible output. It first constructs a stable intermediate representation. Likewise, the platform does not connect tactical reasoning directly to a Renderer, dashboard, API, or coaching document.

```text
Causal Reasoning & Hypothesis Evaluation
                  ↓
          Explanation Model
                  ↓
     ┌────────────┼────────────┐
     ↓            ↓            ↓
Didactic Engine   API/Tools   Human Reports
     ↓
  Renderer
```

Reasoning determines what the platform believes. Communication determines how that belief should be presented.

#### Role

The Model forms the contractual boundary between intelligence and presentation.

Every video, dashboard, API response, coaching report, or conversational explanation MUST derive from it.

Downstream consumers MAY select, summarize, or visualize its content but MUST NOT introduce new tactical claims.

#### Core Structure

Conceptually, the Explanation Model contains:

```text
Context
   ↓
Tactical Summary
   ↓
Evidence and Findings
   ↓
State Transitions and Causal Chains
   ↓
Accepted, Alternative, and Rejected Explanations
   ↓
Confidence and Uncertainty
   ↓
Narrative Intent and Presentation Metadata
```

#### Match Context

Context identifies the competition, match, teams, score, match time, possession, attacking direction, and analyzed interval.

It carries no tactical interpretation.

#### Tactical Summary

The Tactical Summary is a concise, presentation-independent statement of the accepted explanation.

It acts as the executive summary of the Model and MUST remain consistent with its detailed evidence, hypotheses, and causal chains.

#### Required Structure

Every Explanation Model MUST contain:

- model and schema version;
- match, possession, and temporal identifiers;
- input provenance;
- relevant World State references;
- tactical findings;
- accepted hypothesis or hypotheses;
- causal chain or chains;
- supporting and contradicting evidence;
- rejected hypotheses with reasons;
- confidence and uncertainty;
- narrative intent;
- generation metadata.

#### Finding Record

Each finding MUST reference its canonical ontology concept, involved entities, temporal interval, evidence, detector version, and confidence.

#### Causal Chain Record

Each causal node represents a fact, finding, or state transition. Each causal edge states the proposed dependency and cites its evidence.

The chain MUST distinguish direct causes, enabling conditions, contributions, and outcomes.

#### Hypothesis Record

Accepted and rejected hypotheses share the same schema so they can be compared consistently.

A rejection record MUST explain whether the cause was insufficient evidence, contradictory evidence, inferior coverage, lower causal coherence, or excessive assumptions.

Accepted hypotheses SHOULD be classified as Primary Cause, Contributing Factor, or Contextual Factor. Alternative and rejected hypotheses MUST remain available for inspection.

#### Confidence Hierarchy

Confidence exists independently at multiple levels:

```text
Observation Confidence
         ↓
Primitive Confidence
         ↓
Pattern Confidence
         ↓
Hypothesis Confidence
         ↓
Explanation Confidence
```

The Model MUST preserve these values separately rather than collapsing them into one opaque score.

#### Narrative Intent

Narrative intent describes what should be communicated, not how it should be rendered.

It MAY define:

- primary teaching objective;
- decisive tactical mechanism;
- supporting mechanisms;
- intended audience;
- required caveats;
- recommended emphasis.

Camera movements, colors, animation timing, and layout SHALL NOT appear in the Explanation Model.

#### Presentation Metadata

The Model MAY contain presentation-agnostic hints such as target audience, recommended duration range, conceptual complexity, or visual density.

These hints assist consumers but SHALL NOT prescribe renderer-specific implementation.

#### Model Properties

Every Explanation Model MUST be:

- **Deterministic** — identical inputs and component versions produce identical Models;
- **Traceable** — every conclusion links to evidence;
- **Immutable** — downstream systems cannot modify a published Model;
- **Domain-aware** — it represents tactical meaning rather than raw computation;
- **Presentation-agnostic** — it contains no renderer-specific instructions.

#### Immutability and Versioning

A published Explanation Model SHALL be immutable.

Improved reasoning produces a new Model with a new identifier and explicit lineage to the superseded Model.

Schema migrations MUST preserve semantic meaning and auditability.

#### Minimal Conceptual Example

```yaml
model_id: explanation-001
schema_version: 1.0
subject:
  match_id: match-001
  possession_id: possession-042
primary_explanation:
  concept: wide_overload
  confidence: 0.86
  evidence_refs: [evidence-12, evidence-18]
causal_chain:
  - from: defensive_shift
    to: open_cutback_lane
    relation: enabled
rejected_hypotheses:
  - concept: individual_error
    reason: insufficient_evidence
narrative_intent:
  objective: explain_how_width_created_the_cutback
```

This example is illustrative; normative schemas belong in the Appendix.

#### Architectural Constraints

- The Explanation Model SHALL constitute the primary output of the Tactical Intelligence Platform.
- The Model SHALL contain no unsupported tactical claims.
- Every conclusion SHALL be traceable to evidence.
- Every explanation SHALL expose confidence.
- Alternative and rejected hypotheses, together with uncertainty, SHALL be preserved.
- Published Models SHALL be immutable and versioned.
- Presentation details SHALL remain downstream.
- Presentation systems SHALL consume but SHALL NOT modify the Model.
- No tactical reasoning SHALL occur after Model generation.
- No tactical conclusion SHALL bypass the Model.

#### Design Consequences

Treating the Explanation Model as the canonical tactical artifact separates reasoning completely from visualization, guarantees consistent understanding across presentation formats, enables validation without rendering, and allows new consumers to be added without modifying the intelligence pipeline.

#### Chapter Summary

The Explanation Model formalizes tactical understanding in a durable, auditable, and presentation-independent form.

It is the product from which all downstream experiences are derived.

### 12. Didactic Engine

#### Purpose

The Didactic Engine translates an Explanation Model into a deterministic communication plan.

It decides how established tactical understanding should be sequenced and emphasized without generating or modifying that understanding.

Its purpose is not to summarize the analysis. Its purpose is to construct a deliberate learning path for a defined audience.

#### Design Philosophy

Understanding and communication are separate cognitive tasks.

The Didactic Engine fulfills the role of a teacher: it receives complete tactical understanding, selects what the audience needs to learn, orders concepts, manages cognitive load, and decides what can be omitted without distortion.

#### Communication Rather Than Rendering

The Didactic Engine thinks in terms of ideas rather than graphics.

It defines teaching objectives, boundaries, ordering, duration, emphasis, omission, and conceptual focus.

It SHALL NOT define colors, camera coordinates, animation libraries, encoding settings, or renderer-specific effects.

#### Inputs and Outputs

The Didactic Engine consumes only an immutable Explanation Model together with non-tactical communication parameters such as audience profile, output format, duration constraints, accessibility requirements, and presentation policy.

It produces a presentation-neutral Communication Plan containing:

- ordered communication units;
- teaching objectives;
- referenced concepts, entities, and evidence;
- information priority;
- pacing and pause intent;
- emphasis and omission decisions;
- accessibility requirements;
- full traceability to the Explanation Model.

For video, the canonical implementation is a Scene Planner that serializes this intent as a Scene Plan. Other implementations MAY produce lesson plans, coaching presentations, interactive tutorials, or conversational teaching flows.

#### Core Questions

The Didactic Engine answers six questions:

1. **What should be shown?** Only information necessary to understand the explanation.
2. **In which order?** The clearest educational sequence, which need not be chronological.
3. **For how long?** Attention proportional to conceptual difficulty and importance.
4. **What deserves emphasis?** The entities, spaces, and transitions the audience must notice.
5. **What should remain hidden?** Redundant or irrelevant information that increases cognitive load.
6. **How should concepts build upon each other?** Each communication unit prepares the audience for the next.

Omission is educational compression, not permission to distort evidence or uncertainty.

#### Planning Principles

The plan SHOULD reveal causal structure in an order the audience can understand.

It MAY simplify presentation density but MUST preserve tactical meaning, uncertainty, and attribution.

Every communication unit SHOULD have one primary learning objective.

#### Narrative Construction

The Didactic Engine constructs a Narrative Graph that is distinct from the causal graph.

```text
Causal order:    Pass → Run → Shift → Goal

Teaching order:  Goal → Question → Overload → Shift → Return to Goal
```

The causal graph represents the platform's explanation of reality. The Narrative Graph represents the selected learning path. Narrative reordering MUST NOT change causal claims.

#### Educational Compression

A possession containing many tactical actions MAY be compressed into a small number of decisive teaching units.

Compression optimizes clarity, learning, and cognitive load rather than chronological completeness. It MUST preserve the mechanisms necessary to understand the accepted explanation.

#### Audience Adaptation

The same Explanation Model MAY produce different Communication Plans:

| Profile | Communication Strategy |
| --- | --- |
| Beginner | One primary principle, minimal terminology, long pauses, low visual density |
| Intermediate | Interacting concepts, moderate pacing, selected tactical terminology |
| Expert | High information density, concise explanation, technical vocabulary |

Audience adaptation changes communication, never tactical understanding.

#### Scene Types

Common scene types include:

- **Context Scene** — establish the situation;
- **Focus Scene** — direct attention to an entity, space, or interaction;
- **Comparison Scene** — contrast two tactical states;
- **Pause Scene** — hold the sequence for explanation;
- **Transition Scene** — resume movement while preserving orientation;
- **Outcome Scene** — reveal the consequence of prior mechanisms.

These are reusable didactic primitives rather than renderer-specific templates.

#### Information Hierarchy

```text
Primary Learning Objective
          ↓
Supporting Concepts
          ↓
Context
          ↓
Background Information
```

Higher-priority concepts SHOULD receive greater attention, earlier introduction, or stronger emphasis.

#### Fidelity

Every tactical annotation MUST reference a finding, evidence item, or causal claim in the Explanation Model.

If the Model contains no defensible explanation, the Didactic Engine MUST NOT manufacture one for narrative completeness.

#### Architectural Constraints

- The Didactic Engine SHALL NOT infer tactical concepts.
- It SHALL NOT alter evidence, confidence, or causal claims.
- It SHALL preserve links from communication units to Model content.
- It SHALL optimize communication rather than visual fidelity.
- It SHALL remain independent of rendering technology.
- It SHALL produce declarative plans rather than rendered pixels.
- Given identical inputs and policy, it SHALL produce identical Communication Plans.

#### Design Consequences

The same Communication Plan can support multiple delivery formats, while educational improvements can be tested without changing tactical reasoning or rendering.

Coaches and educators can review the learning path before any visual output is generated.

#### Chapter Summary

The Didactic Engine is the pedagogical layer of the platform.

It turns structured tactical understanding into educational intent while keeping tactical intelligence upstream and rendering decisions downstream.

### 13. Renderer

#### Purpose

The Renderer converts a medium-specific presentation plan and its Render Instructions into visual or audiovisual output. For video, that presentation plan is a Scene Plan.

It is a pure execution component with no football intelligence.

Its responsibility begins only after all tactical, causal, and didactic decisions have been made.

#### Design Philosophy

Rendering is entirely separated from intelligence.

The Renderer never decides what is important, which entity deserves attention, which tactical concept explains the sequence, or what the audience should learn. It executes resolved presentation intent.

For the canonical video pipeline:

```text
Explanation Model
        ↓
Didactic Engine
        ↓
Communication Plan
        ↓
Scene Planner
        ↓
Scene Plan
        ↓
Video Renderer
        ↓
Video
```

The Video Renderer communicates with no upstream reasoning component and consumes only the approved Scene Plan and referenced assets.

#### Responsibilities

The Renderer performs:

- asset loading;
- coordinate transformation;
- drawing and compositing;
- interpolation and animation;
- typography and annotation layout;
- audio synchronization;
- encoding and export.

It answers implementation questions such as which frame is rendered next, how instructed entities are drawn, how a declared focus is framed, when an animation begins, and where a caption can be placed without collision.

#### Input Contract

Render Instructions MUST specify all semantic choices required for execution, including referenced entities, geometry, styling roles, timing, camera behavior, and output settings.

The Renderer MAY resolve technical layout collisions or device-specific constraints, but SHALL NOT decide which tactical concept deserves emphasis.

#### Rendering Pipeline

Each frame is generated through a deterministic sequence:

```text
Scene Plan
     ↓
Timeline State
     ↓
Camera State
     ↓
Entity State
     ↓
Overlay State
     ↓
Animation State
     ↓
Frame
     ↓
Encoded Output
```

#### Internal Components

##### Timeline Engine

Resolves scene timing, pauses, transitions, playback speed, and the current position within the plan.

##### Camera Engine

Executes zoom, panning, framing, smoothing, and viewport transitions. It applies declared focus but never decides what deserves focus.

##### Entity Renderer

Draws the pitch, players, ball, zones, trajectories, and other declared entities using the state and style supplied by the plan.

##### Overlay Engine

Draws annotations such as arrows, highlighted entities, shaded spaces, passing lanes, defensive lines, captions, and labels. It MUST NOT invent annotations.

##### Animation Engine

Executes interpolation, fades, opacity changes, pulses, movement, and caption transitions solely to implement communication intent.

##### Output Engine

Produces formats such as MP4, GIF, image sequences, web streams, or interactive playback packages without changing tactical or didactic meaning.

#### Determinism

Given identical Render Instructions, assets, Renderer version, fonts, and encoding settings, output SHOULD be reproducible.

Any unavoidable platform-dependent variance MUST be documented and bounded.

Random visual behavior is prohibited unless explicitly declared in the input and controlled by a reproducible seed.

#### Rendering Quality

Rendering quality is evaluated independently from tactical and didactic quality.

Measures MAY include:

- frame stability;
- animation smoothness;
- caption readability;
- camera continuity;
- visual clutter;
- spatial consistency;
- object visibility;
- rendering performance.

A visually polished output can communicate a poor explanation, while a simple output can communicate excellent tactical understanding. Rendering scores MUST NOT substitute for upstream quality measures.

#### Multiple Renderers

The architecture MAY support independent Renderers for video, static graphics, web canvases, presentations, or future immersive formats.

Each Renderer consumes a medium-specific plan derived from the same Communication Plan and therefore communicates the same underlying explanation.

Candidate technologies and formats MAY include Matplotlib, Three.js, WebGL, Unity, Unreal Engine, native mobile rendering, augmented reality, and virtual reality.

#### Failure Behavior

Missing assets, invalid geometry, unsupported instructions, and encoding failures MUST be surfaced as rendering errors.

The Renderer MUST NOT silently replace missing tactical content with invented visuals.

It SHOULD issue actionable diagnostics, expose warnings, and fail predictably when faithful execution is impossible.

#### Rendering Validation

Rendering validation includes:

- visual regression testing;
- deterministic frame comparison;
- animation-timing verification;
- caption-overlap detection;
- viewport-stability checks;
- object-visibility checks;
- output-format conformance.

No tactical correctness is evaluated within the Renderer. Validation checks whether the approved presentation plan was executed faithfully.

#### Architectural Constraints

- The Renderer SHALL operate only on medium-specific presentation plans and Render Instructions.
- It SHALL NOT access the Tactical Intelligence Engine directly.
- It SHALL NOT access Causal Reasoning & Hypothesis Evaluation or the Didactic Engine directly.
- It SHALL NOT infer, rank, or modify tactical claims.
- It SHALL perform no educational reasoning.
- It SHALL execute deterministically.
- Visual elements representing claims SHALL remain traceable through the presentation plan to the Communication Plan and Explanation Model.
- It SHALL faithfully execute the approved plan without semantic modification.
- Rendering failures SHALL NOT mutate upstream artifacts.

#### Future Extensions

Potential outputs include short-form social video, broadcast telestration, coach tablets, interactive web applications, tactical whiteboards, AR coaching glasses, VR learning environments, and AI tutoring interfaces.

These outputs reuse the same Explanation Model and Communication Plan. Only the medium-specific plan and rendering implementation change.

#### Chapter Summary

The Renderer produces pixels, audio, and encoded media—nothing more.

Its strict lack of football intelligence makes presentation replaceable, testable, and incapable of corrupting tactical understanding.

---

## Part IV — Data & Quality

### 14. Data Strategy

#### Purpose

The Data Strategy defines how heterogeneous football observations enter the platform without coupling the core architecture to a single provider or modality.

#### Source Classes

Supported source classes include:

- event feeds;
- optical or wearable tracking data;
- freeze frames;
- broadcast and tactical video;
- metadata and lineup feeds;
- future multimodal or sensor inputs.

StatsBomb MAY serve as an initial provider, but provider-specific structures SHALL remain outside canonical domain models.

#### Adapter Architecture

Every source enters through a versioned adapter.

```text
Provider Payload
      ↓
Source Adapter
      ↓
Canonical Observation
      ↓
Validation and Synchronization
      ↓
Football World Model
```

Adapters normalize identifiers, coordinates, timestamps, units, confidence, and provenance. They SHALL NOT perform tactical reasoning.

#### Canonical Observation Contract

Every observation MUST include:

- source and provider identifier;
- source schema version;
- match and entity references where available;
- event time and ingestion time;
- observed value and units;
- coordinate-system declaration where relevant;
- confidence or source reliability;
- transformation provenance.

#### Data Fusion

Multiple sources MAY describe the same entity or moment.

Fusion SHOULD preserve each original observation, record alignment decisions, expose disagreement, and calculate derived confidence without erasing provenance.

Source disagreement MUST NOT be silently resolved.

#### Temporal and Spatial Normalization

All inputs MUST be mapped to a canonical match clock and pitch coordinate system before entering the Football World Model.

Transformations MUST be reversible or fully documented.

#### Missing and Partial Data

The platform MUST treat missing data explicitly.

Interpolation and prediction MAY fill temporary gaps, but derived values MUST remain distinguishable from direct observations and MUST carry confidence.

Capabilities SHOULD degrade gracefully according to available evidence. Tracking-dependent conclusions, for example, MUST NOT be asserted from event data alone unless an alternative evidence path is defined and validated.

#### Governance and Reproducibility

Datasets, adapters, transformations, and calibration parameters MUST be versioned.

Benchmark results MUST identify the exact data versions used.

Licensing, privacy, retention, and access constraints MUST be recorded for every source and enforced by implementation policy.

#### Architectural Constraints

- Provider schemas SHALL NOT leak into the Football World Model.
- Raw observations SHALL remain recoverable and traceable.
- Adapters SHALL normalize data but SHALL NOT infer tactics.
- Missingness, transformations, and confidence SHALL remain explicit.
- Multimodal fusion SHALL preserve source provenance and disagreement.

#### Chapter Summary

The Data Strategy makes the platform source-independent while preserving evidence quality and reproducibility.

Canonical observations, versioned adapters, explicit uncertainty, and complete provenance allow new modalities to extend the system without redesigning its reasoning architecture.

### 15. Validation & Scientific Integrity

#### Purpose

The Tactical Intelligence Platform is designed to generate explanations rather than predictions.

Consequently, its primary quality criterion is not accuracy in the traditional machine-learning sense, but the validity, consistency, and reproducibility of its explanations.

This chapter defines how tactical intelligence SHALL be evaluated, verified, and continuously improved.

#### Design Philosophy

A tactical explanation cannot be considered correct simply because it appears plausible.

Every conclusion produced by the platform MUST be:

- grounded in observable evidence;
- reproducible;
- explainable;
- falsifiable.

Scientific integrity requires that explanations can be challenged, inspected, and improved.

The platform therefore treats every explanation as a testable hypothesis rather than an unquestionable fact.

#### Levels of Validation

Validation occurs at multiple architectural levels.

```text
Football Data
      ↓
World Model Validation
      ↓
Reasoning Validation
      ↓
Explanation Validation
      ↓
Communication Validation
      ↓
Rendering Validation
```

Each level evaluates a different aspect of the system.

#### World Model Validation

The Football World Model represents objective football reality.

Validation therefore focuses on factual correctness.

Examples include:

- player identity continuity;
- ball trajectory consistency;
- spatial reconstruction accuracy;
- possession continuity;
- temporal consistency;
- tracking confidence.

Its claims are evaluated for factual correctness rather than tactical plausibility. There is no tactical judgment at this stage.

#### Primitive Validation

Primitive tactical concepts MUST be validated independently.

Examples include:

- Line Break;
- Support Angle;
- Passing Lane;
- Overlap;
- Progressive Carry.

Each primitive SHOULD possess:

- a formal definition;
- benchmark examples;
- counterexamples;
- expected evidence.

Primitive validation ensures that higher-order reasoning rests upon reliable foundations.

#### Pattern Validation

Patterns emerge from combinations of primitives.

Validation therefore examines whether recognized tactical structures genuinely exist.

For example, validation of a Third-Man Combination may ask:

- Did three distinct players participate?
- Was the intermediate action necessary?
- Did the final receiver benefit from the combination?

Pattern validation focuses on structural correctness rather than tactical importance.

#### Causal Validation

Causal validation represents one of the platform's defining capabilities.

The objective is to determine whether reconstructed causal chains genuinely explain the outcome.

Questions include:

- Did the proposed chain alter the tactical state?
- Were important state transitions omitted?
- Could an equally plausible explanation exist?
- Did contradictory evidence receive appropriate weight?

Unlike primitive validation, causal validation inherently involves uncertainty.

#### Explanation Validation

The Explanation Model SHOULD satisfy several quality criteria.

##### Completeness

Does the explanation cover all decisive tactical mechanisms?

##### Parsimony

Does the explanation avoid unnecessary complexity?

##### Consistency

Are all conclusions mutually compatible?

##### Traceability

Can every statement be traced back to evidence?

##### Transparency

Are rejected hypotheses preserved?

##### Reproducibility

Will identical input produce identical explanations?

#### Expert Validation

Human experts remain an essential component of the validation process.

Expert reviewers may evaluate:

- tactical correctness;
- educational value;
- missing concepts;
- inappropriate emphasis;
- alternative explanations.

Disagreement between experts is expected.

Such disagreement SHOULD enrich the Tactical Ontology and reasoning framework rather than invalidate the platform.

#### Benchmark Library

The platform SHOULD maintain a curated benchmark collection.

Each benchmark contains:

```text
Match
  ↓
Possession
  ↓
Expert-Validated Reference Explanation
  ↓
Alternative Explanations
  ↓
Supporting Evidence
  ↓
Expert Commentary
```

Benchmarks provide stable reference cases for regression testing and future research.

#### Regression Testing

Every architectural change SHOULD be evaluated against the benchmark library.

Expected outcomes include:

- no deterioration in previously validated explanations;
- improved explanation quality where intended;
- stable confidence estimates;
- consistent Explanation Models.

Regression testing protects the architecture from gradual degradation.

#### Explainability Audits

Every explanation SHOULD support inspection.

Example audit questions include:

- Why was this hypothesis accepted?
- Why was another rejected?
- Which evidence increased confidence?
- Which observations weakened the conclusion?
- Can every statement be traced to observable facts?

The platform SHOULD always be able to answer these questions.

#### Failure Analysis

Incorrect explanations are valuable.

Every failure SHOULD be classified.

Failure classes include:

- Football World Model failure;
- primitive detection failure;
- pattern construction failure;
- hypothesis-ranking failure;
- scene-planning failure;
- rendering failure.

Correct diagnosis enables targeted improvements without unnecessary architectural changes.

#### Architectural Constraints

The following statements are normative:

- The platform SHALL validate every architectural layer independently.
- Every tactical concept SHALL possess benchmark examples.
- Every accepted explanation SHALL remain traceable to observable evidence.
- Regression testing SHALL accompany architectural modifications.
- Validation datasets SHALL evolve without altering canonical concept definitions.

#### Scientific Integrity

The Tactical Intelligence Platform does not claim objective truth.

Instead, it produces the most plausible explanation supported by the available evidence.

Every explanation remains open to refinement as better observations, an improved ontology, and stronger reasoning algorithms become available.

This principle reflects both scientific methodology and the inherently uncertain nature of football.

#### Chapter Summary

Validation is not a final development step but an architectural principle.

By validating observations, reasoning, explanations, and communication independently, the platform maintains scientific integrity while enabling continuous improvement.

### 16. Engineering Principles

#### Purpose

This chapter defines the engineering principles that govern the implementation of the Tactical Intelligence Platform.

Where previous chapters describe what the architecture is, this chapter defines how it SHALL be implemented and maintained over time.

These principles exist to preserve architectural integrity as the platform evolves.

#### Architecture Before Code

Implementation SHALL follow architecture.

Architecture SHALL NOT emerge accidentally from implementation.

Every major engineering decision MUST be justifiable within the architectural framework defined by this document.

Whenever implementation conflicts with architecture, the architecture SHALL be reviewed before exceptions are introduced into production code.

#### Separation of Responsibilities

Every architectural component SHALL have one clearly defined responsibility.

Components SHOULD collaborate through explicit interfaces rather than shared implementation details.

| Component | Responsibility |
| --- | --- |
| Football World Model | Represent reality |
| Tactical Intelligence Engine | Recognize tactical concepts and patterns |
| Causal Reasoning & Hypothesis Evaluation | Generate and evaluate explanations |
| Explanation Model | Store understanding |
| Didactic Engine | Plan communication |
| Renderer | Execute presentation |

No component SHALL assume the responsibilities of another.

#### Determinism by Default

All reasoning SHALL be deterministic unless stochastic behavior is explicitly justified.

Given identical inputs, the platform SHALL produce:

- identical Football World Models;
- identical Explanation Models;
- identical Communication Plans;
- identical Scene Plans;
- identical rendered outputs.

Determinism enables reproducibility, debugging, and scientific validation.

#### Explicit Data Flow

Information SHALL always move forward through the architecture.

```text
Football Data
      ↓
Football World Model
      ↓
Tactical Intelligence Engine
      ↓
Causal Reasoning & Hypothesis Evaluation
      ↓
Explanation Model
      ↓
Didactic Engine
      ↓
Renderer
```

Reverse dependencies SHOULD NOT exist.

Downstream components SHALL NOT modify upstream knowledge.

#### Immutable Knowledge

Once a knowledge artifact has been published, it becomes immutable.

Examples include:

- World State snapshots;
- Explanation Models;
- Communication Plans;
- Scene Plans.

Immutability simplifies reasoning, debugging, and versioning.

#### Composition Over Complexity

Complex tactical behavior SHOULD emerge through the composition of smaller concepts.

```text
Primitive
    ↓
Pattern
    ↓
Hypothesis
    ↓
Explanation
```

Rather than implementing increasingly complex detectors, the architecture SHOULD favor assembling reusable building blocks.

#### Testability

Every architectural component SHALL be testable independently.

```text
Unit Testing
     ↓
Integration Testing
     ↓
Regression Testing
     ↓
Benchmark Validation
```

No component SHOULD require the complete pipeline for verification.

#### Explainability First

Internal reasoning SHOULD remain inspectable.

Engineers MUST always be able to answer:

- Why was this hypothesis accepted?
- Why was another rejected?
- Which evidence influenced confidence?

If these questions cannot be answered, the proposed architectural changes SHOULD be reconsidered.

#### Extensibility

The platform is expected to grow continuously.

Future additions SHOULD extend existing abstractions rather than replace them.

Examples include:

- new tactical concepts;
- additional Renderers;
- richer ontologies;
- stronger reasoning capabilities.

Existing architectural contracts SHOULD remain stable wherever possible.

#### Performance

Performance is important but secondary to correctness.

The platform SHALL prioritize:

```text
Correctness
     ↓
Explainability
     ↓
Maintainability
     ↓
Performance
```

Optimization SHOULD occur only after correctness has been established.

#### Engineering Culture

The architecture encourages an engineering culture based upon:

- clarity over cleverness;
- explicitness over implicit behavior;
- reusable abstractions over duplication;
- scientific curiosity over assumptions.

These principles SHOULD guide every implementation decision.

#### Architectural Constraints

The following statements are normative:

- Implementation SHALL follow architecture.
- Components SHALL expose explicit interfaces.
- Knowledge SHALL flow in one direction.
- Architectural responsibilities SHALL remain separated.
- Code SHALL remain explainable.
- Optimization SHALL NOT compromise correctness.

#### Chapter Summary

The Engineering Principles preserve the long-term integrity of the Tactical Intelligence Platform.

They ensure that implementation remains aligned with architecture, enabling sustainable growth as the platform evolves.

---

## Part V — Future

### 17. Roadmap

#### Purpose

The Tactical Intelligence Platform is intentionally designed as a long-term research and engineering program.

This roadmap describes the anticipated evolution of the architecture.

It is not a product backlog. It is an architectural roadmap.

#### Phase I — Foundations

**Objective:** Construct a reliable, explainable pipeline.

**Deliverables:**

- Football World Model;
- Tactical Ontology;
- primitive detectors;
- Explanation Model;
- Didactic Engine;
- deterministic Renderer.

**Outcome:** Reliable, explainable tactical videos.

#### Phase II — Rich Tactical Intelligence

**Focus:** Expand tactical understanding.

Examples include:

- pressing behavior;
- defensive compactness;
- overload recognition;
- rotations;
- positional play;
- rest defense;
- transition analysis.

**Outcome:** Explanation quality increases significantly.

#### Phase III — Contextual Intelligence

Reasoning becomes increasingly contextual.

Examples include:

- score effects;
- player roles;
- tactical systems;
- coaching philosophies;
- opponent adaptations;
- game state.

**Outcome:** The platform begins explaining why teams make particular decisions.

#### Phase IV — Counterfactual Reasoning

Introduce what-if analysis.

Examples include:

- What if the fullback had stayed deeper?
- What if the midfielder had not pressed?
- Would the goal still have occurred?

**Outcome:** Explanations become counterfactual and predictive rather than purely retrospective.

#### Phase V — Interactive Intelligence

Static videos evolve into interactive learning systems.

Capabilities include:

- asking questions;
- inspecting hypotheses;
- replaying explanations;
- comparing tactical alternatives.

The user interacts directly with the structured knowledge in the Explanation Model.

#### Phase VI — Autonomous Tactical Analyst

This phase represents the long-term vision.

Capabilities may include:

- complete match reports;
- scouting analysis;
- player development;
- opposition preparation;
- coaching recommendations;
- educational tutoring.

The platform becomes a collaborative tactical analyst rather than a video generator.

#### Guiding Principle

Each phase extends the architecture.

No phase SHOULD require redesigning the architectural foundations.

### 18. Research Directions

#### Purpose

This chapter captures open research questions that intentionally remain unresolved.

The architecture is stable.

The science will continue evolving.

#### Open Research Areas

##### Tactical Intent

Can intent be inferred reliably from observable behavior?

##### Team Strategy

How should long-term tactical strategy be represented?

##### Space Semantics

Can semantic space replace or enrich geometric space?

##### Player Roles

Can roles emerge dynamically from behavior?

##### Counterfactual Simulation

How accurately can alternative tactical futures be estimated?

##### Learning from Experts

Can expert analysts directly improve the Tactical Ontology?

##### Multi-Agent Reasoning

Can attacking and defending teams be modeled as competing reasoning systems?

##### Generalization

Can the reasoning architecture be transferred beyond football?

Candidate domains include:

- basketball;
- hockey;
- rugby;
- military simulations;
- traffic analysis.

##### Domain-General Reasoning Engine

Could Causal Reasoning & Hypothesis Evaluation eventually become a domain-independent Explainable Reasoning Engine, with football-specific knowledge supplied exclusively by the World Model and Ontology?

This is a research direction for a future Masterplan revision, not a v1 architectural requirement.

#### Research Philosophy

Research SHOULD extend the architecture rather than undermine it.

Stable architectural principles provide the foundation upon which scientific exploration occurs.

#### Final Statement

Football is not a sequence of events.

It is a continuously evolving system of interacting players, spaces, and intentions.

Understanding football therefore requires more than detecting actions.

It requires constructing explanations.

This architecture proposes that explainable football intelligence emerges through successive transformations:

```text
Reality
   ↓
Observation
   ↓
Representation
   ↓
Reasoning
   ↓
Explanation
   ↓
Communication
   ↓
Presentation
```

Each layer reduces uncertainty while preserving traceability.

Each layer has one responsibility.

Each layer prepares the next.

The result is not merely a system that renders football.

It is a system that understands football well enough to explain it.

The same architectural pattern can support explainable domain intelligence beyond football by replacing the World Model, Tactical Ontology, and reasoning knowledge while preserving the sequence:

```text
Observe → Represent → Reason → Explain → Communicate → Render
```

### 19. Appendix

#### A. Glossary

This glossary supplements the normative definitions in Chapter 2.

| Term | Short Definition |
| --- | --- |
| Adapter | A boundary component that converts provider data into canonical observations. |
| Canonical Concept | The single authoritative ontology definition referenced by all detectors. |
| Contradicting Evidence | Evidence that weakens or invalidates a finding, hypothesis, or causal claim. |
| Detector | A versioned procedure that evaluates evidence against an ontology concept. |
| Provenance | The traceable origin and transformation history of data or knowledge. |
| Scene | A bounded communication unit with one primary teaching objective. |
| State Transition | A meaningful difference between World States over time. |
| Tactical Primitive | A low-level ontology concept from which patterns can be composed. |

#### B. Canonical Observation Schema

The following YAML defines the minimum logical contract. Production schemas MUST add strict types, formats, enumerations, and validation rules.

```yaml
observation_id: string
source:
  provider: string
  dataset_id: string
  schema_version: string
subject:
  match_id: string
  entity_id: string | null
time:
  match_clock_ms: integer
  observed_at: datetime | null
  ingested_at: datetime
measurement:
  type: string
  value: object
  units: string | null
  coordinate_system: string | null
confidence: number  # 0.0–1.0
provenance:
  raw_reference: string
  transformations: [string]
```

#### C. Explanation Model Schema

```yaml
model_id: string
schema_version: string
reasoning_pipeline_version: string
created_at: datetime
supersedes_model_id: string | null
subject:
  match_id: string
  possession_id: string | null
  interval:
    start_ms: integer
    end_ms: integer
input_provenance:
  world_model_version: string
  ontology_version: string
  dataset_versions: [string]
findings:
  - finding_id: string
    concept_id: string
    entity_ids: [string]
    interval: {start_ms: integer, end_ms: integer}
    evidence_refs: [string]
    contradicting_evidence_refs: [string]
    confidence: number
hypotheses:
  accepted: [Hypothesis]
  rejected: [Hypothesis]
causal_chains:
  - chain_id: string
    nodes: [CausalNode]
    edges: [CausalEdge]
uncertainty:
  confidence: number
  unresolved_questions: [string]
narrative_intent:
  objective: string
  primary_concept_id: string
  audience: string
  required_caveats: [string]
```

`Hypothesis`, `CausalNode`, and `CausalEdge` MUST remain versioned schema definitions rather than unstructured text.

#### D. Communication Plan Schema

```yaml
communication_plan_id: string
schema_version: string
source_model_id: string
didactic_engine_version: string
audience_profile:
  level: beginner | intermediate | expert
  terminology_profile: string
  accessibility_requirements: [string]
constraints:
  medium: string
  duration_ms: integer | null
learning_objectives:
  primary: string
  supporting: [string]
communication_units:
  - unit_id: string
    objective: string
    model_refs: [string]
    priority: primary | supporting | context | background
    pacing: string
    emphasis: [string]
    omitted_model_refs: [string]
narrative_edges:
  - {from: string, to: string, relation: string}
```

#### E. Scene Plan Schema

```yaml
scene_plan_id: string
schema_version: string
source_communication_plan_id: string
source_model_id: string
planner_version: string
output_profile:
  medium: video | static | interactive
  audience: string
  duration_ms: integer | null
scenes:
  - scene_id: string
    objective: string
    model_refs: [string]
    source_interval: {start_ms: integer, end_ms: integer}
    visible_entities: [string]
    annotations: [Annotation]
    camera: object
    timing: object
    transition: object
```

Every semantically meaningful scene element MUST reference content from the source Explanation Model.

#### F. Example Explanation Model

```yaml
model_id: explanation-match001-possession042-v1
schema_version: "1.0"
reasoning_pipeline_version: "0.1.0"
subject:
  match_id: match001
  possession_id: possession042
  interval: {start_ms: 3812000, end_ms: 3824000}
findings:
  - finding_id: finding-wide-overload
    concept_id: wide_overload
    entity_ids: [attacker-7, attacker-8, defender-2]
    evidence_refs: [evidence-position-17, evidence-space-09]
    contradicting_evidence_refs: []
    confidence: 0.91
  - finding_id: finding-open-cutback
    concept_id: open_cutback_lane
    entity_ids: [attacker-7, attacker-10]
    evidence_refs: [evidence-lane-04]
    contradicting_evidence_refs: []
    confidence: 0.87
hypotheses:
  accepted:
    - hypothesis_id: hypothesis-overload-cutback
      explanation: Wide occupation shifted the defensive block and enabled the cutback lane.
      confidence: 0.86
  rejected:
    - hypothesis_id: hypothesis-isolated-error
      explanation: The chance resulted primarily from an individual defensive error.
      confidence: 0.31
      rejection_reason: Lower evidential coverage and causal coherence.
causal_chains:
  - chain_id: chain-primary
    nodes: [wide_overload, defensive_shift, open_cutback_lane, finish]
    edges:
      - {from: wide_overload, to: defensive_shift, relation: caused}
      - {from: defensive_shift, to: open_cutback_lane, relation: enabled}
      - {from: open_cutback_lane, to: finish, relation: enabled}
uncertainty:
  confidence: 0.86
  unresolved_questions: [Whether the defensive shift was instructed or improvised.]
narrative_intent:
  objective: Explain how wide occupation created the decisive central space.
  primary_concept_id: wide_overload
  audience: analyst
  required_caveats: [Defensive intent cannot be observed directly.]
```

#### G. Example Internal Football Action Graph

```text
[World State t0]
       │ evidence
       ▼
[Wide Overload] ──caused──▶ [Defensive Shift]
       │                           │
       │                           └──enabled──▶ [Open Cutback Lane]
       │                                                │
       └──supports hypothesis A                         └──enabled──▶ [Finish]

[Individual Error] ──contradicted by──▶ [Coordinated Defensive Shift]
```

This graph is an internal reasoning structure shared through the boundary between tactical recognition and Causal Reasoning & Hypothesis Evaluation. The Explanation Model remains the external knowledge contract.

#### H. Architectural Decision Records

Every material deviation from or refinement of this Masterplan MUST be recorded as an ADR.

Each ADR MUST contain:

- identifier and title;
- status;
- context;
- decision;
- alternatives considered;
- consequences;
- affected requirements and interfaces;
- migration or review plan.

ADR statuses are `Proposed`, `Accepted`, `Superseded`, and `Rejected`.

The initial ADR follows this Appendix.

#### Appendix Status

The schemas in this Appendix define canonical logical contracts for v1.0. Machine-validatable JSON Schema or equivalent artifacts SHOULD be maintained alongside implementation code and MUST preserve these semantics.

---

## Architectural Decision — Football Action Graph

This Masterplan establishes one deliberate change from the platform's earlier architectural direction.

The Football Action Graph will be treated as an internal reasoning data structure spanning Tactical Findings and Causal Reasoning & Hypothesis Evaluation rather than as a separate chapter or top-level component.

### Rationale

- The Football World Model describes the current state of the match.
- The Tactical Intelligence Engine recognizes concepts and patterns in that state; Causal Reasoning & Hypothesis Evaluation builds dependencies, competing hypotheses, and causal chains from those findings.
- A graph is an excellent internal representation for this purpose, but the platform does not ultimately expose a graph to the outside world. It produces an Explanation Model.

This decision simplifies the top-level architecture and better aligns it with the objective: an AI that understands and explains football, not an AI that produces a graph.

---

## Document Completion

The Masterplan v1.0 architecture is complete and ready for formal review, schema extraction, ADR expansion, and implementation planning.
