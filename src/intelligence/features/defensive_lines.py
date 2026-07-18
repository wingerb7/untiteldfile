from __future__ import annotations

from dataclasses import dataclass

from src.domain.enums import AttackingDirection
from src.domain.models import PlayerSnapshot, Position


@dataclass(frozen=True)
class DefensiveLineBreakEvidence:
    line_broken: bool
    line_x: float | None
    defenders_in_line: int
    defenders_bypassed: int
    start_side: str
    end_side: str
    sufficient_data: bool
    reason: str | None = None


def _side(position: Position, line_x: float, attacking_direction: AttackingDirection) -> str:
    if attacking_direction == AttackingDirection.LEFT_TO_RIGHT:
        return "behind_line" if position.x > line_x else "in_front_of_line"
    return "behind_line" if position.x < line_x else "in_front_of_line"


def _between(value: float, start: float, end: float) -> bool:
    low, high = sorted((start, end))
    return low < value < high


def estimate_line_break(
    start: Position,
    end: Position,
    defenders: list[PlayerSnapshot],
    attacking_direction: str,
    band_gap: float = 6.0,
    min_defenders_in_line: int = 2,
) -> DefensiveLineBreakEvidence:
    direction = AttackingDirection(attacking_direction)
    outfield = [defender for defender in defenders if not defender.is_goalkeeper]
    if len(outfield) < min_defenders_in_line:
        return DefensiveLineBreakEvidence(False, None, 0, 0, "unknown", "unknown", False, "insufficient_defenders")

    sorted_defenders = sorted(outfield, key=lambda player: player.position.x)
    groups: list[list[PlayerSnapshot]] = []
    current: list[PlayerSnapshot] = []
    for defender in sorted_defenders:
        if not current or abs(defender.position.x - current[-1].position.x) <= band_gap:
            current.append(defender)
        else:
            groups.append(current)
            current = [defender]
    if current:
        groups.append(current)

    candidate_groups = [group for group in groups if len(group) >= min_defenders_in_line]
    if not candidate_groups:
        return DefensiveLineBreakEvidence(False, None, 0, 0, "unknown", "unknown", False, "no_defensive_band")

    crossing_groups = []
    for group in candidate_groups:
        line_x = sum(player.position.x for player in group) / len(group)
        if _between(line_x, start.x, end.x):
            crossing_groups.append((group, line_x))

    if not crossing_groups:
        nearest_group = min(candidate_groups, key=lambda group: min(abs(player.position.x - start.x) for player in group))
        line_x = sum(player.position.x for player in nearest_group) / len(nearest_group)
        return DefensiveLineBreakEvidence(
            False,
            line_x,
            len(nearest_group),
            0,
            _side(start, line_x, direction),
            _side(end, line_x, direction),
            True,
            "pass_does_not_cross_estimated_line",
        )

    selected_group, line_x = max(crossing_groups, key=lambda item: len(item[0]))
    start_side = _side(start, line_x, direction)
    end_side = _side(end, line_x, direction)
    line_broken = start_side == "in_front_of_line" and end_side == "behind_line"
    defenders_bypassed = sum(1 for defender in outfield if _between(defender.position.x, start.x, end.x)) if line_broken else 0
    return DefensiveLineBreakEvidence(
        line_broken,
        line_x,
        len(selected_group),
        defenders_bypassed,
        start_side,
        end_side,
        True,
        None if line_broken else "pass_crosses_line_without_ending_behind_it",
    )
