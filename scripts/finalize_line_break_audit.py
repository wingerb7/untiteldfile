from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_line_break_production import PRIOR_DIAGNOSTIC_CROSSINGS


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "audit/line_break_production"


def finalize_trace(name: str) -> tuple[dict, dict]:
    path = DIRECTORY / f"{name}_line_break_trace.json"
    data = json.loads(path.read_text())
    measurement = data.pop("audit_measurement", {})
    for candidate in data["candidates"]:
        receipts = candidate["related_receipts"]
        crosses = bool(candidate["authenticated_opposite_sides"])
        crossing_emitted = bool(candidate["crossing_recognition_ids"])
        after_pass = any(receipt["after_pass"] for receipt in receipts)
        receiver_control = any(
            receipt["after_pass"] and receipt["actor_matches_declared_receiver"]
            for receipt in receipts
        )
        candidate.update(
            prior_audit_only_diagnostic_crossing=(
                candidate["source_event_id"] in PRIOR_DIAGNOSTIC_CROSSINGS[name]
            ),
            geometric_crossing_decision="CROSSES" if crosses else "DOES_NOT_CROSS",
            authenticated_crossing_recognition_decision=(
                "EMITTED" if crossing_emitted else "NOT_EMITTED"
            ),
            completed_pass_decision=(
                "AUTHENTICATED_COMPLETED"
                if candidate["pass_completion_status"] == "COMPLETED"
                else "NOT_COMPLETED"
            ),
            authenticated_related_receipt_decision=(
                "PRESENT_AFTER_PASS" if after_pass else "NOT_PRESENT_AFTER_PASS"
            ),
            receiver_identity_decision=(
                "MATCHES_DECLARED_RECEIVER" if receiver_control else "NOT_AUTHENTICATED"
            ),
            final_episode_eligibility=(
                "ELIGIBLE" if candidate["graph_episode_eligibility"] else "INELIGIBLE"
            ),
        )
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    return data, measurement


def _short(event_id: str) -> str:
    return event_id.removeprefix("event:statsbomb:")


def main() -> None:
    fixtures: dict[str, dict] = {}
    measurements: dict[str, dict] = {}
    for name in ("locatelli", "depay"):
        fixtures[name], measurements[name] = finalize_trace(name)

    lines = [
        "# Graph-backed LINE_BREAK production comparison",
        "",
        "The previous production policy rejected every completed pass at "
        "`INCOMPLETE_ABSOLUTE_POSITION_EVIDENCE`. The corrected policy evaluates "
        "authenticated source-declared pass endpoints and does not require passer or "
        "receiver same-frame positions.",
        "",
        "## Summary",
        "",
        "| Fixture | Completed passes | Endpoint features | Defensive lines | Geometric crossings | Crossing Recognition | Graph relations | Eligible episodes | Audit runtime | Peak RSS |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in fixtures.items():
        candidates = data["candidates"]
        measurement = measurements[name]
        lines.append(
            f"| {name.title()} | {len(candidates)} | "
            f"{sum(bool(c['pass_start_feature_id']) + bool(c['pass_end_feature_id']) for c in candidates)} | "
            f"{sum(bool(c['candidate_defensive_line_recognition_ids']) for c in candidates)} | "
            f"{sum(c['authenticated_opposite_sides'] for c in candidates)} | "
            f"{sum(bool(c['crossing_recognition_ids']) for c in candidates)} | "
            f"{sum(bool(c['crossing_relation_ids']) for c in candidates)} | "
            f"{len(data['line_break_episode_ids'])} | "
            f"{measurement.get('wall_seconds', 0):.2f} s | "
            f"{measurement.get('peak_rss_bytes', 0) / 1_000_000_000:.2f} GB |"
        )

    lines += [
        "",
        "## Candidate-level authenticated decisions",
        "",
        "| Fixture | Source pass event | Start feature | End feature | Defensive-line Recognition | Geometry | Crossing Recognition | Completed pass | Related receipt | Receiver identity | First failure | Graph relation | Episode |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, data in fixtures.items():
        for candidate in data["candidates"]:
            line_id = next(iter(candidate["candidate_defensive_line_recognition_ids"]), "—")
            relation_id = next(iter(candidate["crossing_relation_ids"]), "—")
            episode_id = next(iter(candidate["line_break_episode_ids"]), "—")
            lines.append(
                f"| {name.title()} | `{_short(candidate['source_event_id'])}` | "
                f"`{candidate['pass_start_feature_id']}` | `{candidate['pass_end_feature_id']}` | "
                f"`{line_id}` | {candidate['geometric_crossing_decision']} | "
                f"{candidate['authenticated_crossing_recognition_decision']} | "
                f"{candidate['completed_pass_decision']} | "
                f"{candidate['authenticated_related_receipt_decision']} | "
                f"{candidate['receiver_identity_decision']} | "
                f"`{candidate['first_failing_condition'] or 'NONE'}` | "
                f"`{relation_id}` | `{episode_id}` |"
            )

    lines += [
        "",
        "## Comparison with the prior audit-only candidate set",
        "",
        "The prior audit-only geometry selected 3 Locatelli and 8 Depay crossings. "
        "Those results bypassed Perception and were diagnostic only. Under the "
        "authenticated team-component and recognized-line contract:",
        "",
    ]
    for name, data in fixtures.items():
        by_id = {candidate["source_event_id"]: candidate for candidate in data["candidates"]}
        prior = PRIOR_DIAGNOSTIC_CROSSINGS[name]
        retained = sorted(
            event_id for event_id in prior
            if by_id[event_id]["line_break_episode_ids"]
        )
        rejected = sorted(event_id for event_id in prior if event_id not in retained)
        added = sorted(
            candidate["source_event_id"]
            for candidate in data["candidates"]
            if candidate["line_break_episode_ids"]
            and candidate["source_event_id"] not in prior
        )
        lines += [
            f"### {name.title()}",
            "",
            f"- Prior diagnostic crossings retained as episodes: "
            f"{', '.join(f'`{_short(value)}`' for value in retained) or 'none'}.",
        ]
        for event_id in rejected:
            candidate = by_id[event_id]
            lines.append(
                f"- `{_short(event_id)}` does not become an episode: "
                f"`{candidate['first_failing_condition']}`."
            )
        for event_id in added:
            lines.append(
                f"- `{_short(event_id)}` is an additional authenticated crossing: "
                "the corrected same-team component traversal identifies the defending "
                "line even though the passer has no same-frame position."
            )
        lines.append("")

    lines += [
        "## Contract boundaries",
        "",
        "Endpoint coordinates are canonical 105×68 pitch metres preserved from the "
        "normalized pass event. Start and end share the pass event ID, timestamp, "
        "match, possession, coordinate system, and exact-field provenance. No "
        "orientation transform, interpolation, clamping, repair, receipt-location "
        "substitution, or attacker-direction assumption is used.",
        "",
        "Defensive-line evidence remains same-frame defender `ABSOLUTE_POSITION` plus "
        "same-team `CONNECTION_DISTANCE`. Crossing uses strict opposite sides, so an "
        "endpoint on the line is not a crossing. Completion, later related receipt, "
        "declared-receiver identity, confidence, selection, relevance, scenes, "
        "renderer, CLI, and artifact-authentication semantics are unchanged.",
        "",
        "Every candidate retains `previous_rejection_reason: "
        "INCOMPLETE_ABSOLUTE_POSITION_EVIDENCE` in its deterministic JSON trace.",
        "",
        "## Failure distributions",
        "",
    ]
    for name, data in fixtures.items():
        failures = Counter(
            candidate["first_failing_condition"] or "ELIGIBLE"
            for candidate in data["candidates"]
        )
        lines.append(f"- {name.title()}: {dict(sorted(failures.items()))}.")

    (DIRECTORY / "line_break_comparison.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
