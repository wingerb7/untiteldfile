from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "renders/.matplotlib"))

import yaml

from render.reconstruction import render_reconstruction
from scripts.validate_event_windows import audit, decoded_hashes, sheet
from src.reconstruction import SUPPORTED_ACTIONS, build_window_reconstruction, load_statsbomb_match, select_reconstruction_window

BASE = ROOT / "data/open-data/data"
FIXTURES = [
    {"slug":"netherlands_argentina_2022","match_id":3869321,"competition":"FIFA World Cup","season":"2022","requested_role":"Netherlands – Argentina (World Cup 2022)"},
    {"slug":"netherlands_france_euro_2024","match_id":3930173,"competition":"UEFA Euro","season":"2024","requested_role":"Netherlands Euro 2024 (preferred France)"},
    {"slug":"usa_netherlands_women_2023","match_id":3893808,"competition":"Women's World Cup","season":"2023","requested_role":"Netherlands Women's World Cup (2019 or 2023)"},
    {"slug":"ajax_inter_1972","match_id":3750235,"competition":"Champions League","season":"1971/1972","requested_role":"Closest available alternative to Johan Cruijff Icons","substitution_note":"No Johan Cruijff Icons dataset exists in the local competition inventory; Ajax–Inter 1972 is explicitly used as the closest Cruijff-era alternative."},
    {"slug":"netherlands_argentina_1974","match_id":3888717,"competition":"FIFA World Cup","season":"1974","requested_role":"Total Football (Netherlands 1974)"},
]
ACTION_ORDER=("PASS","CARRY","SHOT","MIXED")


def dump(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")


def metadata()->dict[int,dict[str,Any]]:
    result={}
    for path in (BASE/"matches").glob("*/*.json"):
        for match in json.loads(path.read_text()):result[int(match["match_id"])]=match
    return result


def inventory_record(fixture:dict[str,Any],matches:dict[int,dict[str,Any]])->dict[str,Any]:
    mid=fixture["match_id"];ep=BASE/f"events/{mid}.json";fp=BASE/f"three-sixty/{mid}.json";lp=BASE/f"lineups/{mid}.json"
    events=json.loads(ep.read_text()) if ep.exists() else []
    types=Counter((event.get("type") or {}).get("name","UNKNOWN") for event in events)
    supported={SUPPORTED_ACTIONS[name]:count for name,count in types.items() if name in SUPPORTED_ACTIONS}
    match=matches[mid]
    return {**fixture,"teams":[match["home_team"]["home_team_name"],match["away_team"]["away_team_name"]],"date":match["match_date"],"events_available":ep.exists(),"three_sixty_available":fp.exists(),"lineups_available":lp.exists(),"lineups_unavailable_reason":None if lp.exists() else "lineups directory/file absent from local sparse StatsBomb Open Data checkout","event_count":len(events),"possession_count":len({event.get("possession") for event in events if event.get("possession") is not None}),"supported_reconstruction_actions":supported,"unsupported_action_types":dict(sorted((name,count) for name,count in types.items() if name not in SUPPORTED_ACTIONS)),"substitution_note":fixture.get("substitution_note")}


def discover(fixture:dict[str,Any],config:dict[str,Any])->list[dict[str,Any]]:
    mid=fixture["match_id"];ep=BASE/f"events/{mid}.json";fp=BASE/f"three-sixty/{mid}.json"
    if not ep.exists():return []
    if not fp.exists():
        return [{"fixture":fixture["slug"],"match_id":mid,"action_group":group,"admission_estimate":"REJECTED_INSUFFICIENT_OBSERVATION","reasons":["STATSBOMB_360_UNAVAILABLE"],"rank_score":None} for group in ACTION_ORDER]
    match=load_statsbomb_match(ep,fp,match_id=mid)
    players_by_event={frame["event_id"]:len(frame.get("players",[])) for frame in match["frames"]}
    rows=[]
    supported=[event for event in match["events"] if event["type"] in SUPPORTED_ACTIONS]
    for event in supported:
        action=SUPPORTED_ACTIONS[event["type"]]
        selection=select_reconstruction_window(match,event_id=event["id"],pre_roll_seconds=.75,post_roll_seconds=2.0,config=config)
        visible=max((players_by_event.get(event_id,0) for event_id in selection.get("available_360_frame_ids",[])),default=0)
        rows.append({"fixture":fixture["slug"],"match_id":mid,"action_group":action,"event_ids":[event["id"]],"event_indices":[event["index"]],"timestamps":[event["timestamp"]],"period":event["period"],"duration":selection.get("duration_seconds"),"available_360_frames":selection.get("source_360_frame_count",0),"admission_estimate":selection["admission"],"admission_reasons":selection["reasons"],"estimated_visible_players":visible,"rank_score":score(selection,visible)})
    for index,event in enumerate(supported[:-1]):
        end=next((candidate for candidate in supported[index+1:] if candidate["period"]==event["period"] and candidate["type"]!=event["type"] and 0<float(candidate["timestamp"])-float(event["timestamp"])<=6),None)
        if end is None:continue
        selection=select_reconstruction_window(match,event_id=event["id"],sequence_end_event_id=end["id"],pre_roll_seconds=.5,post_roll_seconds=.75,config=config)
        visible=max((players_by_event.get(event_id,0) for event_id in selection.get("available_360_frame_ids",[])),default=0)
        rows.append({"fixture":fixture["slug"],"match_id":mid,"action_group":"MIXED","event_ids":[event["id"],end["id"]],"event_indices":[event["index"],end["index"]],"timestamps":[event["timestamp"],end["timestamp"]],"period":event["period"],"duration":selection.get("duration_seconds"),"available_360_frames":selection.get("source_360_frame_count",0),"admission_estimate":selection["admission"],"admission_reasons":selection["reasons"],"estimated_visible_players":visible,"rank_score":score(selection,visible)})
    return rows


def score(selection:dict[str,Any],visible:int)->list[Any]:
    rank={"ACCEPTED":0,"ACCEPTED_WITH_LIMITATIONS":1}.get(selection.get("admission"),2)
    duration=float(selection.get("duration_seconds") or 99)
    return [rank,-int(selection.get("source_360_frame_count",0)),-visible,abs(duration-5),str(selection.get("anchor_event_id"))]


def choose(candidates:list[dict[str,Any]],count:int=5)->list[dict[str,Any]]:
    selected=[]
    for group in ACTION_ORDER:
        pool=sorted((row for row in candidates if row["action_group"]==group and row["admission_estimate"]=="ACCEPTED"),key=lambda row:row["rank_score"])
        used=Counter()
        while pool and len([row for row in selected if row["action_group"]==group])<count:
            row=min(pool,key=lambda item:(used[item["fixture"]],item["rank_score"]));pool.remove(row);selected.append(row);used[row["fixture"]]+=1
    return selected


def aggregate(items:list[dict[str,Any]],key:str)->dict[str,Any]:
    groups=defaultdict(list)
    for item in items:groups[item[key]].append(item)
    return {name:summarize(rows) for name,rows in sorted(groups.items())}


def summarize(items:list[dict[str,Any]])->dict[str,Any]:
    admitted=[item for item in items if str(item["admission"]).startswith("ACCEPTED")]
    rejected=[item for item in items if not str(item["admission"]).startswith("ACCEPTED")]
    fields=("unknown_percentage","active_track_count","anonymous_track_count","average_visible_players","interpolated_percentage","observed_source_support_percentage","maximum_player_speed_mps","maximum_ball_speed_mps","duration_seconds")
    return {"total":len(items),"admitted":len(admitted),"rejected":len(rejected),"admission_rate":len(admitted)/max(1,len(items)),"rejection_rate":len(rejected)/max(1,len(items)),**{f"average_{field}":mean(item["metrics"][field] for item in admitted) if admitted else None for field in fields}}


def main()->None:
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("--output",required=True,type=Path);parser.add_argument("--fps",type=int,default=8);args=parser.parse_args()
    if args.output.exists():raise SystemExit("refusing to overwrite immutable Dutch benchmark")
    args.output.mkdir(parents=True);config=yaml.safe_load((ROOT/"config.yaml").read_text());config["animation"].update({"fps":args.fps,"width":540,"height":900})
    matches=metadata();inventory=[inventory_record(fixture,matches) for fixture in FIXTURES];dump(args.output/"dataset_inventory.json",{"schema_id":"tip.dutch_dataset_inventory","fixtures":inventory})
    candidates=[]
    for fixture in FIXTURES:candidates.extend(discover(fixture,config))
    selected=choose(candidates);selected_keys={(row["fixture"],tuple(row.get("event_ids",[])),row["action_group"]) for row in selected}
    for row in candidates:row["selected"]=(row["fixture"],tuple(row.get("event_ids",[])),row["action_group"]) in selected_keys
    dump(args.output/"candidate_windows.json",{"schema_id":"tip.dutch_candidate_windows","candidate_count":len(candidates),"selected_count":len(selected),"candidates":candidates})
    results=[]
    for number,candidate in enumerate(selected,1):
        slug=f"{number:02d}_{candidate['fixture']}_{candidate['action_group'].lower()}_{candidate['event_indices'][0]}";directory=args.output/"windows"/slug;directory.mkdir(parents=True)
        mid=candidate["match_id"];match=load_statsbomb_match(BASE/f"events/{mid}.json",BASE/f"three-sixty/{mid}.json",match_id=mid)
        kwargs={"event_id":candidate["event_ids"][0],"sequence_end_event_id":candidate["event_ids"][-1] if len(candidate["event_ids"])>1 else None,"pre_roll_seconds":.5 if candidate["action_group"]=="MIXED" else .75,"post_roll_seconds":.75 if candidate["action_group"]=="MIXED" else 2.0,"config":config}
        first=build_window_reconstruction(match,**kwargs);second=build_window_reconstruction(deepcopy(match),**kwargs);dump(directory/"selection.json",first["selection"])
        result={"window":slug,"fixture":candidate["fixture"],"competition":next(f["competition"] for f in FIXTURES if f["slug"]==candidate["fixture"]),"action_type":candidate["action_group"],"event_ids":candidate["event_ids"],"admission":first["selection"]["admission"],"admission_reasons":first["selection"]["reasons"],"deterministic_selection":first["selection"]==second["selection"],"deterministic_reconstruction":first["reconstruction"]==second["reconstruction"]}
        reconstruction=first["reconstruction"]
        if reconstruction is not None and str(result["admission"]).startswith("ACCEPTED"):
            dump(directory/"reconstruction.json",reconstruction);a=audit(reconstruction,args.fps,config["reconstruction_window"]["observed_support_seconds"]);b=audit(second["reconstruction"],args.fps,config["reconstruction_window"]["observed_support_seconds"])
            visible=[sum(track["visible"] for track in frame["tracks"]) for frame in a["frames"]];a["metrics"]["average_visible_players"]=mean(visible) if visible else 0;a["admission"]=result["admission"];a["admission_reasons"]=result["admission_reasons"];dump(directory/"audit.json",a)
            raw=directory/"raw.mp4";ghost=directory/"uncertainty.mp4";qa=directory/"visual_qa.mp4";rerun=directory/"raw_rerun.mp4"
            render_reconstruction(reconstruction,config,raw);render_reconstruction(reconstruction,config,ghost,uncertainty_presentation=True);render_reconstruction(reconstruction,config,qa,visual_qa=True,uncertainty_presentation=True);render_reconstruction(second["reconstruction"],config,rerun)
            ha=decoded_hashes(raw,directory/"decoded_a");hb=decoded_hashes(rerun,directory/"decoded_b");sheet(qa,directory/"contact_sheet.png")
            result.update({"metrics":a["metrics"],"deterministic_audit":a==b or a["frames"]==b["frames"],"deterministic_decoded_frames":ha==hb,"decoded_frame_hash":hashlib.sha256("".join(ha).encode()).hexdigest()})
        else:dump(directory/"audit.json",{"admission":result["admission"],"admission_reasons":result["admission_reasons"],"rendered":False})
        results.append(result)
    by_fixture=aggregate(results,"fixture");by_competition=aggregate(results,"competition");by_action=aggregate(results,"action_type")
    for fixture in FIXTURES:
        if fixture["slug"] not in by_fixture:by_fixture[fixture["slug"]]={"total":0,"admitted":0,"rejected":0,"admission_rate":0.0,"rejection_rate":None,"reason":"STATSBOMB_360_UNAVAILABLE; no reconstruction windows selected"}
    admitted=[r for r in results if str(r["admission"]).startswith("ACCEPTED")]
    showcase=sorted(admitted,key=lambda r:(r["metrics"]["unknown_percentage"],r["metrics"]["implausible_player_jumps"],-r["metrics"]["observed_source_support_percentage"],r["metrics"]["active_track_count"]))[:5]
    summary={"schema_id":"tip.dutch_benchmark_summary","selected_window_count":len(results),"overall":summarize(results),"by_competition":by_competition,"by_fixture":by_fixture,"by_action_type":by_action,"showcase_windows":[{"window":r["window"],"fixture":r["fixture"],"action_type":r["action_type"],"event_ids":r["event_ids"],"selection_basis":"lowest UNKNOWN and zero jump evidence; promising action candidate only, no tactical interpretation","reconstruction_confidence":100-r["metrics"]["unknown_percentage"],"visual_quality":"HIGH" if r["metrics"]["unknown_percentage"]<15 else "MODERATE","source_quality":{"observation_support_percentage":r["metrics"]["observed_source_support_percentage"],"source_360_frames":r["metrics"]["source_360_frame_count"]}} for r in showcase],"fixture_readiness":readiness(inventory,by_fixture)}
    dump(args.output/"benchmark_summary.json",summary)


def readiness(inventory:list[dict[str,Any]],by_fixture:dict[str,Any])->dict[str,Any]:
    out={}
    for fixture in inventory:
        stats=by_fixture[fixture["slug"]]
        if not fixture["three_sixty_available"]:classification="NOT_RECOMMENDED";reason="No StatsBomb 360 file; event-only data cannot support player reconstruction."
        elif stats.get("admission_rate",0)==1.0 and (stats.get("average_unknown_percentage") or 100)<25 and (stats.get("average_observed_source_support_percentage") or 0)>=50:classification="READY_FOR_ANALYSIS";reason="All selected windows admitted with bounded uncertainty and at least 50% average observed-source support."
        elif stats.get("admitted",0)>0:classification="READY_WITH_LIMITATIONS";reason="Some admitted windows, but coverage or uncertainty remains uneven."
        else:classification="NOT_RECOMMENDED";reason="No admitted selected reconstruction windows."
        out[fixture["slug"]]={"classification":classification,"reason":reason}
    return out


if __name__=="__main__":main()
