"""Project a frozen development specialist onto saved, unlabelled lab gaps.

This performs no model API calls and imports no predictions into the lab. The
development fitting partition is reconstructed exactly, checked against frozen
evaluation probabilities, and saved before scoring residual gaps.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time

import joblib
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import MaxAbsScaler

import specialist_survey as core


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(row: dict) -> tuple[str, str]:
    return str(row["query_id"]), row["product_id"]


def selection_counts(
    rows: list[dict], predictions: np.ndarray, accepted: np.ndarray
) -> dict:
    return {
        "accepted": int(accepted.sum()),
        "queries": len(
            {
                core.normalise(row["request"]["query"])
                for row, yes in zip(rows, accepted)
                if yes
            }
        ),
        "classes": dict(
            Counter(
                core.LABELS[int(pred)]
                for pred, yes in zip(predictions, accepted)
                if yes
            )
        ),
    }


def run(state: Path, survey: Path, destination: Path) -> dict:
    started = time.monotonic()
    report_path = survey / "report.json"
    frozen = json.loads(report_path.read_text(encoding="utf-8"))
    assert frozen["gate_eligible"] is False and len(frozen["candidates"]) == 9
    best = next(
        row for row in frozen["candidates"] if row["name"] == "probability_lexical"
    )
    source = state / "esci-packaging" / "label-calibration-20261003"
    development = core.load_development(source, frozen["seed"])
    for name, expected in frozen["source_sha256"].items():
        assert sha(source / name) == expected
    assert sha(Path(core.__file__)) == frozen["source_code_sha256"]
    fit = [row for row in development if row["partition"] == "fit"]
    evaluation = [row for row in development if row["partition"] == "evaluation"]
    dictionaries = [
        core.relation_features(row, categories=False, probabilities=True) for row in fit
    ]
    vector = DictVectorizer()
    x_fit = vector.fit_transform(dictionaries)
    scaler = MaxAbsScaler()
    x_fit = scaler.fit_transform(x_fit)
    model = LogisticRegression(**best["model_parameters"])
    model.fit(x_fit, [core.LABELS.index(row["reference_label"]) for row in fit])
    x_evaluation = scaler.transform(
        vector.transform(
            core.relation_features(row, categories=False, probabilities=True)
            for row in evaluation
        )
    )
    probabilities = model.predict_proba(x_evaluation)
    old_path = survey / "probability_lexical-evaluation-predictions.jsonl"
    old = [
        json.loads(line) for line in old_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [key(row) for row in evaluation] == [key(row) for row in old]
    old_probabilities = np.array([row["probabilities_ESCI"] for row in old])
    np.testing.assert_allclose(probabilities, old_probabilities, rtol=0.0, atol=1e-12)
    predicted, accepted = core.apply_thresholds(probabilities, best["thresholds"])
    assert [core.LABELS[int(i)] for i in predicted] == [
        row["prediction"] for row in old
    ]
    assert accepted.tolist() == [row["accepted"] for row in old]
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / "frozen-fitted-recalibrator.joblib"
    joblib.dump(
        {
            "vectorizer": vector,
            "scaler": scaler,
            "classifier": model,
            "thresholds": best["thresholds"],
            "classes": core.LABELS,
        },
        model_path,
    )
    gap_path = state / "esci-packaging" / "progressive-20261003" / "inputs.json"
    pass_path = gap_path.parent / "first-pass" / "pass.json"
    gap_inputs = json.loads(gap_path.read_text(encoding="utf-8"))
    gap_pass = json.loads(pass_path.read_text(encoding="utf-8"))
    pairs = {key(row): row for row in gap_inputs["pairs"]}
    saved = {key(row): row for row in gap_pass["records"]}
    assert len(pairs) == 6969 and len(saved) == 6920 and set(saved) <= set(pairs)
    assert len(pairs) - len(saved) == gap_pass["excluded_pairs"] == 49
    # Only the already eligible saved pairs are scored; specialist exclusions stay excluded.
    rows = [
        dict(pairs[pair_key], base_probabilities=record["probabilities"])
        for pair_key, record in saved.items()
    ]
    base = core.exact_base_stage(rows)
    residual = np.flatnonzero(~base)
    residual_rows = [rows[i] for i in residual]
    x_gap = scaler.transform(
        vector.transform(
            core.relation_features(row, categories=False, probabilities=True)
            for row in residual_rows
        )
    )
    gap_probabilities = model.predict_proba(x_gap)
    gap_predicted, gap_accepted = core.apply_thresholds(
        gap_probabilities, best["thresholds"]
    )
    all_predictions = np.zeros(len(rows), dtype=int)
    all_accepted = base.copy()
    all_predictions[residual] = gap_predicted
    all_accepted[residual] = gap_accepted
    additional = selection_counts(residual_rows, gap_predicted, gap_accepted)
    first_stage = selection_counts(rows, np.zeros(len(rows), dtype=int), base)
    combination = selection_counts(rows, all_predictions, all_accepted)
    required = 9915
    source_accepted = 2946
    minimum = math.ceil(required * 0.8)
    assert all(
        side["before"] == source_accepted and side["required"] == required
        for side in gap_pass["coverage"].values()
    )
    hypothetical = source_accepted + combination["accepted"]
    result = {
        "kind": "esci-frozen-recalibrator-unlabelled-gap-projection",
        "schema_version": 1,
        "gate_eligible": False,
        "activated": False,
        "model_api_calls": 0,
        "hashes": {
            "script": sha(Path(__file__)),
            "survey_code": sha(Path(core.__file__)),
            "survey_report": sha(report_path),
            "frozen_evaluation_predictions": sha(old_path),
            "fitted_artifact": sha(model_path),
            "gap_inputs": sha(gap_path),
            "saved_pass": sha(pass_path),
        },
        "fitted_model": {
            "candidate": "probability_lexical",
            "fit_pairs": len(fit),
            "fit_queries": len(
                {core.normalise(row["request"]["query"]) for row in fit}
            ),
            "fit_partition_only": True,
            "thresholds_unchanged": best["thresholds"],
            "maximum_development_probability_difference": float(
                np.max(np.abs(probabilities - old_probabilities))
            ),
        },
        "eligible_saved_gap_pairs": len(rows),
        "excluded_pairs": 49,
        "first_stage_exact_095": first_stage,
        "specialist_residual_inputs": len(residual),
        "specialist_additional": additional,
        "combined_predictions": combination,
        "coverage": {
            "required_pairs_per_side": required,
            "actual_source_qualified_pairs": source_accepted,
            "actual_source_qualified_fraction": source_accepted / required,
            "hypothetical_source_plus_unqualified_cascade_pairs": hypothetical,
            "hypothetical_fraction": hypothetical / required,
            "minimum_pairs_for_80_percent": minimum,
            "remaining_to_80_percent": max(0, minimum - hypothetical),
            "specialist_increment_percentage_points": 100
            * additional["accepted"]
            / required,
        },
        "seconds": time.monotonic() - started,
        "limitations": [
            "No reference labels for these gaps were read; no quality, error rate or confidence interval is established for these predictions.",
            "All model-derived labels remain unqualified and inactive; actual gate coverage is unchanged.",
            "The fitted classifier was reconstructed using exactly the frozen fitting partition and checked against saved development evaluation outputs; evaluation labels were never fitted.",
            "The original classifier probabilities are reused only for this measurement; this does not remove repeated searches from offline evaluation.",
            "The 49 specialist-excluded pairs remain excluded. Published source judgements are not changed.",
        ],
    }
    (destination / "report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    with (destination / "unqualified-residual-predictions.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as out:
        for row, probs, pred, yes in zip(
            residual_rows, gap_probabilities, gap_predicted, gap_accepted
        ):
            out.write(
                json.dumps(
                    {
                        "query_id": row["query_id"],
                        "product_id": row["product_id"],
                        "probabilities_ESCI": probs.tolist(),
                        "prediction": core.LABELS[int(pred)],
                        "accepted": bool(yes),
                        "gate_eligible": False,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    print(
        json.dumps(
            {
                "first_stage": first_stage,
                "additional": additional,
                "coverage": result["coverage"],
            },
            indent=2,
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--survey", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.state, args.survey, args.output)
