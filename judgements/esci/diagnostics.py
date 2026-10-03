"""Describe paired probability differences with uncertainty grouped by query."""

import numpy as np


def summarise(reference, actual, queries, threshold=0.90, tolerance=1e-4,
              bootstrap_count=5000, seed=20261002):
    a, b = np.asarray(reference, dtype=float), np.asarray(actual, dtype=float)
    if a.shape != b.shape or a.ndim != 2 or a.shape[1] != 4 or not len(a):
        raise ValueError("Expected equally sized, non-empty ESCI probability matrices.")
    if len(queries) != len(a) or not np.isfinite([a, b]).all():
        raise ValueError("Each finite probability row requires a query identity.")
    if (a < 0).any() or (b < 0).any() or (a > 1).any() or (b > 1).any() or not (
        np.allclose(a.sum(axis=1), 1, atol=1e-5, rtol=0)
        and np.allclose(b.sum(axis=1), 1, atol=1e-5, rtol=0)
    ):
        raise ValueError("Rows must contain probabilities summing to one.")
    signed = b - a
    maximum = np.abs(signed).max(axis=1)
    first, second = a.argmax(axis=1), b.argmax(axis=1)
    accepted_a, accepted_b = a.max(axis=1) >= threshold, b.max(axis=1) >= threshold
    decisions_a = np.where(accepted_a, first, -1)
    decisions_b = np.where(accepted_b, second, -1)
    measurements = np.column_stack([
        maximum, maximum > tolerance, first != second,
        decisions_a != decisions_b, accepted_a != accepted_b, signed,
    ])
    names = ["mean_max_absolute_delta", "above_tolerance_rate", "winning_class_change_rate",
             "label_or_abstention_change_rate", "acceptance_change_rate",
             "mean_signed_E", "mean_signed_S", "mean_signed_C", "mean_signed_I"]
    unique, groups = np.unique(queries, return_inverse=True)
    counts = np.bincount(groups)
    sums = np.zeros((len(unique), measurements.shape[1]))
    np.add.at(sums, groups, measurements)
    rng = np.random.default_rng(seed)
    estimates = np.empty((bootstrap_count, measurements.shape[1]))
    # Resample whole queries, retaining all their pairs and the pair-weighted estimand.
    for start in range(0, bootstrap_count, 100):
        selected = rng.integers(len(unique), size=(min(100, bootstrap_count-start), len(unique)))
        estimates[start:start+len(selected)] = sums[selected].sum(axis=1) / counts[selected].sum(axis=1)[:, None]
    low, high = np.quantile(estimates, [0.025, 0.975], axis=0)
    values = measurements.mean(axis=0)
    transitions = {}
    labels = ["E", "S", "C", "I"]
    for old, new in zip(decisions_a, decisions_b, strict=True):
        key = (labels[old] if old >= 0 else "abstain") + "->" + (labels[new] if new >= 0 else "abstain")
        transitions[key] = transitions.get(key, 0) + 1
    confidence_bins = []
    confidence = a.max(axis=1)
    boundaries = [0, .85, .88, .90, .92, .95, 1.00000001]
    for lower, upper in zip(boundaries[:-1], boundaries[1:], strict=True):
        selected = (confidence >= lower) & (confidence < upper)
        confidence_bins.append({"lower_inclusive": lower, "upper": min(upper, 1),
                                "upper_inclusive": upper > 1,
                                "pairs": int(selected.sum()),
                                "changed_labels_or_abstentions": int(((decisions_a != decisions_b) & selected).sum())})
    return {
        "pairs": len(a), "queries": len(unique), "tolerance": tolerance,
        "max_absolute_delta": float(maximum.max()),
        "median_max_absolute_delta": float(np.median(maximum)),
        "p95_max_absolute_delta": float(np.quantile(maximum, .95)),
        "p99_max_absolute_delta": float(np.quantile(maximum, .99)),
        "above_tolerance_pairs": int((maximum > tolerance).sum()),
        "changed_winning_classes": int((first != second).sum()),
        "changed_labels_or_abstentions": int((decisions_a != decisions_b).sum()),
        "queries_with_changed_decisions": int(len(np.unique(np.asarray(queries)[decisions_a != decisions_b]))),
        "changed_acceptance": int((accepted_a != accepted_b).sum()),
        "reference_accepted": int(accepted_a.sum()), "actual_accepted": int(accepted_b.sum()),
        "decision_transitions": transitions,
        "changes_by_reference_confidence": confidence_bins,
        "metrics": {name: {"value": float(value), "query_bootstrap_95_interval": [float(lower), float(upper)]}
                    for name, value, lower, upper in zip(names, values, low, high, strict=True)},
        "uncertainty": {"method": "whole-query percentile bootstrap; pair-weighted statistics",
                        "replicates": bootstrap_count, "seed": seed,
                        "scope": "Conditional on this exposed cohort; not a population quality guarantee."},
    }
