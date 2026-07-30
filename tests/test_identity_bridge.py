from __future__ import annotations

from src.identity_bridge import IdentityResolutionState, resolve_identity, resolve_render_target


def test_statsbomb_numeric_id_resolves_to_authenticated_track():
    resolution = resolve_identity("7173")
    assert resolution.state == IdentityResolutionState.AUTHENTICATED_TRACK
    assert resolution.resolved_player_id == "7173"


def test_recon_prefixed_id_resolves_to_observation_only():
    resolution = resolve_identity("recon:abc-123:4")
    assert resolution.state == IdentityResolutionState.OBSERVATION_ONLY
    assert resolution.resolved_player_id is None


def test_missing_id_resolves_to_unresolved():
    resolution = resolve_identity(None)
    assert resolution.state == IdentityResolutionState.UNRESOLVED
    resolution = resolve_identity("")
    assert resolution.state == IdentityResolutionState.UNRESOLVED


def test_unknown_id_scheme_resolves_to_unresolved():
    resolution = resolve_identity("player-name-not-an-id")
    assert resolution.state == IdentityResolutionState.UNRESOLVED


def test_candidate_set_resolves_to_ambiguous():
    resolution = resolve_identity("7173", candidate_ids=("7173", "7174"))
    assert resolution.state == IdentityResolutionState.AMBIGUOUS_TRACK_SET
    assert resolution.resolved_player_id is None


def test_identity_bridge_never_fabricates_identity_for_observation_only():
    resolution = resolve_identity("recon:xyz:0")
    assert resolution.resolved_player_id is None


def test_render_target_downgrades_authenticated_track_not_in_scene_to_unresolved():
    resolution = resolve_render_target("7173", visible_players=("7174", "recon:xyz:0"))
    assert resolution.state == IdentityResolutionState.UNRESOLVED


def test_render_target_keeps_authenticated_track_when_visible():
    resolution = resolve_render_target("7173", visible_players=("7173", "recon:xyz:0"))
    assert resolution.state == IdentityResolutionState.AUTHENTICATED_TRACK


def test_render_target_downgrades_observation_only_not_in_scene_to_unresolved():
    resolution = resolve_render_target("recon:xyz:0", visible_players=("7173",))
    assert resolution.state == IdentityResolutionState.UNRESOLVED
