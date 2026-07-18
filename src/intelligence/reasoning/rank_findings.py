from __future__ import annotations

from src.domain.models import NormalizedPossession
from src.intelligence.patterns.line_break import TacticalFinding


def rank_findings(possession: NormalizedPossession, findings: list[TacticalFinding]) -> list[TacticalFinding]:
    event_order = {event.event_id: idx for idx, event in enumerate(possession.events)}
    shot_idx = next((idx for idx, event in enumerate(possession.events) if event.event_type == "Shot"), len(possession.events))

    def key(finding: TacticalFinding) -> tuple[float, float, float, float]:
        idx = event_order.get(finding.event_id, 0)
        proximity = 1.0 / (1.0 + abs(shot_idx - idx))
        visual = 1.0 if finding.evidence.get("defensive_line_x") is not None else 0.0
        data = finding.evidence.get("confidence_components", {}).get("data_quality", 0.0)
        return finding.confidence, proximity, visual, data

    return sorted(findings, key=key, reverse=True)
