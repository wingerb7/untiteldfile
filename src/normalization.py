from __future__ import annotations
from decimal import Decimal
import re
from copy import deepcopy
from src.contracts import Artifact,StageError
from src.source_selection import MEDIA_TYPE as SOURCE_MEDIA
MEDIA_TYPE='application/vnd.tip.normalized-dataset+json';TS=re.compile(r'^(\d\d):(\d\d):(\d\d)\.(\d\d\d)$')
TM={(30,'Pass'):'PASS',(42,'Ball Receipt*'):'BALL_RECEIPT',(43,'Carry'):'CARRY',(16,'Shot'):'SHOT'}
class NormalizationError(StageError):
 def __init__(self,c,refs=()):super().__init__(c,'normalization',refs)
def _time(s):
 m=TS.fullmatch(s) if isinstance(s,str) else None
 if not m:raise NormalizationError('NORM_TIMESTAMP_INVALID')
 h,mi,se,ms=map(int,m.groups())
 if mi>59 or se>59:raise NormalizationError('NORM_TIMESTAMP_INVALID')
 return Decimal(h*3600+mi*60+se)+Decimal(ms)/1000
def _source(rid,path,value=None):
 d={'source_record_id':rid,'source_path':'source_selection#'+path}
 if value is not None:d['source_value']=deepcopy(value)
 return d
def _prov(fields,rid,path,op='DERIVED_DETERMINISTICALLY'):return {'/'+f:{'class':'DERIVED_DETERMINISTICALLY','operation':op,'sources':[_source(rid,path)]} for f in fields}
def statsbomb_to_canonical_position(raw,rid='source:position',path=''):
 x,y=Decimal(str(raw[0])),Decimal(str(raw[1]));z=Decimal(str(raw[2])) if len(raw)>2 else None
 available=0<=x<=120 and 0<=y<=80
 p={'availability':'AVAILABLE' if available else 'UNAVAILABLE','x_m':x*Decimal(105)/120 if available else None,'y_m':(80-y)*Decimal(68)/80 if available else None,'z_m':z if available else None,'unavailable_reason':None if available else 'SOURCE_POSITION_OUT_OF_BOUNDS'}
 p['provenance']={'/availability':{'class':'DERIVED_DETERMINISTICALLY','operation':'CLASSIFY_SOURCE_POSITION','sources':[_source(rid,path,raw)]},'/x_m':{'class':'COORDINATE_CONVERTED' if available else 'SOURCE_UNAVAILABLE','operation':'CONVERT_X_METRES' if available else 'SET_NULL_OUT_OF_BOUNDS','sources':[_source(rid,path+'/0',raw[0])]},'/y_m':{'class':'COORDINATE_CONVERTED' if available else 'SOURCE_UNAVAILABLE','operation':'CONVERT_Y_METRES' if available else 'SET_NULL_OUT_OF_BOUNDS','sources':[_source(rid,path+'/1',raw[1])]},'/z_m':{'class':'COORDINATE_CONVERTED' if available and z is not None else 'NOT_APPLICABLE' if available else 'SOURCE_UNAVAILABLE','operation':'COPY_Z_METRES' if available and z is not None else 'SET_NULL_NOT_APPLICABLE' if available else 'SET_NULL_OUT_OF_BOUNDS','sources':[_source(rid,path,raw)]},'/unavailable_reason':{'class':'NOT_APPLICABLE' if available else 'SOURCE_UNAVAILABLE','operation':'SET_NULL_NOT_APPLICABLE' if available else 'SOURCE_POSITION_OUT_OF_BOUNDS','sources':[_source(rid,path,raw)]}}
 return p
def build_normalized_dataset(s:Artifact)->Artifact:
 if not isinstance(s,Artifact) or not s.authentic(SOURCE_MEDIA):raise NormalizationError('NORM_INPUT_ARTIFACT_INVALID')
 if s['contract_version']!='0.1.0':raise NormalizationError('NORM_INPUT_VERSION_UNSUPPORTED')
 if set(s)!= {'contract_version','source_dataset','source_revision','match_id','possession_id','events','three_sixty','source_event_count','retained_event_count','associated_360_count'}:raise NormalizationError('NORM_INPUT_SCHEMA_INVALID')
 mid=f"match:statsbomb:{s['match_id']}";pos=f"{mid}:possession:{s['possession_id']}";rev=s['source_revision'];out=[]
 for i,e in enumerate(s['events']):
  kind=TM.get((e['type']['id'],e['type']['name']))
  if not kind:raise NormalizationError('NORM_UNSUPPORTED_MAPPING')
  eid=f"event:statsbomb:{e['id']}";rid=f"source:statsbomb_open_data:{rev}:events:{s['match_id']}:{e['id']}";t=_time(e['timestamp']);period=e['period'];body=None;end=None;recipient_id=recipient_name=outcome=xg=None
  if kind=='PASS':
   body=e['pass'];end=statsbomb_to_canonical_position(body['end_location'],rid,f'/events/{i}/pass/end_location');recipient_id=f"player:statsbomb:{body['recipient']['id']}";recipient_name=body['recipient']['name'];op=body.get('outcome');outcome='COMPLETED' if op is None else 'INCOMPLETE' if (op['id'],op['name'])==(9,'Incomplete') else None
   if outcome is None:raise NormalizationError('NORM_UNSUPPORTED_MAPPING')
  elif kind=='CARRY':end=statsbomb_to_canonical_position(e['carry']['end_location'],rid,f'/events/{i}/carry/end_location')
  elif kind=='SHOT':end=statsbomb_to_canonical_position(e['shot']['end_location'],rid,f'/events/{i}/shot/end_location');outcome='GOAL';xg=Decimal(str(e['shot']['statsbomb_xg']))
  r={'schema_id':'tip.normalized_event','event_id':eid,'source_record_id':rid,'source_index':e['index'],'event_order':0,'period_id':f'{mid}:period:{period}','period_number':period,'period_time_seconds':t,'match_time_seconds':Decimal({1:0,2:2700,3:5400,4:6300}[period])+t,'duration_seconds':Decimal(str(e['duration'])) if 'duration'in e else None,'possession_id':pos,'possession_team_id':f"team:statsbomb:{e['possession_team']['id']}",'possession_team_name':e['possession_team']['name'],'team_id':f"team:statsbomb:{e['team']['id']}",'team_name':e['team']['name'],'actor_player_id':f"player:statsbomb:{e['player']['id']}",'actor_player_name':e['player']['name'],'event_type':kind,'play_pattern':'REGULAR_PLAY','start_position':statsbomb_to_canonical_position(e['location'],rid,f'/events/{i}/location'),'end_position':end,'recipient_player_id':recipient_id,'recipient_player_name':recipient_name,'outcome':outcome,'shot_xg':xg,'related_event_ids':tuple(e.get('related_events',()))}
  r['provenance']=_prov([k for k in r if k not in ('start_position','end_position')],rid,f'/events/{i}');out.append(r)
  r['provenance']['/related_event_ids']={'class':'PRESERVED_AUTHENTICATED_INPUT','operation':'NORM_PRESERVE_RELATED_EVENTS','sources':[_source(rid,f'/events/{i}/related_events',e.get('related_events',[]))]}
 out.sort(key=lambda e:(e['period_number'],e['period_time_seconds'],e['source_index'],e['event_id']))
 for i,e in enumerate(out):e['event_order']=i
 by={e['event_id']:e for e in out};ffs=[]
 for i,f in enumerate(s['three_sixty']):
  eid=f"event:statsbomb:{f['event_uuid']}";event=by[eid];ffid=f'{eid}:freeze_frame:statsbomb360';rid=f"source:statsbomb_open_data:{rev}:three_sixty:{s['match_id']}:{f['event_uuid']}"
  points=[statsbomb_to_canonical_position(f['visible_area'][j:j+2],rid,f'/three_sixty/{i}/visible_area/{j}') for j in range(0,len(f['visible_area']),2)];obs=[]
  for j,o in enumerate(f['freeze_frame']):
   q={'schema_id':'tip.normalized_player_observation','observation_id':f'{ffid}:observation:{j}','source_record_id':rid,'source_index':j,'player_id':event['actor_player_id'] if o['actor'] else None,'player_name':event['actor_player_name'] if o['actor'] else None,'team_id':event['possession_team_id'] if o['teammate'] else None,'team_relation':'TEAMMATE' if o['teammate'] else 'OPPONENT','actor':o['actor'],'goalkeeper':o['keeper'],'visible':True,'position':statsbomb_to_canonical_position(o['location'],rid,f'/three_sixty/{i}/freeze_frame/{j}/location')};q['provenance']=_prov([k for k in q if k!='position'],rid,f'/three_sixty/{i}/freeze_frame/{j}');obs.append(q)
  area={'schema_id':'tip.normalized_visible_area','visible_area_id':f'{ffid}:visible_area','points':points};area['provenance']=_prov(list(area),rid,f'/three_sixty/{i}/visible_area')
  q={'schema_id':'tip.normalized_freeze_frame','freeze_frame_id':ffid,'source_record_id':rid,'source_index':i,'event_id':eid,'visible_area':area,'observations':obs};q['provenance']=_prov([k for k in q if k!='visible_area'],rid,f'/three_sixty/{i}');ffs.append(q)
 ffs.sort(key=lambda f:(by[f['event_id']]['event_order'],f['source_index']));pids=[]
 for e in out:
  if e['period_id'] not in pids:pids.append(e['period_id'])
 d={'schema_id':'tip.normalized_dataset','contract_version':'0.1.0','source_dataset':s['source_dataset'],'source_revision':rev,'match_id':mid,'possession_id':pos,'period_ids':pids,'events':out,'freeze_frames':ffs};d['provenance']=_prov(list(d),f"source:statsbomb_open_data:{rev}:selection:{s['match_id']}:{s['possession_id']}",'')
 return Artifact(d,MEDIA_TYPE,s.sha256,s.source_hashes)
