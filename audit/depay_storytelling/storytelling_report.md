# Depay production storytelling audit

## Executive verdict

The decisive attack was detected by the graph-backed route: six authenticated LINE_BREAK
episodes and the finish all reach the candidate set. The previous storytelling video lost
the multi-player mechanism at **narrative grouping**, before episode relevance, ranking, or
scene direction. Its entry point did not consume graph-backed episodes. Because Depay has no
authenticated return-combination match, it selected the first canonical same-player
continuation ending in the shot and rendered that as one episode.

The renderer is not responsible. It executed all three supplied scenes and the planned
8.95-second timeline exactly (8.92 seconds at the encoded container boundary). A
post-semantic three-frame inspection shows the planned Depay-continuation caption through
the compressed play and the planned shot caption at the end; it introduces no upstream
tactical meaning.

## Canonical decisive attack

The possession begins at `df062304-317d-4ecc-940e-848563aa6140`, but the canonical attack begins
at `33afe8ec-1aea-40be-a7cc-97610032e3b5` (Blind to Depay, 557.943s), the earliest authenticated line break
in the decisive sequence. It continues through the quick progression and the final
Depay–Gakpo–Dumfries chain:

1. Blind → Depay: attack-entry line break.
2. De Roon → Klaassen and Klaassen → Depay: supporting combination/progression.
3. Depay → Gakpo: decisive mechanism begins.
4. Gakpo → Dumfries: wide progression within the mechanism.
5. Dumfries → Depay: final line-breaking action.
6. Depay shoots at 571.453s.

No graph-backed box-entry or final-third-arrival concept exists, so none is asserted.

## Candidate and LINE_BREAK audit

All seven graph-backed candidates have authenticated paths to the finish. Three episodes are
`CORE_CAUSAL`, one is `SUPPORTING_CONTEXT`, two are
`TACTICALLY_VALID_BUT_NARRATIVELY_SECONDARY`, and FINISH is `CORE_CAUSAL`.

The six LINE_BREAK episodes are semantically distinct and useful for analysis. Presenting
all six as equal individual storytelling beats is excessive: the middle progression has no
unique setup, decisive, or finish purpose and should be summarized rather than independently
paused. This is narrative redundancy, not episode duplication.

## Exact divergence

For the historical 23.5-second generic tactical-episode video, the first divergence is
generic episode generation without causal relevance selection: BUILDUP, ISOLATION,
OFF_BALL_RUN, SWITCH_OF_PLAY, and CUTBACK were all treated as equally scene-worthy, so five
earlier-possession explanations preceded the finish.

For the later 8.95-second storytelling render,
`scripts/render_tactical_storytelling.py::action_chain_for` is the first divergent layer.
The graph episode candidate count supplied to that branch is zero. The fallback
`FIRST_CANONICAL_CHAIN_ENDING_IN_AUTHENTICATED_SHOT` follows only Depay's repeated
involvements, starts at his receipt rather than Blind's line-breaking pass, and omits the
other players' decisive actions as explained beats. The scene builder then faithfully
creates one pause, one compressed play, and one finish hold.

There is no maximum-episode rule, ranking score, or causal-importance score in the graph
semantic route. Confidence is 1.0 for every authenticated episode and is not used to rank
them. Canonical time is the effective ordering rule. The model is optimized for validity,
not narrative importance.

## Duration

Three separate durations matter:

- Historical generic tactical-episode render: **23.5s**; long enough, but focused on
  earlier generic detections.
- Previous storytelling render: **8.95s**, planned and rendered identically.
- Known generic Depay regression: **12.5s**. The generic
  builder currently groups 56 events as BUILDUP and caps its play at 4.0s; fixed pauses,
  the final play, and hold produce 12.5s.
- Graph semantic plan: **22.583333s** across
  14 scenes.

The 12.5-second result is a symptom and amplifier, not the first cause. Coarse grouping and
fixed compression create the short plan; the reduced duration then leaves no room to explain
the attack.

## Narrowest recommended correction

Change the storytelling orchestration between graph-backed episode adaptation and scene
planning. Add a causal narrative-selection/grouping policy that:

1. anchors on FINISH;
2. walks authenticated predecessors;
3. retains one setup line break and the final decisive pass/finish chain;
4. groups intervening distinct LINE_BREAK episodes as sustained progression;
5. assigns explicit setup, mechanism, final-action, and finish roles before scene planning.

Recognition, Action Graph, graph episode semantics, tactical thresholds, renderer behavior,
and the six episode identities should not change. No production correction is implemented
by this audit.
