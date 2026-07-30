from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import pytest
from src.contracts import Artifact
from src.perception.authentication import PERCEPTION_MEDIA_TYPE
from src.recognition import RecognitionError,build_recognition_dataset,validate_recognition_dataset

def feature(fid,code,subjects,value,status='AVAILABLE'):
 return {'schema_id':'tip.perception_feature','feature_id':fid,'feature_code':code,'feature_name':code,'category':'MOTION','world_state_id':'world:0','world_state_index':0,'canonical_time_seconds':1.0,'subject_ids':list(subjects),'input_observation_ids':[],'dependency_feature_ids':[],'status':status,'unavailable_reason':None if status=='AVAILABLE' else 'POSITION_MISSING','value':value if status=='AVAILABLE' else None,'unit':'NONE','perception_provenance':{}}
def evidence(event_id='event:1',event_type='PASS'):
 provenance={field:{'class':'PRESERVED_AUTHENTICATED_INPUT','operation':'WORLD_PRESERVE_EVENT_EVIDENCE','sources':[{'source_record_id':'source:1','source_path':f'synchronized_dataset#/timeline/0/{field}'}]} for field in ('/event_id','/event_type','/actor','/recipient','/canonical_timestamp','/source_record_id','/related_event_ids','/outcome')}
 return {'event_id':event_id,'event_type':event_type,'actor':'player:a','recipient':'player:b' if event_type=='PASS' else None,'canonical_timestamp':1.0,'source_record_id':'source:1','related_event_ids':(),'outcome':'COMPLETED' if event_type=='PASS' else None,'authenticated_provenance':provenance}
def perception():
 features=[feature('speed:a','ENTITY_SPEED',('player:a',),{'scalar':2.0}),feature('speed:b','ENTITY_SPEED',('player:b',),{'scalar':0.0}),feature('distance:a','PAIR_DISTANCE',('ball:m','player:a'),{'scalar':1.0}),feature('distance:b','PAIR_DISTANCE',('ball:m','player:b'),{'scalar':2.0}),feature('corridor','CONNECTION_CORRIDOR',('player:a','player:b'),{'polygon2':[]}),feature('occupancy','CORRIDOR_OCCUPANCY',('player:a','player:b'),{'integer':1})]
 definitions=[{'feature_code':x} for x in ('ENTITY_SPEED','PAIR_DISTANCE','CONNECTION_CORRIDOR','CORRIDOR_OCCUPANCY')]
 frame={'schema_id':'tip.perception_frame','perception_frame_id':'perception_frame:world:0','world_state_id':'world:0','world_state_index':0,'canonical_time_seconds':1.0,'features':features,'perception_provenance':{}}
 data={'schema_id':'tip.perception_dataset','contract_version':'0.1.0','input_contract_version':'0.1.0','world_model_sha256':'0'*64,'match_id':'match:m','possession_id':'possession:1','event_evidence':[evidence()],'feature_definitions':definitions,'frames':[frame],'input_provenance':{},'perception_provenance':{}}
 return Artifact(data,PERCEPTION_MEDIA_TYPE,'0'*64,validated=True)

def test_recognition_generation_authentication_order_and_determinism():
 a=build_recognition_dataset(perception());b=build_recognition_dataset(perception())
 assert a.validated and a.canonical_bytes()==b.canonical_bytes() and a.sha256==b.sha256
 codes=[r['concept_code'] for r in a['frames'][0]['records']]
 assert codes==['PASSING_CORRIDOR_OBSTRUCTED','PLAYER_MOVING','PLAYER_NEAREST_BALL','PLAYER_STATIONARY','SOURCE_DECLARED_PASS']
 assert all(r['recognition_provenance']['/value']['sources'] for r in a['frames'][0]['records'])

def test_recognition_classifies_authenticated_source_declaration_only():
 recognition=build_recognition_dataset(perception());record=next(r for r in recognition['frames'][0]['records'] if r['concept_code']=='SOURCE_DECLARED_PASS')
 assert record['supporting_event_evidence_ids']==('event:1',)
 assert record['supporting_feature_ids']==()
 assert record['participant_entity_ids']==('player:a','player:b')
 assert record['recognition_provenance']['/value']['sources']==[{'source_record_id':'event:1','source_path':'perception_dataset#/event_evidence/0'}]

def test_recognition_rejects_unauthenticated_and_missing_features():
 with pytest.raises(RecognitionError,match='TIP-REC-INPUT-ARTIFACT-INVALID'):build_recognition_dataset(perception().data)
 raw=perception().data;raw['feature_definitions']=[]
 with pytest.raises(RecognitionError,match='TIP-REC-FEATURE-MISSING'):build_recognition_dataset(Artifact(raw,PERCEPTION_MEDIA_TYPE,'0'*64,validated=True))
 raw=perception().data;raw['event_evidence']=[]
 with pytest.raises(RecognitionError,match='TIP-REC-EVENT-EVIDENCE-INVALID'):build_recognition_dataset(Artifact(raw,PERCEPTION_MEDIA_TYPE,'0'*64,validated=True))
 raw=perception().data;raw['event_evidence'][0]['authenticated_provenance']={}
 with pytest.raises(RecognitionError,match='TIP-REC-EVENT-EVIDENCE-INVALID'):build_recognition_dataset(Artifact(raw,PERCEPTION_MEDIA_TYPE,'0'*64,validated=True))

def test_recognition_validator_rejects_duplicate_and_invalid_provenance():
 good=build_recognition_dataset(perception());raw=good.data;raw['frames'][0]['records']=list(raw['frames'][0]['records']);raw['frames'][0]['records'].append(deepcopy(raw['frames'][0]['records'][0]));bad=Artifact(raw,good.media_type,good.direct_input_sha256)
 with pytest.raises(RecognitionError,match='TIP-REC-IDENTIFIER-DUPLICATE'):validate_recognition_dataset(bad)
 raw=good.data;raw['frames'][0]['records'][0]['recognition_provenance']={};bad=Artifact(raw,good.media_type,good.direct_input_sha256)
 with pytest.raises(RecognitionError,match='TIP-REC-PROVENANCE-INVALID'):validate_recognition_dataset(bad)

def test_recognition_validator_rejects_unknown_perception_reference():
 source=perception();good=build_recognition_dataset(source);raw=good.data;raw['frames'][0]['records'][0]['supporting_feature_ids']=('unknown:feature',);bad=Artifact(raw,good.media_type,good.direct_input_sha256)
 with pytest.raises(RecognitionError,match='TIP-REC-DEPENDENCY-INVALID'):validate_recognition_dataset(bad,source)

def test_authenticated_fixture_diagnostic_covers_locatelli_depay_and_di_maria():
 report=json.loads(Path('audit/recognition/recognition_diagnostic.json').read_text())
 fixtures={f['fixture']:f for f in report['fixtures']}
 assert fixtures['locatelli']['status']=='SUCCEEDED' and fixtures['locatelli']['frame_count']==44
 assert fixtures['depay']['status']=='SUCCEEDED' and fixtures['depay']['frame_count']==59
 assert fixtures['locatelli']['recognition_sha256']=='f083f48adaacca8893996e27d424fd8a6c4030e46387f5128fa51a0e7383c827'
 assert fixtures['depay']['recognition_sha256']=='b8f59d1fafc823f9b0bfcc0e8834cde8337f3c19b75948436dfe5a889d9ae5b3'
 assert fixtures['di_maria']=={'fixture':'di_maria','status':'UPSTREAM_REJECTED','stage':'source_validation','code':'SRC_EVENT_INDEX_INVALID','recognition_executed':False}
