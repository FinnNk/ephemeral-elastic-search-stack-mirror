"""CPU-only, development-only surveys of selective ESCI gap specialists.

Only the already exposed calibration cohort is read. Query groups are split
before fitting; a separate calibration partition chooses thresholds. Results
on the third partition are exploratory development evidence, never qualification.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import time

import numpy as np
import scipy
import sklearn
from scipy import sparse
from scipy.stats import beta
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import MaxAbsScaler
from sklearn.ensemble import HistGradientBoostingClassifier, ExtraTreesClassifier


LABELS = ("E", "S", "C", "I")
THRESHOLDS = (0.70, 0.80, 0.90, 0.95, 0.975, 0.99, 0.995)
STOP = {"a", "an", "and", "the", "for", "of", "with", "to", "in", "by", "on", "at"}
ACCESSORIES = {
    "case",
    "cover",
    "charger",
    "adapter",
    "holder",
    "stand",
    "cable",
    "protector",
    "replacement",
    "refill",
}


def normalise(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def tokens(value: str) -> set[str]:
    return {word for word in normalise(value).split() if word not in STOP}


def query_partition(query: str, seed: str) -> str:
    bucket = (
        int(hashlib.sha256(f"{seed}\0{normalise(query)}".encode()).hexdigest()[:16], 16)
        % 10
    )
    return "fit" if bucket < 6 else "calibration" if bucket < 8 else "evaluation"


def relation_features(row: dict, *, categories: bool, probabilities: bool) -> dict:
    product = row["product"]
    q = tokens(row["request"]["query"])
    title = tokens(product.get("title") or "")
    body = tokens(
        (product.get("description") or "") + " " + (product.get("bullets") or "")
    )
    category = tokens(
        " ".join(product.get("category_path") or [])
        + " "
        + (product.get("category") or "")
        + " "
        + (product.get("product_type") or "")
    )
    brand = tokens(product.get("brand") or "")
    common = q & title
    all_product = title | body
    numbers = {word for word in q if any(char.isdigit() for char in word)}
    features = {
        "title_query_recall": len(common) / max(1, len(q)),
        "title_jaccard": len(common) / max(1, len(q | title)),
        "body_query_recall": len(q & body) / max(1, len(q)),
        "product_query_recall": len(q & all_product) / max(1, len(q)),
        "brand_query_overlap": len(q & brand) / max(1, len(brand)),
        "number_recall": len(numbers & all_product) / max(1, len(numbers)),
        "query_numbers_present": float(bool(numbers)),
        "query_length": len(q),
        "title_length": min(100, len(title)),
        "query_accessory": float(bool(q & ACCESSORIES)),
        "product_accessory": float(bool(title & ACCESSORIES)),
        "accessory_product_only": float(
            bool(title & ACCESSORIES) and not bool(q & ACCESSORIES)
        ),
        "brand_named": float(bool(brand and brand <= q)),
        "query_in_title": float(
            normalise(row["request"]["query"]) in normalise(product.get("title") or "")
        ),
    }
    # No identifiers, source labels, synthetic prices, colours or stock enter features.
    if categories:
        features["category_query_overlap"] = len(q & category) / max(1, len(q))
        for cat in sorted(category - {"uncategorised"})[:15]:
            features[f"category={cat}"] = 1.0
            for query_token in sorted(q)[:20]:
                features[f"category_query={cat}/{query_token}"] = 1.0
            features[f"category_recall={cat}"] = features["title_query_recall"]
            features[f"category_accessory={cat}"] = features["accessory_product_only"]
    for term in common:
        features[f"shared={term}"] = 1.0
    if probabilities:
        probs = row["base_probabilities"]
        for label, probability in zip(LABELS, probs):
            features[f"base_probability={label}"] = probability
            features[f"base_logprob={label}"] = np.log(max(1e-7, probability))
            features[f"base_x_recall={label}"] = (
                probability * features["title_query_recall"]
            )
    return features


def exact_base_stage(rows: list[dict]) -> np.ndarray:
    probs = np.asarray([row["base_probabilities"] for row in rows])
    return (probs.argmax(axis=1) == 0) & (probs[:, 0] >= 0.95)


def upper_binomial(errors: int, trials: int) -> float | None:
    if not trials:
        return None
    return (
        1.0 if errors == trials else float(beta.ppf(0.95, errors + 1, trials - errors))
    )


def evaluate(
    rows: list[dict],
    labels: np.ndarray,
    accepted: np.ndarray,
    *,
    seed: int = 20261003,
    repetitions: int = 2000,
) -> dict:
    truth = np.array([LABELS.index(row["reference_label"]) for row in rows])
    correct = labels == truth
    queries = [normalise(row["request"]["query"]) for row in rows]
    groups = sorted(set(queries))
    query_idx = {q: i for i, q in enumerate(groups)}
    counts = np.zeros((len(groups), 2), dtype=int)
    for q, is_accepted, is_correct in zip(queries, accepted, correct):
        if is_accepted:
            counts[query_idx[q]] += (int(is_correct), 1)
    rng = np.random.default_rng(seed)
    acc = []
    for _ in range(repetitions):
        total = counts[rng.integers(len(groups), size=len(groups))].sum(axis=0)
        if total[1]:
            acc.append(total[0] / total[1])
    per_class = {}
    matrix = np.zeros((4, 4), dtype=int)
    for expected, predicted, is_accepted in zip(truth, labels, accepted):
        if is_accepted:
            matrix[expected, predicted] += 1
    for i, label in enumerate(LABELS):
        selected = accepted & (labels == i)
        n = int(selected.sum())
        good = int((selected & correct).sum())
        per_class[label] = {
            "accepted": n,
            "correct": good,
            "precision": good / n if n else None,
            "precision_lower_one_sided_95": float(beta.ppf(0.05, good, n - good + 1))
            if good
            else 0.0
            if n
            else None,
        }
    irrelevant = truth == 3
    exact = accepted & (labels == 0)
    harmful = exact & irrelevant
    harmful_queries = {q for q, h in zip(queries, harmful) if h}
    irrelevant_queries = {q for q, h in zip(queries, irrelevant) if h}
    exact_queries = {q for q, h in zip(queries, exact) if h}
    n = int(accepted.sum())
    return {
        "pairs": len(rows),
        "queries": len(groups),
        "accepted": n,
        "accepted_queries": sum(counts[:, 1] > 0).item(),
        "coverage": n / len(rows),
        "accuracy": int((accepted & correct).sum()) / n if n else None,
        "accuracy_query_bootstrap_interval_95": [
            float(v) for v in np.quantile(acc, (0.025, 0.975))
        ]
        if acc
        else None,
        "per_class": per_class,
        "confusion_true_rows_prediction_columns_ESCI": matrix.tolist(),
        "irrelevant_to_exact_errors": int(harmful.sum()),
        "irrelevant_pairs": int(irrelevant.sum()),
        "irrelevant_to_exact_pair_upper_one_sided_95": upper_binomial(
            int(harmful.sum()), int(irrelevant.sum())
        ),
        "exact_contamination_pair_upper_one_sided_95": upper_binomial(
            int(harmful.sum()), int(exact.sum())
        ),
        "irrelevant_to_exact_query_incidence_upper_one_sided_95": upper_binomial(
            len(harmful_queries), len(irrelevant_queries)
        ),
        "exact_contamination_query_incidence_upper_one_sided_95": upper_binomial(
            len(harmful_queries), len(exact_queries)
        ),
    }


def choose_thresholds(truth: np.ndarray, probabilities: np.ndarray) -> dict:
    """Select independently per class from the fixed grid on calibration only."""
    predictions = probabilities.argmax(axis=1)
    choices = {}
    for i, label in enumerate(LABELS):
        chosen = None
        evidence = []
        for threshold in THRESHOLDS:
            selected = (predictions == i) & (probabilities[:, i] >= threshold)
            support = int(selected.sum())
            correct = int((selected & (truth == i)).sum())
            precision = correct / support if support else None
            evidence.append(
                {"threshold": threshold, "support": support, "precision": precision}
            )
            # Exploratory screen only. Formal uncertainty/sample requirements remain separate.
            if (
                chosen is None
                and support >= 20
                and precision is not None
                and precision >= 0.98
            ):
                chosen = threshold
        choices[label] = {"threshold": chosen, "calibration_grid": evidence}
    return choices


def apply_thresholds(
    probabilities: np.ndarray, choices: dict
) -> tuple[np.ndarray, np.ndarray]:
    predicted = probabilities.argmax(axis=1)
    accepted = np.zeros(len(predicted), dtype=bool)
    for i, label in enumerate(LABELS):
        threshold = choices[label]["threshold"]
        if threshold is not None:
            accepted |= (predicted == i) & (probabilities[:, i] >= threshold)
    return predicted, accepted


def load_development(source: Path, seed: str) -> list[dict]:
    # Intentionally no arbitrary source CLI: this survey cannot load confirmation.
    inputs = [
        json.loads(line)
        for line in (source / "inputs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    references = {
        (str(row["query_id"]), row["product_id"]): row
        for row in map(
            json.loads,
            (source / "references.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    }
    predictions = {
        (str(row["query_id"]), row["product_id"]): row
        for row in map(
            json.loads,
            (source / "inference-01" / "predictions.jsonl")
            .read_text(encoding="utf-8")
            .splitlines(),
        )
    }
    rows = []
    for original in inputs:
        key = (str(original["query_id"]), original["product_id"])
        row = dict(original)
        row["reference_label"] = references[key]["label"]
        row["base_probabilities"] = predictions[key]["probabilities"]
        row["partition"] = query_partition(row["request"]["query"], seed)
        rows.append(row)
    assert (
        len(rows) == 6525
        and len({normalise(row["request"]["query"]) for row in rows}) == 400
    )
    return rows


def run(state: Path, destination: Path) -> dict:
    started = time.monotonic()
    source = state / "esci-packaging" / "label-calibration-20261003"
    seed = "esci-gap-cpu-survey-20261003-v1"
    rows = load_development(source, seed)
    split = {
        name: np.array([i for i, row in enumerate(rows) if row["partition"] == name])
        for name in ("fit", "calibration", "evaluation")
    }
    truth = np.array([LABELS.index(row["reference_label"]) for row in rows])
    fit, calibration, test = (split[k] for k in ("fit", "calibration", "evaluation"))
    test_rows = [rows[i] for i in test]
    base = exact_base_stage(test_rows)
    report = {
        "kind": "esci-gap-cpu-specialist-development-survey",
        "schema_version": 1,
        "gate_eligible": False,
        "source": str(source),
        "seed": seed,
        "source_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "libraries": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "sklearn": sklearn.__version__,
        },
        "source_sha256": {
            name: hashlib.sha256((source / name).read_bytes()).hexdigest()
            for name in (
                "inputs.jsonl",
                "references.jsonl",
                "inference-01/predictions.jsonl",
            )
        },
        "partitions": {
            name: {
                "pairs": len(idx),
                "queries": len({normalise(rows[i]["request"]["query"]) for i in idx}),
                "labels": dict(Counter(rows[i]["reference_label"] for i in idx)),
            }
            for name, idx in split.items()
        },
        "category_audit": {
            "category_present": sum(
                row["product"].get("category") not in (None, "", "Uncategorised")
                for row in rows
            ),
            "category_path_present": sum(
                bool(row["product"].get("category_path")) for row in rows
            ),
            "product_type_present": sum(
                bool(row["product"].get("product_type")) for row in rows
            ),
        },
        "base_exact_095": evaluate(test_rows, np.zeros(len(test), dtype=int), base),
        "limitations": [
            "All partitions come from an already exposed development cohort; this is not fresh confirmation.",
            "Calibration selects thresholds; evaluation reports cannot qualify or activate a model.",
            "Observed agreement with published labels does not establish quality on unlabelled retrieved gaps.",
            "Binomial pair intervals ignore query clustering; query incidence guards and whole-query accuracy bootstrap are reported separately.",
            "The 0.95 Exact first stage is an exploratory comparator, not a qualified production policy.",
        ],
        "candidates": [],
    }
    candidates = [
        ("lexical", False, False, False, "linear"),
        ("lexical_category", True, False, False, "linear"),
        ("probability_lexical", False, True, False, "linear"),
        ("probability_lexical_category", True, True, False, "linear"),
        ("sparse_text_category", True, False, True, "linear"),
        ("probability_only", False, True, False, "probability_only"),
        ("probability_numeric", False, True, False, "numeric_linear"),
        ("probability_numeric_hist", False, True, False, "hist"),
        ("probability_numeric_trees", False, True, False, "trees"),
    ]
    for name, categories, probabilities, text, learner in candidates:
        began = time.monotonic()
        dictionaries = [
            relation_features(row, categories=categories, probabilities=probabilities)
            for row in rows
        ]
        if learner == "probability_only":
            dictionaries = [
                {
                    k: v
                    for k, v in dictionary.items()
                    if k.startswith(("base_probability=", "base_logprob="))
                }
                for dictionary in dictionaries
            ]
        elif learner in ("numeric_linear", "hist", "trees"):
            dictionaries = [
                {
                    k: v
                    for k, v in dictionary.items()
                    if "=" not in k or k.startswith("base_")
                }
                for dictionary in dictionaries
            ]
        vectorizer = DictVectorizer()
        x_fit = vectorizer.fit_transform(dictionaries[i] for i in fit)
        # Binary category/term indicators retain unit scale, including rare terms.
        scaler = MaxAbsScaler()
        x_fit = scaler.fit_transform(x_fit)
        x_calibration = scaler.transform(
            vectorizer.transform(dictionaries[i] for i in calibration)
        )
        x_test = scaler.transform(vectorizer.transform(dictionaries[i] for i in test))
        if text:
            q = [normalise(row["request"]["query"]) for row in rows]
            product = [
                normalise(
                    (row["product"].get("title") or "")
                    + " "
                    + (row["product"].get("description") or "")[:3000]
                )
                for row in rows
            ]
            for texts in (q, product):
                tfidf = TfidfVectorizer(
                    ngram_range=(1, 2), min_df=2, max_features=15000, sublinear_tf=True
                )
                x_fit = sparse.hstack(
                    [x_fit, tfidf.fit_transform(texts[i] for i in fit)], format="csr"
                )
                x_calibration = sparse.hstack(
                    [x_calibration, tfidf.transform(texts[i] for i in calibration)],
                    format="csr",
                )
                x_test = sparse.hstack(
                    [x_test, tfidf.transform(texts[i] for i in test)], format="csr"
                )
        if learner == "hist":
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
        elif learner == "trees":
            model = ExtraTreesClassifier(
                n_estimators=200,
                max_depth=12,
                min_samples_leaf=8,
                max_features=0.8,
                n_jobs=2,
                random_state=20261003,
            )
        else:
            model = LogisticRegression(
                C=1.0 if probabilities else 0.1, max_iter=2000, solver="lbfgs", n_jobs=1
            )
        model.fit(x_fit, truth[fit])
        calibration_probs = model.predict_proba(x_calibration)
        test_probs = model.predict_proba(x_test)
        assert list(model.classes_) == list(range(4))
        choices = choose_thresholds(truth[calibration], calibration_probs)
        predicted, accepted = apply_thresholds(test_probs, choices)
        incremental = accepted & ~base
        combined_predictions = predicted.copy()
        combined_predictions[base] = 0
        result = {
            "name": name,
            "seconds": time.monotonic() - began,
            "features": int(x_fit.shape[1]),
            "model_parameters": model.get_params(),
            "thresholds": choices,
            "standalone": evaluate(test_rows, predicted, accepted),
            "residual_added": evaluate(test_rows, predicted, incremental),
            "cascade": evaluate(test_rows, combined_predictions, accepted | base),
            "argmax_accuracy_unfiltered": float((predicted == truth[test]).mean()),
        }
        report["candidates"].append(result)
        destination.mkdir(parents=True, exist_ok=True)
        with (destination / f"{name}-evaluation-predictions.jsonl").open(
            "w", encoding="utf-8", newline="\n"
        ) as out:
            for row, probs, pred, yes, existing in zip(
                test_rows, test_probs, predicted, accepted, base
            ):
                out.write(
                    json.dumps(
                        {
                            "query_id": row["query_id"],
                            "product_id": row["product_id"],
                            "probabilities_ESCI": probs.tolist(),
                            "prediction": LABELS[pred],
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
                    "seconds": round(result["seconds"], 2),
                    "added": result["residual_added"]["accepted"],
                    "added_accuracy": result["residual_added"]["accuracy"],
                    "cascade_coverage": result["cascade"]["coverage"],
                }
            ),
            flush=True,
        )
    report["seconds"] = time.monotonic() - started
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.state, args.output)
