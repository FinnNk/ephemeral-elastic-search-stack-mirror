"""Quality qualification keeps query dependence and missing evidence visible."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from label_quality import assess, bootstrap, canonical, query_key


def fixture(query_count=200):
    policy = json.loads(
        (Path(__file__).parent / "specs/esci-label-quality-v1.json").read_bytes()
    )
    policy["bootstrap_repetitions"] = 500
    manifest = {
        "kind": "esci-label-quality-cohort",
        "cohort": "published",
        "reservation_confirmed": True,
        "reservation_sha256": "f" * 64,
        "query_keys": [],
        "model": {"name": "judge", "version": "4", "artifact_sha256": "a" * 64},
        "release_sha256": "b" * 64,
        "runtime_image": "judge@sha256:" + "c" * 64,
        "model_policy_sha256": "d" * 64,
        "reference_source_id": "e" * 64,
    }
    audit = {
        "kind": "esci-query-independence-audit",
        "audit_complete": True,
        "normalisation": "nfkc_html_whitespace_v1",
        "excluded_query_keys": [],
    }
    inputs, references, predictions = [], [], []
    for q in range(query_count):
        query = "shoe " + str(q)
        identity = query_key(query)
        manifest["query_keys"].append(identity)
        for product, label in [("a", "E"), ("b", "E"), ("c", "I")]:
            pair = {
                "query_id": str(q),
                "product_id": product,
                "request": {"query": query},
                "product": {"product_id": product, "title": product},
            }
            inputs.append({**pair, "query_key": identity})
            references.append(
                {
                    "query_id": str(q),
                    "product_id": product,
                    "label": label,
                    "provenance": {
                        "kind": "published",
                        "source_id": manifest["reference_source_id"],
                    },
                }
            )
            predictions.append(
                {
                    "query_id": str(q),
                    "product_id": product,
                    "input_sha256": hashlib.sha256(canonical(pair)).hexdigest(),
                    "outcome": "labelled" if label == "E" else "abstain",
                    "label": "E" if label == "E" else None,
                    "confidence": 0.96 if label == "E" else 0.6,
                    "probabilities": [0.96, 0.02, 0.01, 0.01]
                    if label == "E"
                    else [0.6, 0.2, 0.1, 0.1],
                    "gate_eligible": False,
                    "provenance": {
                        "kind": "model",
                        "model": manifest["model"],
                        "release_sha256": manifest["release_sha256"],
                        "runtime_image": manifest["runtime_image"],
                        "policy_sha256": manifest["model_policy_sha256"],
                    },
                }
            )
    return inputs, references, predictions, manifest, audit, policy


def test_sufficient_accurate_published_cohort_does_not_activate_model():
    result = assess(*fixture())
    assert result["status"] == "passed"
    assert result["accepted"] == 400
    assert result["accepted_accuracy"] == 1
    assert result["accepted_accuracy_query_bootstrap_95_interval"] == [1, 1]
    assert result["zero_harm_query_incidence_95_upper_bound"] > 0
    assert not result["gate_eligible"]


def test_missing_reference_pairs_or_duplicate_predictions_are_rejected():
    values = fixture()
    values[1].pop()
    with pytest.raises(ValueError, match="exactly the same"):
        assess(*values)
    values = fixture()
    values[2].append(values[2][0])
    with pytest.raises(ValueError, match="Duplicate"):
        assess(*values)


def test_protected_or_forged_query_identity_is_rejected():
    values = fixture()
    values[4]["excluded_query_keys"] = [values[0][0]["query_key"]]
    with pytest.raises(ValueError, match="excluded"):
        assess(*values)
    values = fixture()
    values[0][0]["query_key"] = "f" * 64
    with pytest.raises(ValueError, match="identity"):
        assess(*values)


def test_wrong_model_or_input_hash_cannot_supply_quality_evidence():
    values = fixture()
    values[2][0]["input_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="input bytes"):
        assess(*values)
    values = fixture()
    values[2][0]["provenance"] = deepcopy(values[2][0]["provenance"])
    values[2][0]["provenance"]["release_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="release"):
        assess(*values)


def test_missing_gap_blinding_or_model_generated_references_are_rejected():
    values = fixture()
    values[3]["cohort"] = "human-gap"
    for row in values[1]:
        row["provenance"]["kind"] = "human"
    with pytest.raises(ValueError, match="blindly"):
        assess(*values)
    values = fixture()
    values[1][0]["provenance"]["kind"] = "model"
    with pytest.raises(ValueError, match="independently pinned"):
        assess(*values)


def test_small_or_all_abstaining_samples_remain_inconclusive():
    assert assess(*fixture(20))["status"] == "inconclusive"
    values = fixture()
    for row in values[2]:
        row.update(
            outcome="abstain",
            label=None,
            confidence=0.6,
            probabilities=[0.6, 0.2, 0.1, 0.1],
        )
    result = assess(*values)
    assert result["status"] == "inconclusive" and result["accepted_accuracy"] is None


def test_harmful_exact_predictions_fail_the_unchanged_quality_policy():
    values = fixture()
    for row in values[2]:
        if row["product_id"] == "c":
            row.update(
                outcome="labelled",
                label="E",
                confidence=0.96,
                probabilities=[0.96, 0.02, 0.01, 0.01],
            )
    result = assess(*values)
    assert result["status"] == "failed"
    assert result["irrelevant_to_exact_rate"] == 1
    assert result["confusion"]["I"]["E"] == 200


def test_query_resampling_does_not_shrink_uncertainty_for_repeated_pairs():
    queries = ["one"] * 5 + ["two"] * 5
    numerators = [1] * 5 + [0] * 5
    denominators = [1] * 10
    first = bootstrap(queries, numerators, denominators, 1000, 42)
    repeated = bootstrap(queries * 20, numerators * 20, denominators * 20, 1000, 42)
    assert repeated == pytest.approx(first) and first == [0, 1]


def test_alias_queries_share_the_conservative_identity():
    assert query_key(" ＳＨＯＥ &amp; boot ") == query_key("shoe & boot")
    assert query_key("<b>Shoe</b><script>hidden</script> boot") == query_key(
        "shoe boot"
    )
