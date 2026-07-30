# Player action continuation

`PLAYER_ACTION_CONTINUATION` asserts only that two authenticated supported source actions have the same
authenticated actor in one match and possession context, and that the target is that actor's first later
supported action under canonical event ordering.

The direct-selection rule emits `A → B` and `B → C`, never the transitive `A → C`. Other players' supported
actions may intervene and are preserved in source order. An authenticated incomplete pass remains a valid
source action because this relation concerns later player involvement, not pass completion. Recipient identity
is never used as actor identity.

Current source normalization rejects unsupported retained event mappings, so an unsupported same-player event
cannot silently occur between supported ActionGraph events. If such evidence becomes preservable upstream, it
must be modeled explicitly before this stage may skip it. No time-gap heuristic, tracking, geometry, tactical,
causal, narrative, scene-planning, camera, or rendering semantics are used.
