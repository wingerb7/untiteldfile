from __future__ import annotations

from src.domain.models import TacticalFinding


def explain_finding(finding: TacticalFinding, language: str = "en") -> str:
    if finding.pattern_type != "line_breaking_pass":
        label = finding.pattern_type.replace("_", " ")
        return f"Detected {label} from reusable spatial and event-derived features."
    defenders = int(finding.evidence.get("defenders_bypassed") or 0)
    if language == "nl":
        return (
            f"Deze pass breekt de defensieve linie, passeert {defenders} verdedigers "
            "en bereikt een speler achter het defensieve blok."
        )
    return (
        f"This pass breaks the defensive line, bypasses {defenders} defenders "
        "and finds the receiver behind the defensive block."
    )
