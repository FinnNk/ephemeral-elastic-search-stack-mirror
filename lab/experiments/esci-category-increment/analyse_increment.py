"""Measure exploratory category labels added after a frozen development prefix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "esci-fitted-specialists"))
import fit_specialists as fitted  # noqa: E402

sys.path.insert(0, str(HERE.parents[2] / "evaluation"))
from label_quality import bootstrap, checksum, indexed, read_json, read_rows  # noqa: E402

VARIANTS = ("A", "B", "C", "D")
CONTRASTS = (("B", "A"), ("C", "B"), ("D", "C"))
PREFIX_SHA = "cbebf1e00dc51437786013c8b9e6880b7400a12789e3480cb368e59592227018"
REGISTRATION_SHA = "1ee0da2cfd78e71cf72c7522b43814b42b17a8995df6d8f58f7724fa263a2acd"
ANALYSIS_SHA = "a6728540121970901376af023d820e9e73f1b819b138445884e86d20f837b5f0"
DEPENDENCIES = (
    HERE / "analyse_increment.py",
    HERE.parent / "esci-fitted-specialists" / "fit_specialists.py",
    HERE.parent / "esci-gap-surveys" / "specialist_survey.py",
    HERE.parents[2] / "evaluation" / "label_quality.py",
)
OWNER_DEPENDENCIES = (
    "operations/category_metrics.py",
    "operations/category_input_experiment.py",
    "operations/category_numerical_checks.py",
)


def write_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )


def align(rows, other, exact=True):
    if not rows:
        raise ValueError("A non-empty matched survey is required")
    members, values = indexed(rows), indexed(other)
    if (exact and set(members) != set(values)) or not set(members) <= set(values):
        raise ValueError("Pair membership differs")
    aligned = []
    for row in rows:
        value = values[(row["query_id"], row["product_id"])]
        if value.get("query_key", fitted.group(row)) != fitted.group(row):
            raise ValueError("Query identity differs")
        aligned.append(value)
    return aligned


def prefix_mask(rows, prefix):
    aligned = align(rows, prefix, exact=False)
    for value in aligned:
        if (
            type(value.get("prefix_accepted")) is not bool
            or type(value.get("exact_095_accepted")) is not bool
            or value.get("gate_eligible") is not False
            or value.get("prediction") not in fitted.LABELS
            or (value["exact_095_accepted"] and not value["prefix_accepted"])
        ):
            raise ValueError("Invalid frozen prefix decision")
    return np.array([value["prefix_accepted"] for value in aligned])


def analyse(rows, references, prefix, candidates):
    if set(candidates) != set(VARIANTS):
        raise ValueError("Four matched variants are required")
    references = align(rows, references)
    if any(value.get("label") not in fitted.LABELS for value in references):
        raise ValueError("Invalid reference label")
    truth = np.array([fitted.LABELS.index(value["label"]) for value in references])
    prior = prefix_mask(rows, prefix)
    queries = np.array([fitted.group(row) for row in rows])
    extras, correct, variants = {}, {}, {}
    for name in VARIANTS:
        predictions = align(rows, candidates[name])
        for value in predictions:
            if (
                value.get("gate_eligible") is not False
                or value.get("outcome") not in ("labelled", "abstain")
                or (
                    value["outcome"] == "labelled"
                    and value.get("label") not in fitted.LABELS
                )
                or (value["outcome"] == "abstain" and value.get("label") is not None)
            ):
                raise ValueError("Invalid experimental candidate decision")
        labels = np.array(
            [
                fitted.LABELS.index(value["label"]) if value["label"] else 0
                for value in predictions
            ]
        )
        extras[name] = ~prior & np.array(
            [value["outcome"] == "labelled" for value in predictions]
        )
        correct[name] = extras[name] & (labels == truth)
        stats = fitted.statistics(rows, truth, labels, extras[name])
        stats["complement_to_exact_errors"] = stats[
            "confusion_true_rows_prediction_columns_ESCI"
        ][2][0]
        stats["additional_errors"] = int((extras[name] & (labels != truth)).sum())
        variants[name] = stats
    contrasts = {}
    for left, right in CONTRASTS:
        contrasts[f"{left}-{right}"] = {}
        for metric, values in (
            ("additional_coverage", extras),
            ("correct_additional_coverage", correct),
        ):
            delta = values[left].astype(int) - values[right].astype(int)
            contrasts[f"{left}-{right}"][metric] = {
                "net_pairs": int(delta.sum()),
                "denominator": len(rows),
                "estimate": float(delta.mean()),
                "whole_query_bootstrap_interval_95": bootstrap(
                    queries, delta, np.ones(len(rows)), 20000, 20261003
                ),
            }
    return {
        "kind": "esci-category-increment-development-result-v1",
        "gate_eligible": False,
        "pairs": len(rows),
        "queries": len(set(queries)),
        "prefix_accepted": int(prior.sum()),
        "residual_pairs": int((~prior).sum()),
        "residual_queries": len(set(queries[~prior])),
        "variants": variants,
        "contrasts": contrasts,
        "limits": [
            "Published references and the partly fitted prefix are exposed development evidence.",
            "All coverage and gold-class risk denominators use the complete matched survey.",
            "Zero-event bootstrap intervals do not establish rare-error protection.",
            "These results neither qualify predictions nor change the gate.",
        ],
    }


def freeze(packet, prefix, owner, output):
    if (
        checksum(prefix) != PREFIX_SHA
        or checksum(packet / "study/registration.json") != REGISTRATION_SHA
        or checksum(packet / "analysis/protocol.json") != ANALYSIS_SHA
    ):
        raise ValueError("The retained quick survey or prefix changed")
    inputs = packet / "development/inputs.jsonl"
    rows = read_rows(inputs)
    mask = prefix_mask(rows, read_rows(prefix))
    if len(rows) != 512 or len({fitted.group(row) for row in rows}) != 295:
        raise ValueError("The registered quick survey membership differs")
    plan = {
        "kind": "esci-category-increment-development-protocol-v1",
        "gate_eligible": False,
        "packet": str(packet.resolve()),
        "prefix": str(prefix.resolve()),
        "owner": str(owner.resolve()),
        "files_sha256": {
            str(path.resolve()): checksum(path)
            for path in (
                *DEPENDENCIES,
                *(owner / name for name in OWNER_DEPENDENCIES),
                inputs,
                prefix,
                packet / "study/registration.json",
                packet / "analysis/protocol.json",
            )
        },
        "pairs": len(rows),
        "queries": 295,
        "prefix_accepted": int(mask.sum()),
        "residual_pairs": int((~mask).sum()),
        "candidate_threshold": 0.90,
        "mapping": "Use saved mapped probabilities and decisions without recalibration.",
        "statistics": {"repetitions": 2000, "seed": 20261004},
        "paired_contrasts": {
            "names": [f"{a}-{b}" for a, b in CONTRASTS],
            "repetitions": 20000,
            "seed": 20261003,
            "denominator": "all 512 pairs",
        },
        "reference_labels_read": False,
        "prediction_outputs_read": False,
        "host_prerequisite": "Verify completed exclusive grant, per-job host completion, numerical repeats and cleanup before run; retain that evidence with the result.",
    }
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "protocol.json", plan)
    return {
        "protocol_sha256": checksum(output / "protocol.json"),
        "prefix_accepted": int(mask.sum()),
        "residual_pairs": int((~mask).sum()),
    }


def run(protocol, runs_root, output):
    plan = read_json(protocol)
    if (
        plan.get("kind") != "esci-category-increment-development-protocol-v1"
        or plan.get("gate_eligible") is not False
    ):
        raise ValueError("A frozen exploratory protocol is required")
    for path, expected in plan["files_sha256"].items():
        if checksum(path) != expected:
            raise ValueError("Frozen analysis dependency or input changed")
    packet = Path(plan["packet"])
    sys.path.insert(0, plan["owner"])
    from operations.category_metrics import check_completed_runs

    # Existing owner checks validate all four contracts and numerical receipts
    # before any exposed development reference contents are opened here.
    original, bound, candidates, _ = check_completed_runs(
        packet / "study",
        packet / "analysis",
        runs_root / "development",
        runs_root / "comparisons",
    )
    manifest = packet / "development/manifest.json"
    refs = packet / "development/references.jsonl"
    if (
        checksum(manifest) != original["development_manifest_sha256"]
        or checksum(refs) != original["references_sha256"]
    ):
        raise ValueError("Frozen development references changed")
    scope = read_json(manifest)
    if (
        scope.get("cohort") != "published"
        or scope.get("selection_role") != "development"
    ):
        raise ValueError("Only exposed published development references are allowed")
    references = read_rows(refs)
    if any(
        value.get("provenance", {}).get("kind") != "published"
        or value["provenance"].get("source_id") != original["reference_source_id"]
        for value in references
    ):
        raise ValueError("Reference source differs")
    result = analyse(
        read_rows(packet / "development/inputs.jsonl"),
        references,
        read_rows(plan["prefix"]),
        candidates,
    )
    result.update(
        protocol_sha256=checksum(protocol),
        bound_runs=bound,
        runs_root=str(runs_root.resolve()),
    )
    write_new(output, result)
    return {
        "output": str(output),
        "gate_eligible": False,
        "additional_pairs": {
            name: value["accepted"] for name, value in result["variants"].items()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("freeze")
    for name in ("packet", "prefix", "owner", "output"):
        prep.add_argument("--" + name, type=Path, required=True)
    assess = sub.add_parser("run")
    for name in ("protocol", "runs-root", "output"):
        assess.add_argument("--" + name, type=Path, required=True)
    args = vars(parser.parse_args())
    action = args.pop("action")
    print(json.dumps((freeze if action == "freeze" else run)(**args), allow_nan=False))
