"""Add full-class development support and confusion to a frozen CPU screen."""

import argparse
import json
from collections import Counter
from pathlib import Path

import fit_specialists as survey
import numpy as np


def run(state: Path, output: Path):
    report_path = output / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    development = survey.old.load_development(
        state / "esci-packaging" / "label-calibration-20261003",
        "esci-gap-cpu-survey-20261003-v1",
    )
    truth = np.array(
        [survey.LABELS.index(row["reference_label"]) for row in development]
    )
    summary = {
        "kind": "esci-fitted-specialists-class-support-audit",
        "gate_eligible": False,
        "survey_report_sha256": survey.sha(report_path),
        "reference_class_support": dict(
            Counter(row["reference_label"] for row in development)
        ),
        "candidates": [],
        "limits": [
            "This audit opens only already exposed development references and frozen candidate predictions.",
            "No thresholds are changed or selected here. Unfiltered confusion is descriptive, not a deployment policy.",
        ],
    }
    for candidate in report["candidates"]:
        path = output / f"{candidate['name']}-development.jsonl"
        predictions = survey.read_rows(path)
        assert [(row["query_id"], row["product_id"]) for row in development] == [
            (row["query_id"], row["product_id"]) for row in predictions
        ]
        predicted = np.array(
            [survey.LABELS.index(row["prediction"]) for row in predictions]
        )
        matrix = np.zeros((4, 4), dtype=int)
        for label, guess in zip(truth, predicted):
            matrix[label, guess] += 1
        classes = {}
        for i, label in enumerate(survey.LABELS):
            correct = int(matrix[i, i])
            selected = int(matrix[:, i].sum())
            references = int(matrix[i, :].sum())
            classes[label] = {
                "references": references,
                "predicted": selected,
                "correct": correct,
                "precision": correct / selected if selected else None,
                "recall": correct / references if references else None,
            }
        summary["candidates"].append(
            {
                "name": candidate["name"],
                "predictions_sha256": survey.sha(path),
                "unfiltered_confusion_true_rows_prediction_columns_ESCI": matrix.tolist(),
                "unfiltered_classes": classes,
                "selective_accepted": candidate["standalone"]["accepted"],
                "selective_added_after_prior_stages": candidate[
                    "residual_after_prior_two_stages"
                ]["accepted"],
                "meaningful_to_project": candidate["meaningful_to_project"],
            }
        )
    (output / "class-support-audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "class_support": summary["reference_class_support"],
                "candidates": len(summary["candidates"]),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.state, args.output)
