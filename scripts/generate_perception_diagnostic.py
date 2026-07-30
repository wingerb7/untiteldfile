"""Generate the Locatelli diagnostic through the sole Chapters 5–9 route."""
from __future__ import annotations
import json,sys
from pathlib import Path
if __package__ in {None,""}:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.contracts import canonical_bytes
from src.source_selection import PINNED_REVISION,select_source_documents
from src.normalization import build_normalized_dataset
from src.synchronization import build_synchronized_dataset
from src.world_model import build_world_model_dataset,validate_world_model_dataset
from src.perception.engine import build_perception_dataset

def main()->None:
 base=Path('data/open-data/data');events=json.loads((base/'events/3788754.json').read_text());frames=json.loads((base/'three-sixty/3788754.json').read_text())
 request={'source_dataset':'statsbomb-open-data','source_revision':PINNED_REVISION,'match_id':3788754,'possession_id':40}
 selection=select_source_documents(events,frames,request);normalized=build_normalized_dataset(selection);synchronized=build_synchronized_dataset(normalized);world=build_world_model_dataset(synchronized);validated=validate_world_model_dataset(world);perception=build_perception_dataset(validated)
 artifacts=(('source_selection',selection),('normalized',normalized),('synchronized',synchronized),('world_model',world))
 rows=[]
 for name,artifact in artifacts:
  rows.append({'artifact_type':name,'schema_version':artifact.get('contract_version'),'count':len(artifact.get('events',artifact.get('timeline',artifact.get('world_states',[])))),'canonical_sha256':artifact.sha256,'direct_input_sha256':artifact.direct_input_sha256,'source_document_sha256':artifact.source_hashes,'canonical_path':'src.contracts.canonical_bytes','validation_status':'VALID'})
 rows.append({'artifact_type':'perception','schema_version':perception.contract_version,'count':len(perception.frames),'canonical_sha256':perception.sha256,'direct_input_sha256':world.sha256,'source_document_sha256':world.source_hashes,'canonical_path':'src.perception.models.canonical_json_bytes','validation_status':'VALID'})
 report={'schema_id':'tip.perception_diagnostic','artifacts':rows,'unavailable_world_positions':sum(o['position']['availability']=='UNAVAILABLE' for s in world['world_states'] for o in s['observations'])}
 out=Path('audit/locatelli/perception_diagnostic.json');out.write_bytes(canonical_bytes(report));print(out,perception.sha256,len(perception.frames))
if __name__=='__main__':main()
