import json
from pathlib import Path


DIRECTORY = Path("audit/line_break_production")


def _trace(name):
    path = DIRECTORY / f"{name}_line_break_trace.json"
    data = json.loads(path.read_text())
    assert path.read_text() == json.dumps(data, sort_keys=True, indent=2) + "\n"
    return data


def test_production_traces_expose_authenticated_endpoint_causal_path():
    expected = {
        "locatelli": (15, 3, 1),
        "depay": (21, 8, 6),
    }
    for name, (candidate_count, prior_diagnostic_count, episode_count) in expected.items():
        trace = _trace(name)
        candidates = trace["candidates"]
        assert trace["candidate_count"] == candidate_count
        assert len(trace["line_break_episode_ids"]) == episode_count
        assert sum(c["prior_audit_only_diagnostic_crossing"] for c in candidates) == prior_diagnostic_count
        assert all(c["previous_rejection_reason"] == "INCOMPLETE_ABSOLUTE_POSITION_EVIDENCE" for c in candidates)
        assert all(c["pass_start_feature_id"] and c["pass_end_feature_id"] for c in candidates)
        assert all(c["completed_pass_decision"] == "AUTHENTICATED_COMPLETED" for c in candidates)

        eligible = [c for c in candidates if c["final_episode_eligibility"] == "ELIGIBLE"]
        assert len(eligible) == episode_count
        assert all(c["geometric_crossing_decision"] == "CROSSES" for c in eligible)
        assert all(c["authenticated_crossing_recognition_decision"] == "EMITTED" for c in eligible)
        assert all(c["authenticated_related_receipt_decision"] == "PRESENT_AFTER_PASS" for c in eligible)
        assert all(c["receiver_identity_decision"] == "MATCHES_DECLARED_RECEIVER" for c in eligible)
        assert all(c["crossing_relation_ids"] and c["line_break_episode_ids"] for c in eligible)


def test_candidate_lines_are_deterministic_authenticated_defender_only_sets():
    for name in ("locatelli", "depay"):
        for candidate in _trace(name)["candidates"]:
            line = candidate["selected_line"]
            if line is None:
                continue
            defenders = line["defender_ids"]
            assert defenders == sorted(defenders)
            assert len(defenders) >= 3
            assert line["longitudinal_compactness_m"] <= 8.0
            assert line["lateral_span_m"] >= 8.0
            assert candidate["passer"] not in defenders
            assert candidate["declared_receiver"] not in defenders
            assert all(item["absolute_position_feature_id"] for item in line["defender_positions"])
            assert all(item["input_observation_ids"] for item in line["defender_positions"])


def test_endpoint_and_graph_references_are_exact_for_every_episode():
    for name in ("locatelli", "depay"):
        for candidate in _trace(name)["candidates"]:
            assert candidate["evaluated_origin_position"] == {
                axis: candidate["source_pass_start_position"][axis] for axis in ("x_m", "y_m")
            }
            assert candidate["evaluated_endpoint_position"] == {
                axis: candidate["source_pass_end_position"][axis] for axis in ("x_m", "y_m")
            }
            if not candidate["line_break_episode_ids"]:
                continue
            assert len(candidate["crossing_recognition_ids"]) == 1
            assert len(candidate["crossing_relation_ids"]) == 1
            assert candidate["first_failing_condition"] is None
