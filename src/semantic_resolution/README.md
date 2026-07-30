# Pass-receipt semantic resolution

`PASS_RECEIPT_LINK` means: the authenticated pass event represented by the
source node and the authenticated ball-receipt event represented by the target
node are explicitly linked by authenticated source relation evidence, and
satisfy all required pass-receipt resolution constraints.

It does not assert tactics, causality, possession continuation, successful
control, progression, line breaking, chance creation, off-ball movement,
importance, narrative relevance, or presentation behavior.

The stage runs after Recognition and ActionGraph. It reads authenticated
EventEvidence and existing `SOURCE_RELATED_EVENT` edges but never modifies or
reinterprets `SOURCE_RELATED_EVENT`, `TEMPORAL_SUCCESSION`, or
`STATE_CONTINUATION`.

## StatsBomb completion normalization

The existing normalization in `src/normalization.py` maps an absent StatsBomb
`pass.outcome` to canonical `COMPLETED`. This is StatsBomb's source-default
success representation; it is not inferred from a related receipt. The
supported explicit StatsBomb outcome `(9, "Incomplete")` maps to canonical
`INCOMPLETE`. Any other present pass outcome fails upstream with
`NORM_UNSUPPORTED_MAPPING`. Consequently, this resolver accepts only canonical
`COMPLETED`; `INCOMPLETE` is an explicit unsuccessful rejection, and a missing
or otherwise unrecognized canonical pass outcome fails closed.

The existing normalization currently represents ball-receipt outcome as
`None`; it does not inspect the nested StatsBomb `ball_receipt.outcome`. This
stage does not change that normalization rule. It preserves the normalized
receipt outcome in EventEvidence, rejects canonical explicit failure values if
supplied, and does not invent a receipt outcome.

## Canonical relation and provenance

The canonical direction is `PASS_EVENT -> BALL_RECEIPT_EVENT`. One relation is
emitted for a uniquely resolved endpoint pair regardless of whether source
declarations run pass-to-receipt, receipt-to-pass, or both. Each relation
contains deterministic endpoint node, Recognition, EventEvidence, and source
UUID references; canonical actor, recipient, and outcome representations; and
all supporting source-edge IDs with each exact declaration direction and list
index.
