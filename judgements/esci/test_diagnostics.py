"""Probability diagnostics distinguish drift, repeatability and decision changes."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from esci.diagnostics import summarise


def test_identical_runs_have_no_drift_or_decision_changes():
    rows = [[.92, .03, .03, .02], [.6, .2, .1, .1]]
    result = summarise(rows, rows, ["q1", "q2"], bootstrap_count=200)
    assert result["changed_labels_or_abstentions"] == 0
    assert result["queries_with_changed_decisions"] == 0
    assert result["max_absolute_delta"] == 0
    assert result["metrics"]["mean_signed_E"]["query_bootstrap_95_interval"] == [0, 0]


def test_systematic_shift_can_change_acceptance_without_changing_winner():
    before = [[.91, .03, .03, .03]] * 6
    after = [[.89, .05, .03, .03]] * 6
    result = summarise(before, after, ["q1"]*3 + ["q2"]*3, bootstrap_count=200)
    assert result["queries"] == 2
    assert result["above_tolerance_pairs"] == 6
    assert result["changed_winning_classes"] == 0
    assert result["changed_acceptance"] == 6
    assert result["queries_with_changed_decisions"] == 2
    assert result["metrics"]["mean_signed_E"]["query_bootstrap_95_interval"][1] < 0


def test_more_correlated_pairs_do_not_artificially_narrow_query_uncertainty():
    before = [[.91, .03, .03, .03]] * 4
    after = [[.89, .05, .03, .03]] * 3 + [before[0]]
    first = summarise(before, after, ["q1"]*3+["q2"], bootstrap_count=1000)
    repeated = summarise(before*20, after*20, (["q1"]*3+["q2"])*20, bootstrap_count=1000)
    metric = "mean_max_absolute_delta"
    assert first["metrics"][metric]["value"] == pytest.approx(.015)
    assert first["metrics"][metric]["query_bootstrap_95_interval"] == pytest.approx([0, .02])
    assert repeated["metrics"][metric]["query_bootstrap_95_interval"] == pytest.approx(
        first["metrics"][metric]["query_bootstrap_95_interval"])


def test_invalid_probabilities_are_rejected_before_reporting():
    with pytest.raises(ValueError, match="summing to one"):
        summarise([[.9, .1, .1, .1]], [[.9, .1, 0, 0]], ["q1"])
