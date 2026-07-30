from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

REQUIRED_MATCH_FIELDS = ("match_id", "possession_id")


class NarrativeConfigError(ValueError):
    """Raised when a per-possession narrative file is missing or malformed."""


def load_narrative_config(path: Path) -> dict[str, Any]:
    """Load a per-possession narrative file (see narratives/*.yaml).

    Unlike config.yaml, this file is never shared across possessions: it is the
    only place hook_text, hook_model_time, and annotations_file for a given
    match/possession may come from."""
    path = Path(path)
    if not path.exists():
        raise NarrativeConfigError(f"narrative config not found: {path}")
    narrative = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    match = narrative.get("match") or {}
    missing = [field for field in REQUIRED_MATCH_FIELDS if match.get(field) is None]
    if missing:
        raise NarrativeConfigError(
            f"narrative config {path} is missing required match.{'/'.join(missing)}"
        )
    return narrative


def apply_narrative(config: dict[str, Any], narrative: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the generic render config with this possession's explicit
    narrative content applied. Never inherits hook_text/hook_model_time/annotations_file
    from whatever the generic config already contains for these fields."""
    resolved = copy.deepcopy(config)
    animation = resolved.setdefault("animation", {})
    narrative_animation = narrative.get("animation") or {}
    hook_text = str(narrative_animation.get("hook_text") or "")
    animation["hook_text"] = hook_text
    animation["hook_model_time"] = float(narrative_animation.get("hook_model_time") or 0.0)
    animation["annotations_file"] = narrative_animation.get("annotations_file")
    if narrative_animation.get("hook_hold_seconds") is not None:
        animation["hook_hold_seconds"] = float(narrative_animation["hook_hold_seconds"])
    elif not hook_text:
        animation["hook_hold_seconds"] = 0.0
    return resolved
