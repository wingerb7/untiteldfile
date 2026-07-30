from .models import ContinuationRelationDefinition


PLAYER_ACTION_CONTINUATION_MEANING = (
    "The authenticated source action and authenticated target action are performed by the same "
    "uniquely resolved player within the same authenticated match and attacking context, and the "
    "target action is a later supported re-involvement of that player according to canonical event ordering."
)

RELATION_TYPES = (
    ContinuationRelationDefinition(
        "tip.continuation_relation_definition", "PLAYER_ACTION_CONTINUATION", "0.1.0",
        PLAYER_ACTION_CONTINUATION_MEANING,
    ),
)

SUPPORTED_ACTION_TYPES = frozenset({"PASS_EVENT", "BALL_RECEIPT_EVENT", "CARRY_EVENT", "SHOT_EVENT"})
