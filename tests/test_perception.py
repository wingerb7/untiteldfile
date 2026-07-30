from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.perception.engine import build_perception_dataset, nearest_player_to_ball
from src.perception.errors import PerceptionError
from src.perception.geometry import corridor, point_in_corridor, point_segment_distance
from src.perception.registry import DEFAULT_ENTRIES, RegistryEntry, validate_registry
from src.contracts import Artifact
from src.world_model import MEDIA_TYPE as WORLD_MEDIA


def world(states: list[dict[str, tuple[float,float]]]|None=None) -> dict:
    samples=states or [
        {"player:a":(10,10),"player:b":(20,14),"player:c":(15,11),"ball:m:analysis_scope:1":(10,10)},
        {"player:a":(12,10),"player:b":(20,16),"player:c":(14,11),"ball:m:analysis_scope:1":(14,10)},
        {"player:a":(14,10),"player:b":(20,18),"player:c":(13,11),"ball:m:analysis_scope:1":(18,10)},
    ]
    players=[
        {"schema_id":"tip.player","player_id":"player:a","identity_kind":"IDENTIFIED","display_name":"A","team_id":"team:x","origin_observation_id":None,"world_provenance":{}},
        {"schema_id":"tip.player","player_id":"player:b","identity_kind":"IDENTIFIED","display_name":"B","team_id":"team:x","origin_observation_id":None,"world_provenance":{}},
        {"schema_id":"tip.player","player_id":"player:c","identity_kind":"IDENTIFIED","display_name":"C","team_id":"team:y","origin_observation_id":None,"world_provenance":{}},
    ]
    ws=[]
    for i,positions in enumerate(samples):
        sid=f"world_state:m:1:e{i}"; obs=[]; pstates=[]
        for eid,pos in sorted(positions.items()):
            oid=f"observation:{sid}:{eid}"; kind="BALL" if eid.startswith("ball:") else "PLAYER"
            obs.append({"schema_id":"tip.world_observation","observation_id":oid,"world_state_id":sid,"subject_kind":kind,"subject_id":eid,"observation_kind":"EVENT_BALL" if kind=="BALL" else "FREEZE_FRAME","position":{"x_m":pos[0],"y_m":pos[1],"z_m":None},"visibility":"UNKNOWN","anchor_event_id":f"event:{i}","source_timeline_index":i,"normalized_observation_id":None,"world_provenance":{}})
            if kind=="PLAYER":pstates.append({"schema_id":"tip.player_state","player_id":eid,"lifecycle":"OBSERVED","visibility":"VISIBLE","observation_ids":[oid],"position_observation_ids":[oid],"world_provenance":{}})
        boid=f"observation:{sid}:ball:m:analysis_scope:1"
        team_states=[{"schema_id":"tip.team_state","team_id":tid,"lifecycle":"OBSERVED","player_ids":[p["player_id"] for p in players if p["team_id"]==tid],"observed_player_ids":[p["player_id"] for p in pstates if next(x for x in players if x["player_id"]==p["player_id"])["team_id"]==tid],"world_provenance":{}} for tid in ("team:x","team:y")]
        ws.append({"schema_id":"tip.world_state","world_state_id":sid,"world_state_index":i,"anchor_timeline_index":i,"canonical_time_seconds":float(i),"period_id":"period:1","period_number":1,"period_time_seconds":float(i),"anchor_event_id":f"event:{i}","pitch_id":"pitch:m:canonical:105x68","possession_id":"possession:1","ball_state":{"schema_id":"tip.ball_state","ball_id":"ball:m:analysis_scope:1","lifecycle":"OBSERVED","visibility":"UNKNOWN","ownership_status":"UNKNOWN","owner_player_id":None,"observation_id":boid,"position_observation_id":boid,"world_provenance":{}},"team_states":team_states,"player_states":pstates,"observations":obs,"relationships":[],"world_provenance":{}})
    data={"schema_id":"tip.world_model_dataset","contract_version":"0.1.0","input_contract_version":"0.1.0","synchronized_dataset_sha256":"0"*64,"match_id":"match:m","possession_id":"possession:1","pitch":{},"possession":{},"ball":{"schema_id":"tip.ball","ball_id":"ball:m:analysis_scope:1","world_provenance":{}},"teams":[{"schema_id":"tip.team","team_id":"team:x","identity_kind":"IDENTIFIED","display_name":"X","world_provenance":{}},{"schema_id":"tip.team","team_id":"team:y","identity_kind":"IDENTIFIED","display_name":"Y","world_provenance":{}}],"players":players,"event_evidence":[],"world_states":ws,"input_provenance":{"normalized_provenance":{},"synchronization_provenance":{}},"world_provenance":{}}
    return Artifact(data,WORLD_MEDIA,"0"*64,validated=True)


def features(dataset, frame, code):
    return [f for f in dataset.frames[frame].features if f.feature_code==code]


def one(dataset, frame, code, subjects):
    return next(f for f in features(dataset,frame,code) if f.subject_ids==subjects)


def test_spatial_motion_team_ball_and_temporal_features() -> None:
    d=build_perception_dataset(world())
    assert one(d,0,"PAIR_DISTANCE",("player:a","player:b")).value.scalar == pytest.approx(10.770329614)
    assert one(d,0,"RELATIVE_POSITION",("player:a","player:b")).value.vector2 == {"x":10,"y":4}
    assert one(d,0,"TEAM_CENTROID",("team:x",)).value.position2 == {"x_m":15,"y_m":12}
    assert one(d,0,"TEAM_WIDTH",("team:x",)).value.scalar == 4
    assert one(d,0,"TEAM_DEPTH",("team:x",)).value.scalar == 10
    assert one(d,1,"ENTITY_VELOCITY",("player:a",)).value.vector2 == {"x":2,"y":0}
    assert one(d,1,"ENTITY_SPEED",("player:a",)).value.scalar == 2
    assert one(d,1,"BALL_VELOCITY",("ball:m:analysis_scope:1",)).value.vector2 == {"x":4,"y":0}
    assert one(d,1,"BALL_DIRECTION",("ball:m:analysis_scope:1",)).value.scalar == 0
    player_ball=one(d,1,"PLAYER_BALL_DISTANCE",("player:a","ball:m:analysis_scope:1"))
    assert player_ball.value.scalar == 2
    assert len(player_ball.dependency_feature_ids) == 1
    assert one(d,2,"POSITION_STABILITY_3",("player:a",)).status == "AVAILABLE"


def test_nearest_tie_break_density_and_corridor() -> None:
    d=build_perception_dataset(world([{ "player:a":(9,10),"player:b":(11,10),"player:c":(14,10),"ball:m:analysis_scope:1":(10,10)}]))
    assert nearest_player_to_ball(d,0)=="player:a"
    assert one(d,0,"NEIGHBOR_COUNT_5M",("player:a",)).value.integer == 2
    poly=one(d,0,"CONNECTION_CORRIDOR",("player:a","player:b")).value.polygon2
    assert len(poly)==5
    assert one(d,0,"CORRIDOR_OCCUPANCY",("player:a","player:b")).value.integer == 0
    assert point_in_corridor((10,10),corridor((9,10),(11,10)))
    assert point_segment_distance((10,12),(9,10),(11,10))==2


def test_provenance_identifiers_order_and_serialization_are_stable() -> None:
    a=build_perception_dataset(world()); b=build_perception_dataset(world())
    assert a.canonical_bytes()==b.canonical_bytes() and a.sha256==b.sha256
    ids=[f.feature_id for frame in a.frames for f in frame.features]
    assert len(ids)==len(set(ids))
    assert all(f.perception_provenance for frame in a.frames for f in frame.features)
    assert [f.world_state_index for f in a.frames]==[0,1,2]


def test_registry_and_input_failures() -> None:
    duplicate=DEFAULT_ENTRIES+(DEFAULT_ENTRIES[0],)
    with pytest.raises(PerceptionError,match="TIP-PER-FEATURE-DEFINITION-INVALID"):validate_registry(duplicate)
    bad=RegistryEntry("X","x","x",DEFAULT_ENTRIES[0].category,"ENTITY","SCALAR","NONE",("NOPE",))
    with pytest.raises(PerceptionError,match="TIP-PER-DEPENDENCY-MISSING"):validate_registry((bad,))
    cycle=(RegistryEntry("A","a","a",DEFAULT_ENTRIES[0].category,"ENTITY","SCALAR","NONE",("B",)),RegistryEntry("B","b","b",DEFAULT_ENTRIES[0].category,"ENTITY","SCALAR","NONE",("A",)))
    with pytest.raises(PerceptionError):validate_registry(cycle)
    raw=world().data; raw["players"].append(raw["players"][0]); broken=Artifact(raw,WORLD_MEDIA,"0"*64,validated=True)
    with pytest.raises(PerceptionError,match="TIP-PER-ENTITY-REFERENCE-INVALID"):build_perception_dataset(broken)


def test_missing_and_degenerate_inputs_are_unavailable() -> None:
    raw=world().data; raw["world_states"][0]["player_states"][0]["position_observation_ids"]=[]; w=Artifact(raw,WORLD_MEDIA,"0"*64,validated=True)
    d=build_perception_dataset(w)
    assert one(d,0,"ABSOLUTE_POSITION",("player:a",)).unavailable_reason=="POSITION_MISSING"
    assert one(d,0,"STATE_DELTA_TIME",(w["world_states"][0]["world_state_id"],)).unavailable_reason=="PREVIOUS_STATE_MISSING"
    assert one(d,0,"PLAYER_BALL_DISTANCE",("player:a","ball:m:analysis_scope:1")).unavailable_reason=="DEPENDENCY_UNAVAILABLE"


def test_locatelli_fixture_can_form_real_perception_dataset() -> None:
    from src.source_selection import PINNED_REVISION, select_source_documents
    from src.normalization import build_normalized_dataset
    from src.synchronization import build_synchronized_dataset
    from src.world_model import build_world_model_dataset, validate_world_model_dataset
    events=json.loads(Path("data/open-data/data/events/3788754.json").read_text()); frames=json.loads(Path("data/open-data/data/three-sixty/3788754.json").read_text())
    request={"source_dataset":"statsbomb-open-data","source_revision":PINNED_REVISION,"match_id":3788754,"possession_id":40}
    w=validate_world_model_dataset(build_world_model_dataset(build_synchronized_dataset(build_normalized_dataset(select_source_documents(events,frames,request)))))
    d=build_perception_dataset(w)
    assert len(d.frames)==46
    assert any(f.status=="AVAILABLE" for f in features(d,38,"BALL_POSITION"))
    assert d.match_id.startswith("match:statsbomb:")
    pass_evidence=next(e for e in d.event_evidence if e["event_id"]=="event:statsbomb:e51fde20-708e-49e4-ae77-5bc768e5f411")
    assert pass_evidence==next(e for e in w["event_evidence"] if e["event_id"]==pass_evidence["event_id"])


def test_semantic_foundations_diagnostic_is_complete_and_fail_closed() -> None:
    report=json.loads(Path("audit/semantic_foundations/semantic_foundations_diagnostic.json").read_text())
    rows={row["concept"]:row for row in report["concept_audit_matrix"]}
    assert rows["PLAYER_BALL_DISTANCE"]["implementation_decision"]=="IMPLEMENT"
    assert all(not rows[code]["normatively_supportable_now"] for code in (
        "BALL_CONTROLLED","BALL_FREE","BALL_RECEIVED","BALL_RELEASED","BALL_LOST","BALL_RECOVERED",
        "PASS_START","PASS_END","CARRY_START","CARRY_END","SHOT",
        "PLAYER_CAN_REACH_BALL","PLAYER_CANNOT_REACH_BALL",
        "PASSING_CORRIDOR_OPEN","PASSING_CORRIDOR_CLOSED"))
    fixtures={item["fixture"]:item for item in report["fixtures"]}
    assert fixtures["locatelli"]["repeated_run_deterministic"] is True
    assert fixtures["depay"]["repeated_run_deterministic"] is True
    assert fixtures["di_maria"]["failure_code"]=="SRC_EVENT_INDEX_INVALID"
    assert fixtures["di_maria"]["downstream_executed"] is False
    assert report["import_isolation_result"]["passed"] is True
