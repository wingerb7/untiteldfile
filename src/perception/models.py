from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from enum import StrEnum
from typing import Any


class FeatureCategory(StrEnum):
    SPATIAL = "SPATIAL"
    MOTION = "MOTION"
    BALL = "BALL"
    DENSITY = "DENSITY"
    PASSING_GEOMETRY = "PASSING_GEOMETRY"
    TEMPORAL = "TEMPORAL"


@dataclass(frozen=True)
class EntityReference:
    entity_id: str


@dataclass(frozen=True)
class FeatureDependency:
    feature_code: str
    feature_id: str


FeatureProvenance = dict[str, dict[str, Any]]


@dataclass(frozen=True)
class FeatureDefinition:
    schema_id: str
    feature_code: str
    feature_name: str
    description: str
    category: str
    candidate_scope: str
    output_type: str
    unit: str
    valid_min: float | None
    valid_max: float | None
    precision_decimals: int
    dependency_codes: tuple[str, ...]
    definition_version: str
    perception_provenance: FeatureProvenance


@dataclass(frozen=True)
class FeatureValue:
    scalar: float | None = None
    integer: int | None = None
    boolean: bool | None = None
    enum_value: str | None = None
    entity_id: str | None = None
    entity_ids: tuple[str, ...] | None = None
    vector2: dict[str, float] | None = None
    position2: dict[str, float] | None = None
    polygon2: tuple[dict[str, float], ...] | None = None
    polyline2: tuple[dict[str, float], ...] | None = None
    circle2: dict[str, float] | None = None


@dataclass(frozen=True)
class PerceptionFeature:
    schema_id: str
    feature_id: str
    feature_code: str
    feature_name: str
    category: str
    world_state_id: str
    world_state_index: int
    canonical_time_seconds: float
    subject_ids: tuple[str, ...]
    input_observation_ids: tuple[str, ...]
    dependency_feature_ids: tuple[str, ...]
    status: str
    unavailable_reason: str | None
    value: FeatureValue | None
    unit: str
    perception_provenance: FeatureProvenance


@dataclass(frozen=True)
class PerceptionFrame:
    schema_id: str
    perception_frame_id: str
    world_state_id: str
    world_state_index: int
    canonical_time_seconds: float
    features: tuple[PerceptionFeature, ...]
    perception_provenance: FeatureProvenance


@dataclass(frozen=True)
class PerceptionDataset:
    schema_id: str
    contract_version: str
    input_contract_version: str
    world_model_sha256: str
    match_id: str
    possession_id: str
    event_evidence: tuple[dict[str, Any], ...]
    pass_trajectory_evidence: tuple[dict[str, Any], ...]
    feature_definitions: tuple[FeatureDefinition, ...]
    frames: tuple[PerceptionFrame, ...]
    input_provenance: dict[str, Any]
    perception_provenance: FeatureProvenance

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def _canonical(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        rounded = float(Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))
        return 0.0 if rounded == 0 else rounded
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
