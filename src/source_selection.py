from __future__ import annotations
import json,math,uuid
from pathlib import Path
from typing import Any
from src.contracts import Artifact,StageError,digest
PINNED_REVISION='b0bc9f22dd77c206ddedc1d742893b3bbe64baec';MEDIA_TYPE='application/vnd.tip.source-selection+json'
TYPES={(30,'Pass'),(42,'Ball Receipt*'),(43,'Carry'),(16,'Shot')}
class SourceSelectionError(StageError):
 def __init__(self,c,refs=()):super().__init__(c,'source_validation',refs)
def _load(v):
 try:
  if isinstance(v,Path):v=v.read_bytes()
  if isinstance(v,bytes):v=v.decode()
  if isinstance(v,str):v=json.loads(v)
 except Exception as e:raise SourceSelectionError('SRC_JSON_INVALID') from e
 if not isinstance(v,list):raise SourceSelectionError('SRC_ROOT_INVALID')
 return v
def _pair(x):return (x.get('id'),x.get('name')) if isinstance(x,dict) else (None,None)
def _loc(x,z=False):return isinstance(x,list) and len(x) in ({2,3} if z else {2}) and all(not isinstance(n,bool) and isinstance(n,(int,float)) and math.isfinite(n) for n in x) and (len(x)<3 or x[2]>=0)
def select_source_documents(events_document:Any,three_sixty_document:Any,request:dict)->Artifact:
 if request.get('source_dataset')!='statsbomb-open-data':raise SourceSelectionError('SRC_UNSUPPORTED_DATASET')
 if request.get('source_revision')!=PINNED_REVISION:raise SourceSelectionError('SRC_UNSUPPORTED_REVISION')
 mid,pid=request.get('match_id'),request.get('possession_id')
 if isinstance(mid,bool) or not isinstance(mid,int) or mid<=0 or isinstance(pid,bool) or not isinstance(pid,int) or pid<=0:raise SourceSelectionError('SRC_FIELD_INVALID')
 es,fs=_load(events_document),_load(three_sixty_document);ids={};indices={}
 for i,e in enumerate(es):
  if not isinstance(e,dict) or not isinstance(e.get('id'),str) or not e['id'] or e['id'] in ids:raise SourceSelectionError('SRC_EVENT_ID_INVALID',(f'events#/{i}/id',))
  if isinstance(e.get('index'),bool) or not isinstance(e.get('index'),int) or e['index'] in indices:raise SourceSelectionError('SRC_EVENT_INDEX_INVALID',(f'events#/{i}/index',))
  ids[e['id']]=i;indices[e['index']]=i
 for i,e in enumerate(es):
  related=e.get('related_events',[])
  try:valid_related=isinstance(related,list) and all(isinstance(rid,str) and str(uuid.UUID(rid))==rid and rid!=e['id'] and rid in ids for rid in related)
  except (ValueError,AttributeError):valid_related=False
  if not valid_related or len(related)!=len(set(related)):raise SourceSelectionError('SRC_RELATED_EVENT_INVALID',(f'events#/{i}/related_events',))
 prev=None
 for e in sorted(es,key=lambda x:x['index']):
  key=(e.get('period'),e.get('timestamp'))
  if not isinstance(key[0],int) or not isinstance(key[1],str):raise SourceSelectionError('SRC_FIELD_INVALID')
  if prev and key<prev:raise SourceSelectionError('SRC_EVENT_INDEX_INVALID')
  prev=key
 seen=set()
 for i,f in enumerate(fs):
  if not isinstance(f,dict) or f.get('event_uuid') not in ids or f['event_uuid'] in seen:raise SourceSelectionError('SRC_360_REFERENCE_INVALID',(f'three_sixty#/{i}/event_uuid',))
  seen.add(f['event_uuid']);frame=f.get('freeze_frame');area=f.get('visible_area')
  if not isinstance(frame,list) or not isinstance(area,list) or len(area)%2 or len(area)<8 or any(not isinstance(n,(int,float)) or isinstance(n,bool) or not math.isfinite(n) for n in area):raise SourceSelectionError('SRC_FIELD_INVALID',(f'three_sixty#/{i}',))
  actors=0
  for j,o in enumerate(frame):
   if not isinstance(o,dict) or not all(isinstance(o.get(k),bool) for k in ('teammate','actor','keeper')) or not _loc(o.get('location')):raise SourceSelectionError('SRC_FIELD_INVALID',(f'three_sixty#/{i}/freeze_frame/{j}',))
   actors+=int(o['actor'])
   if o['actor'] and not o['teammate']:actors+=10
  if frame and actors!=1:raise SourceSelectionError('SRC_360_ACTOR_INVALID',(f'three_sixty#/{i}/freeze_frame',))
 selected=sorted((e for e in es if e.get('possession')==pid),key=lambda e:e['index'])
 if not selected:raise SourceSelectionError('SRC_POSSESSION_NOT_FOUND')
 if len({_pair(e.get('possession_team')) for e in selected})!=1:raise SourceSelectionError('SRC_POSSESSION_INCONSISTENT')
 if any(_pair(e.get('play_pattern'))!=(1,'Regular Play') for e in selected):raise SourceSelectionError('SRC_UNSUPPORTED_PHASE')
 pt=selected[0]['possession_team']['id']
 # TIP-SRC-014: opponent actions may occur inside the possession but are not retained.
 retained=[e for e in selected if _pair(e.get('type')) in TYPES and e.get('team',{}).get('id')==pt]
 retained_ids={e['id'] for e in retained};selected_by_id={e['id']:e for e in selected};changed=True
 while changed:
  changed=False
  for rid in [rid for e in retained for rid in e.get('related_events',[])]:
   target=selected_by_id.get(rid)
   if target is not None and rid not in retained_ids and _pair(target.get('type')) in TYPES:
    retained.append(target);retained_ids.add(rid);changed=True
 retained.sort(key=lambda e:e['index'])
 for e in retained:
  if not _loc(e.get('location')):raise SourceSelectionError('SRC_FIELD_INVALID')
  child={30:'pass',43:'carry',16:'shot'}.get(e['type']['id'])
  if child and not _loc(e.get(child,{}).get('end_location'),child=='shot'):raise SourceSelectionError('SRC_FIELD_INVALID')
 goals=[e for e in retained if _pair(e.get('type'))==(16,'Shot') and _pair(e.get('shot',{}).get('outcome'))==(97,'Goal')]
 if len(goals)!=1 or retained[-1] is not goals[0] or not any(_pair(e['type'])==(30,'Pass') for e in retained):raise SourceSelectionError('SRC_UNSUPPORTED_OUTCOME')
 rids={e['id'] for e in retained};sfs=[f for f in fs if f['event_uuid'] in rids]
 if not any(f['freeze_frame'] for f in sfs):raise SourceSelectionError('SRC_360_UNAVAILABLE')
 data={'contract_version':'0.1.0','source_dataset':'statsbomb-open-data','source_revision':PINNED_REVISION,'match_id':mid,'possession_id':pid,'events':retained,'three_sixty':sfs,'source_event_count':len(selected),'retained_event_count':len(retained),'associated_360_count':len(sfs)}
 return Artifact(data,MEDIA_TYPE,source_hashes={'events':digest(es),'three_sixty':digest(fs)})
