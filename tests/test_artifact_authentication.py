import json

import pytest

from src.contracts import Artifact, artifact_metrics, reset_artifact_metrics


MEDIA = "application/vnd.test+json"


def artifact(data=None):
    return Artifact(data or {"schema_id": "test", "ordered": [1, 2], "nested": {"value": 3}}, MEDIA)


def test_validated_copy_reuses_only_identical_immutable_authenticated_content():
    reset_artifact_metrics()
    original = artifact()
    validated = original.validated_copy()
    assert validated.validated and validated.authentic(MEDIA, "test")
    assert validated.sha256 == original.sha256
    assert validated.canonical_bytes() == original.canonical_bytes()
    assert artifact_metrics()["validated_copy_reuses"] == 1
    changed = validated.data
    changed["nested"]["value"] = 4
    replacement = Artifact(changed, MEDIA)
    assert replacement.sha256 != validated.sha256


def test_input_and_all_public_access_paths_cannot_tamper_with_payload():
    source = {"schema_id": "test", "ordered": [1, 2], "nested": {"value": 3}}
    sealed = Artifact(source, MEDIA, validated=True)
    source["nested"]["value"] = 9
    source["ordered"].append(3)
    accessed = sealed.data
    accessed["nested"]["value"] = 8
    accessed["ordered"].append(4)
    nested = sealed["nested"]
    nested["value"] = 7
    assert sealed.authentic(MEDIA, "test")
    assert sealed.data == {"schema_id": "test", "ordered": [1, 2], "nested": {"value": 3}}
    with pytest.raises(TypeError):
        sealed.payload["nested"]["value"] = 6
    with pytest.raises(TypeError):
        sealed.payload["nested"].update(value=6)
    with pytest.raises(AttributeError):
        sealed.sha256 = "0" * 64
    with pytest.raises(AttributeError):
        sealed.validated = False


def test_canonical_round_trip_ordering_and_hash_invariants():
    one = artifact({"schema_id": "test", "b": 2, "a": 1, "ordered": [1, 2]})
    reordered_mapping = artifact({"ordered": [1, 2], "a": 1, "b": 2, "schema_id": "test"})
    reordered_sequence = artifact({"schema_id": "test", "b": 2, "a": 1, "ordered": [2, 1]})
    assert one.canonical_bytes() == reordered_mapping.canonical_bytes()
    assert one.sha256 == reordered_mapping.sha256
    assert reordered_sequence.sha256 != one.sha256
    restored = Artifact(json.loads(one.canonical_bytes()), MEDIA)
    assert restored.authentic(MEDIA, "test")
    assert restored.sha256 == one.sha256
    assert restored.canonical_bytes() == one.canonical_bytes()


def test_mutated_copy_cannot_inherit_digest_or_cached_authenticity():
    sealed = artifact().validated_copy()
    mutation = sealed.data
    mutation["ordered"].reverse()
    changed = Artifact(mutation, MEDIA, validated=True)
    assert changed.sha256 != sealed.sha256
    assert changed.canonical_bytes() != sealed.canonical_bytes()
    assert sealed.authentic(MEDIA, "test")
