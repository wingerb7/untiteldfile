"""Engineering validation for the authenticated Perception-to-Recognition route."""
from __future__ import annotations
import json,sys
from pathlib import Path
if __package__ in {None,""}:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.contracts import canonical_bytes
from src.source_selection import PINNED_REVISION,select_source_documents
from src.normalization import build_normalized_dataset
from src.synchronization import build_synchronized_dataset
from src.world_model import build_world_model_dataset,validate_world_model_dataset
from src.perception import build_perception_dataset,validate_perception_dataset
from src.recognition import build_recognition_dataset

def positive(name:str,match_id:int,possession_id:int)->dict:
 base=Path('data/open-data/data');events=json.loads((base/f'events/{match_id}.json').read_text());frames=json.loads((base/f'three-sixty/{match_id}.json').read_text());request={'source_dataset':'statsbomb-open-data','source_revision':PINNED_REVISION,'match_id':match_id,'possession_id':possession_id}
 selection=select_source_documents(events,frames,request);normalized=build_normalized_dataset(selection);synchronized=build_synchronized_dataset(normalized);world=build_world_model_dataset(synchronized);validated_world=validate_world_model_dataset(world);perception=validate_perception_dataset(build_perception_dataset(validated_world),source_hashes=world.source_hashes);recognition=build_recognition_dataset(perception)
 rows=[]
 for frame in recognition['frames']:
  rows.append({'world_state_index':frame['world_state_index'],'canonical_time_seconds':frame['canonical_time_seconds'],'records':[{'recognition_id':r['recognition_id'],'concept_code':r['concept_code'],'participating_entities':r['participant_entity_ids'],'supporting_perception_features':r['supporting_feature_ids'],'provenance':r['recognition_provenance']} for r in frame['records']]})
 return {'fixture':name,'status':'SUCCEEDED','selection_sha256':selection.sha256,'perception_sha256':perception.sha256,'recognition_sha256':recognition.sha256,'frame_count':len(recognition['frames']),'record_count':recognition['metadata']['record_count'],'frames':rows}

def negative(name:str,match_id:int,possession_id:int)->dict:
 base=Path('data/open-data/data');request={'source_dataset':'statsbomb-open-data','source_revision':PINNED_REVISION,'match_id':match_id,'possession_id':possession_id}
 try:select_source_documents(json.loads((base/f'events/{match_id}.json').read_text()),json.loads((base/f'three-sixty/{match_id}.json').read_text()),request)
 except Exception as exc:return {'fixture':name,'status':'UPSTREAM_REJECTED','stage':getattr(exc,'stage','unknown'),'code':getattr(exc,'code',type(exc).__name__),'recognition_executed':False}
 raise RuntimeError(f'{name} unexpectedly passed source selection')

def main()->None:
 report={'schema_id':'tip.recognition_diagnostic','contract_version':'0.1.0','fixtures':[positive('locatelli',3788754,40),positive('depay',3869117,20),negative('di_maria',3869685,52)]}
 target=Path('audit/recognition/recognition_diagnostic.json');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(canonical_bytes(report));print(target)
 for f in report['fixtures']:print(f['fixture'],f['status'],f.get('frame_count'),f.get('record_count'),f.get('recognition_sha256'),f.get('code'))
if __name__=='__main__':main()
