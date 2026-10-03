"""Development calibration cannot replace independent quality confirmation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_labels import GRID, select
from label_quality import query_key
from test_label_quality import fixture


def development(query_count=400):
    values = fixture(query_count)
    values[3]["selection_role"] = "development"
    values[3]["confirmation_query_keys"] = [query_key("reserved confirmation")]
    return values


def set_scores(prediction, scores):
    prediction["probabilities"] = scores
    prediction["confidence"] = max(scores)
    prediction["outcome"] = "labelled" if max(scores) >= 0.9 else "abstain"
    prediction["label"] = (
        ("E", "S", "C", "I")[scores.index(max(scores))] if max(scores) >= 0.9 else None
    )


def test_class_thresholds_add_irrelevant_labels_without_lowering_exact_threshold():
    values = development()
    for reference, prediction in zip(values[1], values[2], strict=True):
        if reference["label"] == "I":
            set_scores(prediction, [0.1, 0.1, 0.1, 0.7])
    result = select(*values)
    assert result["status"] == "development-selected"
    assert result["selected"]["coverage"] == 1
    assert result["selected"]["thresholds"]["I"] == 0.5
    assert result["selected"]["thresholds"]["E"] in GRID
    assert result["gate_eligible"] is False
    assert result["confirmation_required"] is True


def test_high_confidence_irrelevant_to_exact_errors_force_exact_off():
    values = development()
    for prediction in values[2]:
        set_scores(prediction, [1.0, 0.0, 0.0, 0.0])
    result = select(*values)
    assert result["status"] == "no-feasible-development-policy"
    assert result["selected"] is None


def test_zero_event_bootstrap_needs_independent_query_evidence():
    values = development(200)
    result = select(*values)
    # 200 zero-incident queries still leave >1% one-sided incident uncertainty.
    assert result["status"] == "no-feasible-development-policy"


def test_repeated_products_do_not_manufacture_independent_queries():
    values = development(200)
    # Accepted-pair requirement is already met: 400 exact pairs, but 200 queries.
    assert len(values[2]) == 600
    assert select(*values)["selected"] is None


def test_confirmation_cannot_be_used_for_threshold_selection():
    values = development()
    values[3]["selection_role"] = "confirmation"
    with pytest.raises(ValueError, match="development"):
        select(*values)
    values = development()
    values[3]["confirmation_query_keys"] = [values[3]["query_keys"][0]]
    with pytest.raises(ValueError, match="non-overlapping"):
        select(*values)


def test_original_probability_and_provenance_contract_still_applies():
    values = development()
    values[2][0]["probabilities"] = [float("nan"), 0, 0, 0]
    with pytest.raises(ValueError, match="probabilities"):
        select(*values)
    values = development()
    values[2][0]["provenance"]["release_sha256"] = "wrong"
    with pytest.raises(ValueError, match="release"):
        select(*values)


def test_ties_and_selection_are_deterministic():
    values = development()
    first = select(*values)
    assert first == select(*values)
    assert first["selected"]["thresholds"]["E"] == 0.7


def test_empty_exact_acceptance_can_select_other_classes_without_fake_exact_quality():
    values = development()
    for reference, prediction in zip(values[1], values[2], strict=True):
        reference["label"] = "I"
        set_scores(prediction, [0.1, 0.1, 0.1, 0.7])
    result = select(*values)
    assert result["selected"]["coverage"] == 1
    assert result["selected"]["exact_contamination_95_interval"] is None
    assert result["gate_eligible"] is False


def confirmation_evidence(query_count=400):
    from hashlib import sha256
    from label_quality import canonical

    dev = development()
    confirmation = fixture(query_count)
    confirmation[3]["selection_role"] = "confirmation"
    confirmation[3]["query_keys"] = []
    for pair, prediction in zip(confirmation[0], confirmation[2], strict=True):
        pair["request"]["query"] = "confirmation " + pair["query_id"]
        pair["query_key"] = query_key(pair["request"]["query"])
        actual = {
            name: pair[name]
            for name in ("query_id", "product_id", "request", "product")
        }
        prediction["input_sha256"] = sha256(canonical(actual)).hexdigest()
    confirmation[3]["query_keys"] = sorted(
        {pair["query_key"] for pair in confirmation[0]}
    )
    dev[3]["confirmation_query_keys"] = confirmation[3]["query_keys"]
    selection = select(*dev)
    confirmation[3]["selection_sha256"] = sha256(canonical(selection)).hexdigest()
    return confirmation, selection


def test_fixed_policy_confirms_only_published_without_gate_activation():
    from calibrate_labels import confirm

    values, selection = confirmation_evidence()
    result = confirm(*values, selection)
    assert result["status"] == "confirmed-on-published"
    assert result["selected"]["coverage"] == 2 / 3
    assert result["gate_eligible"] is False
    assert result["independent_gap_transfer_required"] is True
    assert result["selected"]["thresholds"] == selection["selected"]["thresholds"]


def test_changed_selection_bytes_model_or_membership_are_rejected():
    from copy import deepcopy
    from hashlib import sha256
    from calibrate_labels import confirm
    from label_quality import canonical

    values, selection = confirmation_evidence()
    changed = deepcopy(selection)
    changed["selected"]["thresholds"]["E"] = 0.8
    with pytest.raises(ValueError, match="bytes"):
        confirm(*values, changed)
    values[3]["model"] = {**values[3]["model"], "version": "5"}
    with pytest.raises(ValueError, match="model"):
        confirm(*values, selection)
    values, selection = confirmation_evidence()
    selection["confirmation_query_keys"] = [query_key("different reservation")]
    values[3]["selection_sha256"] = sha256(canonical(selection)).hexdigest()
    with pytest.raises(ValueError, match="membership"):
        confirm(*values, selection)


def test_development_overlap_and_no_feasible_selection_are_rejected():
    from hashlib import sha256
    from calibrate_labels import confirm
    from label_quality import canonical

    values, selection = confirmation_evidence()
    selection["development_query_keys"].append(values[3]["query_keys"][0])
    values[3]["selection_sha256"] = sha256(canonical(selection)).hexdigest()
    with pytest.raises(ValueError, match="exclude development"):
        confirm(*values, selection)
    selection["status"] = "no-feasible-development-policy"
    values[3]["selection_sha256"] = sha256(canonical(selection)).hexdigest()
    with pytest.raises(ValueError, match="successful"):
        confirm(*values, selection)


def test_confirmation_does_not_search_for_better_thresholds_after_errors():
    from calibrate_labels import confirm

    values, selection = confirmation_evidence()
    for reference in values[1]:
        reference["label"] = "I"
    result = confirm(*values, selection)
    assert result["status"] == "failed"
    assert result["selected"]["thresholds"] == selection["selected"]["thresholds"]
    assert result["selected"]["exact_contamination_rate"] == 1


def test_confirmation_with_too_few_independent_queries_is_inconclusive():
    from calibrate_labels import confirm

    values, selection = confirmation_evidence(200)
    result = confirm(*values, selection)
    assert result["status"] == "inconclusive"


def test_confirmation_confusion_uses_selected_policy_not_original_abstention():
    from hashlib import sha256
    from calibrate_labels import confirm
    from label_quality import canonical

    values, selection = confirmation_evidence()
    selection["selected"]["thresholds"]["I"] = 0.5
    values[3]["selection_sha256"] = sha256(canonical(selection)).hexdigest()
    for reference, prediction in zip(values[1], values[2], strict=True):
        if reference["label"] == "I":
            set_scores(prediction, [0.1, 0.1, 0.1, 0.7])
    result = confirm(*values, selection)
    assert result["selected"]["confusion"]["I"]["I"] == 400
    assert result["selected"]["confusion"]["I"]["abstain"] == 0
    assert result["selected"]["counts"]["I"] == 400
    assert result["selected"]["accepted_accuracy"] == 1
    assert result["selected"]["exact_to_irrelevant_errors"] == 0
    assert result["selected"]["exact_to_irrelevant_rate"] == 0
    for reference in values[1]:
        if reference["product_id"] == "c":
            reference["label"] = "E"
    result = confirm(*values, selection)
    assert result["selected"]["exact_to_irrelevant_errors"] == 400
    assert result["selected"]["exact_to_irrelevant_rate"] == 1 / 3
    assert result["selected"]["accepted_accuracy"] == 2 / 3
