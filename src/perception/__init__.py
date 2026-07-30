"""Deterministic, objective Perception Layer (SPEC.md Chapter 9)."""

from .engine import build_perception_dataset
from .errors import PerceptionError
from .models import PerceptionDataset

__all__ = ["PerceptionDataset", "PerceptionError", "build_perception_dataset"]
from .authentication import PERCEPTION_MEDIA_TYPE, validate_perception_dataset
from .engine import build_perception_dataset

__all__ = ["PERCEPTION_MEDIA_TYPE", "build_perception_dataset", "validate_perception_dataset"]
