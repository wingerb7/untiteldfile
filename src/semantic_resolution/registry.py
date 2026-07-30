from .models import SemanticRelationDefinition


PASS_RECEIPT_MEANING = (
    "The authenticated pass event represented by the source node and the authenticated "
    "ball-receipt event represented by the target node are explicitly linked by authenticated "
    "source relation evidence, and satisfy all required pass-receipt resolution constraints."
)

RELATION_TYPES = (
    SemanticRelationDefinition(
        "tip.semantic_relation_definition", "PASS_RECEIPT_LINK", "0.1.0", PASS_RECEIPT_MEANING
    ),
)
