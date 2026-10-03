"""Fit a small CPU specialist survey on a newly reserved ESCI training pool.

The old calibration cohort is exposed development evidence, never fitting or
confirmation. No model labels are activated by this experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import warnings
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import scipy
import sklearn
from scipy.stats import beta
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import MaxAbsScaler, StandardScaler

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "esci-gap-surveys"))
import specialist_survey as old  # noqa: E402 - shared experiment CLI helper

sys.path.insert(0, str(HERE.parents[2] / "evaluation"))
from label_quality import query_key  # noqa: E402 - canonical evaluation contract

LABELS = ("E", "S", "C", "I")
SEED = "esci-fitted-specialists-20261004-v1"
GRID = (0.70, 0.80, 0.90, 0.95, 0.975, 0.99, 0.995)
CANDIDATES = (
    {
        "name": "lexical_category_lr",
        "features": "sparse_lexical_category",
        "learner": "lr",
    },
    {"name": "numeric_role_hist", "features": "numeric_roles", "learner": "hist"},
    {"name": "minilm_cosine_lr", "features": "numeric_roles_cosines", "learner": "lr"},
    {
        "name": "minilm_cosine_hist",
        "features": "numeric_roles_cosines",
        "learner": "hist",
    },
    {"name": "minilm_pair_lr", "features": "numeric_roles_pair", "learner": "lr"},
    {"name": "minilm_pair_mlp", "features": "numeric_roles_pair", "learner": "mlp"},
)
LR = {"C": 1.0, "max_iter": 1000, "solver": "lbfgs", "n_jobs": 1}
HIST = {
    "max_iter": 150,
    "max_depth": 3,
    "min_samples_leaf": 40,
    "l2_regularization": 10.0,
    "random_state": 20261004,
}
MLP = {
    "hidden_layer_sizes": (64,),
    "alpha": 0.01,
    "max_iter": 80,
    "batch_size": 128,
    "early_stopping": False,
    "n_iter_no_change": 10,
    "random_state": 20261004,
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def group(row: dict) -> str:
    computed = query_key(row["request"]["query"])
    if "query_key" in row and row["query_key"] != computed:
        raise ValueError(
            "Frozen query key differs from the current normalisation contract"
        )
    return computed


def split_queries(groups: set[str]) -> dict[str, str]:
    ordered = sorted(
        groups, key=lambda q: hashlib.sha256(f"{SEED}\0{q}".encode()).hexdigest()
    )
    cut = math.floor(len(ordered) * 0.7)
    return {q: "fit" if i < cut else "calibration" for i, q in enumerate(ordered)}


def freeze(pool: Path, state: Path, output: Path) -> dict:
    inputs = read_rows(pool / "inputs.jsonl")
    source_manifest = json.loads((pool / "manifest.json").read_text(encoding="utf-8"))
    assert (
        source_manifest["kind"] == "esci-fitting-pool"
        and source_manifest["normalisation"] == "nfkc_html_whitespace_v1"
    )
    for name, expected in source_manifest["files_sha256"].items():
        assert sha(pool / name) == expected
    groups = {group(row) for row in inputs}
    assert len(groups) == 1000 and len(inputs) == source_manifest["pairs"]
    development_path = (
        state / "esci-packaging" / "label-calibration-20261003" / "inputs.jsonl"
    )
    dev_groups = {group(row) for row in read_rows(development_path)}
    assert not groups & dev_groups
    partitions = split_queries(groups)
    plan = {
        "kind": "esci-fitted-specialists-development-plan",
        "schema_version": 1,
        "gate_eligible": False,
        "tool_sha256": sha(Path(__file__)),
        "pool": str(pool),
        "pool_manifest_sha256": sha(pool / "manifest.json"),
        "pool_files_sha256": source_manifest["files_sha256"],
        "development_inputs_sha256": sha(development_path),
        "seed": SEED,
        "normalisation": "nfkc_html_whitespace_v1",
        "partitions": partitions,
        "partition_queries": dict(Counter(partitions.values())),
        "candidates": list(CANDIDATES),
        "learner_parameters": {"lr": LR, "hist": HIST, "mlp": MLP},
        "threshold_grid": GRID,
        "calibration_minimum_support": 30,
        "calibration_observed_precision_minimum": 0.98,
        "bootstrap_repetitions": 2000,
        "bootstrap_seed": 20261004,
        "embedding": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
            "device": "cpu",
            "torch_threads": 4,
            "fields": ["request.query", "product.title", "product.category_path"],
            "max_tokens": 256,
            "pooling": "attention-mask mean, L2 normalised",
        },
        "meaningful_projection_screen": {
            "minimum_added_fraction": 0.03,
            "minimum_added_accuracy": 0.98,
            "minimum_query_bootstrap_accuracy_lower": 0.95,
            "maximum_added_irrelevant_to_exact_errors": 0,
        },
        "limits": [
            "Only the new published training pool may be fitted; calibration queries are whole-query disjoint.",
            "The 400-query cohort is exposed development only. It is not fresh confirmation.",
            "Identifiers, labels and synthetic serving fields are excluded from model inputs.",
            "Fixed screens are not qualification; no label activation or gate-policy change.",
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "frozen": str(output / "plan.json"),
                "partitions": plan["partition_queries"],
                "pairs": len(inputs),
            }
        ),
        flush=True,
    )
    return plan


def input_features(row: dict, sparse_categories: bool = False) -> dict:
    features = old.relation_features(
        row, categories=sparse_categories, probabilities=False
    )
    if not sparse_categories:
        features = {k: v for k, v in features.items() if not k.startswith("shared=")}
    product = row["product"]
    q = old.tokens(row["request"]["query"])
    path = product.get("category_path") or []
    leaves = path[1:][-2:] if len(path) > 1 else path

    def stem(token):
        return (
            "accessory"
            if token == "accessories"
            else token[:-1]
            if token.endswith("s") and len(token) > 3
            else token
        )

    leaf = {stem(word) for word in old.tokens(" ".join(leaves))}
    q_stem = {stem(word) for word in q}
    accessory = old.ACCESSORIES | {"sleeve", "holster", "mount", "stylus", "cartridge"}
    query_accessory = bool(q_stem & accessory)
    product_accessory = bool(leaf & accessory)
    features.update(
        {
            "role_path_present": float(bool(path)),
            "role_leaf_accessory": float(product_accessory),
            "role_query_accessory": float(query_accessory),
            "role_product_only_accessory": float(
                product_accessory and not query_accessory
            ),
            "role_query_only_accessory": float(
                query_accessory and not product_accessory
            ),
            "role_leaf_query_recall": len(leaf & q_stem) / max(1, len(q_stem)),
        }
    )
    if path:
        features[f"department={path[0]}"] = 1.0
    if product.get("product_type"):
        features[f"product_type={product['product_type']}"] = 1.0
    return features


def embedding_features(
    folder: Path, inputs_hash: str, n: int, pair: bool
) -> np.ndarray:
    receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
    assert receipt["device"] == "cpu" and receipt["reference_labels_read"] is False
    assert (
        plan["inputs_sha256"] == inputs_hash
        and plan["revision"] == "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    )
    assert (
        sha(folder / "plan.json") == receipt["plan_sha256"]
        and sha(folder / "embeddings.npz") == receipt["embeddings_sha256"]
    )
    data = np.load(folder / "embeddings.npz", allow_pickle=False)
    q, title, category = (data[name] for name in ("query", "title", "category"))
    assert all(
        matrix.shape == (n, 384) and np.isfinite(matrix).all()
        for matrix in (q, title, category)
    )
    cosine = np.column_stack(
        (
            np.einsum("ij,ij->i", q, title),
            np.einsum("ij,ij->i", q, category),
            np.einsum("ij,ij->i", title, category),
        )
    )
    return (
        np.hstack((cosine, q, title, np.abs(q - title), q * title)) if pair else cosine
    )


def thresholds(truth: np.ndarray, probabilities: np.ndarray) -> dict:
    prediction = probabilities.argmax(axis=1)
    result = {}
    for i, label in enumerate(LABELS):
        chosen, grid = None, []
        for threshold in GRID:
            selected = (prediction == i) & (probabilities[:, i] >= threshold)
            n = int(selected.sum())
            correct = int((selected & (truth == i)).sum())
            precision = correct / n if n else None
            grid.append({"threshold": threshold, "support": n, "precision": precision})
            if chosen is None and n >= 30 and precision >= 0.98:
                chosen = threshold
        result[label] = {"threshold": chosen, "calibration_grid": grid}
    return result


def statistics(
    rows: list[dict], truth: np.ndarray, prediction: np.ndarray, accepted: np.ndarray
) -> dict:
    groups = sorted({group(row) for row in rows})
    lookup = {value: i for i, value in enumerate(groups)}
    # accepted/correct/all-I/accepted-E/I->E/all-E/E->I, then per-class selected/correct.
    counts = np.zeros((len(groups), 15), dtype=np.int64)
    matrix = np.zeros((4, 4), dtype=int)
    accepted_queries = set()
    class_queries = {label: set() for label in LABELS}
    for row, true, pred, yes in zip(rows, truth, prediction, accepted):
        gid = group(row)
        c = counts[lookup[gid]]
        c[2] += int(true == 3)
        c[5] += int(true == 0)
        if yes:
            c[0] += 1
            c[1] += int(true == pred)
            c[3] += int(pred == 0)
            c[4] += int(true == 3 and pred == 0)
            c[6] += int(true == 0 and pred == 3)
            c[7 + 2 * pred] += 1
            c[8 + 2 * pred] += int(true == pred)
            matrix[true, pred] += 1
            accepted_queries.add(gid)
            class_queries[LABELS[int(pred)]].add(gid)
    point = counts.sum(axis=0)
    rng = np.random.default_rng(20261004)
    bootstrap = np.empty((2000, 15), dtype=np.int64)
    for start in range(0, 2000, 100):
        draw = rng.integers(len(groups), size=(100, len(groups)))
        bootstrap[start : start + 100] = counts[draw].sum(axis=1)

    def ratio(numerator: int, denominator: int, risk: bool = False) -> dict:
        invalid = bootstrap[:, denominator] == 0
        interval = (
            None
            if invalid.any()
            else np.quantile(
                bootstrap[:, numerator] / bootstrap[:, denominator], (0.025, 0.975)
            ).tolist()
        )
        return {
            "numerator": int(point[numerator]),
            "denominator": int(point[denominator]),
            "estimate": float(point[numerator] / point[denominator])
            if point[denominator]
            else None,
            "whole_query_bootstrap_interval_95": interval,
            "zero_denominator_repetitions": int(invalid.sum()),
            "usable_pair_risk_upper": None
            if risk and (not point[numerator] or interval is None)
            else float(interval[1])
            if risk
            else None,
        }

    n = int(point[0])
    classes = {}
    for i, label in enumerate(LABELS):
        classes[label] = ratio(8 + 2 * i, 7 + 2 * i) | {
            "accepted_queries": len(class_queries[label])
        }
    risks = {
        "irrelevant_to_exact": ratio(4, 2, True),
        "exact_irrelevant_contamination": ratio(4, 3, True),
        "exact_to_irrelevant": ratio(6, 5, True),
    }
    for risk in risks.values():
        errors, trials = risk["numerator"], risk["denominator"]
        risk["pair_independence_CP_upper_one_sided_95_descriptive_only"] = (
            (
                float(beta.ppf(0.95, errors + 1, trials - errors))
                if errors < trials
                else 1.0
            )
            if trials
            else None
        )
    return {
        "pairs": len(rows),
        "query_groups": len(groups),
        "accepted": n,
        "accepted_query_groups": len(accepted_queries),
        "coverage": n / len(rows),
        "accuracy": ratio(1, 0),
        "classes": classes,
        "risks": risks,
        "confusion_true_rows_prediction_columns_ESCI": matrix.tolist(),
        "limits": [
            "Whole-query bootstrap uses frozen query keys and pair-weighted ratios.",
            "Any bootstrap replicate with zero denominator makes that interval inconclusive.",
            "Zero-event bootstrap cannot establish a pair-risk upper bound.",
            "Pair CP bounds assume independent pairs and are descriptive only, never qualification.",
        ],
    }


def meaningful(stats: dict) -> bool:
    accuracy = stats["accuracy"]
    interval = accuracy["whole_query_bootstrap_interval_95"]
    return (
        stats["coverage"] >= 0.03
        and accuracy["estimate"] is not None
        and accuracy["estimate"] >= 0.98
        and interval is not None
        and interval[0] >= 0.95
        and stats["risks"]["irrelevant_to_exact"]["numerator"] == 0
    )


def run(state: Path, output: Path, pool_embeddings: Path, dev_embeddings: Path) -> dict:
    plan_path = output / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert sha(Path(__file__)) == plan["tool_sha256"] and plan["gate_eligible"] is False
    pool = Path(plan["pool"])
    assert sha(pool / "manifest.json") == plan["pool_manifest_sha256"]
    for name, expected in plan["pool_files_sha256"].items():
        assert sha(pool / name) == expected
    inputs = read_rows(pool / "inputs.jsonl")
    references = {
        (str(row["query_id"]), row["product_id"]): row
        for row in read_rows(pool / "references.jsonl")
    }
    assert len(references) == len(inputs)
    assert all(
        row["provenance"]["kind"] == "published"
        and row["provenance"]["source_split"] == "train"
        for row in references.values()
    )
    truth = np.array(
        [
            LABELS.index(references[(str(row["query_id"]), row["product_id"])]["label"])
            for row in inputs
        ]
    )
    split = np.array([plan["partitions"][group(row)] for row in inputs])
    fit_idx, calibration_idx = (
        np.flatnonzero(split == "fit"),
        np.flatnonzero(split == "calibration"),
    )
    development = old.load_development(
        state / "esci-packaging" / "label-calibration-20261003",
        "esci-gap-cpu-survey-20261003-v1",
    )
    dev_truth = np.array([LABELS.index(row["reference_label"]) for row in development])
    assert not {group(row) for row in inputs} & {group(row) for row in development}
    frozen_old = (
        state / "esci-gap-surveys" / "specialist-survey" / "actual-gap-projection"
    )
    old_receipt = json.loads((frozen_old / "report.json").read_text(encoding="utf-8"))
    assert (
        sha(frozen_old / "frozen-fitted-recalibrator.joblib")
        == old_receipt["hashes"]["fitted_artifact"]
    )
    prior = joblib.load(frozen_old / "frozen-fitted-recalibrator.joblib")
    stage_one = old.exact_base_stage(development)
    old_matrix = prior["scaler"].transform(
        prior["vectorizer"].transform(
            old.relation_features(row, categories=False, probabilities=True)
            for row in development
        )
    )
    old_probs = prior["classifier"].predict_proba(old_matrix)
    prior_prediction, prior_accepted = old.apply_thresholds(
        old_probs, prior["thresholds"]
    )
    prior_prediction[stage_one] = 0
    prefix = stage_one | prior_accepted
    result = {
        "kind": "esci-fitted-specialists-development-survey",
        "schema_version": 1,
        "gate_eligible": False,
        "plan_sha256": sha(plan_path),
        "libraries": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "sklearn": sklearn.__version__,
        },
        "partitions": {
            name: {
                "pairs": int((split == name).sum()),
                "queries": len(
                    {group(row) for row, role in zip(inputs, split) if role == name}
                ),
                "labels": dict(Counter(LABELS[int(i)] for i in truth[split == name])),
            }
            for name in ("fit", "calibration")
        },
        "development": {
            "pairs": len(development),
            "query_groups": len({group(row) for row in development}),
        },
        "prefix": statistics(development, dev_truth, prior_prediction, prefix),
        "old_recalibrator_sha256": sha(
            frozen_old / "frozen-fitted-recalibrator.joblib"
        ),
        "candidates": [],
        "limits": plan["limits"]
        + [
            "The prior recalibrator was fitted on part of the exposed development cohort; prefix metrics are descriptive and may be optimistic.",
            "The new specialists fit none of the old development references. Source coverage and deployed judgements are unchanged.",
        ],
    }
    pairs_pool = embedding_features(
        pool_embeddings, plan["pool_files_sha256"]["inputs.jsonl"], len(inputs), True
    )
    pairs_dev = embedding_features(
        dev_embeddings, plan["development_inputs_sha256"], len(development), True
    )
    for candidate in plan["candidates"]:
        began = time.monotonic()
        sparse_cats = candidate["features"] == "sparse_lexical_category"
        dictionaries = [input_features(row, sparse_cats) for row in inputs]
        vector = DictVectorizer(sparse=False)
        # Sparse categorical fits avoid dense high-cardinality query/category interactions.
        if sparse_cats:
            vector = DictVectorizer(sparse=True)
        x_fit = vector.fit_transform(dictionaries[i] for i in fit_idx)
        x_cal = vector.transform(dictionaries[i] for i in calibration_idx)
        x_dev = vector.transform(
            input_features(row, sparse_cats) for row in development
        )
        numeric_scaler = MaxAbsScaler()
        x_fit = numeric_scaler.fit_transform(x_fit)
        x_cal, x_dev = numeric_scaler.transform(x_cal), numeric_scaler.transform(x_dev)
        if "cosines" in candidate["features"]:
            x_fit = np.hstack((x_fit, pairs_pool[fit_idx, :3]))
            x_cal = np.hstack((x_cal, pairs_pool[calibration_idx, :3]))
            x_dev = np.hstack((x_dev, pairs_dev[:, :3]))
        elif "pair" in candidate["features"]:
            x_fit = np.hstack((x_fit, pairs_pool[fit_idx]))
            x_cal = np.hstack((x_cal, pairs_pool[calibration_idx]))
            x_dev = np.hstack((x_dev, pairs_dev))
        extra_scaler = None
        if candidate["learner"] == "mlp":
            extra_scaler = StandardScaler()
            x_fit = extra_scaler.fit_transform(x_fit)
            x_cal, x_dev = extra_scaler.transform(x_cal), extra_scaler.transform(x_dev)
            model = MLPClassifier(**MLP)
        else:
            model = (
                LogisticRegression(**LR)
                if candidate["learner"] == "lr"
                else HistGradientBoostingClassifier(**HIST)
            )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(x_fit, truth[fit_idx])
        assert tuple(model.classes_) == (0, 1, 2, 3)
        choice = thresholds(truth[calibration_idx], model.predict_proba(x_cal))
        probabilities = model.predict_proba(x_dev)
        predicted, accepted = old.apply_thresholds(probabilities, choice)
        extra = accepted & ~prefix
        cascade_prediction = predicted.copy()
        cascade_prediction[prefix] = prior_prediction[prefix]
        added = statistics(development, dev_truth, predicted, extra)
        candidate_result = {
            "name": candidate["name"],
            "features": int(x_fit.shape[1]),
            "learner_parameters": model.get_params(),
            "fit_seconds": time.monotonic() - began,
            "fit_warnings": [str(w.message) for w in caught],
            "thresholds": choice,
            "standalone": statistics(development, dev_truth, predicted, accepted),
            "residual_after_prior_two_stages": added,
            "cascade": statistics(
                development, dev_truth, cascade_prediction, accepted | prefix
            ),
            "argmax_development_accuracy": float((predicted == dev_truth).mean()),
            "meaningful_to_project": meaningful(added),
        }
        model_path = output / f"{candidate['name']}.joblib"
        joblib.dump(
            {
                "vectorizer": vector,
                "numeric_scaler": numeric_scaler,
                "extra_scaler": extra_scaler,
                "model": model,
                "thresholds": choice,
                "candidate": candidate,
                "labels": LABELS,
            },
            model_path,
        )
        candidate_result["fitted_model_sha256"] = sha(model_path)
        result["candidates"].append(candidate_result)
        with (output / f"{candidate['name']}-development.jsonl").open(
            "w", encoding="utf-8", newline="\n"
        ) as handle:
            for row, probability, prediction, yes, previous in zip(
                development, probabilities, predicted, accepted, prefix
            ):
                handle.write(
                    json.dumps(
                        {
                            "query_id": row["query_id"],
                            "product_id": row["product_id"],
                            "query_key": group(row),
                            "probabilities_ESCI": probability.tolist(),
                            "prediction": LABELS[int(prediction)],
                            "accepted": bool(yes),
                            "prior_two_stages_accepted": bool(previous),
                            "gate_eligible": False,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        (output / "report.json").write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "candidate": candidate["name"],
                    "seconds": round(candidate_result["fit_seconds"], 2),
                    "extra": added["accepted"],
                    "extra_accuracy": added["accuracy"]["estimate"],
                    "extra_classes": {
                        k: v["denominator"] for k, v in added["classes"].items()
                    },
                    "meaningful_to_project": candidate_result["meaningful_to_project"],
                }
            ),
            flush=True,
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("freeze", "run"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--state", type=Path, required=True)
        sub.add_argument("--output", type=Path, required=True)
        if command == "freeze":
            sub.add_argument("--pool", type=Path, required=True)
        else:
            sub.add_argument("--pool-embeddings", type=Path, required=True)
            sub.add_argument("--development-embeddings", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.pool, args.state, args.output)
    else:
        run(args.state, args.output, args.pool_embeddings, args.development_embeddings)
