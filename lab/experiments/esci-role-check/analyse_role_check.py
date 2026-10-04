"""Analyse supplied role-check records without loading data or running a model."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "esci-fitted-specialists"))
import fit_specialists as fitted  # noqa: E402

sys.path.insert(0, str(HERE.parents[2] / "evaluation"))
from label_quality import bootstrap, indexed  # noqa: E402

from role_check import route_decision, validate_prediction  # noqa: E402


def align(rows, records, *, exact=True, require_query_key=True):
    members, values = indexed(rows), indexed(records)
    if not members or not set(members) <= set(values):
        raise ValueError("Missing role-check pair membership")
    if exact and set(members) != set(values):
        raise ValueError("Different role-check pair membership")
    aligned = []
    for row in rows:
        query = fitted.group(row)
        if row.get("query_key") != query:
            raise ValueError("Input query identity differs")
        value = values[row["query_id"], row["product_id"]]
        if (require_query_key or "query_key" in value) and value.get(
            "query_key"
        ) != query:
            raise ValueError("Matched query identity differs")
        aligned.append(value)
    return aligned


def changes(queries, truth, labels, accepted, baseline, mask):
    """Use one matched query population and the stated stratum denominator."""
    correct = accepted & (labels == truth)
    baseline_correct = baseline & (truth == 0)
    result = {}
    for name, after, before in (
        ("additional_coverage", accepted, baseline),
        ("correct_additional_coverage", correct, baseline_correct),
    ):
        delta = (after.astype(int) - before.astype(int)) * mask
        denominator = int(mask.sum())
        result[name] = {
            "net_pairs": int(delta.sum()),
            "denominator": denominator,
            "estimate": float(delta.sum() / denominator) if denominator else None,
            "whole_query_bootstrap_interval_95": bootstrap(
                queries, delta, mask.astype(int), 20000, 20261003
            )
            if denominator
            else None,
        }
    return result


def summary(rows, truth, labels, accepted):
    result = fitted.statistics(rows, truth, labels, accepted)
    queries = np.array([fitted.group(row) for row in rows])
    result["gold_support"] = {
        label: {
            "pairs": int((truth == i).sum()),
            "query_groups": len(set(queries[truth == i])),
        }
        for i, label in enumerate(fitted.LABELS)
    }
    result["additional_errors"] = int((accepted & (labels != truth)).sum())
    result["Exact_to_non_Exact_errors"] = {
        label: {
            "errors": int((accepted & (truth == 0) & (labels == i)).sum()),
            "gold_Exact_pairs": int((truth == 0).sum()),
            "gold_Exact_query_groups": len(set(queries[truth == 0])),
        }
        for i, label in enumerate(fitted.LABELS)
        if i
    }
    return result


def analyse(rows, references, prefix, baseline_a, predictions):
    """Assess only the 128 supplied residual pairs; registration stays external."""
    if len(rows) != 128:
        raise ValueError("The frozen proposal requires 128 pairs")
    references = align(rows, references, require_query_key=False)
    prior = align(rows, prefix, exact=False)
    baseline_a = align(rows, baseline_a, exact=False)
    predictions = align(rows, predictions)
    if any(value.get("label") not in fitted.LABELS for value in references):
        raise ValueError("Invalid reference label")
    for value in prior:
        if (
            type(value.get("prefix_accepted")) is not bool
            or type(value.get("exact_095_accepted")) is not bool
            or value.get("gate_eligible") is not False
            or value.get("prediction") not in fitted.LABELS
            or value["prefix_accepted"]
            or value["exact_095_accepted"]
        ):
            raise ValueError("The supplied packet must contain only frozen prefix gaps")
    for value in baseline_a:
        if value.get("gate_eligible") is not False or (
            value.get("outcome"),
            value.get("label"),
        ) not in (("labelled", "E"), ("abstain", None)):
            raise ValueError("Frozen A must supply Exact decisions or abstentions")
    baseline = np.array([value["outcome"] == "labelled" for value in baseline_a])
    if int(baseline.sum()) != 80:
        raise ValueError("The frozen proposal requires 80 A additions and 48 A gaps")
    decisions = []
    for prediction, a_exact in zip(predictions, baseline, strict=True):
        prediction = validate_prediction(prediction)
        decisions.append(
            route_decision(
                prediction["role_probabilities"],
                prediction["non_exact_probabilities"],
                a_additional_exact=bool(a_exact),
            )
        )
    labels = np.array(
        [
            fitted.LABELS.index(value["label"]) if value["label"] is not None else 0
            for value in decisions
        ]
    )
    full = np.array([value["outcome"] == "labelled" for value in decisions])
    veto = np.array([value["deciding_route"] == "exact_veto" for value in decisions])
    non_exact = np.array(
        [value["deciding_route"] == "non_exact" for value in decisions]
    )
    truth = np.array([fitted.LABELS.index(value["label"]) for value in references])
    queries = np.array([fitted.group(row) for row in rows])
    masks = {
        "all": np.ones(128, dtype=bool),
        "A_accepted_80": baseline,
        "A_abstained_48": ~baseline,
    }
    candidates = {
        "baseline_A": (np.zeros(128, dtype=int), baseline),
        "veto_only": (np.zeros(128, dtype=int), veto),
        "full_route": (labels, full),
    }
    strata = {}
    for name, mask in masks.items():
        chosen = [row for row, include in zip(rows, mask, strict=True) if include]
        strata[name] = {
            "statistics": {
                candidate: summary(chosen, truth[mask], predicted[mask], accepted[mask])
                for candidate, (predicted, accepted) in candidates.items()
            },
            "paired_changes_vs_A": {
                candidate: changes(queries, truth, predicted, accepted, baseline, mask)
                for candidate, (predicted, accepted) in candidates.items()
                if candidate != "baseline_A"
            },
        }
    base_correct = baseline & (truth == 0)
    base_harm = baseline & (truth == 3)
    retained_correct = int((veto & base_correct).sum())
    removed_harm = int((base_harm & ~veto).sum())
    supported_veto = int(base_correct.sum()) == 66 and int(base_harm.sum()) == 4
    new = ~baseline & non_exact
    new_count, new_correct = int(new.sum()), int((new & (labels == truth)).sum())
    exact_to_irrelevant = int((non_exact & (truth == 0) & (labels == 3)).sum())
    return {
        "kind": "esci-role-check-development-analysis-v1",
        "gate_eligible": False,
        "qualification": False,
        "pairs": 128,
        "query_groups": len(set(queries)),
        "prefix_accepted_pairs_in_packet": 0,
        "residual_only_analysis": True,
        "strata": strata,
        "A_accepted_changes": {
            "correct_Exact_lost_to_veto": int((base_correct & ~veto).sum()),
            "correct_Exact_retained": retained_correct,
            "non_Exact_replacements": int((baseline & non_exact).sum()),
            "correct_non_Exact_corrections": int(
                (baseline & non_exact & (labels == truth)).sum()
            ),
            "incorrect_non_Exact_replacements": int(
                (baseline & non_exact & (labels != truth)).sum()
            ),
        },
        "selection": {
            "Exact_veto": {
                "supported": supported_veto,
                "baseline_correct_Exact": int(base_correct.sum()),
                "baseline_I_to_E": int(base_harm.sum()),
                "I_to_E_removed": removed_harm,
                "correct_Exact_retained": retained_correct,
                "advance": removed_harm >= 2 and retained_correct >= 53
                if supported_veto
                else None,
            },
            "non_Exact": {
                "accuracy_supported": bool(new_count),
                "new_pairs_in_48": new_count,
                "correct_new_pairs": new_correct,
                "point_accuracy": new_correct / new_count if new_count else None,
                "E_to_I_errors_full_route": exact_to_irrelevant,
                "E_to_I_gold_Exact_pairs": int((truth == 0).sum()),
                "E_to_I_gold_Exact_query_groups": len(set(queries[truth == 0])),
                "E_to_I_supported": bool((truth == 0).any()),
                "rare_error_protection_established": False,
                "advance": new_count >= 10
                and new_correct / new_count >= 0.95
                and not exact_to_irrelevant
                if new_count
                else None,
            },
        },
        "SCI_route_I_to_E_absence": {
            "structural_assertion": not bool((non_exact & (labels == 0)).any()),
            "quality_pass": False,
        },
        "uncertainty": {
            "statistics_repetitions": 2000,
            "statistics_seed": 20261004,
            "paired_repetitions": 20000,
            "paired_seed": 20261003,
            "unit": "whole_normalised_query",
            "paired_denominators": "128, 80 or 48 selected pairs; original matched query draws",
        },
        "limits": [
            "Selected exposed development evidence; no full-pool coverage estimate or independent confirmation.",
            "Prefix decisions are outside this residual-only analysis and cannot be overwritten.",
            "Source hashes, exact frozen membership, reference provenance and execution receipts require separate registration checks.",
            "Empty class denominators remain null; zero-error intervals do not establish rare-error protection.",
        ],
    }
