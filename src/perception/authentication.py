from __future__ import annotations
from src.contracts import Artifact
from .errors import PerceptionError
from .models import PerceptionDataset

PERCEPTION_MEDIA_TYPE = "application/vnd.tip.perception-dataset+json"

def _validate_pass_endpoints(artifact:Artifact)->None:
    trajectories={item["event_id"]:(index,item) for index,item in enumerate(artifact.get("pass_trajectory_evidence",()))}
    for frame in artifact["frames"]:
        for feature in frame["features"]:
            if feature.get("feature_code") not in {"PASS_START_POSITION","PASS_END_POSITION"}:continue
            event_ids=tuple(feature.get("subject_ids",()));event_id=event_ids[0] if len(event_ids)==1 else None
            if event_id not in trajectories:raise PerceptionError("TIP-PER-PASS-ENDPOINT-INVALID","unknown pass event")
            index,trajectory=trajectories[event_id];field="start_position" if feature["feature_code"]=="PASS_START_POSITION" else "end_position"
            expected_id=f"feature:{frame['world_state_id']}:{feature['feature_code'].lower()}:{event_id}"
            position=(feature.get("value") or {}).get("position2") or {};x,y=position.get("x_m"),position.get("y_m")
            if feature.get("feature_id")!=expected_id or feature.get("status")!="AVAILABLE" or feature.get("input_observation_ids") or feature.get("canonical_time_seconds")!=trajectory.get("canonical_timestamp"):raise PerceptionError("TIP-PER-PASS-ENDPOINT-INVALID","identity or time mismatch")
            if not isinstance(x,(int,float)) or not isinstance(y,(int,float)) or not 0<=x<=105 or not 0<=y<=68:raise PerceptionError("TIP-PER-PASS-ENDPOINT-INVALID","invalid coordinate")
            parent=trajectory.get(field,{})
            if parent.get("availability")!="AVAILABLE" or float(parent.get("x_m"))!=float(x) or float(parent.get("y_m"))!=float(y):raise PerceptionError("TIP-PER-PASS-ENDPOINT-INVALID","parent mismatch")
            record=feature.get("perception_provenance",{}).get("/value",{});sources=record.get("sources",[])
            expected_path=f"world_model_dataset#/pass_trajectory_evidence/{index}/{field}"
            if record.get("operation")!="PER_CALCULATE_FEATURE" or len(sources)!=1 or sources[0]!={"source_record_id":event_id,"source_path":expected_path}:raise PerceptionError("TIP-PER-PASS-ENDPOINT-INVALID","provenance mismatch")

def validate_perception_dataset(dataset: PerceptionDataset | Artifact, *, source_hashes: dict[str, str] | None = None) -> Artifact:
    if isinstance(dataset, Artifact):
        if not dataset.authentic(PERCEPTION_MEDIA_TYPE, "tip.perception_dataset"):
            raise PerceptionError("TIP-PER-INPUT-ARTIFACT-INVALID", "invalid Perception artifact")
        _validate_pass_endpoints(dataset)
        return dataset.validated_copy()
    if not isinstance(dataset, PerceptionDataset):
        raise PerceptionError("TIP-PER-INPUT-ARTIFACT-INVALID", "expected PerceptionDataset")
    if dataset.schema_id != "tip.perception_dataset" or dataset.contract_version != "0.1.0":
        raise PerceptionError("TIP-PER-INPUT-SCHEMA-INVALID", "invalid PerceptionDataset identity")
    if not dataset.frames or not dataset.feature_definitions:
        raise PerceptionError("TIP-PER-INPUT-SCHEMA-INVALID", "empty mandatory collection")
    if [frame.world_state_index for frame in dataset.frames] != list(range(len(dataset.frames))):
        raise PerceptionError("TIP-PER-ORDERING-INVALID", "frames are not canonically ordered")
    artifact = Artifact(dataset, PERCEPTION_MEDIA_TYPE, dataset.world_model_sha256, source_hashes, validated=True)
    _validate_pass_endpoints(artifact)
    return artifact
