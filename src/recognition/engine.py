from __future__ import annotations
from typing import Any
from src.contracts import Artifact, digest
from src.perception.authentication import PERCEPTION_MEDIA_TYPE,validate_perception_dataset
from .errors import RecognitionError
from .models import RecognitionDataset, RecognitionFrame, RecognitionMetadata, RecognitionRecord
from .registry import CONCEPTS

MEDIA_TYPE = "application/vnd.tip.recognition-dataset+json"
SOURCE_CONCEPTS={"PASS":"SOURCE_DECLARED_PASS","CARRY":"SOURCE_DECLARED_CARRY","SHOT":"SOURCE_DECLARED_SHOT","BALL_RECEIPT":"SOURCE_DECLARED_BALL_RECEIPT"}
EVIDENCE_FIELDS={"event_id","event_type","actor","recipient","canonical_timestamp","source_record_id","related_event_ids","outcome","authenticated_provenance"}

def _source(record_id: str, path: str) -> dict[str, str]:
    return {"source_record_id": record_id, "source_path": f"perception_dataset#{path}"}

def _prov(operation: str, sources: list[dict[str, str]]) -> dict[str, Any]:
    return {"/value":{"class":"DERIVED_DETERMINISTICALLY","operation":operation,
            "sources":sorted(sources,key=lambda s:(s["source_record_id"],s["source_path"]))}}

def _record(concept: str, frame: dict[str, Any], participants: tuple[str, ...], features: tuple[dict[str, Any], ...], frame_index: int) -> RecognitionRecord:
    suffix=":and:".join(participants)
    rid=f"recognition:{frame['perception_frame_id']}:{concept.lower()}:{suffix}"
    supporting=tuple(sorted(f["feature_id"] for f in features))
    sources=[_source(f["feature_id"],f"/frames/{frame_index}/features/{f['feature_id']}") for f in features]
    return RecognitionRecord("tip.recognition_record",rid,concept,frame["perception_frame_id"],frame["world_state_id"],
        frame["world_state_index"],frame["canonical_time_seconds"],participants,supporting,(),_prov("REC_CLASSIFY_CONCEPT",sources))

def _evidenced_record(concept: str, frame: dict[str, Any], participants: tuple[str, ...],
                      features: tuple[dict[str, Any], ...], evidence_id: str, frame_index: int) -> RecognitionRecord:
    base=_record(concept,frame,participants,features,frame_index)
    sources=list(base.recognition_provenance["/value"]["sources"])
    sources.append(_source(evidence_id,f"/event_evidence/{frame_index}"))
    return RecognitionRecord(base.schema_id,base.recognition_id,base.concept_code,base.perception_frame_id,
        base.world_state_id,base.world_state_index,base.canonical_time_seconds,base.participant_entity_ids,
        base.supporting_feature_ids,(evidence_id,),_prov("REC_AUTHENTICATE_PASS_LINE_CROSSING",sources))

def _defensive_line_records(frame:dict[str,Any], by_code:dict[str,list[dict[str,Any]]], all_by_code:dict[str,list[dict[str,Any]]],
                            evidence:dict[str,Any], frame_index:int)->list[RecognitionRecord]:
    if evidence.get("event_type")!="PASS" or not evidence.get("recipient"): return []
    positions={}
    position_features={}
    for feature in by_code.get("ABSOLUTE_POSITION",()):
        subjects=tuple(feature.get("subject_ids",()))
        value=(feature.get("value") or {}).get("position2") or {}
        if len(subjects)==1 and subjects[0].startswith("player:") and isinstance(value.get("x_m"),(int,float)) and isinstance(value.get("y_m"),(int,float)):
            positions[subjects[0]]=(float(value["x_m"]),float(value["y_m"]));position_features[subjects[0]]=feature
    actor,recipient=evidence["actor"],evidence["recipient"]
    start=next((feature for feature in by_code.get("PASS_START_POSITION",()) if tuple(feature.get("subject_ids",()))==(evidence["event_id"],)),None)
    end=next((feature for feature in by_code.get("PASS_END_POSITION",()) if tuple(feature.get("subject_ids",()))==(evidence["event_id"],)),None)
    if start is None or end is None:return []
    start_position=(start.get("value") or {}).get("position2") or {};end_position=(end.get("value") or {}).get("position2") or {}
    if any(not isinstance(position.get(axis),(int,float)) for position in (start_position,end_position) for axis in ("x_m","y_m")):return []
    # CONNECTION_DISTANCE is emitted only for same-team pairs, so its authenticated
    # subject pairs provide team membership without importing World Model identity.
    adjacency={player:set() for player in positions}
    connection_features=[]
    for feature in all_by_code.get("CONNECTION_DISTANCE",()):
        subjects=tuple(feature.get("subject_ids",()))
        if len(subjects)==2:
            adjacency.setdefault(subjects[0],set()).add(subjects[1]);adjacency.setdefault(subjects[1],set()).add(subjects[0])
            if feature.get("status")=="AVAILABLE" and all(subject in positions for subject in subjects):connection_features.append(feature)
    attacking=set();pending=[actor]
    while pending:
        player=pending.pop()
        if player in attacking:continue
        attacking.add(player);pending.extend(sorted(adjacency.get(player,())-attacking))
    opponents=sorted(set(positions)-attacking)
    if len(opponents)<3:return []
    best=None
    for anchor in opponents:
        members=tuple(sorted(player for player in opponents if abs(positions[player][0]-positions[anchor][0])<=4.0))
        if len(members)<3:continue
        span=max(positions[player][1] for player in members)-min(positions[player][1] for player in members)
        if span<8.0:continue
        mean_x=sum(positions[player][0] for player in members)/len(members)
        key=(-len(members),-span,mean_x,members)
        if best is None or key<best[0]:best=(key,members,mean_x)
    if best is None:return []
    _,members,line_x=best
    member_connections=tuple(feature for feature in connection_features if set(feature["subject_ids"])<=set(members))
    if not member_connections:return []
    supporting=tuple((*[position_features[player] for player in members],*member_connections))
    line=_record("DEFENSIVE_LINE_STATE",frame,members,supporting,frame_index)
    if (float(start_position["x_m"])-line_x)*(float(end_position["x_m"])-line_x)>=0:return [line]
    crossing_features=tuple({feature["feature_id"]:feature for feature in (*supporting,start,end)}.values())
    crossing=_evidenced_record("PASS_CROSSES_DEFENSIVE_LINE",frame,(actor,recipient,*members),crossing_features,evidence["event_id"],frame_index)
    return [line,crossing]

def _validate_event_evidence(data: dict[str,Any]) -> list[dict[str,Any]]:
    evidence=data.get("event_evidence");frames=data.get("frames",[])
    if not isinstance(evidence,(list,tuple)) or len(evidence)!=len(frames):raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
    ids=set()
    for index,(item,frame) in enumerate(zip(evidence,frames)):
        if not isinstance(item,dict) or set(item)!=EVIDENCE_FIELDS or item.get("event_type") not in SOURCE_CONCEPTS:raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
        if not isinstance(item.get("event_id"),str) or item["event_id"] in ids or not isinstance(item.get("actor"),str) or (item.get("recipient") is not None and not isinstance(item["recipient"],str)):raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
        if item.get("canonical_timestamp")!=frame.get("canonical_time_seconds") or not isinstance(item.get("source_record_id"),str):raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
        provenance=item.get("authenticated_provenance")
        related=item.get("related_event_ids")
        if not isinstance(related,(list,tuple)) or any(not isinstance(rid,str) or not rid for rid in related) or len(related)!=len(set(related)):raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
        if item.get("outcome") is not None and not isinstance(item["outcome"],str):raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
        if not isinstance(provenance,dict) or set(provenance)!={"/event_id","/event_type","/actor","/recipient","/canonical_timestamp","/source_record_id","/related_event_ids","/outcome"}:raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
        for record in provenance.values():
            sources=record.get("sources",[]) if isinstance(record,dict) else []
            if record.get("class")!="PRESERVED_AUTHENTICATED_INPUT" or record.get("operation")!="WORLD_PRESERVE_EVENT_EVIDENCE" or len(sources)!=1 or not sources[0].get("source_path","").startswith("synchronized_dataset#/timeline/"):raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
        ids.add(item["event_id"])
    return list(evidence)

def _event_record(evidence:dict[str,Any],frame:dict[str,Any],index:int)->RecognitionRecord:
    concept=SOURCE_CONCEPTS[evidence["event_type"]];participants=(evidence["actor"],) if evidence["recipient"] is None else (evidence["actor"],evidence["recipient"])
    rid=f"recognition:{frame['perception_frame_id']}:{concept.lower()}:{evidence['event_id']}"
    source=_source(evidence["event_id"],f"/event_evidence/{index}")
    return RecognitionRecord("tip.recognition_record",rid,concept,frame["perception_frame_id"],frame["world_state_id"],frame["world_state_index"],frame["canonical_time_seconds"],participants,(),(evidence["event_id"],),_prov("REC_CLASSIFY_SOURCE_DECLARATION",[source]))

def build_recognition_dataset(perception: Artifact) -> Artifact:
    if not isinstance(perception,Artifact) or not perception.validated or not perception.authentic(PERCEPTION_MEDIA_TYPE,"tip.perception_dataset"):
        raise RecognitionError("TIP-REC-INPUT-ARTIFACT-INVALID")
    if perception.get("contract_version")!="0.1.0": raise RecognitionError("TIP-REC-INPUT-VERSION-UNSUPPORTED")
    try:validate_perception_dataset(perception)
    except Exception as exc:raise RecognitionError("TIP-REC-INPUT-SCHEMA-INVALID") from exc
    data=perception.payload
    event_evidence=_validate_event_evidence(data)
    definitions={d.get("feature_code") for d in data.get("feature_definitions",[])}
    optional={"DEFENSIVE_LINE_STATE","PASS_CROSSES_DEFENSIVE_LINE"}
    required={code for concept in CONCEPTS if concept.concept_code not in optional for code in concept.required_feature_codes}
    if not required<=definitions: raise RecognitionError("TIP-REC-FEATURE-MISSING")
    frames=[]; all_ids=set(); total=0
    for fi,frame in enumerate(data.get("frames",[])):
        if frame.get("world_state_index")!=fi: raise RecognitionError("TIP-REC-TIMESTAMP-INVALID")
        available=[f for f in frame.get("features",[]) if f.get("status")=="AVAILABLE"]
        by_code:dict[str,list[dict[str,Any]]]={}
        for feature in available: by_code.setdefault(feature["feature_code"],[]).append(feature)
        all_by_code:dict[str,list[dict[str,Any]]]={}
        for feature in frame.get("features",[]):all_by_code.setdefault(feature["feature_code"],[]).append(feature)
        records=[_event_record(event_evidence[fi],frame,fi)]
        records.extend(_defensive_line_records(frame,by_code,all_by_code,event_evidence[fi],fi))
        for feature in by_code.get("ENTITY_SPEED",[]):
            subjects=tuple(feature["subject_ids"]); value=(feature.get("value") or {}).get("scalar")
            if len(subjects)!=1 or not subjects[0].startswith("player:") or not isinstance(value,(int,float)): continue
            if value>0: records.append(_record("PLAYER_MOVING",frame,subjects,(feature,),fi))
            elif value==0: records.append(_record("PLAYER_STATIONARY",frame,subjects,(feature,),fi))
        distances=[]
        for feature in by_code.get("PAIR_DISTANCE",[]):
            subjects=tuple(feature["subject_ids"]); value=(feature.get("value") or {}).get("scalar")
            player=next((s for s in subjects if s.startswith("player:")),None);ball=next((s for s in subjects if s.startswith("ball:")),None)
            if player and ball and isinstance(value,(int,float)): distances.append((value,player,feature))
        if distances:
            _,player,feature=min(distances,key=lambda x:(x[0],x[1]));records.append(_record("PLAYER_NEAREST_BALL",frame,(player,),(feature,),fi))
        corridors={tuple(f["subject_ids"]):f for f in by_code.get("CONNECTION_CORRIDOR",[])}
        for occupancy in by_code.get("CORRIDOR_OCCUPANCY",[]):
            subjects=tuple(occupancy["subject_ids"]); corridor=corridors.get(subjects); count=(occupancy.get("value") or {}).get("integer")
            if corridor is None or not isinstance(count,int): continue
            concept="PASSING_CORRIDOR_EXISTS" if count==0 else "PASSING_CORRIDOR_OBSTRUCTED"
            records.append(_record(concept,frame,subjects,(corridor,occupancy),fi))
        records.sort(key=lambda r:(r.concept_code,r.participant_entity_ids,r.supporting_feature_ids,r.supporting_event_evidence_ids,r.recognition_id))
        ids=[r.recognition_id for r in records]
        if len(ids)!=len(set(ids)) or any(x in all_ids for x in ids): raise RecognitionError("TIP-REC-IDENTIFIER-DUPLICATE")
        all_ids.update(ids);total+=len(records)
        rf=RecognitionFrame("tip.recognition_frame",f"recognition_frame:{frame['perception_frame_id']}",frame["perception_frame_id"],
            frame["world_state_id"],fi,frame["canonical_time_seconds"],tuple(records),
            _prov("REC_BUILD_FRAME",[_source(frame["perception_frame_id"],f"/frames/{fi}")]))
        frames.append(rf)
    metadata=RecognitionMetadata("tip.recognition_metadata","0.1.0",len(CONCEPTS),len(frames),total,
        _prov("REC_BUILD_METADATA",[_source(data["match_id"],"")]))
    dataset=RecognitionDataset("tip.recognition_dataset","0.1.0","0.1.0",perception.sha256,data["match_id"],data["possession_id"],
        tuple(event_evidence),CONCEPTS,tuple(frames),metadata,{"input_provenance":data["input_provenance"],"perception_provenance":data["perception_provenance"]},
        _prov("REC_BUILD_DATASET",[_source(data["match_id"],"")]))
    artifact=Artifact(dataset,MEDIA_TYPE,perception.sha256,perception.source_hashes)
    return validate_recognition_dataset(artifact, perception)

def validate_recognition_dataset(recognition: Artifact, perception: Artifact | None = None) -> Artifact:
    if not isinstance(recognition,Artifact) or not recognition.authentic(MEDIA_TYPE,"tip.recognition_dataset"):
        raise RecognitionError("TIP-REC-INPUT-ARTIFACT-INVALID")
    if recognition.get("contract_version")!="0.1.0": raise RecognitionError("TIP-REC-INPUT-VERSION-UNSUPPORTED")
    if recognition.get("perception_dataset_sha256")!=recognition.direct_input_sha256: raise RecognitionError("TIP-REC-INPUT-HASH-INVALID")
    data=recognition.payload;frames=data.get("frames",[]);event_evidence=_validate_event_evidence(data)
    perception_frames={}
    if perception is not None:
        if not perception.validated or not perception.authentic(PERCEPTION_MEDIA_TYPE,"tip.perception_dataset") or perception.sha256!=recognition.direct_input_sha256:
            raise RecognitionError("TIP-REC-INPUT-HASH-INVALID")
        perception_data=perception.payload
        perception_frames={f["perception_frame_id"]:f for f in perception_data.get("frames",[])}
        if tuple(perception_data.get("event_evidence",()))!=tuple(event_evidence):raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
    if [f.get("world_state_index") for f in frames]!=list(range(len(frames))): raise RecognitionError("TIP-REC-ORDERING-INVALID")
    seen=set();previous=None
    concept_codes={c["concept_code"] for c in data.get("concepts",[])}
    for frame in frames:
        timestamp=frame.get("canonical_time_seconds")
        if not isinstance(timestamp,(int,float)) or (previous is not None and timestamp<previous): raise RecognitionError("TIP-REC-TIMESTAMP-INVALID")
        previous=timestamp
        upstream=perception_frames.get(frame.get("perception_frame_id")) if perception_frames else None
        if perception_frames and upstream is None: raise RecognitionError("TIP-REC-DEPENDENCY-INVALID")
        upstream_features={f["feature_id"]:f for f in upstream.get("features",[])} if upstream else {}
        frame_ids=[r["recognition_id"] for r in frame.get("records",[])]
        if len(frame_ids)!=len(set(frame_ids)) or any(x in seen for x in frame_ids): raise RecognitionError("TIP-REC-IDENTIFIER-DUPLICATE")
        keys=[(r["concept_code"],r["participant_entity_ids"],r["supporting_feature_ids"],r.get("supporting_event_evidence_ids",()),r["recognition_id"]) for r in frame.get("records",[])]
        if keys!=sorted(keys): raise RecognitionError("TIP-REC-ORDERING-INVALID")
        for record in frame.get("records",[]):
            seen.add(record["recognition_id"])
            if record.get("concept_code") not in concept_codes: raise RecognitionError("TIP-REC-CONCEPT-INVALID")
            if not record.get("participant_entity_ids"): raise RecognitionError("TIP-REC-ENTITY-MISSING")
            source_declared=record["concept_code"] in SOURCE_CONCEPTS.values();crossing=record["concept_code"]=="PASS_CROSSES_DEFENSIVE_LINE";evidence_ids=tuple(record.get("supporting_event_evidence_ids",()))
            if source_declared:
                expected=event_evidence[frame["world_state_index"]] if frame["world_state_index"]<len(event_evidence) else None
                if record.get("supporting_feature_ids") or expected is None or evidence_ids!=(expected["event_id"],) or record["canonical_time_seconds"]!=expected["canonical_timestamp"]:raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
                expected_participants=(expected["actor"],) if expected["recipient"] is None else (expected["actor"],expected["recipient"])
                if tuple(record["participant_entity_ids"])!=expected_participants or record["concept_code"]!=SOURCE_CONCEPTS[expected["event_type"]]:raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
            elif crossing:
                expected=event_evidence[frame["world_state_index"]]
                if evidence_ids!=(expected["event_id"],) or expected["event_type"]!="PASS" or not record.get("supporting_feature_ids"):raise RecognitionError("TIP-REC-EVENT-EVIDENCE-INVALID")
            elif evidence_ids or not record.get("supporting_feature_ids"): raise RecognitionError("TIP-REC-DEPENDENCY-INVALID")
            if upstream and any(fid not in upstream_features or upstream_features[fid].get("status")!="AVAILABLE" for fid in record["supporting_feature_ids"]):
                raise RecognitionError("TIP-REC-DEPENDENCY-INVALID")
            if upstream and not source_declared and not crossing:
                subjects={s for fid in record["supporting_feature_ids"] for s in upstream_features[fid].get("subject_ids",[])}
                if any(entity not in subjects for entity in record["participant_entity_ids"]): raise RecognitionError("TIP-REC-ENTITY-MISSING")
            if upstream and crossing:
                endpoint_features=[upstream_features[fid] for fid in record["supporting_feature_ids"] if upstream_features[fid]["feature_code"] in {"PASS_START_POSITION","PASS_END_POSITION"}]
                if sorted(feature["feature_code"] for feature in endpoint_features)!=["PASS_END_POSITION","PASS_START_POSITION"] or any(tuple(feature["subject_ids"])!=(expected["event_id"],) for feature in endpoint_features):raise RecognitionError("TIP-REC-DEPENDENCY-INVALID")
            prov=record.get("recognition_provenance",{}).get("/value",{})
            if not prov.get("sources") or any(not s.get("source_path","").startswith("perception_dataset#") for s in prov.get("sources",[])):
                raise RecognitionError("TIP-REC-PROVENANCE-INVALID")
            if source_declared and prov.get("sources")!=[_source(expected["event_id"],f"/event_evidence/{frame['world_state_index']}")]:raise RecognitionError("TIP-REC-PROVENANCE-INVALID")
    return recognition.validated_copy()
