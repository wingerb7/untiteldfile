from scripts.render_continuation_locatelli import upstream


def test_authenticated_locatelli_fixture_matches_return_combination():
    _, _, _, _, patterns = upstream()
    assert len(patterns["matches"]) == 1
    match = patterns["matches"][0]
    assert [action["role"] for action in match["actions"]] == ["initial_pass", "teammate_receipt", "teammate_carry", "return_pass", "return_receipt", "finish"]
    assert match["initial_actor_id"] == "player:statsbomb:7038"
    assert match["teammate_actor_id"] == "player:statsbomb:7131"
    assert not any(action["role"] == "transitive_action" for action in match["actions"])
