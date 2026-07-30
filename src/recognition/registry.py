from __future__ import annotations
from .models import RecognitionConcept

def _prov(): return {"/concept_code":{"class":"CONSTANT","operation":"REC_SET_CONCEPT_CONSTANT","sources":[]}}

CONCEPTS = (
 RecognitionConcept("tip.recognition_concept","SOURCE_DECLARED_BALL_RECEIPT","Source-Declared Ball Receipt","The authenticated source event type is BALL_RECEIPT.","SOURCE_EVENT_PARTICIPANTS",(),"authenticated EventEvidence event_type equals BALL_RECEIPT","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","SOURCE_DECLARED_CARRY","Source-Declared Carry","The authenticated source event type is CARRY.","SOURCE_EVENT_PARTICIPANTS",(),"authenticated EventEvidence event_type equals CARRY","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","SOURCE_DECLARED_PASS","Source-Declared Pass","The authenticated source event type is PASS.","SOURCE_EVENT_PARTICIPANTS",(),"authenticated EventEvidence event_type equals PASS","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","SOURCE_DECLARED_SHOT","Source-Declared Shot","The authenticated source event type is SHOT.","SOURCE_EVENT_PARTICIPANTS",(),"authenticated EventEvidence event_type equals SHOT","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","DEFENSIVE_LINE_STATE","Defensive Line State","At least three positioned opponents form a longitudinally compact, laterally spanning line.","DEFENSIVE_PLAYER_SET",("ABSOLUTE_POSITION","CONNECTION_DISTANCE"),"three or more opponents within four longitudinal metres and spanning at least eight lateral metres","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","PASS_CROSSES_DEFENSIVE_LINE","Pass Crosses Defensive Line","The authenticated source pass start and end coordinates lie strictly on opposite longitudinal sides of a recognized defensive line.","PASS_PARTICIPANTS_AND_DEFENSIVE_LINE",("PASS_START_POSITION","PASS_END_POSITION","ABSOLUTE_POSITION","CONNECTION_DISTANCE"),"same-event source pass endpoint signed distances from recognized line have opposite signs","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","PASSING_CORRIDOR_EXISTS","Passing Corridor Exists","An available directed same-team corridor has zero perceived occupants.","ORDERED_PLAYER_PAIR",("CONNECTION_CORRIDOR","CORRIDOR_OCCUPANCY"),"corridor available and occupancy equals zero","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","PASSING_CORRIDOR_OBSTRUCTED","Passing Corridor Obstructed","An available directed same-team corridor has at least one perceived occupant.","ORDERED_PLAYER_PAIR",("CONNECTION_CORRIDOR","CORRIDOR_OCCUPANCY"),"corridor available and occupancy greater than zero","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","PLAYER_MOVING","Player Moving","A player has an available strictly positive perceived speed.","PLAYER",("ENTITY_SPEED",),"speed greater than zero metres per second","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","PLAYER_NEAREST_BALL","Player Nearest Ball","The player has the minimum available player-ball distance in the frame.","PLAYER",("PAIR_DISTANCE",),"minimum distance, player identifier tie-break","0.1.0",_prov()),
 RecognitionConcept("tip.recognition_concept","PLAYER_STATIONARY","Player Stationary","A player has an available exactly zero perceived speed.","PLAYER",("ENTITY_SPEED",),"speed equals zero metres per second","0.1.0",_prov()),
)
