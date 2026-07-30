from __future__ import annotations

from .models import ActionRelationDefinition, ActionTypeDefinition


def _action_provenance() -> dict:
    return {"/action_type": {"class": "CONSTANT", "operation": "AG_SET_ACTION_TYPE_CONSTANT", "sources": []}}


def _relation_provenance() -> dict:
    return {"/relation_type": {"class": "CONSTANT", "operation": "AG_SET_RELATION_TYPE_CONSTANT", "sources": []}}


ACTION_TYPES = (
    ActionTypeDefinition("tip.action_type_definition", "BALL_RECEIPT_EVENT", "SOURCE_DECLARED_BALL_RECEIPT", "SOURCE_EVENT_PARTICIPANTS", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "CARRY_EVENT", "SOURCE_DECLARED_CARRY", "SOURCE_EVENT_PARTICIPANTS", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "PASS_EVENT", "SOURCE_DECLARED_PASS", "SOURCE_EVENT_PARTICIPANTS", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "SHOT_EVENT", "SOURCE_DECLARED_SHOT", "SOURCE_EVENT_PARTICIPANTS", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "DEFENSIVE_LINE_STATE", "DEFENSIVE_LINE_STATE", "DEFENSIVE_PLAYER_SET", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "PASS_LINE_CROSSING_FACT", "PASS_CROSSES_DEFENSIVE_LINE", "PASS_PARTICIPANTS_AND_DEFENSIVE_LINE", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "PASSING_CORRIDOR_EXISTS_STATE", "PASSING_CORRIDOR_EXISTS", "ORDERED_PLAYER_PAIR", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "PASSING_CORRIDOR_OBSTRUCTED_STATE", "PASSING_CORRIDOR_OBSTRUCTED", "ORDERED_PLAYER_PAIR", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "PLAYER_MOVING_STATE", "PLAYER_MOVING", "PLAYER", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "PLAYER_NEAREST_BALL_STATE", "PLAYER_NEAREST_BALL", "PLAYER", "0.1.0", _action_provenance()),
    ActionTypeDefinition("tip.action_type_definition", "PLAYER_STATIONARY_STATE", "PLAYER_STATIONARY", "PLAYER", "0.1.0", _action_provenance()),
)

RELATION_TYPES = (
    ActionRelationDefinition("tip.action_relation_definition", "PASS_CROSSES_DEFENSIVE_LINE", "0.1.0", _relation_provenance()),
    ActionRelationDefinition("tip.action_relation_definition", "SOURCE_RELATED_EVENT", "0.1.0", _relation_provenance()),
    ActionRelationDefinition("tip.action_relation_definition", "STATE_CONTINUATION", "0.1.0", _relation_provenance()),
    ActionRelationDefinition("tip.action_relation_definition", "TEMPORAL_SUCCESSION", "0.1.0", _relation_provenance()),
)

CONCEPT_TO_ACTION = {item.supporting_concept_code: item.action_type for item in ACTION_TYPES}
