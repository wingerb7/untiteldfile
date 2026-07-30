from __future__ import annotations

"""Deterministic, generic validators for tactical-episode output.

Every function here operates on plain dicts matching the on-disk JSON schemas
already produced by `scripts/render_tactical_episodes.py`
(`tactical_episodes.json`, `scene_directions.json`) plus the raw fixture event
list (`data/*.json`, the `events` array). Nothing here is specific to Depay,
Locatelli, or any other fixture -- these are the same generic checks the
sprint's audit applied by hand, made repeatable.

Outcomes:
- FAIL is reserved for objective contradictions (an episode's own evidence
  field contradicts its label or its interval; identity that cannot be
  displayed; timing that cannot work).
- WARN covers judgment calls the evidence cannot fully settle deterministically
  (e.g. an observation-scoped identity, or a low-confidence retention).
"""

from typing import Any

from src.identity_bridge import IdentityResolutionState, resolve_render_target
from src.tactical_episodes.engine import EPISODE_TYPES

from .models import ValidationOutcome, ValidationResult

FAIL = ValidationOutcome.FAIL
WARN = ValidationOutcome.WARN
PASS = ValidationOutcome.PASS

# Episode types whose own template language claims the episode advances the
# attack or creates a scoring-relevant advantage; excluded are BUILDUP (an
# explicit "no idea yet" placeholder), PRESS_ESCAPE (can be a lateral/backward
# release by definition) and FINISH (its point is the shot, not progress).
_PROGRESS_CLAIMING_TYPES = {t for t in EPISODE_TYPES if t not in {"BUILDUP", "PRESS_ESCAPE", "FINISH"}}

# Episode types whose entire tactical claim is defined relative to a specific
# opposing player; the render must show that player or the claim is
# unverifiable.
_DEFENDER_DEPENDENT_TYPES = {"ISOLATION", "CUTBACK", "SWITCH_OF_PLAY", "PRESS_ESCAPE", "OVERLOAD"}


def build_position_index(raw_events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map raw fixture event id -> {start, end, type, timestamp, index} from the
    `data/*.json` event schema (location / pass_end_location / carry_end_location
    / shot_end_location)."""
    index: dict[str, dict[str, Any]] = {}
    for event in raw_events:
        end = event.get("pass_end_location") or event.get("carry_end_location") or event.get("shot_end_location")
        index[event["id"]] = {
            "start": event.get("location"),
            "end": end[:2] if end else None,
            "type": event.get("type"),
            "timestamp": event.get("timestamp"),
            "index": event.get("index"),
        }
    return index


def _event_order_index(raw_events: list[dict[str, Any]]) -> dict[str, int]:
    return {event["id"]: position for position, event in enumerate(raw_events)}


def validate_temporal_order(episodes: list[dict[str, Any]], order: dict[str, int]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    ordered = sorted(episodes, key=lambda ep: order.get(ep["start_event_id"], -1))
    previous = None
    for episode in ordered:
        start_idx = order.get(episode["start_event_id"])
        end_idx = order.get(episode["end_event_id"])
        if start_idx is None or end_idx is None:
            results.append(ValidationResult("temporal_order", episode["episode_id"], FAIL, "start/end event id not found in possession event order"))
            previous = episode
            continue
        if start_idx > end_idx:
            results.append(ValidationResult("temporal_order", episode["episode_id"], FAIL, f"start index {start_idx} is after end index {end_idx}"))
        elif previous is not None:
            prev_end = order.get(previous["end_event_id"], -1)
            if start_idx <= prev_end:
                results.append(
                    ValidationResult(
                        "temporal_order",
                        episode["episode_id"],
                        FAIL,
                        f"overlaps previous episode {previous['episode_id']} (starts at {start_idx}, previous ends at {prev_end})",
                    )
                )
            else:
                results.append(ValidationResult("temporal_order", episode["episode_id"], PASS, "chronologically ordered and non-overlapping"))
        else:
            results.append(ValidationResult("temporal_order", episode["episode_id"], PASS, "chronologically ordered and non-overlapping"))
        previous = episode
    return results


def validate_evidence_within_interval(episodes: list[dict[str, Any]], order: dict[str, int]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    for episode in episodes:
        start_idx = order.get(episode["start_event_id"])
        end_idx = order.get(episode["end_event_id"])
        if start_idx is None or end_idx is None:
            continue
        outside = [eid for eid in episode["participating_action_ids"] if order.get(eid, -1) < start_idx or order.get(eid, -1) > end_idx]
        if outside:
            results.append(
                ValidationResult(
                    "evidence_within_interval",
                    episode["episode_id"],
                    FAIL,
                    f"{len(outside)} participating action id(s) fall outside declared [start,end] interval",
                    {"outside_ids": outside},
                )
            )
        else:
            results.append(ValidationResult("evidence_within_interval", episode["episode_id"], PASS, "all participating action ids fall within the declared interval"))
    return results


def validate_no_duplicate_decisive_action(episodes: list[dict[str, Any]]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    seen: dict[str, str] = {}
    for episode in episodes:
        decisive_event_id = episode["end_event_id"]
        prior = seen.get(decisive_event_id)
        if prior is not None:
            results.append(
                ValidationResult(
                    "no_duplicate_decisive_action",
                    episode["episode_id"],
                    FAIL,
                    f"decisive action event {decisive_event_id} is also the decisive action of {prior}",
                )
            )
        else:
            seen[decisive_event_id] = episode["episode_id"]
            results.append(ValidationResult("no_duplicate_decisive_action", episode["episode_id"], PASS, "decisive action is unique to this episode"))
    return results


def validate_supported_episode_type(episodes: list[dict[str, Any]]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    for episode in episodes:
        if episode["episode_type"] not in EPISODE_TYPES:
            results.append(ValidationResult("supported_episode_type", episode["episode_id"], FAIL, f"episode_type {episode['episode_type']!r} is not in the supported catalogue"))
        else:
            results.append(ValidationResult("supported_episode_type", episode["episode_id"], PASS, "episode_type is in the supported catalogue"))
    return results


def validate_switch_of_play_changes_channel(episodes: list[dict[str, Any]]) -> list[ValidationResult]:
    """A SWITCH_OF_PLAY's own evidence must assert `changed_side: true`; a large
    lateral pass that stays on the same side of the pitch is progression, not a
    switch, no matter how many metres it covers."""
    results: list[ValidationResult] = []
    for episode in episodes:
        if episode["episode_type"] != "SWITCH_OF_PLAY":
            continue
        feature_values = episode.get("evidence", {}).get("feature_values", {})
        changed_side = feature_values.get("changed_side")
        if changed_side is not True:
            results.append(
                ValidationResult(
                    "switch_of_play_changes_channel",
                    episode["episode_id"],
                    FAIL,
                    f"labelled SWITCH_OF_PLAY but evidence.feature_values.changed_side={changed_side!r}; "
                    "the ball did not demonstrably move attacking focus to the other side of the pitch",
                    {"feature_values": feature_values},
                )
            )
        else:
            results.append(ValidationResult("switch_of_play_changes_channel", episode["episode_id"], PASS, "evidence confirms the ball crossed to the opposite side"))
    return results


def validate_episode_forward_progress(
    episodes: list[dict[str, Any]], positions: dict[str, dict[str, Any]], attacking_goal_x: float
) -> list[ValidationResult]:
    """Episode types other than BUILDUP/PRESS_ESCAPE/FINISH claim, by their own
    template text, to advance the attack or create a scoring-relevant
    advantage. WARN when the episode's own span nets zero or negative
    reduction in distance to the goal `attacking_goal_x` (i.e. the ball ended
    the episode no closer to goal than it started, despite the label claiming
    an attacking advantage was created)."""
    results: list[ValidationResult] = []
    for episode in episodes:
        if episode["episode_type"] not in _PROGRESS_CLAIMING_TYPES:
            continue
        action_ids = episode["participating_action_ids"]
        start_pos = None
        for eid in action_ids:
            record = positions.get(eid)
            if record and record.get("start"):
                start_pos = record["start"]
                break
        end_pos = None
        for eid in reversed(action_ids):
            record = positions.get(eid)
            if record and record.get("end"):
                end_pos = record["end"]
                break
        if end_pos is None:
            for eid in reversed(action_ids):
                record = positions.get(eid)
                if record and record.get("start"):
                    end_pos = record["start"]
                    break
        if start_pos is None or end_pos is None:
            results.append(ValidationResult("episode_forward_progress", episode["episode_id"], WARN, "insufficient positional evidence to assess forward progress"))
            continue
        goal_distance_reduction = abs(attacking_goal_x - start_pos[0]) - abs(attacking_goal_x - end_pos[0])
        outcome = PASS if goal_distance_reduction > 0 else WARN
        results.append(
            ValidationResult(
                "episode_forward_progress",
                episode["episode_id"],
                outcome,
                f"distance-to-goal reduced by {goal_distance_reduction:.1f}m over the episode span "
                f"({'net progress toward goal' if goal_distance_reduction > 0 else 'no net progress toward goal despite the episode label claiming an attacking advantage'})",
                {"start": start_pos, "end": end_pos, "goal_distance_reduction": goal_distance_reduction},
            )
        )
    return results


def validate_actor_visibility(episode: dict[str, Any], direction: dict[str, Any]) -> ValidationResult:
    visible = set(direction["visible_players"])
    missing = [pid for pid in episode["primary_actor_ids"] if pid not in visible]
    if missing:
        return ValidationResult("actor_visibility", episode["episode_id"], FAIL, f"primary actor(s) {missing} not present in this scene's visible_players")
    return ValidationResult("actor_visibility", episode["episode_id"], PASS, "all primary actors are visible in the scene")


def validate_defender_visibility_when_required(episode: dict[str, Any], direction: dict[str, Any]) -> ValidationResult:
    if episode["episode_type"] not in _DEFENDER_DEPENDENT_TYPES:
        return ValidationResult("defender_visibility", episode["episode_id"], PASS, "episode type does not depend on a specific defender being visible")
    visible = set(direction["visible_players"])
    required = episode["relevant_defender_ids"]
    if not required:
        return ValidationResult("defender_visibility", episode["episode_id"], WARN, "episode type depends on a defender but none was resolved")
    missing = [pid for pid in required if pid not in visible]
    if missing:
        return ValidationResult("defender_visibility", episode["episode_id"], FAIL, f"required defender(s) {missing} not present in this scene's visible_players")
    return ValidationResult("defender_visibility", episode["episode_id"], PASS, "required defender(s) are visible in the scene")


def validate_identity_resolution(episode: dict[str, Any], direction: dict[str, Any]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    visible = tuple(direction["visible_players"])
    for pid in [*episode["primary_actor_ids"], *episode["relevant_defender_ids"]]:
        resolution = resolve_render_target(pid, visible)
        if resolution.state == IdentityResolutionState.AUTHENTICATED_TRACK:
            results.append(ValidationResult("identity_resolution", episode["episode_id"], PASS, f"{pid}: {resolution.reason}"))
        elif resolution.state == IdentityResolutionState.OBSERVATION_ONLY:
            results.append(ValidationResult("identity_resolution", episode["episode_id"], WARN, f"{pid}: {resolution.reason}"))
        else:
            results.append(ValidationResult("identity_resolution", episode["episode_id"], FAIL, f"{pid}: {resolution.reason}"))
    return results


def validate_caption_timing(episode_id: str, duration_seconds: float, lead_seconds: float) -> ValidationResult:
    if lead_seconds > duration_seconds:
        return ValidationResult(
            "caption_timing",
            episode_id,
            FAIL,
            f"caption lead-in ({lead_seconds}s) exceeds the scene's total duration ({duration_seconds}s); the caption cannot appear before or during the action",
        )
    return ValidationResult("caption_timing", episode_id, PASS, "caption lead-in fits within the scene duration")


def validate_causal_transition(edge: dict[str, Any]) -> ValidationResult:
    """A causal transition is only as strong as its evidence. Chronology alone
    (the two episodes are simply adjacent in time) is not evidence of CREATES /
    ENABLES / FORCES / OPENS / ATTRACTS / RELEASES / EXPLOITS / FINISHES."""
    evidence = edge.get("supporting_evidence") or {}
    non_chronology_keys = [k for k in evidence.keys() if k not in ("source_episode_id", "target_episode_id", "adjacent")]
    if not non_chronology_keys:
        return ValidationResult(
            "causal_transition_evidence",
            f"{edge.get('source_episode_id')}->{edge.get('target_episode_id')}",
            FAIL,
            f"transition {edge.get('relation')!r} is supported only by chronological adjacency, not by an independent tactical mechanism",
        )
    return ValidationResult(
        "causal_transition_evidence",
        f"{edge.get('source_episode_id')}->{edge.get('target_episode_id')}",
        PASS if edge.get("confidence", 0) >= 0.6 else WARN,
        f"transition {edge.get('relation')!r} cites evidence beyond chronology: {non_chronology_keys}",
    )


def validate_low_confidence_retention(episodes: list[dict[str, Any]], threshold: float = 0.6) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    for episode in episodes:
        if episode["confidence"] < threshold:
            results.append(
                ValidationResult(
                    "low_confidence_retention",
                    episode["episode_id"],
                    WARN,
                    f"confidence {episode['confidence']} is below {threshold}; verify this episode is not retained only to fill the episode cap",
                )
            )
        else:
            results.append(ValidationResult("low_confidence_retention", episode["episode_id"], PASS, f"confidence {episode['confidence']} meets the retention threshold"))
    return results


def run_all_episode_validators(
    episodes: list[dict[str, Any]],
    directions_by_episode_id: dict[str, dict[str, Any]],
    raw_events: list[dict[str, Any]],
    attacking_goal_x: float,
) -> list[ValidationResult]:
    order = _event_order_index(raw_events)
    positions = build_position_index(raw_events)
    results: list[ValidationResult] = []
    results += validate_temporal_order(episodes, order)
    results += validate_evidence_within_interval(episodes, order)
    results += validate_no_duplicate_decisive_action(episodes)
    results += validate_supported_episode_type(episodes)
    results += validate_switch_of_play_changes_channel(episodes)
    results += validate_episode_forward_progress(episodes, positions, attacking_goal_x)
    results += validate_low_confidence_retention(episodes)
    for episode in episodes:
        direction = directions_by_episode_id[episode["episode_id"]]
        results.append(validate_actor_visibility(episode, direction))
        results.append(validate_defender_visibility_when_required(episode, direction))
        results += validate_identity_resolution(episode, direction)
    return results
