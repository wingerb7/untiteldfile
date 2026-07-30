from __future__ import annotations

import hashlib
from collections.abc import Mapping
from decimal import Decimal
from math import sqrt
from typing import Any, Iterable

from .errors import PerceptionError
from .geometry import bearing, corridor, distance, displacement, magnitude, point_in_corridor
from .models import FeatureValue, PerceptionDataset, PerceptionFeature, PerceptionFrame, canonical_json_bytes
from .registry import DEFAULT_ENTRIES, RegistryEntry, definitions, validate_registry

CATEGORY_RANK = {name: rank for rank, name in enumerate(("SPATIAL","MOTION","BALL","VISIBILITY","REACHABILITY","DENSITY","PASSING_GEOMETRY","TEMPORAL"))}


def _source(record_id: str, path: str) -> dict[str, str]:
    return {"source_record_id": record_id, "source_path": f"world_model_dataset#{path}"}


def _prov(operation: str, sources: Iterable[dict[str, str]], unavailable: bool = False) -> dict[str, Any]:
    return {"/value": {"class": "DERIVED_DETERMINISTICALLY", "operation": "PER_MARK_UNAVAILABLE" if unavailable else operation,
                       "sources": sorted(sources, key=lambda s: (s["source_record_id"], s["source_path"]))}}


def _position_value(p: tuple[float, float]) -> FeatureValue:
    return FeatureValue(position2={"x_m": p[0], "y_m": p[1]})


def _vector_value(v: tuple[float, float]) -> FeatureValue:
    return FeatureValue(vector2={"x": v[0], "y": v[1]})


def _validate_world(world: Mapping[str, Any]) -> None:
    if not isinstance(world, Mapping) or world.get("schema_id") != "tip.world_model_dataset":
        raise PerceptionError("TIP-PER-INPUT-ARTIFACT-INVALID", "expected tip.world_model_dataset")
    if world.get("contract_version") != "0.1.0":
        raise PerceptionError("TIP-PER-INPUT-VERSION-UNSUPPORTED", str(world.get("contract_version")))
    for field in ("match_id","possession_id","ball","teams","players","event_evidence","world_states","input_provenance","world_provenance"):
        if field not in world:
            raise PerceptionError("TIP-PER-INPUT-SCHEMA-INVALID", f"missing {field}")
    if not world["world_states"] or not world["teams"] or not world["players"]:
        raise PerceptionError("TIP-PER-INPUT-SCHEMA-INVALID", "empty mandatory collection")
    ids = [p.get("player_id") for p in world["players"]]
    if None in ids or len(ids) != len(set(ids)):
        raise PerceptionError("TIP-PER-ENTITY-REFERENCE-INVALID", "invalid or duplicate player identity")
    expected = list(range(len(world["world_states"])))
    actual = [s.get("world_state_index") for s in world["world_states"]]
    if actual != expected:
        raise PerceptionError("TIP-PER-TIMESTAMP-INVALID", "world states are not in canonical index order")
    times = [s.get("canonical_time_seconds") for s in world["world_states"]]
    if any(not isinstance(t, (int,float,Decimal)) for t in times) or any(times[i] < times[i-1] for i in range(1,len(times))):
        raise PerceptionError("TIP-PER-TIMESTAMP-INVALID", "invalid or decreasing timestamp")


def _state_context(world: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    observations = {o["observation_id"]: o for o in state.get("observations", [])}
    positions: dict[str, tuple[float, float]] = {}
    observation_ids: dict[str, tuple[str, ...]] = {}
    ambiguous: set[str] = set()
    for entity_state in [*state.get("player_states", []), state.get("ball_state", {})]:
        entity_id = entity_state.get("player_id") or entity_state.get("ball_id")
        ids = tuple(sorted(entity_state.get("position_observation_ids", [entity_state.get("position_observation_id")]) if entity_id else []))
        ids = tuple(i for i in ids if i)
        observation_ids[entity_id] = ids
        valid = [observations[i] for i in ids if i in observations]
        if len(valid) == 1:
            pos = valid[0].get("position", {})
            if pos.get("availability", "AVAILABLE") == "UNAVAILABLE":
                continue
            x, y = pos.get("x_m"), pos.get("y_m")
            if not isinstance(x,(int,float,Decimal)) or not isinstance(y,(int,float,Decimal)) or not (0 <= x <= 105 and 0 <= y <= 68):
                raise PerceptionError("TIP-PER-GEOMETRY-INVALID", entity_id)
            positions[entity_id] = (float(x), float(y))
        elif len(valid) > 1:
            ambiguous.add(entity_id)
    return {"observations": observations, "positions": positions, "observation_ids": observation_ids, "ambiguous": ambiguous}


def _candidate_key(subjects: tuple[str, ...], scope: str) -> str:
    if scope == "ORDERED_ENTITY_PAIR": return f"{subjects[0]}:to:{subjects[1]}"
    if scope == "UNORDERED_ENTITY_PAIR": return f"{subjects[0]}:and:{subjects[1]}"
    return subjects[0]


def _feature(entry: RegistryEntry, state: dict[str, Any], subjects: tuple[str, ...], obs_ids: tuple[str, ...],
             value: FeatureValue | None, reason: str | None, dependencies: tuple[str, ...],
             sources_override: tuple[dict[str,str], ...] = ()) -> PerceptionFeature:
    fid = f"feature:{state['world_state_id']}:{entry.code.lower()}:{_candidate_key(subjects, entry.scope)}"
    sources = list(sources_override) or [_source(state["world_state_id"], f"/world_states/{state['world_state_index']}/canonical_time_seconds")]
    if not sources_override:sources.extend(_source(subject, f"/world_states/{state['world_state_index']}/observations/{oid}") for subject, oid in zip(subjects, obs_ids))
    return PerceptionFeature("tip.perception_feature", fid, entry.code, entry.name, entry.category.value,
        state["world_state_id"], state["world_state_index"], state["canonical_time_seconds"], subjects, obs_ids,
        dependencies, "AVAILABLE" if reason is None else "UNAVAILABLE", reason, value if reason is None else None, entry.unit,
        _prov("PER_CALCULATE_FEATURE", sources, reason is not None))


def _reason(ctx: dict[str, Any], subjects: tuple[str, ...]) -> str | None:
    if any(s in ctx["ambiguous"] for s in subjects): return "POSITION_AMBIGUOUS"
    if any(s not in ctx["positions"] for s in subjects): return "POSITION_MISSING"
    return None


def _pairs(ids: list[str], ordered: bool) -> list[tuple[str, str]]:
    if ordered: return [(a,b) for a in ids for b in ids if a != b]
    return [(ids[i],ids[j]) for i in range(len(ids)) for j in range(i+1,len(ids))]


def build_perception_dataset(world_model_dataset: Mapping[str, Any], config: None = None,
                             registry: tuple[RegistryEntry, ...] = DEFAULT_ENTRIES) -> PerceptionDataset:
    if config is not None:
        raise PerceptionError("TIP-PER-INPUT-ARTIFACT-INVALID", "Chapter 9 permits no configuration override")
    from src.contracts import Artifact
    if not isinstance(world_model_dataset, Artifact) or not world_model_dataset.validated:
        raise PerceptionError("TIP-PER-INPUT-ARTIFACT-INVALID", "validated WorldModelDataset required")
    _validate_world(world_model_dataset); validate_registry(registry)
    world_model_dataset = world_model_dataset.payload
    players = sorted(world_model_dataset["players"], key=lambda p:p["player_id"])
    player_ids = [p["player_id"] for p in players]
    ball_id = world_model_dataset["ball"]["ball_id"]
    entity_ids = player_ids + [ball_id]
    teams = sorted(world_model_dataset["teams"], key=lambda t:t["team_id"])
    team_of = {p["player_id"]:p["team_id"] for p in players}
    identity = {p["player_id"]:p.get("identity_kind") for p in players}; identity[ball_id] = "IDENTIFIED"
    contexts = [_state_context(world_model_dataset, s) for s in world_model_dataset["world_states"]]
    trajectories={item["event_id"]:(index,item) for index,item in enumerate(world_model_dataset.get("pass_trajectory_evidence",()))}
    frames: list[PerceptionFrame] = []
    history: dict[tuple[str, tuple[str,...]], list[PerceptionFeature]] = {}

    for si, state in enumerate(world_model_dataset["world_states"]):
        lifecycle_by_player = {p["player_id"]: p["lifecycle"] for p in state.get("player_states", [])}
        frame_player_ids = [p["player_id"] for p in players
                            if p.get("identity_kind") == "IDENTIFIED" or lifecycle_by_player.get(p["player_id"]) == "OBSERVED"]
        frame_entity_ids = frame_player_ids + [ball_id]
        ctx = contexts[si]; features: list[PerceptionFeature] = []; by_key: dict[tuple[str,tuple[str,...]],PerceptionFeature] = {}
        def emit(e: RegistryEntry, subjects: tuple[str,...], value: FeatureValue|None, reason: str|None, deps: tuple[str,...]=(),
                 sources: tuple[dict[str,str],...]=()) -> None:
            obs = tuple(oid for s in subjects for oid in ctx["observation_ids"].get(s, ()))
            f = _feature(e,state,subjects,obs,value,reason,deps,sources); features.append(f); by_key[(e.code,subjects)] = f
        for e in registry:
            if e.scope == "OBSERVATION":
                candidates = [(o["observation_id"],) for o in sorted(ctx["observations"].values(), key=lambda o:o["observation_id"])]
            elif e.scope == "ENTITY": candidates = [(x,) for x in frame_entity_ids if not (e.code.startswith("TEAM") or e.code.startswith("LOCAL") or e.code.startswith("NEIGHBOR")) or x in frame_player_ids]
            elif e.scope == "TEAM": candidates = [(t["team_id"],) for t in teams]
            elif e.scope == "WORLD_STATE": candidates = [(state["world_state_id"],)]
            elif e.scope == "SOURCE_PASS_EVENT":
                candidates=[(state["anchor_event_id"],)] if state["anchor_event_id"] in trajectories else []
            elif e.scope == "ORDERED_ENTITY_PAIR": candidates = _pairs(frame_entity_ids,True)
            else: candidates = _pairs(frame_entity_ids,False)
            # exact subject restrictions
            if e.code.startswith("BALL_"): candidates=[(ball_id,)]
            if e.code == "PLAYER_BALL_DISTANCE": candidates=[(p,ball_id) for p in frame_player_ids]
            if e.code == "LIFECYCLE_PERSISTENCE": candidates=[(x,) for x in [*frame_entity_ids,*[t["team_id"] for t in teams]]]
            if e.code in {"CONNECTION_DISTANCE","CONNECTION_CORRIDOR","CORRIDOR_OCCUPANCY"}: candidates=[p for p in _pairs(frame_player_ids,True) if team_of[p[0]]==team_of[p[1]]]
            if e.code in {"NEIGHBOR_COUNT_5M","LOCAL_TEAMMATE_COUNT_10M","LOCAL_OPPONENT_COUNT_10M"}: candidates=[(p,) for p in frame_player_ids]
            for subjects in candidates:
                value=None; reason=None; deps: tuple[str,...]=()
                if e.code == "OBSERVATION_POSITION":
                    o=ctx["observations"][subjects[0]]; p=o["position"]
                    if p.get("availability", "AVAILABLE") == "UNAVAILABLE": reason="POSITION_MISSING"
                    else: value=_position_value((float(p["x_m"]),float(p["y_m"])))
                elif e.code in {"PASS_START_POSITION","PASS_END_POSITION"}:
                    trajectory_index,trajectory=trajectories[subjects[0]]
                    field="start_position" if e.code=="PASS_START_POSITION" else "end_position";position=trajectory[field]
                    reason=None if position.get("availability")=="AVAILABLE" else position.get("unavailable_reason") or "POSITION_MISSING"
                    if not reason:value=_position_value((float(position["x_m"]),float(position["y_m"])))
                    source=(_source(trajectory["event_id"],f"/pass_trajectory_evidence/{trajectory_index}/{field}"),)
                elif e.code == "ABSOLUTE_POSITION": reason=_reason(ctx,subjects); value=None if reason else _position_value(ctx["positions"][subjects[0]])
                elif e.code == "PAIR_DISTANCE": reason=_reason(ctx,subjects); value=None if reason else FeatureValue(scalar=distance(ctx["positions"][subjects[0]],ctx["positions"][subjects[1]]))
                elif e.code == "RELATIVE_POSITION": reason=_reason(ctx,subjects); value=None if reason else _vector_value(displacement(ctx["positions"][subjects[0]],ctx["positions"][subjects[1]]))
                elif e.code == "BEARING":
                    reason=_reason(ctx,subjects)
                    if not reason:
                        try:value=FeatureValue(scalar=bearing(ctx["positions"][subjects[0]],ctx["positions"][subjects[1]]))
                        except ValueError:reason="DEGENERATE_GEOMETRY"
                elif e.code.startswith("TEAM_"):
                    members=sorted(p for p in player_ids if team_of[p]==subjects[0]); reason="POSITION_AMBIGUOUS" if any(p in ctx["ambiguous"] for p in members) else None
                    ps=[ctx["positions"][p] for p in members if p in ctx["positions"]]
                    if not reason and not ps: reason="INSUFFICIENT_SAMPLE_COUNT"
                    if not reason:
                        if e.code=="TEAM_CENTROID": value=_position_value((sum(p[0] for p in ps)/len(ps),sum(p[1] for p in ps)/len(ps)))
                        elif e.code=="TEAM_WIDTH": value=FeatureValue(scalar=max(p[1] for p in ps)-min(p[1] for p in ps))
                        else:value=FeatureValue(scalar=max(p[0] for p in ps)-min(p[0] for p in ps))
                elif e.code in {"ENTITY_VELOCITY","ENTITY_SPEED","MOTION_HEADING"}:
                    reason=_reason(ctx,subjects)
                    if identity.get(subjects[0])!="IDENTIFIED":reason="ENTITY_NOT_IDENTIFIED"
                    if si==0:reason="PREVIOUS_STATE_MISSING"
                    elif not reason:
                        prior=contexts[si-1]
                        if subjects[0] not in prior["positions"]:reason="PREVIOUS_POSITION_MISSING"
                        else:
                            dt=state["canonical_time_seconds"]-world_model_dataset["world_states"][si-1]["canonical_time_seconds"]
                            if dt==0:reason="ZERO_TIME_DELTA"
                            else:
                                v=tuple(x/dt for x in displacement(prior["positions"][subjects[0]],ctx["positions"][subjects[0]]))
                                if e.code=="ENTITY_VELOCITY":value=_vector_value(v)
                                elif e.code=="ENTITY_SPEED":value=FeatureValue(scalar=magnitude(v))
                                elif magnitude(v)==0:reason="DEGENERATE_GEOMETRY"
                                else:value=FeatureValue(scalar=bearing((0,0),v))
                elif e.code in {"RELATIVE_VELOCITY","CLOSING_SPEED","SEPARATION_SPEED"}:
                    reason=_reason(ctx,subjects)
                    if si==0:reason="PREVIOUS_STATE_MISSING"
                    elif any(identity.get(s)!="IDENTIFIED" for s in subjects):reason="ENTITY_NOT_IDENTIFIED"
                    elif not reason:
                        prior=contexts[si-1]; dt=state["canonical_time_seconds"]-world_model_dataset["world_states"][si-1]["canonical_time_seconds"]
                        if any(s not in prior["positions"] for s in subjects):reason="PREVIOUS_POSITION_MISSING"
                        elif dt==0:reason="ZERO_TIME_DELTA"
                        else:
                            va=tuple(x/dt for x in displacement(prior["positions"][subjects[0]],ctx["positions"][subjects[0]])); vb=tuple(x/dt for x in displacement(prior["positions"][subjects[1]],ctx["positions"][subjects[1]])); rv=(vb[0]-va[0],vb[1]-va[1])
                            if e.code=="RELATIVE_VELOCITY":value=_vector_value(rv)
                            else:
                                rp=displacement(ctx["positions"][subjects[0]],ctx["positions"][subjects[1]]); d=magnitude(rp)
                                if d==0:reason="DEGENERATE_GEOMETRY"
                                else:
                                    closing=-(rp[0]*rv[0]+rp[1]*rv[1])/d; value=FeatureValue(scalar=closing if e.code=="CLOSING_SPEED" else -closing)
                elif e.code in {"BALL_POSITION","BALL_VELOCITY","BALL_DIRECTION"}:
                    source={"BALL_POSITION":"ABSOLUTE_POSITION","BALL_VELOCITY":"ENTITY_VELOCITY","BALL_DIRECTION":"MOTION_HEADING"}[e.code]
                    f=by_key.get((source,subjects)); reason="DEPENDENCY_UNAVAILABLE" if not f or f.status=="UNAVAILABLE" else None; value=None if reason else f.value; deps=() if not f else (f.feature_id,)
                elif e.code == "PLAYER_BALL_DISTANCE":
                    f=next((candidate for (code,pair),candidate in by_key.items()
                            if code == "PAIR_DISTANCE" and set(pair) == set(subjects)),None)
                    reason="DEPENDENCY_UNAVAILABLE" if not f or f.status=="UNAVAILABLE" else None
                    value=None if reason else f.value
                    deps=() if not f else (f.feature_id,)
                elif e.code in {"NEIGHBOR_COUNT_5M","LOCAL_TEAMMATE_COUNT_10M","LOCAL_OPPONENT_COUNT_10M"}:
                    reason=_reason(ctx,subjects)
                    if not reason:
                        radius=5 if e.code=="NEIGHBOR_COUNT_5M" else 10
                        candidates2=[p for p in frame_player_ids if p!=subjects[0] and p in ctx["positions"]]
                        if e.code=="LOCAL_TEAMMATE_COUNT_10M":candidates2=[p for p in candidates2 if team_of[p]==team_of[subjects[0]]]
                        if e.code=="LOCAL_OPPONENT_COUNT_10M":candidates2=[p for p in candidates2 if team_of[p]!=team_of[subjects[0]]]
                        value=FeatureValue(integer=sum(distance(ctx["positions"][subjects[0]],ctx["positions"][p])<=radius for p in candidates2))
                elif e.code=="CONNECTION_DISTANCE": reason=_reason(ctx,subjects); value=None if reason else FeatureValue(scalar=distance(ctx["positions"][subjects[0]],ctx["positions"][subjects[1]]))
                elif e.code in {"CONNECTION_CORRIDOR","CORRIDOR_OCCUPANCY"}:
                    reason=_reason(ctx,subjects)
                    if not reason:
                        try: poly=corridor(ctx["positions"][subjects[0]],ctx["positions"][subjects[1]])
                        except ValueError:reason="DEGENERATE_GEOMETRY"
                        else:
                            if e.code=="CONNECTION_CORRIDOR":value=FeatureValue(polygon2=tuple({"x_m":p[0],"y_m":p[1]} for p in poly))
                            else:value=FeatureValue(integer=sum(point_in_corridor(ctx["positions"][p],poly) for p in frame_player_ids if team_of[p]!=team_of[subjects[0]] and p in ctx["positions"]))
                elif e.code=="STATE_DELTA_TIME":
                    if si==0:reason="PREVIOUS_STATE_MISSING"
                    else:value=FeatureValue(scalar=state["canonical_time_seconds"]-world_model_dataset["world_states"][si-1]["canonical_time_seconds"])
                elif e.code=="LIFECYCLE_PERSISTENCE":
                    eid=subjects[0]; current=_lifecycle(state,eid); start=si
                    while start>0 and _lifecycle(world_model_dataset["world_states"][start-1],eid)==current:start-=1
                    value=FeatureValue(scalar=state["canonical_time_seconds"]-world_model_dataset["world_states"][start]["canonical_time_seconds"])
                elif e.code=="POSITION_STABILITY_3":
                    reason=_reason(ctx,subjects)
                    if si<2:reason="INSUFFICIENT_SAMPLE_COUNT"
                    elif not reason:
                        ps=[contexts[j]["positions"].get(subjects[0]) for j in range(si-2,si+1)]
                        if any(p is None for p in ps):reason="PREVIOUS_POSITION_MISSING"
                        else:
                            cx=sum(p[0] for p in ps)/3; cy=sum(p[1] for p in ps)/3
                            value=FeatureValue(scalar=sqrt(sum(distance(p,(cx,cy))**2 for p in ps)/3))
                if not deps and e.dependencies:
                    deps=tuple(sorted(f.feature_id for (code, candidate),f in by_key.items()
                                      if code in e.dependencies and (set(candidate) & set(subjects) or e.scope in {"TEAM","WORLD_STATE"})))
                emit(e,subjects,value,reason,deps,source if e.code in {"PASS_START_POSITION","PASS_END_POSITION"} else ())
        features.sort(key=lambda f:(CATEGORY_RANK[f.category],f.feature_code,f.subject_ids,f.input_observation_ids,f.dependency_feature_ids,f.feature_id))
        frames.append(PerceptionFrame("tip.perception_frame",f"perception_frame:{state['world_state_id']}",state["world_state_id"],si,state["canonical_time_seconds"],tuple(features),_prov("PER_BUILD_COLLECTION",[_source(state["world_state_id"],f"/world_states/{si}")])))
    from src.contracts import canonical_bytes as contract_canonical_bytes
    world_bytes=contract_canonical_bytes(world_model_dataset)
    result=PerceptionDataset("tip.perception_dataset","0.1.0","0.1.0",hashlib.sha256(world_bytes).hexdigest(),world_model_dataset["match_id"],world_model_dataset["possession_id"],tuple(world_model_dataset["event_evidence"]),tuple(world_model_dataset.get("pass_trajectory_evidence",())),definitions(registry),tuple(frames),{"input_provenance":world_model_dataset["input_provenance"],"world_provenance":world_model_dataset["world_provenance"]},_prov("PER_BUILD_COLLECTION",[_source(world_model_dataset["match_id"],"")]))
    # Authentication performs the single canonical finite-number validation.
    # Avoid serializing this large immutable dataclass a second time here.
    return result


def _lifecycle(state: dict[str,Any], entity_id: str) -> str:
    if state.get("ball_state",{}).get("ball_id")==entity_id:return state["ball_state"].get("lifecycle","UNKNOWN")
    for item in [*state.get("player_states",[]),*state.get("team_states",[])]:
        if item.get("player_id")==entity_id or item.get("team_id")==entity_id:return item.get("lifecycle","UNKNOWN")
    raise PerceptionError("TIP-PER-ENTITY-REFERENCE-INVALID",entity_id)


def nearest_player_to_ball(dataset: PerceptionDataset, frame_index: int) -> str | None:
    pairs=[]
    for f in dataset.frames[frame_index].features:
        if f.feature_code=="PAIR_DISTANCE" and f.status=="AVAILABLE" and f.value and f.value.scalar is not None and any(s.startswith("ball:") for s in f.subject_ids):
            player=next((s for s in f.subject_ids if s.startswith("player:")),None)
            if player:pairs.append((f.value.scalar,player))
    return min(pairs)[1] if pairs else None
