"""Select development-only ESCI acceptance thresholds; never activate labels."""

import argparse
from hashlib import sha256
import itertools
import json
from pathlib import Path

import numpy as np

from label_quality import (
    LABELS,
    assess,
    canonical,
    checksum,
    indexed,
    bootstrap,
    read_json,
    read_rows,
)

GRID = (0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 0.975, 0.99, 0.995, 1.0, None)


def _interval(numerator, denominator):
    if np.any(denominator == 0):
        return None
    return np.quantile(numerator / denominator, [0.025, 0.975]).tolist()


def _zero_incidence(errors, eligible_queries):
    if errors or not eligible_queries:
        return None
    return 1 - 0.05 ** (1 / eligible_queries)


def select(inputs, references, predictions, manifest, audit, policy):
    """Search a predeclared grid on development data, keeping confirmation untouched."""
    if manifest.get("selection_role") != "development":
        raise ValueError(
            "Threshold selection requires an explicitly frozen development cohort."
        )
    confirmation = set(manifest.get("confirmation_query_keys", []))
    if not confirmation or confirmation & set(manifest["query_keys"]):
        raise ValueError(
            "A separate, non-overlapping confirmation reservation is required."
        )
    # Reuse the strict provenance, membership, score and original-policy checks.
    assessment = assess(inputs, references, predictions, manifest, audit, policy)
    if assessment["counts"].get("error", 0):
        raise ValueError("Incomplete inference cannot select acceptance thresholds.")
    pairs, gold, observed = indexed(inputs), indexed(references), indexed(predictions)
    keys = sorted(pairs)
    queries, groups = np.unique(
        [pairs[k]["query_key"] for k in keys], return_inverse=True
    )
    truth = np.array([gold[k]["label"] for k in keys])
    scores = np.array([observed[k]["probabilities"] for k in keys])
    winners, confidence = np.argmax(scores, axis=1), np.max(scores, axis=1)
    repetitions, seed = policy["bootstrap_repetitions"], policy["bootstrap_seed"]
    if repetitions < 100 or len(queries) < 2:
        raise ValueError(
            "At least two queries and 100 bootstrap repetitions are required."
        )
    rng = np.random.default_rng(seed)
    # Identical sampled query counts for every candidate make comparisons reproducible.
    weights = rng.multinomial(
        len(queries), np.full(len(queries), 1 / len(queries)), repetitions
    )
    irrelevant = truth == "I"
    irrelevant_sums = np.bincount(groups, weights=irrelevant, minlength=len(queries))
    irrelevant_sampled = weights @ irrelevant_sums
    n_irrelevant_queries = int((irrelevant_sums > 0).sum())
    options = []
    for class_id, label in enumerate(LABELS):
        class_options, seen = [], set()
        for threshold in GRID:
            accepted = (
                (winners == class_id) & (confidence >= threshold)
                if threshold is not None
                else np.zeros(len(keys), dtype=bool)
            )
            signature = accepted.tobytes()
            if signature in seen:
                continue
            seen.add(signature)
            correct = accepted & (truth == label)
            harmful = (
                accepted & irrelevant
                if label == "E"
                else np.zeros(len(keys), dtype=bool)
            )
            sums = np.column_stack(
                [
                    np.bincount(groups, weights=mask, minlength=len(queries))
                    for mask in (accepted, correct, harmful)
                ]
            )
            sampled = weights @ sums
            class_options.append(
                {
                    "threshold": threshold if accepted.any() else None,
                    "count": int(accepted.sum()),
                    "correct": int(correct.sum()),
                    "harmful": int(harmful.sum()),
                    "queries": sums[:, 0] > 0,
                    "sampled": sampled,
                }
            )
        options.append(class_options)
    combinations = list(itertools.product(*(range(len(values)) for values in options)))
    # Stable grid-order tie-break: the lowest threshold producing an identical set wins.
    combinations.sort(
        key=lambda combination: -sum(
            options[c][i]["count"] for c, i in enumerate(combination)
        )
    )
    tested, chosen = 0, None
    for combination in combinations:
        selected = [options[c][i] for c, i in enumerate(combination)]
        count = sum(o["count"] for o in selected)
        if count < policy["minimum_accepted_pairs"]:
            break
        accepted_queries = int(
            np.logical_or.reduce([o["queries"] for o in selected]).sum()
        )
        if accepted_queries < policy["minimum_confirmation_queries"]:
            continue
        tested += 1
        sampled = sum(o["sampled"] for o in selected)
        accuracy = _interval(sampled[:, 1], sampled[:, 0])
        exact = selected[0]
        harm = _interval(exact["sampled"][:, 2], irrelevant_sampled)
        contamination = (
            _interval(exact["sampled"][:, 2], exact["sampled"][:, 0])
            if exact["count"]
            else None
        )
        errors = count - sum(o["correct"] for o in selected)
        accuracy_guard = _zero_incidence(errors, accepted_queries)
        harm_guard = _zero_incidence(exact["harmful"], n_irrelevant_queries)
        contamination_guard = (
            _zero_incidence(exact["harmful"], int(exact["queries"].sum()))
            if exact["count"]
            else None
        )
        limit = policy["maximum_irrelevant_to_exact_rate"]
        passes = (
            accuracy is not None
            and accuracy[0] >= policy["minimum_accuracy_lower_bound"]
        )
        passes = passes and (
            accuracy_guard is None
            or accuracy_guard <= 1 - policy["minimum_accuracy_lower_bound"]
        )
        if exact["count"]:
            passes = (
                passes
                and n_irrelevant_queries >= policy["minimum_confirmation_queries"]
                and int(exact["queries"].sum())
                >= policy["minimum_confirmation_queries"]
            )
            passes = (
                passes
                and harm is not None
                and contamination is not None
                and harm[1] <= limit
                and contamination[1] <= limit
            )
            passes = (
                passes
                and (harm_guard is None or harm_guard <= limit)
                and (contamination_guard is None or contamination_guard <= limit)
            )
        if passes:
            chosen = {
                "thresholds": dict(
                    zip(LABELS, [o["threshold"] for o in selected], strict=True)
                ),
                "accepted": count,
                "accepted_queries": accepted_queries,
                "coverage": count / len(keys),
                "accuracy_95_interval": accuracy,
                "irrelevant_to_exact_95_interval": harm,
                "exact_contamination_95_interval": contamination,
                "irrelevant_to_exact_errors": exact["harmful"],
                "zero_error_query_incidence_95_upper": accuracy_guard,
                "zero_harm_query_incidence_95_upper": harm_guard,
                "zero_contamination_query_incidence_95_upper": contamination_guard,
            }
            break
    return {
        "kind": "esci-label-calibration-report",
        "schema_version": 1,
        "status": "development-selected"
        if chosen
        else "no-feasible-development-policy",
        "gate_eligible": False,
        "model": manifest["model"],
        "release_sha256": manifest["release_sha256"],
        "pairs": len(keys),
        "queries": len(queries),
        "development_query_keys": sorted(manifest["query_keys"]),
        "confirmation_query_keys": sorted(confirmation),
        "runtime_image": manifest["runtime_image"],
        "model_policy_sha256": manifest["model_policy_sha256"],
        "quality_policy_sha256": __import__("hashlib")
        .sha256(canonical(policy))
        .hexdigest(),
        "grid": list(GRID),
        "tested_combinations": tested,
        "selected": chosen,
        "confirmation_required": True,
        "limits": [
            "Grid search makes development confidence intervals optimistic; untouched confirmation is required.",
            "Zero-event guards bound independent query incident probability, not pair error probability. They prevent zero-width bootstrap intervals being treated as proof of zero risk.",
            "Published-label development evidence does not establish quality on unlabelled search gaps.",
            "Disabled Exact acceptance has no Exact contamination estimate and makes no claim about Exact accuracy.",
        ],
    }


def confirm(inputs, references, predictions, manifest, audit, policy, selection):
    """Assess one byte-frozen policy on its untouched, reserved published cohort."""
    if (
        manifest.get("selection_role") != "confirmation"
        or manifest.get("cohort") != "published"
    ):
        raise ValueError(
            "Fixed-policy confirmation requires a published confirmation cohort."
        )
    if manifest.get("selection_sha256") != sha256(canonical(selection)).hexdigest():
        raise ValueError("Selection bytes must be pinned before confirmation.")
    if (
        selection.get("kind") != "esci-label-calibration-report"
        or selection.get("schema_version") != 1
        or selection.get("status") != "development-selected"
        or selection.get("gate_eligible") is not False
        or not isinstance(selection.get("selected"), dict)
    ):
        raise ValueError("A successful development-only selection is required.")
    thresholds = selection["selected"].get("thresholds", {})
    if set(thresholds) != set(LABELS) or any(
        isinstance(v, bool) or v not in GRID for v in thresholds.values()
    ):
        raise ValueError(
            "Fixed thresholds must use exactly the predeclared class grid."
        )
    for name in ("model", "release_sha256", "runtime_image", "model_policy_sha256"):
        if selection.get(name) != manifest.get(name):
            raise ValueError(
                "Confirmation model, release, runtime or model policy differs."
            )
    if selection.get("quality_policy_sha256") != sha256(canonical(policy)).hexdigest():
        raise ValueError(
            "Confirmation quality criteria differ from development selection."
        )
    declared = set(selection.get("confirmation_query_keys", []))
    development = set(selection.get("development_query_keys", []))
    if (
        not development
        or not declared
        or declared != set(manifest["query_keys"])
        or declared & development
    ):
        raise ValueError(
            "Confirmation membership must match its reservation and exclude development queries."
        )
    original = assess(inputs, references, predictions, manifest, audit, policy)
    pairs, gold, observed = indexed(inputs), indexed(references), indexed(predictions)
    keys = sorted(pairs)
    queries = [pairs[k]["query_key"] for k in keys]
    truth = np.array([gold[k]["label"] for k in keys])
    emitted = []
    for key in keys:
        record = observed[key]
        if record["outcome"] == "error":
            emitted.append("error")
            continue
        scores = record["probabilities"]
        winner = LABELS[int(np.argmax(scores))]
        threshold = thresholds[winner]
        emitted.append(
            winner if threshold is not None and max(scores) >= threshold else "abstain"
        )
    emitted = np.array(emitted)
    accepted = np.isin(emitted, LABELS)
    correct = accepted & (truth == emitted)
    exact, irrelevant = emitted == "E", truth == "I"
    harmful = exact & irrelevant
    count, exact_count = int(accepted.sum()), int(exact.sum())
    accepted_queries = len({q for q, yes in zip(queries, accepted, strict=True) if yes})
    exact_queries = len({q for q, yes in zip(queries, exact, strict=True) if yes})
    irrelevant_queries = len(
        {q for q, yes in zip(queries, irrelevant, strict=True) if yes}
    )
    repetitions, seed = policy["bootstrap_repetitions"], policy["bootstrap_seed"]
    accuracy = bootstrap(queries, correct, accepted, repetitions, seed)
    harm = bootstrap(queries, harmful, irrelevant, repetitions, seed)
    contamination = (
        bootstrap(queries, harmful, exact, repetitions, seed) if exact_count else None
    )
    accuracy_guard = _zero_incidence(count - int(correct.sum()), accepted_queries)
    harm_guard = _zero_incidence(int(harmful.sum()), irrelevant_queries)
    contamination_guard = (
        _zero_incidence(int(harmful.sum()), exact_queries) if exact_count else None
    )
    limit = policy["maximum_irrelevant_to_exact_rate"]
    enough = (
        accepted_queries >= policy["minimum_confirmation_queries"]
        and count >= policy["minimum_accepted_pairs"]
        and accuracy is not None
        and not original["counts"].get("error", 0)
    )
    if exact_count:
        enough = (
            enough
            and exact_queries >= policy["minimum_confirmation_queries"]
            and irrelevant_queries >= policy["minimum_confirmation_queries"]
            and harm is not None
            and contamination is not None
        )
        enough = (
            enough
            and (harm_guard is None or harm_guard <= limit)
            and (contamination_guard is None or contamination_guard <= limit)
        )
    passes = (
        enough
        and accuracy[0] >= policy["minimum_accuracy_lower_bound"]
        and (
            accuracy_guard is None
            or accuracy_guard <= 1 - policy["minimum_accuracy_lower_bound"]
        )
    )
    if exact_count and enough:
        passes = passes and harm[1] <= limit and contamination[1] <= limit
    metrics = {
        "thresholds": thresholds,
        "accepted": count,
        "accepted_queries": accepted_queries,
        "coverage": count / len(keys),
        "accepted_accuracy": int(correct.sum()) / count if count else None,
        "counts": {
            label: int((emitted == label).sum())
            for label in (*LABELS, "abstain", "error")
        },
        "confusion": {
            gold_label: {
                label: int(((truth == gold_label) & (emitted == label)).sum())
                for label in (*LABELS, "abstain", "error")
            }
            for gold_label in LABELS
        },
        "exact_to_irrelevant_errors": int(((truth == "E") & (emitted == "I")).sum()),
        "exact_to_irrelevant_rate": int(((truth == "E") & (emitted == "I")).sum())
        / int((truth == "E").sum())
        if (truth == "E").any()
        else None,
        "reference_exact_pairs": int((truth == "E").sum()),
        "accuracy_95_interval": accuracy,
        "irrelevant_pairs": int(irrelevant.sum()),
        "irrelevant_to_exact_rate": int(harmful.sum()) / int(irrelevant.sum())
        if irrelevant.any()
        else None,
        "irrelevant_to_exact_95_interval": harm,
        "exact_pairs": exact_count,
        "exact_contamination_rate": int(harmful.sum()) / exact_count
        if exact_count
        else None,
        "exact_contamination_95_interval": contamination,
        "irrelevant_to_exact_errors": int(harmful.sum()),
        "zero_error_query_incidence_95_upper": accuracy_guard,
        "zero_harm_query_incidence_95_upper": harm_guard,
        "zero_contamination_query_incidence_95_upper": contamination_guard,
    }
    return {
        "kind": "esci-label-calibration-confirmation",
        "schema_version": 1,
        "status": "confirmed-on-published"
        if passes
        else "failed"
        if enough
        else "inconclusive",
        "gate_eligible": False,
        "model": manifest["model"],
        "release_sha256": manifest["release_sha256"],
        "selection_sha256": manifest["selection_sha256"],
        "pairs": len(keys),
        "queries": len(declared),
        "selected": metrics,
        "independent_gap_transfer_required": True,
        "limits": selection["limits"][1:],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "inputs",
        "references",
        "predictions",
        "manifest",
        "audit",
        "policy",
        "reservation",
        "output",
    ):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--confirmation-selection", type=Path)
    args = parser.parse_args()
    manifest = read_json(args.manifest)
    for name in ("inputs", "references", "audit", "policy", "reservation"):
        if checksum(getattr(args, name)) != manifest[name + "_sha256"]:
            raise ValueError(
                "Frozen " + name + " bytes differ from the development manifest."
            )
    evidence = (
        read_rows(args.inputs),
        read_rows(args.references),
        read_rows(args.predictions),
        manifest,
        read_json(args.audit),
        read_json(args.policy),
    )
    if args.confirmation_selection:
        if checksum(args.confirmation_selection) != manifest.get("selection_sha256"):
            raise ValueError(
                "Selection file differs from the frozen confirmation hash."
            )
        result = confirm(*evidence, read_json(args.confirmation_selection))
    else:
        result = select(*evidence)
    result["hashes"] = {
        name: checksum(getattr(args, name))
        for name in (
            "inputs",
            "references",
            "predictions",
            "manifest",
            "audit",
            "policy",
            "reservation",
        )
    }
    if args.confirmation_selection:
        result["hashes"]["selection"] = checksum(args.confirmation_selection)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as output:
        output.write(canonical(result))
    print(json.dumps({"status": result["status"], "selected": result["selected"]}))


if __name__ == "__main__":
    main()
