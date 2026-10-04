"""Synthetic checks of residual masks, matched differences and input rejection."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import analyse_increment as analysis  # noqa: E402


@pytest.fixture
def sample():
    rows = [
        {"query_id": str(i), "product_id": f"p{i}", "request": {"query": f"query {i}"}}
        for i in range(4)
    ]
    prefix = [
        row
        | {
            "prediction": "E",
            "prefix_accepted": i == 0,
            "exact_095_accepted": i == 0,
            "gate_eligible": False,
        }
        for i, row in enumerate(rows)
    ]
    references = [row | {"label": label} for row, label in zip(rows, "EICE")]
    candidates = {
        name: [
            row | {"outcome": "abstain", "label": None, "gate_eligible": False}
            for row in rows
        ]
        for name in analysis.VARIANTS
    }
    return rows, references, prefix, candidates


def select(candidates, name, index, label):
    candidates[name][index].update(outcome="labelled", label=label)


def test_prefix_decisions_cannot_be_overwritten_and_harm_uses_all_rows(sample):
    rows, refs, prefix, candidates = sample
    for name in candidates:
        select(candidates, name, 0, "I")  # Must not replace accepted prefix E.
        select(candidates, name, 1, "E")  # I -> E.
        select(candidates, name, 2, "E")  # C -> E.
    result = analysis.analyse(rows, refs, prefix, candidates)
    stats = result["variants"]["A"]
    assert result["prefix_accepted"] == 1 and result["residual_pairs"] == 3
    assert stats["accepted"] == 2 and stats["additional_errors"] == 2
    assert stats["risks"]["irrelevant_to_exact"]["numerator"] == 1
    assert stats["risks"]["irrelevant_to_exact"]["denominator"] == 1
    assert stats["risks"]["exact_to_irrelevant"]["denominator"] == 2
    assert stats["risks"]["exact_to_irrelevant"]["numerator"] == 0
    assert stats["complement_to_exact_errors"] == 1
    assert result["gate_eligible"] is False


def test_paired_contrasts_keep_sign_and_common_denominator(sample):
    rows, refs, prefix, candidates = sample
    select(candidates, "A", 1, "I")
    select(candidates, "A", 2, "E")
    select(candidates, "B", 2, "C")
    result = analysis.analyse(rows, refs, prefix, candidates)
    delta = result["contrasts"]["B-A"]
    assert delta["additional_coverage"]["net_pairs"] == -1
    assert delta["additional_coverage"]["estimate"] == -0.25
    assert delta["additional_coverage"]["denominator"] == 4
    assert delta["correct_additional_coverage"]["net_pairs"] == 0
    repeat = analysis.analyse(rows, refs, prefix, candidates)
    assert repeat["contrasts"] == result["contrasts"]


def test_no_additions_has_no_accuracy_or_risk_support(sample):
    result = analysis.analyse(*sample)
    stats = result["variants"]["A"]
    assert stats["accepted"] == 0
    assert stats["accuracy"]["estimate"] is None
    assert stats["accuracy"]["whole_query_bootstrap_interval_95"] is None
    assert stats["risks"]["exact_irrelevant_contamination"]["denominator"] == 0
    assert stats["risks"]["irrelevant_to_exact"]["usable_pair_risk_upper"] is None


@pytest.mark.parametrize(
    "change",
    ["duplicate", "missing", "query", "invalid_label", "prefix_subset", "eligible"],
)
def test_rejects_mismatched_or_unqualified_evidence(sample, change):
    rows, refs, prefix, candidates = copy.deepcopy(sample)
    if change == "duplicate":
        refs.append(refs[0])
    elif change == "missing":
        candidates["D"].pop()
    elif change == "query":
        prefix[0]["query_key"] = "wrong"
    elif change == "invalid_label":
        refs[0]["label"] = "unknown"
    elif change == "prefix_subset":
        prefix[0]["prefix_accepted"] = False
    elif change == "eligible":
        candidates["A"][0]["gate_eligible"] = True
    with pytest.raises(ValueError):
        analysis.analyse(rows, refs, prefix, candidates)
