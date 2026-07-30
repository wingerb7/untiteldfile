from __future__ import annotations

from typing import Any


class RenderProvenanceError(RuntimeError):
    """Raised when narrative/render inputs do not all refer to the same match and possession."""


def validate_config_match(config: dict[str, Any], match_id: Any, possession_id: Any) -> None:
    """Refuse to render if config.yaml's declared match/possession identity disagrees with
    the possession actually being rendered. config.yaml is a single shared file whose
    `animation.hook_text`, `animation.hook_model_time`, and `animation.annotations_file`
    are per-match narrative content, not generic defaults: if its `match` block was
    authored for a different match, none of that content is safe to reuse."""
    declared = config.get("match") or {}
    declared_match_id = declared.get("match_id")
    declared_possession_id = declared.get("possession_id")
    if match_id is not None and declared_match_id is not None and int(declared_match_id) != int(match_id):
        raise RenderProvenanceError(
            f"config declares match.match_id={declared_match_id!r} but the possession being processed is "
            f"match_id={match_id!r}; refusing to reuse narrative config (hook_text/hook_model_time/"
            "annotations_file) across matches"
        )
    if (
        possession_id is not None
        and declared_possession_id is not None
        and int(declared_possession_id) != int(possession_id)
    ):
        raise RenderProvenanceError(
            f"config declares match.possession_id={declared_possession_id!r} but the possession being processed "
            f"is possession_id={possession_id!r}; refusing to reuse narrative config (hook_text/hook_model_time/"
            "annotations_file) across matches"
        )


def validate_scene_plan_possession(scene_plan: dict[str, Any], possession_id: Any) -> None:
    """Refuse to render if the scene plan was built for a different possession than the
    one being rendered now (stale file on disk, or an output-directory collision)."""
    scene_plan_possession_id = scene_plan.get("possession_id")
    if (
        possession_id is not None
        and scene_plan_possession_id is not None
        and int(scene_plan_possession_id) != int(possession_id)
    ):
        raise RenderProvenanceError(
            f"scene_plan possession_id={scene_plan_possession_id!r} does not match the possession being "
            f"rendered (possession_id={possession_id!r}); refusing to render a mismatched scene plan"
        )


def validate_annotations_payload(annotations_payload: dict[str, Any] | None, match_id: Any, possession_id: Any) -> None:
    """Refuse to overlay hand-authored annotations onto a possession they were not authored for."""
    if not annotations_payload:
        return
    declared_match_id = annotations_payload.get("match_id")
    declared_possession_id = annotations_payload.get("possession")
    if match_id is not None and declared_match_id is not None and int(declared_match_id) != int(match_id):
        raise RenderProvenanceError(
            f"annotations file declares match_id={declared_match_id!r} but the possession being rendered is "
            f"match_id={match_id!r}; refusing to overlay annotations authored for a different match"
        )
    if (
        possession_id is not None
        and declared_possession_id is not None
        and int(declared_possession_id) != int(possession_id)
    ):
        raise RenderProvenanceError(
            f"annotations file declares possession={declared_possession_id!r} but the possession being rendered "
            f"is possession_id={possession_id!r}; refusing to overlay annotations authored for a different "
            "possession"
        )
