from __future__ import annotations

from src.intelligence.patterns.line_break import TacticalFinding


def explain_finding(finding: TacticalFinding, language: str = "en") -> str:
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
