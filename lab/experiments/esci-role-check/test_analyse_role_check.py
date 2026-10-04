"""Synthetic whole-query checks of the frozen 128-pair role survey analysis."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import analyse_role_check as analysis  # noqa: E402


@pytest.fixture
def sample():
    rows, references, prefix, baseline, predictions = [], [], [], [], []
    truth = "E" * 66 + "S" * 7 + "C" * 3 + "I" * 4 + "S" * 14 + "C" + "I" * 9 + "E" * 24
    for i, label in enumerate(truth):
        row = {
            "query_id": str(i % 108),
            "product_id": f"p{i}",
            "request": {"query": f"Synthetic request {i % 108}"},
        }
        row["query_key"] = analysis.fitted.group(row)
        identity = {key: row[key] for key in ("query_id", "product_id", "query_key")}
        rows.append(row)
        references.append(identity | {"label": label})
        prefix.append(
            identity
            | {
                "prediction": "E",
                "prefix_accepted": False,
                "exact_095_accepted": False,
                "gate_eligible": False,
            }
        )
        baseline.append(
            identity
            | {
                "outcome": "labelled" if i < 80 else "abstain",
                "label": "E" if i < 80 else None,
                "gate_eligible": False,
            }
        )
        predictions.append(
            identity
            | {
                "role_probabilities": [0.95, 0.03, 0.02]
                if i < 80
                else [0.03, 0.02, 0.95],
                "non_exact_probabilities": [0.01, 0.01, 0.01, 0.97],
                "gate_eligible": False,
            }
        )
    return rows, references, prefix, baseline, predictions


def non_exact(predictions, index, label):
    predictions[index]["role_probabilities"] = [0.03, 0.95, 0.02]
    scores = [0.01] * 4
    scores["SCI".index(label)] = 0.97
    predictions[index]["non_exact_probabilities"] = scores


def test_supported_selection_separates_corrections_from_new_coverage(sample):
    rows, refs, prefix, baseline, predictions = sample
    for index in (76, 77):
        non_exact(predictions, index, "I")
    for index in range(80, 90):
        non_exact(predictions, index, "S")
    result = analysis.analyse(rows, refs, prefix, baseline, predictions)
    assert result["pairs"] == 128 and result["query_groups"] == 108
    assert result["prefix_accepted_pairs_in_packet"] == 0
    assert result["residual_only_analysis"] is True
    assert "prefix_decisions_preserved" not in result
    assert (
        result["strata"]["A_accepted_80"]["statistics"]["full_route"]["accepted"] == 80
    )
    assert (
        result["strata"]["A_abstained_48"]["statistics"]["full_route"]["accepted"] == 10
    )
    assert result["A_accepted_changes"]["correct_non_Exact_corrections"] == 2
    assert result["A_accepted_changes"]["correct_Exact_lost_to_veto"] == 0
    assert result["selection"]["Exact_veto"]["advance"] is True
    assert result["selection"]["non_Exact"]["advance"] is True
    assert result["selection"]["non_Exact"]["E_to_I_gold_Exact_pairs"] == 90
    assert result["selection"]["non_Exact"]["E_to_I_gold_Exact_query_groups"] == 70
    assert result["selection"]["non_Exact"]["E_to_I_supported"] is True
    assert (
        result["selection"]["non_Exact"]["rare_error_protection_established"] is False
    )
    change = result["strata"]["all"]["paired_changes_vs_A"]["full_route"]
    assert change["additional_coverage"]["net_pairs"] == 10
    assert change["additional_coverage"]["denominator"] == 128
    assert change["correct_additional_coverage"]["net_pairs"] == 12
    assert result["gate_eligible"] is False and result["qualification"] is False
    encoded = json.dumps(result, allow_nan=False)
    assert "product_id" not in encoded and "Synthetic request" not in encoded


def test_corrections_in_80_cannot_pass_new_label_quota(sample):
    for index in range(66, 80):
        non_exact(sample[4], index, sample[1][index]["label"])
    result = analysis.analyse(*sample)
    assert result["A_accepted_changes"]["correct_non_Exact_corrections"] == 14
    assert result["selection"]["non_Exact"]["new_pairs_in_48"] == 0
    assert result["selection"]["non_Exact"]["advance"] is None
    assert (
        result["strata"]["all"]["paired_changes_vs_A"]["full_route"][
            "additional_coverage"
        ]["net_pairs"]
        == 0
    )


def test_meets_in_48_never_adds_exact_and_empty_support_stays_null(sample):
    for prediction in sample[4][80:]:
        prediction["role_probabilities"] = [0.95, 0.03, 0.02]
    result = analysis.analyse(*sample)
    new_stats = result["strata"]["A_abstained_48"]["statistics"]["full_route"]
    assert new_stats["accepted"] == 0
    assert new_stats["accuracy"]["estimate"] is None
    assert new_stats["accuracy"]["whole_query_bootstrap_interval_95"] is None
    assert new_stats["classes"]["E"]["estimate"] is None
    assert result["selection"]["non_Exact"]["point_accuracy"] is None
    assert result["selection"]["non_Exact"]["advance"] is None
    assert result["SCI_route_I_to_E_absence"] == {
        "structural_assertion": True,
        "quality_pass": False,
    }
    assert (
        result["strata"]["all"]["statistics"]["full_route"]["risks"][
            "irrelevant_to_exact"
        ]["numerator"]
        == 4
    )


def test_veto_selection_is_unsupported_without_frozen_reference_support(sample):
    sample[1][76]["label"] = "E"
    result = analysis.analyse(*sample)
    selection = result["selection"]["Exact_veto"]
    assert (
        selection["baseline_correct_Exact"] == 67 and selection["baseline_I_to_E"] == 3
    )
    assert selection["supported"] is False and selection["advance"] is None


def test_reference_query_keys_are_optional_but_must_match_when_present(sample):
    for reference in sample[1]:
        reference.pop("query_key")
    result = analysis.analyse(*sample)
    assert result["selection"]["Exact_veto"]["supported"] is True
    sample[1][0]["query_key"] = "changed"
    with pytest.raises(ValueError, match="query identity"):
        analysis.analyse(*sample)


def test_zero_exact_risk_denominator_is_explicit_and_never_qualifies(sample):
    for reference in sample[1]:
        if reference["label"] == "E":
            reference["label"] = "S"
    for index in range(80, 90):
        non_exact(sample[4], index, "S")
    result = analysis.analyse(*sample)
    selection = result["selection"]["non_Exact"]
    assert selection["accuracy_supported"] is True
    assert selection["point_accuracy"] == 1.0
    assert selection["E_to_I_errors_full_route"] == 0
    assert selection["E_to_I_gold_Exact_pairs"] == 0
    assert selection["E_to_I_gold_Exact_query_groups"] == 0
    assert selection["E_to_I_supported"] is False
    assert selection["rare_error_protection_established"] is False
    assert selection["advance"] is True
    assert result["qualification"] is False and result["gate_eligible"] is False


@pytest.mark.parametrize("retained, advance", [(53, True), (52, False)])
def test_veto_retention_uses_the_frozen_integer_boundary(sample, retained, advance):
    for index in (76, 77):
        non_exact(sample[4], index, "I")
    for index in range(66 - retained):
        sample[4][index]["role_probabilities"] = [0.01, 0.01, 0.98]
    selection = analysis.analyse(*sample)["selection"]["Exact_veto"]
    assert selection["correct_Exact_retained"] == retained
    assert selection["advance"] is advance


def test_veto_retention_and_full_route_exact_to_irrelevant_are_selection_checks(sample):
    for index in (76, 77):
        non_exact(sample[4], index, "I")
    for index in range(80, 90):
        non_exact(sample[4], index, "S")
    for index in range(14):
        sample[4][index]["role_probabilities"] = [0.01, 0.01, 0.98]
    non_exact(sample[4], 14, "I")
    result = analysis.analyse(*sample)
    assert result["selection"]["Exact_veto"]["correct_Exact_retained"] == 51
    assert result["selection"]["Exact_veto"]["advance"] is False
    assert result["selection"]["non_Exact"]["point_accuracy"] == 1.0
    assert result["selection"]["non_Exact"]["E_to_I_errors_full_route"] == 1
    assert result["selection"]["non_Exact"]["advance"] is False


def test_query_clustered_contrasts_are_deterministic_and_row_order_independent(sample):
    non_exact(sample[4], 80, "S")
    result = analysis.analyse(*sample)
    reordered = analysis.analyse(*(list(reversed(records)) for records in sample))
    assert result == reordered
    contrast = result["strata"]["A_abstained_48"]["paired_changes_vs_A"]["full_route"][
        "additional_coverage"
    ]
    assert contrast["estimate"] == 1 / 48
    assert contrast["whole_query_bootstrap_interval_95"][0] == 0
    assert contrast["whole_query_bootstrap_interval_95"][1] > 1 / 48


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "query",
        "input_query",
        "stratum",
        "prefix",
        "gate",
        "probability",
        "reference",
    ],
)
def test_rejects_incomplete_or_different_evidence(sample, change):
    rows, refs, prefix, baseline, predictions = copy.deepcopy(sample)
    if change == "missing":
        predictions.pop()
    elif change == "duplicate":
        refs.append(refs[0])
    elif change == "query":
        predictions[0]["query_key"] = "changed"
    elif change == "input_query":
        rows[0]["query_key"] = "changed"
    elif change == "stratum":
        baseline[80].update(outcome="labelled", label="E")
    elif change == "prefix":
        prefix[0]["prefix_accepted"] = True
    elif change == "gate":
        predictions[0]["gate_eligible"] = True
    elif change == "probability":
        predictions[0]["role_probabilities"] = [0.95, 0.05]
    elif change == "reference":
        refs[0]["label"] = "unknown"
    with pytest.raises(ValueError):
        analysis.analyse(rows, refs, prefix, baseline, predictions)
