from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, dataclass
from decimal import Decimal
import math
from typing import Any
from src.contracts import Artifact,StageError,digest
from src.synchronization import MEDIA_TYPE as SMEDIA
MEDIA_TYPE='application/vnd.tip.world-model+json'
class WorldModelError(StageError):
 def __init__(self,c):super().__init__(c,'world_model')

@dataclass(frozen=True)
class EventEvidence:
 event_id: str
 event_type: str
 actor: str
 recipient: str|None
 canonical_timestamp: float
 source_record_id: str
 related_event_ids: tuple[str,...]
 outcome: str|None
 authenticated_provenance: dict[str,Any]

def _prov(fields,rid,path):return {'/'+f:{'class':'DERIVED_DETERMINISTICALLY','operation':'WORLD_BUILD_COLLECTION','sources':[{'source_record_id':rid,'source_path':'synchronized_dataset#'+path}]} for f in fields}
def _withprov(q,rid,path):q['world_provenance']=_prov([k for k in q if k!='world_provenance'],rid,path);return q
def _rel(sid,typ,subject,obj,observation,path):
 suffix=observation or obj or 'none';rid=f'relationship:{sid}:{typ.lower()}:{subject}:{suffix}'
 return _withprov({'schema_id':'tip.world_relationship','relationship_id':rid,'world_state_id':sid,'relationship_type':typ,'subject_id':subject,'object_id':obj,'observation_id':observation},rid,path)
def build_world_model_dataset(s:Artifact)->Artifact:
 if not isinstance(s,Artifact) or not s.authentic(SMEDIA,'tip.synchronized_dataset'):raise WorldModelError('WORLD_INPUT_ARTIFACT_INVALID')
 tl=s['timeline'];events=[r for r in tl if r['record_kind']=='EVENT'];attachments={r['event_id']:r for r in tl if r['record_kind']=='FREEZE_FRAME'}
 if not events:raise WorldModelError('WORLD_MANDATORY_ENTITY_MISSING')
 mid,pos=s['match_id'],s['possession_id'];psuffix=pos.rsplit(':',1)[1];members={};teams={};anon={};pos_team=None
 event_evidence=[];pass_trajectory_evidence=[]
 for r in events:
  e=r['normalized_event'];pos_team=pos_team or e['possession_team_id']
  if e['possession_team_id']!=pos_team:raise WorldModelError('WORLD_POSSESSION_INCONSISTENT')
  teams[e['team_id']]=e['team_name'];teams[e['possession_team_id']]=e['possession_team_name'];members[e['actor_player_id']]=(e['actor_player_name'],e['team_id'])
  if e['recipient_player_id']:members[e['recipient_player_id']]=(e['recipient_player_name'],e['possession_team_id'])
  if e['event_id'] in attachments:
   for o in attachments[e['event_id']]['normalized_freeze_frame']['observations']:
    if o['player_id'] is None:anon[o['observation_id']]=(o,e)
  def evidence_source(path):return {'class':'PRESERVED_AUTHENTICATED_INPUT','operation':'WORLD_PRESERVE_EVENT_EVIDENCE','sources':[{'source_record_id':e['source_record_id'],'source_path':f"synchronized_dataset#/timeline/{r['timeline_index']}/{path}"}]}
  evidence_provenance={
   '/event_id':evidence_source('normalized_event/event_id'),
   '/event_type':evidence_source('normalized_event/event_type'),
   '/actor':evidence_source('normalized_event/actor_player_id'),
   '/recipient':evidence_source('normalized_event/recipient_player_id'),
   '/canonical_timestamp':evidence_source('canonical_time_seconds'),
   '/source_record_id':evidence_source('normalized_event/source_record_id'),
   '/related_event_ids':evidence_source('normalized_event/related_event_ids'),
   '/outcome':evidence_source('normalized_event/outcome'),
  }
  event_evidence.append(asdict(EventEvidence(e['event_id'],e['event_type'],e['actor_player_id'],e['recipient_player_id'],float(r['canonical_time_seconds']),e['source_record_id'],tuple(e['related_event_ids']),e['outcome'],evidence_provenance)))
  if e['event_type']=='PASS':
   def trajectory_source(field):
    return {'class':'PRESERVED_AUTHENTICATED_INPUT','operation':'WORLD_PRESERVE_PASS_TRAJECTORY','sources':[{'source_record_id':e['source_record_id'],'source_path':f"synchronized_dataset#/timeline/{r['timeline_index']}/normalized_event/{field}"}]}
   pass_trajectory_evidence.append({
    'schema_id':'tip.pass_trajectory_evidence','event_id':e['event_id'],'actor':e['actor_player_id'],'recipient':e['recipient_player_id'],
    'canonical_timestamp':float(r['canonical_time_seconds']),'match_id':mid,'possession_id':pos,
    'coordinate_system':'CANONICAL_PITCH_METRES','pitch_length_m':105,'pitch_width_m':68,
    'start_position':deepcopy(e['start_position']),'end_position':deepcopy(e['end_position']),
    'authenticated_provenance':{'/start_position':trajectory_source('start_position'),'/end_position':trajectory_source('end_position')},
   })
 opp=f'team:unidentified_opponent:{pos}'
 if anon:teams[opp]=None
 for oid,(o,e) in anon.items():members[f'player:observation_scoped:{oid}']=(None,e['possession_team_id'] if o['team_relation']=='TEAMMATE' else opp)
 tc=[_withprov({'schema_id':'tip.team','team_id':tid,'identity_kind':'UNIDENTIFIED_OPPONENT' if tid==opp else 'IDENTIFIED','display_name':name},tid,'/timeline') for tid,name in sorted(teams.items())]
 pc=[]
 for pid,(name,tid) in sorted(members.items()):
  scoped=pid.startswith('player:observation_scoped:');origin='observation:world:'+pid.removeprefix('player:observation_scoped:') if scoped else None
  pc.append(_withprov({'schema_id':'tip.player','player_id':pid,'identity_kind':'OBSERVATION_SCOPED' if scoped else 'IDENTIFIED','display_name':name,'team_id':tid,'origin_observation_id':origin},pid,'/timeline'))
 ball=f'ball:{mid}:analysis_scope:1';pitch=f'pitch:{mid}:canonical:105x68';states=[];seen=set()
 for si,r in enumerate(events):
  e=r['normalized_event'];sid=f"world_state:{mid}:{psuffix}:{e['event_id'].removeprefix('event:statsbomb:')}";obs=[]
  for kind,subject in (('EVENT_BALL',ball),('EVENT_ACTOR',e['actor_player_id'])):
   oid=f"observation:world:{e['event_id']}:{'ball' if kind=='EVENT_BALL' else 'actor'}";obs.append(_withprov({'schema_id':'tip.world_observation','observation_id':oid,'world_state_id':sid,'subject_kind':'BALL' if kind=='EVENT_BALL' else 'PLAYER','subject_id':subject,'observation_kind':kind,'position':deepcopy(e['start_position']),'visibility':'UNKNOWN','anchor_event_id':e['event_id'],'source_timeline_index':r['timeline_index'],'normalized_observation_id':None},e['event_id'],f"/timeline/{r['timeline_index']}"))
  fr=attachments.get(e['event_id'])
  if fr:
   for no in fr['normalized_freeze_frame']['observations']:
    pid=no['player_id'] or f"player:observation_scoped:{no['observation_id']}";oid=f"observation:world:{no['observation_id']}";obs.append(_withprov({'schema_id':'tip.world_observation','observation_id':oid,'world_state_id':sid,'subject_kind':'PLAYER','subject_id':pid,'observation_kind':'FREEZE_FRAME','position':deepcopy(no['position']),'visibility':'VISIBLE','anchor_event_id':e['event_id'],'source_timeline_index':fr['timeline_index'],'normalized_observation_id':no['observation_id']},no['observation_id'],f"/timeline/{fr['timeline_index']}"))
  obs.sort(key=lambda o:(o['source_timeline_index'],{'EVENT_BALL':0,'EVENT_ACTOR':1,'FREEZE_FRAME':2}[o['observation_kind']],o['observation_id']));current={}
  for o in obs:
   if o['subject_kind']=='PLAYER':current.setdefault(o['subject_id'],[]).append(o['observation_id']);seen.add(o['subject_id'])
  pst=[]
  for p in pc:
   ids=sorted(current.get(p['player_id'],[]));scoped=p['identity_kind']=='OBSERVATION_SCOPED';origin=p['origin_observation_id'];life='OBSERVED' if ids else 'TERMINATED' if scoped and any(origin in [o['observation_id'] for o in st['observations']] for st in states) else 'MISSING' if p['player_id'] in seen else 'UNKNOWN';pst.append(_withprov({'schema_id':'tip.player_state','player_id':p['player_id'],'lifecycle':life,'visibility':'VISIBLE' if any(next(o for o in obs if o['observation_id']==x)['visibility']=='VISIBLE' for x in ids) else 'UNKNOWN','observation_ids':ids,'position_observation_ids':ids},p['player_id'],f"/timeline/{r['timeline_index']}"))
  tst=[]
  for t in tc:
   pids=sorted(p['player_id'] for p in pc if p['team_id']==t['team_id']);observed=sorted(p['player_id'] for p in pst if p['player_id'] in pids and p['lifecycle']=='OBSERVED');prior=any(any(x['player_id'] in pids and x['lifecycle']=='OBSERVED' for x in st['player_states']) for st in states);tst.append(_withprov({'schema_id':'tip.team_state','team_id':t['team_id'],'lifecycle':'OBSERVED' if observed else 'MISSING' if prior else 'UNKNOWN','player_ids':pids,'observed_player_ids':observed},t['team_id'],f"/timeline/{r['timeline_index']}"))
  boid=f"observation:world:{e['event_id']}:ball";bs=_withprov({'schema_id':'tip.ball_state','ball_id':ball,'lifecycle':'OBSERVED','visibility':'UNKNOWN','ownership_status':'UNKNOWN','owner_player_id':None,'observation_id':boid,'position_observation_id':boid},ball,f"/timeline/{r['timeline_index']}")
  rel=[_rel(sid,'PLAYER_MEMBER_OF_TEAM',p['player_id'],p['team_id'],None,f"/timeline/{r['timeline_index']}") for p in pc]
  rel.append(_rel(sid,'POSSESSION_ASSIGNED_TO_TEAM',pos,pos_team,None,f"/timeline/{r['timeline_index']}"))
  for o in obs:
   rel.append(_rel(sid,'ENTITY_OBSERVED_AT',o['subject_id'],None,o['observation_id'],f"/timeline/{r['timeline_index']}"))
   if o['subject_kind']=='PLAYER' and o['visibility']=='VISIBLE':rel.append(_rel(sid,'ENTITY_VISIBLE',o['subject_id'],None,o['observation_id'],f"/timeline/{r['timeline_index']}"))
   rel.append(_rel(sid,'SAME_SYNCHRONIZED_INSTANT',o['observation_id'],e['event_id'],o['observation_id'],f"/timeline/{r['timeline_index']}"))
  rel.append(_rel(sid,'BALL_OWNERSHIP_UNKNOWN',ball,None,None,f"/timeline/{r['timeline_index']}"))
  if states:rel.append(_rel(sid,'TEMPORALLY_FOLLOWS',sid,states[-1]['world_state_id'],None,f"/timeline/{r['timeline_index']}"))
  rel.sort(key=lambda x:(x['relationship_type'],x['subject_id'],x['object_id'] or '',x['observation_id'] or '',x['relationship_id']))
  st={'schema_id':'tip.world_state','world_state_id':sid,'world_state_index':si,'anchor_timeline_index':r['timeline_index'],'canonical_time_seconds':float(r['canonical_time_seconds']),'period_id':r['period_id'],'period_number':r['period_number'],'period_time_seconds':float(r['period_time_seconds']),'anchor_event_id':e['event_id'],'pitch_id':pitch,'possession_id':pos,'ball_state':bs,'team_states':tst,'player_states':pst,'observations':obs,'relationships':rel};states.append(_withprov(st,sid,f"/timeline/{r['timeline_index']}"))
 pitch_obj=_withprov({'schema_id':'tip.pitch','pitch_id':pitch,'length_m':105,'width_m':68,'origin':'OWN_GOAL_LOWER_TOUCHLINE','positive_x':'TOWARD_OPPONENT_GOAL','positive_y':'TOWARD_UPPER_TOUCHLINE','lifecycle':'OBSERVED'},pitch,'');pos_obj=_withprov({'schema_id':'tip.possession','possession_id':pos,'possession_team_id':pos_team,'first_world_state_id':states[0]['world_state_id'],'last_world_state_id':states[-1]['world_state_id'],'lifecycle':'OBSERVED'},pos,'/timeline');ball_obj=_withprov({'schema_id':'tip.ball','ball_id':ball},ball,'')
 d={'schema_id':'tip.world_model_dataset','contract_version':'0.1.0','input_contract_version':'0.1.0','synchronized_dataset_sha256':s.sha256,'match_id':mid,'possession_id':pos,'pitch':pitch_obj,'possession':pos_obj,'ball':ball_obj,'teams':tc,'players':pc,'event_evidence':event_evidence,'pass_trajectory_evidence':pass_trajectory_evidence,'world_states':states,'input_provenance':{'normalized_provenance':s['normalized_provenance'],'synchronization_provenance':s['synchronization_provenance']}};d['world_provenance']=_prov([k for k in d if k not in ('pitch','possession','ball','input_provenance')],mid,'')
 return Artifact(d,MEDIA_TYPE,s.sha256,s.source_hashes)
def validate_world_model_dataset(w:Artifact)->Artifact:
 if not isinstance(w,Artifact) or not w.authentic(MEDIA_TYPE,'tip.world_model_dataset'):raise WorldModelError('WORLD_INPUT_ARTIFACT_INVALID')
 if w['synchronized_dataset_sha256']!=w.direct_input_sha256:raise WorldModelError('WORLD_INPUT_ARTIFACT_INVALID')
 states=w['world_states']
 if [s['world_state_index'] for s in states]!=list(range(len(states))):raise WorldModelError('WORLD_TIMESTAMP_INCONSISTENT')
 tids=[t['team_id'] for t in w['teams']];pids=[p['player_id'] for p in w['players']]
 if len(tids)!=len(set(tids)) or len(pids)!=len(set(pids)):raise WorldModelError('WORLD_IDENTITY_COLLISION')
 evidence=w.get('event_evidence')
 if not isinstance(evidence,list) or len(evidence)!=len(states):raise WorldModelError('WORLD_EVENT_EVIDENCE_INVALID')
 expected_fields={'event_id','event_type','actor','recipient','canonical_timestamp','source_record_id','related_event_ids','outcome','authenticated_provenance'}
 evidence_ids=[]
 for i,item in enumerate(evidence):
  if not isinstance(item,dict) or set(item)!=expected_fields or item['event_id']!=states[i]['anchor_event_id'] or item['canonical_timestamp']!=states[i]['canonical_time_seconds']:raise WorldModelError('WORLD_EVENT_EVIDENCE_INVALID')
  evidence_ids.append(item['event_id'])
  if item['event_type'] not in {'PASS','BALL_RECEIPT','CARRY','SHOT'} or item['actor'] not in pids or (item['recipient'] is not None and item['recipient'] not in pids) or not isinstance(item['source_record_id'],str):raise WorldModelError('WORLD_EVENT_EVIDENCE_INVALID')
  related=item['related_event_ids']
  if not isinstance(related,(list,tuple)) or any(not isinstance(rid,str) or not rid for rid in related) or len(related)!=len(set(related)):raise WorldModelError('WORLD_EVENT_EVIDENCE_INVALID')
  provenance=item['authenticated_provenance']
  if set(provenance)!={'/event_id','/event_type','/actor','/recipient','/canonical_timestamp','/source_record_id','/related_event_ids','/outcome'}:raise WorldModelError('WORLD_EVENT_EVIDENCE_INVALID')
  for record in provenance.values():
   sources=record.get('sources',[]) if isinstance(record,dict) else []
   if record.get('class')!='PRESERVED_AUTHENTICATED_INPUT' or record.get('operation')!='WORLD_PRESERVE_EVENT_EVIDENCE' or len(sources)!=1 or not sources[0].get('source_path','').startswith('synchronized_dataset#/timeline/'):raise WorldModelError('WORLD_EVENT_EVIDENCE_INVALID')
 if len(evidence_ids)!=len(set(evidence_ids)):raise WorldModelError('WORLD_EVENT_EVIDENCE_INVALID')
 trajectories=w.get('pass_trajectory_evidence',[])
 pass_ids={item['event_id'] for item in evidence if item['event_type']=='PASS'}
 if not isinstance(trajectories,list) or {item.get('event_id') for item in trajectories}!=pass_ids:raise WorldModelError('WORLD_PASS_TRAJECTORY_INVALID')
 for item in trajectories:
  if set(item)!={'schema_id','event_id','actor','recipient','canonical_timestamp','match_id','possession_id','coordinate_system','pitch_length_m','pitch_width_m','start_position','end_position','authenticated_provenance'} or item['schema_id']!='tip.pass_trajectory_evidence':raise WorldModelError('WORLD_PASS_TRAJECTORY_INVALID')
  if item['match_id']!=w['match_id'] or item['possession_id']!=w['possession_id'] or item['coordinate_system']!='CANONICAL_PITCH_METRES' or item['pitch_length_m']!=105 or item['pitch_width_m']!=68:raise WorldModelError('WORLD_PASS_TRAJECTORY_INVALID')
  for field in ('start_position','end_position'):
   position=item[field]
   if not isinstance(position,dict) or position.get('availability') not in {'AVAILABLE','UNAVAILABLE'}:raise WorldModelError('WORLD_PASS_TRAJECTORY_INVALID')
   if position['availability']=='AVAILABLE' and (not 0<=float(position['x_m'])<=105 or not 0<=float(position['y_m'])<=68):raise WorldModelError('WORLD_PASS_TRAJECTORY_INVALID')
   record=item['authenticated_provenance'].get('/'+field,{})
   sources=record.get('sources',[])
   if record.get('operation')!='WORLD_PRESERVE_PASS_TRAJECTORY' or len(sources)!=1 or not sources[0].get('source_path','').endswith('/normalized_event/'+field):raise WorldModelError('WORLD_PASS_TRAJECTORY_INVALID')
 for st in states:
  for o in st['observations']:
   p=o['position'];available=p.get('availability')=='AVAILABLE'
   if available:
    if p.get('unavailable_reason') is not None or any(p.get(k) is None for k in ('x_m','y_m')) or not 0<=float(p['x_m'])<=105 or not 0<=float(p['y_m'])<=68:raise WorldModelError('WORLD_SPATIAL_VALUE_INVALID')
   elif p.get('availability')!='UNAVAILABLE' or p.get('unavailable_reason')!='SOURCE_POSITION_OUT_OF_BOUNDS' or any(p.get(k) is not None for k in ('x_m','y_m','z_m')):raise WorldModelError('WORLD_OBSERVATION_INVALID')
  observation_ids={o['observation_id'] for o in st['observations']};relationship_ids=[r['relationship_id'] for r in st['relationships']]
  if len(relationship_ids)!=len(set(relationship_ids)):raise WorldModelError('WORLD_RELATIONSHIP_INVALID')
  for rel in st['relationships']:
   if rel['observation_id'] is not None and rel['observation_id'] not in observation_ids:raise WorldModelError('WORLD_RELATIONSHIP_INVALID')
 return w.validated_copy()
