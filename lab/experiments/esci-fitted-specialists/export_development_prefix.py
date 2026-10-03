"""Export inactive prior-stage predictions for an exposed-development comparison."""

import argparse
import json
from pathlib import Path

import fit_specialists as survey
import joblib


def run(state: Path, output: Path):
    inputs = state / "esci-packaging" / "label-calibration-20261003"
    rows = survey.old.load_development(inputs, "esci-gap-cpu-survey-20261003-v1")
    prefix = state / "esci-gap-surveys" / "specialist-survey" / "actual-gap-projection"
    receipt = json.loads((prefix / "report.json").read_text(encoding="utf-8"))
    model_path = prefix / "frozen-fitted-recalibrator.joblib"
    assert survey.sha(model_path) == receipt["hashes"]["fitted_artifact"]
    model = joblib.load(model_path)
    x = model["scaler"].transform(
        model["vectorizer"].transform(
            survey.old.relation_features(row, categories=False, probabilities=True)
            for row in rows
        )
    )
    probabilities = model["classifier"].predict_proba(x)
    prediction, accepted = survey.old.apply_thresholds(
        probabilities, model["thresholds"]
    )
    first = survey.old.exact_base_stage(rows)
    prediction[first] = 0
    accepted |= first
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for row, label, yes, one in zip(rows, prediction, accepted, first):
            handle.write(
                json.dumps(
                    {
                        "query_id": row["query_id"],
                        "product_id": row["product_id"],
                        "query_key": survey.group(row),
                        "prediction": survey.LABELS[int(label)],
                        "prefix_accepted": bool(yes),
                        "exact_095_accepted": bool(one),
                        "gate_eligible": False,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    output.with_suffix(".receipt.json").write_text(
        json.dumps(
            {
                "kind": "exposed-development-prior-stage-predictions",
                "gate_eligible": False,
                "pairs": len(rows),
                "predictions_sha256": survey.sha(output),
                "original_inputs_sha256": survey.sha(inputs / "inputs.jsonl"),
                "original_classifier_predictions_sha256": survey.sha(
                    inputs / "inference-01" / "predictions.jsonl"
                ),
                "fitted_recalibrator_sha256": survey.sha(model_path),
                "limits": [
                    "Prior recalibrator fits part of this exposed development cohort; its results are descriptive and not independent confirmation.",
                    "These predictions remain unqualified and inactive.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.state, args.output)
