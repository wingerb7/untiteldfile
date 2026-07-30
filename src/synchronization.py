from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
from src.contracts import Artifact,StageError
from src.normalization import MEDIA_TYPE as NMEDIA
MEDIA_TYPE='application/vnd.tip.synchronized-dataset+json'
class SynchronizationError(StageError):
 def __init__(self,c):super().__init__(c,'synchronization')
def _prov(fields,rid,path):return {'/'+f:{'class':'DERIVED_DETERMINISTICALLY','operation':'BUILD_TIMELINE','sources':[{'source_record_id':rid,'source_path':'normalized_dataset#'+path}]} for f in fields}
def build_synchronized_dataset(n:Artifact)->Artifact:
 if not isinstance(n,Artifact) or not n.authentic(NMEDIA,'tip.normalized_dataset'):raise SynchronizationError('SYNC_INPUT_ARTIFACT_INVALID')
 es,ffs=n['events'],n['freeze_frames'];ids=[e['event_id'] for e in es]
 if len(ids)!=len(set(ids)):raise SynchronizationError('SYNC_DUPLICATE_EVENT')
 if [e['event_order'] for e in es]!=list(range(len(es))):raise SynchronizationError('SYNC_EVENT_ORDER_INVALID')
 by={e['event_id']:e for e in es};att={}
 for f in ffs:
  if f['event_id'] not in by:raise SynchronizationError('SYNC_ATTACHMENT_TARGET_MISSING')
  if f['event_id'] in att:raise SynchronizationError('SYNC_DUPLICATE_ATTACHMENT')
  att[f['event_id']]=f
 highest=max(e['period_number'] for e in es);periods=[];starts={};start=Decimal(0)
 for p in range(1,highest+1):
  xs=[e for e in es if e['period_number']==p];nom=Decimal(2700 if p<3 else 900);observed=max((Decimal(str(e['period_time_seconds']))+(Decimal(str(e['duration_seconds'])) if e['duration_seconds'] is not None else 0) for e in xs),default=Decimal(0));span=max(nom,observed);starts[p]=start;rid=xs[0]['period_id'] if xs else f"{n['match_id']}:period:{p}"
  q={'schema_id':'tip.synchronized_period','period_id':rid,'period_number':p,'nominal_span_seconds':nom,'observed_span_seconds':observed,'canonical_span_seconds':span,'canonical_start_seconds':start,'canonical_end_seconds':start+span};q['synchronization_provenance']=_prov(list(q),rid,'/events');periods.append(q);start+=span
 timeline=[]
 for e in es:
  t=starts[e['period_number']]+Decimal(str(e['period_time_seconds']));dur=e['duration_seconds'];q={'schema_id':'tip.synchronized_record','timeline_index':len(timeline),'record_kind':'EVENT','canonical_time_seconds':t,'period_id':e['period_id'],'period_number':e['period_number'],'period_time_seconds':e['period_time_seconds'],'event_id':e['event_id'],'attachment_event_id':None,'event_start_seconds':t,'event_end_seconds':t+Decimal(str(dur)) if dur is not None else None,'boundary_kind':'INTERVAL' if dur is not None else 'INSTANT','normalized_event':deepcopy(e),'normalized_freeze_frame':None,'normalized_provenance':deepcopy(e['provenance'])};q['synchronization_provenance']=_prov([k for k in q if k not in ('normalized_event','normalized_provenance')],e['event_id'],f"/events/{e['event_order']}");timeline.append(q)
  if e['event_id'] in att:
   f=att[e['event_id']];q={'schema_id':'tip.synchronized_record','timeline_index':len(timeline),'record_kind':'FREEZE_FRAME','canonical_time_seconds':t,'period_id':e['period_id'],'period_number':e['period_number'],'period_time_seconds':e['period_time_seconds'],'event_id':e['event_id'],'attachment_event_id':e['event_id'],'event_start_seconds':None,'event_end_seconds':None,'boundary_kind':'ATTACHMENT','normalized_event':None,'normalized_freeze_frame':deepcopy(f),'normalized_provenance':deepcopy(f['provenance'])};q['synchronization_provenance']=_prov([k for k in q if k not in ('normalized_freeze_frame','normalized_provenance')],f['freeze_frame_id'],f"/freeze_frames/{f['source_index']}");timeline.append(q)
 d={'schema_id':'tip.synchronized_dataset','contract_version':'0.1.0','input_contract_version':'0.1.0','normalized_dataset_sha256':n.sha256,'source_dataset':n['source_dataset'],'source_revision':n['source_revision'],'match_id':n['match_id'],'possession_id':n['possession_id'],'periods':periods,'timeline_origin_seconds':0,'timeline':timeline,'normalized_provenance':n['provenance']};d['synchronization_provenance']=_prov([k for k in d if k!='normalized_provenance'],n['match_id'],'')
 return Artifact(d,MEDIA_TYPE,n.sha256,n.source_hashes)
