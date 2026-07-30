from __future__ import annotations

"""Deterministic identity-resolution bridge between tactical-relevance /
tactical-episode player references and what the renderer can actually show.

This module does not touch reconstruction. It classifies an *existing*
identifier (a raw StatsBomb `player_id` string, or a `recon:{event_id}:{idx}`
synthetic freeze-frame snapshot id produced by
`src.ingest.possession_loader._snapshot`) into one of four resolution states,
and separately checks whether a resolved identifier is actually present in a
given scene's `visible_players`. It never invents or upgrades an identity: an
`OBSERVATION_ONLY` id stays `OBSERVATION_ONLY` even if the renderer happens to
display it correctly.
"""

from dataclasses import dataclass
from enum import Enum


class IdentityResolutionState(str, Enum):
    # A persistent, source-authenticated player identity (StatsBomb player_id),
    # stable across every event in the match.
    AUTHENTICATED_TRACK = "AUTHENTICATED_TRACK"
    # A synthetic id scoped to a single freeze-frame observation
    # (`recon:{event_id}:{idx}`); carries no persistence guarantee.
    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    # More than one candidate identity was supplied for the same request and
    # none is marked authoritative.
    AMBIGUOUS_TRACK_SET = "AMBIGUOUS_TRACK_SET"
    # No identifier, an empty identifier, or an identifier that matches
    # neither known id scheme.
    UNRESOLVED = "UNRESOLVED"


_RECON_PREFIX = "recon:"


@dataclass(frozen=True)
class IdentityResolution:
    requested_id: str
    state: IdentityResolutionState
    resolved_player_id: str | None
    reason: str


def resolve_identity(tracking_id: str | None, candidate_ids: tuple[str, ...] = ()) -> IdentityResolution:
    """Classify a single legacy-pipeline tracking id.

    `candidate_ids`, when non-empty, represents a set of ids the caller could
    not disambiguate between (e.g. more than one freeze-frame player equally
    plausible as "the" relevant defender); this always resolves to
    AMBIGUOUS_TRACK_SET rather than silently picking one.
    """
    if candidate_ids:
        return IdentityResolution(
            requested_id=tracking_id or "",
            state=IdentityResolutionState.AMBIGUOUS_TRACK_SET,
            resolved_player_id=None,
            reason=f"{len(candidate_ids)} candidate identities available; none marked authoritative",
        )
    if not tracking_id:
        return IdentityResolution(
            requested_id=tracking_id or "",
            state=IdentityResolutionState.UNRESOLVED,
            resolved_player_id=None,
            reason="no identifier supplied",
        )
    if tracking_id.startswith(_RECON_PREFIX):
        return IdentityResolution(
            requested_id=tracking_id,
            state=IdentityResolutionState.OBSERVATION_ONLY,
            resolved_player_id=None,
            reason="synthetic per-event freeze-frame snapshot id; not persistent across events",
        )
    if tracking_id.isdigit():
        return IdentityResolution(
            requested_id=tracking_id,
            state=IdentityResolutionState.AUTHENTICATED_TRACK,
            resolved_player_id=tracking_id,
            reason="matches a source-provided StatsBomb player_id",
        )
    return IdentityResolution(
        requested_id=tracking_id,
        state=IdentityResolutionState.UNRESOLVED,
        resolved_player_id=None,
        reason="identifier matches neither the statsbomb player_id nor the recon: snapshot id scheme",
    )


def resolve_render_target(tracking_id: str | None, visible_players: tuple[str, ...]) -> IdentityResolution:
    """Resolve an identity request the way a SceneDirection consumer would:
    ask for a known player, an anonymous observation, or accept that neither
    is available -- then check the renderer actually has that id in view.

    An AUTHENTICATED_TRACK id that is absent from `visible_players` downgrades
    to UNRESOLVED: the identity is real, but this scene does not display it,
    so nothing should be asserted about that player in this scene.
    """
    resolution = resolve_identity(tracking_id)
    if resolution.state == IdentityResolutionState.AUTHENTICATED_TRACK and resolution.requested_id not in visible_players:
        return IdentityResolution(
            requested_id=resolution.requested_id,
            state=IdentityResolutionState.UNRESOLVED,
            resolved_player_id=None,
            reason="authenticated player id is not present in this scene's visible_players",
        )
    if resolution.state == IdentityResolutionState.OBSERVATION_ONLY and resolution.requested_id not in visible_players:
        return IdentityResolution(
            requested_id=resolution.requested_id,
            state=IdentityResolutionState.UNRESOLVED,
            resolved_player_id=None,
            reason="observation-scoped snapshot id is not present in this scene's visible_players",
        )
    return resolution
