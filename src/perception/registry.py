from __future__ import annotations

from dataclasses import dataclass

from .errors import PerceptionError
from .models import FeatureCategory, FeatureDefinition


@dataclass(frozen=True)
class RegistryEntry:
    code: str; name: str; description: str; category: FeatureCategory; scope: str; output_type: str; unit: str
    dependencies: tuple[str, ...] = (); valid_min: float | None = None; valid_max: float | None = None


_E = RegistryEntry
DEFAULT_ENTRIES = (
 _E("OBSERVATION_POSITION","Observation Position","direct canonical position.",FeatureCategory.SPATIAL,"OBSERVATION","POSITION2","POSITION_METRES"),
 _E("ABSOLUTE_POSITION","Absolute Position","unique current entity position.",FeatureCategory.SPATIAL,"ENTITY","POSITION2","POSITION_METRES",("OBSERVATION_POSITION",)),
 _E("PAIR_DISTANCE","Pair Distance","Euclidean separation.",FeatureCategory.SPATIAL,"UNORDERED_ENTITY_PAIR","SCALAR","METRES",("ABSOLUTE_POSITION",),0,125.095963),
 _E("RELATIVE_POSITION","Relative Position","vector from first subject to second.",FeatureCategory.SPATIAL,"ORDERED_ENTITY_PAIR","VECTOR2","VECTOR_METRES",("ABSOLUTE_POSITION",)),
 _E("BEARING","Bearing","angle from first subject to second.",FeatureCategory.SPATIAL,"ORDERED_ENTITY_PAIR","SCALAR","RADIANS",("RELATIVE_POSITION",),-3.141593,3.141593),
 _E("TEAM_CENTROID","Team Centroid","arithmetic mean of unique current member positions.",FeatureCategory.SPATIAL,"TEAM","POSITION2","POSITION_METRES",("ABSOLUTE_POSITION",)),
 _E("TEAM_WIDTH","Team Width","current lateral coordinate range.",FeatureCategory.SPATIAL,"TEAM","SCALAR","METRES",("ABSOLUTE_POSITION",),0,68),
 _E("TEAM_DEPTH","Team Depth","current longitudinal coordinate range.",FeatureCategory.SPATIAL,"TEAM","SCALAR","METRES",("ABSOLUTE_POSITION",),0,105),
 _E("ENTITY_VELOCITY","Entity Velocity","backward finite-difference position vector.",FeatureCategory.MOTION,"ENTITY","VECTOR2","VECTOR_METRES_PER_SECOND",("ABSOLUTE_POSITION",)),
 _E("ENTITY_SPEED","Entity Speed","velocity magnitude.",FeatureCategory.MOTION,"ENTITY","SCALAR","METRES_PER_SECOND",("ENTITY_VELOCITY",),0,None),
 _E("MOTION_HEADING","Motion Heading","direction of non-zero velocity.",FeatureCategory.MOTION,"ENTITY","SCALAR","RADIANS",("ENTITY_VELOCITY",),-3.141593,3.141593),
 _E("RELATIVE_VELOCITY","Relative Velocity","second subject velocity minus first subject velocity.",FeatureCategory.MOTION,"ORDERED_ENTITY_PAIR","VECTOR2","VECTOR_METRES_PER_SECOND",("ENTITY_VELOCITY",)),
 _E("CLOSING_SPEED","Closing Speed","positive radial approach rate.",FeatureCategory.MOTION,"ORDERED_ENTITY_PAIR","SCALAR","METRES_PER_SECOND",("RELATIVE_POSITION","RELATIVE_VELOCITY","PAIR_DISTANCE")),
 _E("SEPARATION_SPEED","Separation Speed","positive radial separation rate.",FeatureCategory.MOTION,"ORDERED_ENTITY_PAIR","SCALAR","METRES_PER_SECOND",("CLOSING_SPEED",)),
 _E("BALL_POSITION","Ball Position","unique current direct ball position.",FeatureCategory.BALL,"ENTITY","POSITION2","POSITION_METRES",("ABSOLUTE_POSITION",)),
 _E("BALL_VELOCITY","Ball Velocity","measured backward finite-difference vector.",FeatureCategory.BALL,"ENTITY","VECTOR2","VECTOR_METRES_PER_SECOND",("ENTITY_VELOCITY",)),
 _E("BALL_DIRECTION","Ball Direction","direction of non-zero Ball velocity.",FeatureCategory.BALL,"ENTITY","SCALAR","RADIANS",("MOTION_HEADING",),-3.141593,3.141593),
 _E("PLAYER_BALL_DISTANCE","Player Ball Distance","Euclidean separation from an identified or observation-scoped Player position to the directly observed Ball position in the same WorldState.",FeatureCategory.BALL,"ORDERED_ENTITY_PAIR","SCALAR","METRES",("PAIR_DISTANCE",),0,125.095963),
 _E("NEIGHBOR_COUNT_5M","Neighbor Count 5m","positioned Players within five metres.",FeatureCategory.DENSITY,"ENTITY","INTEGER","COUNT",("PAIR_DISTANCE",),0,None),
 _E("LOCAL_TEAMMATE_COUNT_10M","Local Teammate Count 10m","same-team Players within ten metres.",FeatureCategory.DENSITY,"ENTITY","INTEGER","COUNT",("PAIR_DISTANCE",),0,None),
 _E("LOCAL_OPPONENT_COUNT_10M","Local Opponent Count 10m","different-team Players within ten metres.",FeatureCategory.DENSITY,"ENTITY","INTEGER","COUNT",("PAIR_DISTANCE",),0,None),
 _E("CONNECTION_DISTANCE","Connection Distance","distance between ordered same-team Player positions.",FeatureCategory.PASSING_GEOMETRY,"ORDERED_ENTITY_PAIR","SCALAR","METRES",("PAIR_DISTANCE",),0,126.589889),
 _E("CONNECTION_CORRIDOR","Connection Corridor","closed two-metre-wide rectangle around directed segment.",FeatureCategory.PASSING_GEOMETRY,"ORDERED_ENTITY_PAIR","POLYGON2","POLYGON_METRES",("ABSOLUTE_POSITION","CONNECTION_DISTANCE")),
 _E("CORRIDOR_OCCUPANCY","Corridor Occupancy","uniquely positioned opponent Players inside corridor.",FeatureCategory.PASSING_GEOMETRY,"ORDERED_ENTITY_PAIR","INTEGER","COUNT",("CONNECTION_CORRIDOR","ABSOLUTE_POSITION"),0,None),
 _E("PASS_START_POSITION","Pass Start Position","authenticated canonical start coordinate of a source-declared pass.",FeatureCategory.PASSING_GEOMETRY,"SOURCE_PASS_EVENT","POSITION2","POSITION_METRES"),
 _E("PASS_END_POSITION","Pass End Position","authenticated canonical end coordinate of a source-declared pass.",FeatureCategory.PASSING_GEOMETRY,"SOURCE_PASS_EVENT","POSITION2","POSITION_METRES"),
 _E("STATE_DELTA_TIME","State Delta Time","elapsed time since immediately preceding WorldState.",FeatureCategory.TEMPORAL,"WORLD_STATE","SCALAR","SECONDS",(),0,None),
 _E("LIFECYCLE_PERSISTENCE","Lifecycle Persistence","elapsed time since current lifecycle value began.",FeatureCategory.TEMPORAL,"ENTITY","SCALAR","SECONDS",(),0,None),
 _E("POSITION_STABILITY_3","Position Stability 3","RMS distance to centroid over three consecutive positions.",FeatureCategory.TEMPORAL,"ENTITY","SCALAR","METRES",("ABSOLUTE_POSITION",),0,125.095963),
)


def validate_registry(entries: tuple[RegistryEntry, ...]) -> None:
    codes = [e.code for e in entries]
    if len(codes) != len(set(codes)):
        raise PerceptionError("TIP-PER-FEATURE-DEFINITION-INVALID", "duplicate feature identifier")
    known: set[str] = set()
    for entry in entries:
        for dependency in entry.dependencies:
            if dependency not in codes:
                raise PerceptionError("TIP-PER-DEPENDENCY-MISSING", dependency)
            if dependency not in known:
                raise PerceptionError("TIP-PER-DEPENDENCY-CYCLE", f"dependency is not earlier: {entry.code}->{dependency}")
        known.add(entry.code)


def definitions(entries: tuple[RegistryEntry, ...] = DEFAULT_ENTRIES) -> tuple[FeatureDefinition, ...]:
    validate_registry(entries)
    ordered = sorted(entries, key=lambda e: (list(FeatureCategory).index(e.category), e.code))
    return tuple(FeatureDefinition("tip.feature_definition", e.code, e.name, e.description, e.category.value, e.scope,
        e.output_type, e.unit, e.valid_min, e.valid_max, 6 if e.output_type in {"SCALAR","VECTOR2","POSITION2","POLYGON2","POLYLINE2","CIRCLE2"} else 0,
        e.dependencies,"0.1.0",{"/feature_code":{"class":"CONSTANT","operation":"PER_SET_DEFINITION_CONSTANT","sources":[]}}) for e in ordered)
