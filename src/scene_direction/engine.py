from __future__ import annotations

from src.domain.models import Event, NormalizedPossession
from src.tactical_episodes.models import TacticalEpisode
from src.tactical_relevance import MANDATORY, PlayerRelevance

from .models import SceneDirection

# The full set of overlay instruction types the renderer already understands
# (src/render/overlays.py::execute_instruction). "show_caption" is excluded: it is
# the single caption every scene gets, not a competing overlay choice.
ALL_OVERLAY_TYPES = ("highlight_player", "draw_pass_arrow", "draw_carry_arrow", "draw_defensive_line", "draw_schematic_continuation")

_DIRECTION_BY_EPISODE_TYPE: dict[str, tuple[str, str | None, str | None]] = {
    # episode_type: (camera_intent, primary_overlay, secondary_overlay)
    "BUILDUP": ("track_ball_carrier", "highlight_player", None),
    "PRESS_ESCAPE": ("hold_on_ball_carrier_under_pressure", "highlight_player", "draw_carry_arrow"),
    "LINE_BREAK": ("track_pass_through_the_line", "draw_pass_arrow", "draw_defensive_line"),
    "PROGRESSION": ("track_combination_sequence", "draw_pass_arrow", None),
    "THIRD_MAN_COMBINATION": ("track_combination_sequence", "draw_pass_arrow", "highlight_player"),
    "RETURN_COMBINATION": ("track_combination_sequence", "draw_pass_arrow", "highlight_player"),
    "WIDE_PROGRESSION": ("hold_on_wide_space", "highlight_player", "draw_pass_arrow"),
    "OVERLOAD": ("hold_on_local_numbers", "highlight_player", "draw_pass_arrow"),
    "ISOLATION": ("hold_on_free_player", "highlight_player", "draw_pass_arrow"),
    "SWITCH_OF_PLAY": ("track_switch_across_pitch", "draw_pass_arrow", None),
    "HALF_SPACE_ENTRY": ("track_entry_into_half_space", "draw_carry_arrow", "highlight_player"),
    "OFF_BALL_RUN": ("track_late_arriving_run", "highlight_player", "draw_pass_arrow"),
    "CUTBACK": ("track_cutback_into_the_box", "draw_pass_arrow", "highlight_player"),
    "BOX_ARRIVAL": ("track_ball_into_the_box", "draw_carry_arrow", "highlight_player"),
    "FINISH": ("hold_on_shooter_and_goalkeeper", "highlight_player", None),
}


def _events_in_span(possession: NormalizedPossession, episode: TacticalEpisode) -> list[Event]:
    by_id = {event.event_id: event for event in possession.events}
    return [by_id[event_id] for event_id in episode.participating_action_ids if event_id in by_id]


def _primary_message(episode: TacticalEpisode) -> str:
    return f"{episode.cause} {episode.created_advantage}".strip()


def build_scene_direction(
    possession: NormalizedPossession,
    episode: TacticalEpisode,
    relevance_records: list[PlayerRelevance],
) -> SceneDirection:
    """One scene, one tactical idea: every field here bounds what the renderer may show."""
    span = _events_in_span(possession, episode)
    anchor_event = span[-1] if span else None

    visible_players = [record.player_id for record in relevance_records]
    highlighted_players = [record.player_id for record in relevance_records if record.category == MANDATORY]
    on_pitch_ids = {player.tracking_id for player in (anchor_event.freeze_frame if anchor_event else [])}
    hidden_players = sorted(on_pitch_ids - set(visible_players))

    camera_intent, primary_overlay, secondary_overlay = _DIRECTION_BY_EPISODE_TYPE.get(
        episode.episode_type, ("track_ball_carrier", "highlight_player", None)
    )
    forbidden_overlays = sorted(set(ALL_OVERLAY_TYPES) - {overlay for overlay in (primary_overlay, secondary_overlay) if overlay})

    primary_message = _primary_message(episode)
    return SceneDirection(
        episode_id=episode.episode_id,
        primary_message=primary_message,
        tactical_question=episode.tactical_question,
        visible_players=visible_players,
        highlighted_players=highlighted_players,
        hidden_players=hidden_players,
        camera_intent=camera_intent,
        primary_overlay=primary_overlay,
        secondary_overlay=secondary_overlay,
        caption_intent=primary_message,
        visual_budget={"captions": 1, "primary_overlays": 1 if primary_overlay else 0, "secondary_overlays": 1 if secondary_overlay else 0},
        forbidden_overlays=forbidden_overlays,
    )
