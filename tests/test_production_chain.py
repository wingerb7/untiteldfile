from __future__ import annotations
import json
from pathlib import Path
import pytest
from src.contracts import Artifact
from src.source_selection import PINNED_REVISION,SourceSelectionError,select_source_documents
from src.normalization import NormalizationError,build_normalized_dataset,statsbomb_to_canonical_position
from src.synchronization import SynchronizationError,build_synchronized_dataset
from src.world_model import WorldModelError,build_world_model_dataset,validate_world_model_dataset

def sources():
 base=Path('data/open-data/data');return json.loads((base/'events/3788754.json').read_text()),json.loads((base/'three-sixty/3788754.json').read_text())
def request():return {'source_dataset':'statsbomb-open-data','source_revision':PINNED_REVISION,'match_id':3788754,'possession_id':40}
def chain():
 e,f=sources();a=select_source_documents(e,f,request());b=build_normalized_dataset(a);c=build_synchronized_dataset(b);d=build_world_model_dataset(c);return a,b,c,d,validate_world_model_dataset(d)

def test_coordinate_corners_center_and_out_of_bounds_availability():
 assert statsbomb_to_canonical_position([0,80])['x_m']==0
 assert statsbomb_to_canonical_position([120,0])['y_m']==68
 assert statsbomb_to_canonical_position([60,40])['x_m']==52.5
 p=statsbomb_to_canonical_position([121.5,20])
 assert p['availability']=='UNAVAILABLE' and p['unavailable_reason']=='SOURCE_POSITION_OUT_OF_BOUNDS'
 assert p['x_m'] is p['y_m'] is p['z_m'] is None
 assert p['provenance']['/availability']['sources'][0]['source_value']==[121.5,20]

def test_locatelli_layers_are_authenticated_and_byte_stable():
 one=chain();two=chain()
 assert [x.canonical_bytes() for x in one[:4]]==[x.canonical_bytes() for x in two[:4]]
 assert [x.sha256 for x in one[:4]]==[x.sha256 for x in two[:4]]
 assert len(one[0]['events'])==46 and len(one[1]['freeze_frames'])==43
 assert len(one[2]['timeline'])==89 and len(one[3]['world_states'])==46
 assert one[4].validated
 assert sum(o['position']['availability']=='UNAVAILABLE' for s in one[3]['world_states'] for o in s['observations'])==3

def test_locatelli_pass_event_evidence_survives_synchronization_and_world_model():
 _,_,synchronized,world,validated=chain()
 event_id='event:statsbomb:e51fde20-708e-49e4-ae77-5bc768e5f411'
 source=next(record for record in synchronized['timeline'] if record['record_kind']=='EVENT' and record['event_id']==event_id)
 evidence=next(record for record in world['event_evidence'] if record['event_id']==event_id)
 assert evidence['event_type']=='PASS'
 assert evidence['actor']=='player:statsbomb:7038'
 assert evidence['recipient']=='player:statsbomb:7131'
 assert evidence['canonical_timestamp']==float(source['canonical_time_seconds'])
 assert evidence['source_record_id']==source['normalized_event']['source_record_id']
 assert all(item['sources'] for item in evidence['authenticated_provenance'].values())
 assert validated['event_evidence']==world['event_evidence']

def test_related_event_ids_preserve_source_order_for_completed_and_incomplete_passes():
 selection,normalized,synchronized,world,validated=chain()
 expected={
  'e51fde20-708e-49e4-ae77-5bc768e5f411':('9141f1b5-8961-4842-b566-e583d271c6d3',),
  'a10e93ca-9968-4472-8209-1441ac94b02a':('1cba92f6-e388-483f-8e77-ecf792df4809','e795a26f-89e9-47eb-97bb-30e681294249'),
 }
 for source_id,related_ids in expected.items():
  canonical_id='event:statsbomb:'+source_id
  raw=next(event for event in selection['events'] if event['id']==source_id)
  normalized_event=next(event for event in normalized['events'] if event['event_id']==canonical_id)
  synchronized_event=next(record['normalized_event'] for record in synchronized['timeline'] if record['record_kind']=='EVENT' and record['event_id']==canonical_id)
  evidence=next(event for event in world['event_evidence'] if event['event_id']==canonical_id)
  assert tuple(raw['related_events'])==related_ids
  assert normalized_event['related_event_ids']==synchronized_event['related_event_ids']==related_ids
  assert evidence['related_event_ids']==related_ids
  assert evidence['authenticated_provenance']['/related_event_ids']['sources'][0]['source_path'].endswith('/normalized_event/related_event_ids')
 assert validated['event_evidence']==world['event_evidence']

@pytest.mark.parametrize('related',('invalid',["missing:event"],["9141f1b5-8961-4842-b566-e583d271c6d3"]*2))
def test_source_selection_rejects_malformed_related_event_references(related):
 events,frames=sources();event=next(item for item in events if item['id']=='e51fde20-708e-49e4-ae77-5bc768e5f411');event['related_events']=related
 with pytest.raises(SourceSelectionError,match='SRC_RELATED_EVENT_INVALID'):select_source_documents(events,frames,request())

def test_world_validation_rejects_duplicate_related_event_evidence():
 *_,world,_=chain();raw=world.data;raw['event_evidence'][0]['related_event_ids']=('duplicate','duplicate')
 bad=Artifact(raw,world.media_type,world.direct_input_sha256,world.source_hashes)
 with pytest.raises(WorldModelError,match='WORLD_EVENT_EVIDENCE_INVALID'):validate_world_model_dataset(bad)

def test_each_downstream_layer_rejects_unauthenticated_input():
 e,f=sources();selection=select_source_documents(e,f,request())
 with pytest.raises(NormalizationError,match='NORM_INPUT_ARTIFACT_INVALID'):build_normalized_dataset(selection.data)
 normalized=build_normalized_dataset(selection)
 with pytest.raises(SynchronizationError,match='SYNC_INPUT_ARTIFACT_INVALID'):build_synchronized_dataset(normalized.data)
 synchronized=build_synchronized_dataset(normalized)
 with pytest.raises(WorldModelError,match='WORLD_INPUT_ARTIFACT_INVALID'):build_world_model_dataset(synchronized.data)

def test_world_validator_rejects_available_out_of_pitch_position():
 *_,world,_=chain();raw=world.data;raw['world_states'][0]['observations'][0]['position'].update({'availability':'AVAILABLE','x_m':106,'y_m':1,'z_m':None,'unavailable_reason':None})
 bad=Artifact(raw,world.media_type,world.direct_input_sha256,world.source_hashes)
 with pytest.raises(WorldModelError,match='WORLD_SPATIAL_VALUE_INVALID'):validate_world_model_dataset(bad)
