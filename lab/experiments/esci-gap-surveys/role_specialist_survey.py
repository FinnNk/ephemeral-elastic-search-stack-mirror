"""Separate development-only extension of the frozen nine-candidate CPU survey."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scipy import sparse
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import MaxAbsScaler

import specialist_survey as core


ACCESSORY = core.ACCESSORIES | {
    "sleeve",
    "holster",
    "mount",
    "protector",
    "refill",
    "cartridge",
    "stylus",
}


def category_role_features(row: dict) -> dict:
    """Use category leaves as evidence; ancestor accessory departments are broad."""
    q = core.tokens(row["request"]["query"])
    path = row["product"].get("category_path") or []
    leaf_nodes = path[1:] if len(path) > 1 else path
    leaf = core.tokens(" ".join(leaf_nodes[-2:]))

    def stem(token: str) -> str:
        return (
            "accessory"
            if token == "accessories"
            else token[:-1]
            if token.endswith("s") and len(token) > 3
            else token
        )

    leaf = {stem(token) for token in leaf}
    q_stem = {stem(token) for token in q}
    title = core.tokens(row["product"].get("title") or "")
    query_accessory = bool(q_stem & ACCESSORY)
    leaf_accessory = bool(leaf & ACCESSORY)
    role = {
        "role_path_present": float(bool(path)),
        "role_leaf_accessory": float(leaf_accessory),
        "role_query_accessory": float(query_accessory),
        "role_accessory_product_only": float(leaf_accessory and not query_accessory),
        "role_accessory_query_only": float(query_accessory and not leaf_accessory),
        "role_leaf_query_recall": len(q_stem & leaf) / max(1, len(q_stem)),
        "role_query_title_recall": len(q & title) / max(1, len(q)),
    }
    for label, probability in zip(core.LABELS, row["base_probabilities"]):
        role[f"role_base_x_accessory={label}"] = (
            probability * role["role_accessory_product_only"]
        )
        role[f"role_base_x_leaf_recall={label}"] = (
            probability * role["role_leaf_query_recall"]
        )
    return role


def run(
    state: Path, destination: Path, base_report: Path, embedding: Path | None = None
) -> dict:
    frozen = json.loads(base_report.read_text(encoding="utf-8"))
    assert len(frozen["candidates"]) == 9 and frozen["gate_eligible"] is False
    source = state / "esci-packaging" / "label-calibration-20261003"
    rows = core.load_development(source, frozen["seed"])
    split = {
        name: np.array([i for i, row in enumerate(rows) if row["partition"] == name])
        for name in ("fit", "calibration", "evaluation")
    }
    fit, calibration, test = (split[k] for k in ("fit", "calibration", "evaluation"))
    truth = np.array([core.LABELS.index(row["reference_label"]) for row in rows])
    test_rows = [rows[i] for i in test]
    base = core.exact_base_stage(test_rows)
    extras = None
    if embedding is not None:
        # Text-only, row-ordered features. No labels or identifiers enter embeddings.
        receipt = json.loads(
            embedding.with_name("receipt.json").read_text(encoding="utf-8")
        )
        plan_bytes = embedding.with_name("plan.json").read_bytes()
        plan = json.loads(plan_bytes.decode("utf-8"))
        assert receipt["reference_labels_read"] is False and receipt["device"] == "cpu"
        assert plan["inputs_sha256"] == frozen["source_sha256"]["inputs.jsonl"]
        assert (
            hashlib.sha256(embedding.read_bytes()).hexdigest()
            == receipt["embeddings_sha256"]
        )
        assert hashlib.sha256(plan_bytes).hexdigest() == receipt["plan_sha256"]
        data = np.load(embedding, allow_pickle=False)
        assert all(
            data[k].shape == (len(rows), 384) for k in ("query", "title", "category")
        )
        cosines = np.column_stack(
            (
                np.einsum("ij,ij->i", data["query"], data["title"]),
                np.einsum("ij,ij->i", data["query"], data["category"]),
                np.einsum("ij,ij->i", data["title"], data["category"]),
            )
        )
        base_probabilities = np.asarray([row["base_probabilities"] for row in rows])
        extras = np.hstack(
            (
                cosines,
                (cosines[:, :, None] * base_probabilities[:, None, :]).reshape(
                    len(rows), -1
                ),
            )
        )
        assert (
            extras.ndim == 2
            and extras.shape[0] == len(rows)
            and np.isfinite(extras).all()
        )
    result = {
        "kind": "esci-gap-category-role-development-extension",
        "gate_eligible": False,
        "frozen_nine_report_sha256": hashlib.sha256(
            base_report.read_bytes()
        ).hexdigest(),
        "source_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "seed": frozen["seed"],
        "partitions": frozen["partitions"],
        "embedding_sha256": hashlib.sha256(embedding.read_bytes()).hexdigest()
        if embedding
        else None,
        "limitations": frozen["limitations"],
        "candidates": [],
    }
    configs = [
        ("probability_lexical_roles", False, False, True),
        ("probability_numeric_roles", False, True, True),
        ("probability_numeric_roles_hist", True, True, True),
    ]
    if extras is not None:
        configs += [
            ("probability_lexical_embedding", False, False, False),
            ("probability_numeric_embedding_hist", True, True, False),
            ("probability_lexical_roles_embedding", False, False, True),
            ("probability_numeric_roles_embedding_hist", True, True, True),
        ]
    result["extension_candidates_frozen_before_fit"] = configs
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "plan.json").write_text(
        json.dumps(
            {k: v for k, v in result.items() if k != "candidates"},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    for name, hist, numeric, roles in configs:
        began = time.monotonic()
        dictionaries = [
            core.relation_features(row, categories=False, probabilities=True)
            | (category_role_features(row) if roles else {})
            for row in rows
        ]
        if numeric:
            dictionaries = [
                {k: v for k, v in dictionary.items() if not k.startswith("shared=")}
                for dictionary in dictionaries
            ]
        vector = DictVectorizer()
        x_fit = vector.fit_transform(dictionaries[i] for i in fit)
        scaler = MaxAbsScaler()
        x_fit = scaler.fit_transform(x_fit)
        x_calibration = scaler.transform(
            vector.transform(dictionaries[i] for i in calibration)
        )
        x_test = scaler.transform(vector.transform(dictionaries[i] for i in test))
        if "embedding" in name:
            x_fit = sparse.hstack((x_fit, sparse.csr_matrix(extras[fit])), format="csr")
            x_calibration = sparse.hstack(
                (x_calibration, sparse.csr_matrix(extras[calibration])), format="csr"
            )
            x_test = sparse.hstack(
                (x_test, sparse.csr_matrix(extras[test])), format="csr"
            )
        if hist:
            model = HistGradientBoostingClassifier(
                max_iter=120,
                max_depth=3,
                min_samples_leaf=40,
                l2_regularization=10.0,
                random_state=20261003,
            )
            x_fit, x_calibration, x_test = (
                x.toarray() for x in (x_fit, x_calibration, x_test)
            )
        else:
            model = LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs", n_jobs=1)
        model.fit(x_fit, truth[fit])
        choices = core.choose_thresholds(
            truth[calibration], model.predict_proba(x_calibration)
        )
        probabilities = model.predict_proba(x_test)
        predicted, accepted = core.apply_thresholds(probabilities, choices)
        combined = predicted.copy()
        combined[base] = 0
        summary = {
            "name": name,
            "seconds": time.monotonic() - began,
            "features": int(x_fit.shape[1]),
            "model_parameters": model.get_params(),
            "thresholds": choices,
            "standalone": core.evaluate(test_rows, predicted, accepted),
            "residual_added": core.evaluate(test_rows, predicted, accepted & ~base),
            "cascade": core.evaluate(test_rows, combined, accepted | base),
        }
        result["candidates"].append(summary)
        destination.mkdir(parents=True, exist_ok=True)
        with (destination / f"{name}-evaluation-predictions.jsonl").open(
            "w", encoding="utf-8", newline="\n"
        ) as out:
            for row, probs, prediction, yes, existing in zip(
                test_rows, probabilities, predicted, accepted, base
            ):
                out.write(
                    json.dumps(
                        {
                            "query_id": row["query_id"],
                            "product_id": row["product_id"],
                            "probabilities_ESCI": probs.tolist(),
                            "prediction": core.LABELS[prediction],
                            "accepted": bool(yes),
                            "base_exact_095": bool(existing),
                            "reference_label": row["reference_label"],
                            "gate_eligible": False,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        print(
            json.dumps(
                {
                    "candidate": name,
                    "added": summary["residual_added"]["accepted"],
                    "accuracy": summary["residual_added"]["accuracy"],
                    "cascade_coverage": summary["cascade"]["coverage"],
                }
            ),
            flush=True,
        )
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-report", type=Path, required=True)
    parser.add_argument("--embedding-features", type=Path)
    args = parser.parse_args()
    run(args.state, args.output, args.base_report, args.embedding_features)
