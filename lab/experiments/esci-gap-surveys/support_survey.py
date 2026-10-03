"""Survey published same-query support for unresolved pairs on exposed development data."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

LABELS = ("E", "S", "C", "I")
SEED = "esci-published-support-survey-20261003-v1"
RULES = (
    ("nearest-080", 0.80, "all"),
    ("nearest-090", 0.90, "all"),
    ("nearest-095", 0.95, "all"),
    ("nearest-090-nonexact", 0.90, "nonexact"),
    ("nearest-090-agreement", 0.90, "agreement"),
    ("nearest-080-role", 0.80, "role"),
    ("nearest-090-model-veto", 0.90, "model-veto"),
    ("identical-title", 1.0, "identical"),
)


def normalise(text):
    return " ".join(str(text).lower().split())


def pair(row):
    return row["query_id"], row["product_id"]


def support_partition(rows):
    """Choose supports by identifiers only; target labels never select supports."""
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row["query_key"]].append(index)
    supports, targets = {}, []
    for key, indices in groups.items():
        ordered = sorted(
            indices,
            key=lambda i: sha256(
                f"{SEED}|{key}|{rows[i]['product_id']}".encode()
            ).hexdigest(),
        )
        count = min(len(ordered) - 1, max(1, int(len(ordered) * 0.30)))
        if not count:
            continue
        supports[key] = ordered[:count]
        targets.extend(ordered[count:])
    return supports, sorted(targets)


def numbers(text):
    return set(re.findall(r"\b[a-z]*\d+[a-z\d-]*\b", normalise(text)))


def interval(queries, numerator, denominator, repetitions=5000):
    unique, inverse = np.unique(queries, return_inverse=True)
    grouped = np.zeros((len(unique), 2))
    np.add.at(grouped, inverse, np.column_stack((numerator, denominator)))
    rng = np.random.default_rng(20261003)
    estimates = []
    for start in range(0, repetitions, 100):
        selected = rng.integers(
            len(unique), size=(min(100, repetitions - start), len(unique))
        )
        sums = grouped[selected].sum(axis=1)
        if np.any(sums[:, 1] == 0):
            return None
        estimates.extend(sums[:, 0] / sums[:, 1])
    return np.quantile(estimates, [0.025, 0.975]).tolist()


def metrics(queries, truth, emitted):
    accepted = emitted != ""
    correct = accepted & (emitted == truth)
    irrelevant = truth == "I"
    harmful = irrelevant & (emitted == "E")
    exact = emitted == "E"
    return {
        "targets": len(truth),
        "target_queries": len(set(queries)),
        "accepted": int(accepted.sum()),
        "accepted_queries": len(set(queries[accepted])),
        "coverage": float(accepted.mean()),
        "accepted_accuracy": float(correct.sum() / accepted.sum())
        if accepted.any()
        else None,
        "accepted_accuracy_interval": interval(queries, correct, accepted),
        "irrelevant_reference_pairs": int(irrelevant.sum()),
        "irrelevant_reference_queries": len(set(queries[irrelevant])),
        "irrelevant_to_exact": int(harmful.sum()),
        "irrelevant_to_exact_rate": float(harmful.sum() / irrelevant.sum())
        if irrelevant.any()
        else None,
        "irrelevant_to_exact_interval": interval(queries, harmful, irrelevant),
        "accepted_exact": int(exact.sum()),
        "accepted_exact_irrelevant_contamination": float(harmful.sum() / exact.sum())
        if exact.any()
        else None,
        "zero_error_bootstrap_is_not_qualification": True,
        "emitted_counts": dict(Counter(emitted[accepted])),
        "confusion": {
            label: {
                prediction: int(((truth == label) & (emitted == prediction)).sum())
                for prediction in (*LABELS, "")
            }
            for label in LABELS
        },
    }


def read_rows(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line
    ]


def run(development, output, embeddings=None):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    files = {
        name: development / name
        for name in (
            "inputs.jsonl",
            "references.jsonl",
            "inference-01/predictions.jsonl",
        )
    }
    plan = {
        "kind": "esci-published-support-exploratory-survey-v1",
        "source_hashes": {
            name: sha256(path.read_bytes()).hexdigest() for name, path in files.items()
        },
        "rules": RULES,
        "seed": SEED,
        "support_fraction": 0.30,
        "baseline": "decider-4 Exact confidence >=0.95",
        "feature_contract": (
            "MiniLM title cosine; published support only; no target reference inputs"
            if embeddings
            else "char_wb3-5 title TF-IDF cosine; published support only; no target reference inputs"
        ),
        "query_partitions": "SHA256(seed|query_key) first byte below128 development; other half check",
        "upstream_exposure": "unknown; this is already exposed development, not confirmation",
        "gate_eligible": False,
    }
    if embeddings:
        receipt = json.loads((embeddings / "receipt.json").read_text(encoding="utf-8"))
        embedding_plan = json.loads(
            (embeddings / "plan.json").read_text(encoding="utf-8")
        )
        embedding_file = embeddings / "embeddings.npz"
        if (
            embedding_plan["inputs_sha256"] != plan["source_hashes"]["inputs.jsonl"]
            or receipt["embeddings_sha256"]
            != sha256(embedding_file.read_bytes()).hexdigest()
            or receipt["reference_labels_read"] is not False
        ):
            raise ValueError("Embedding source or checksum differs")
        plan["embedding_receipt_sha256"] = sha256(
            (embeddings / "receipt.json").read_bytes()
        ).hexdigest()
    (output / "plan.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8"
    )
    # The fixed survey plan is durable before opening reference labels.
    inputs = read_rows(files["inputs.jsonl"])
    references = {
        pair(row): row["label"] for row in read_rows(files["references.jsonl"])
    }
    predictions = {
        pair(row): row for row in read_rows(files["inference-01/predictions.jsonl"])
    }
    if (
        len(inputs) != len(references)
        or set(map(pair, inputs)) != references.keys()
        or references.keys() != predictions.keys()
    ):
        raise ValueError("Input, reference and prediction pairs differ")
    supports, targets = support_partition(inputs)
    titles = [normalise(row["product"]["title"]) for row in inputs]
    if embeddings:
        vectors = np.load(embeddings / "embeddings.npz")["title"]
        if vectors.shape[0] != len(inputs) or not np.isfinite(vectors).all():
            raise ValueError("Embedding membership or values differ")
    else:
        vectoriser = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=100000
        )
        vectors = vectoriser.fit_transform(titles)
    selected, similarity = [], []
    for index in targets:
        candidates = supports[inputs[index]["query_key"]]
        if index in candidates or any(
            pair(inputs[index]) == pair(inputs[j]) for j in candidates
        ):
            raise ValueError("Target reference leaked into support")
        scores = vectors[index] @ vectors[candidates].T
        if not embeddings:
            scores = scores.toarray()[0]
        best = int(np.argmax(scores))
        selected.append(candidates[best])
        similarity.append(float(scores[best]))
    truth = np.array([references[pair(inputs[i])] for i in targets])
    queries = np.array([inputs[i]["query_key"] for i in targets])
    source_labels = np.array([references[pair(inputs[i])] for i in selected])
    similarity = np.array(similarity)
    model = np.array([predictions[pair(inputs[i])]["probabilities"] for i in targets])
    baseline = np.where(
        (model.argmax(axis=1) == 0) & (model.max(axis=1) >= 0.95), "E", ""
    )
    partitions = np.array(
        [
            "development"
            if sha256(f"{SEED}|{key}".encode()).digest()[0] < 128
            else "check"
            for key in queries
        ]
    )
    results = []
    for name, threshold, mode in RULES:
        accepted = similarity >= threshold
        if mode == "nonexact":
            accepted &= source_labels != "E"
        if mode == "agreement":
            accepted &= (np.array(LABELS)[model.argmax(axis=1)] == source_labels) & (
                model.max(axis=1) >= 0.50
            )
        if mode in ("role", "model-veto", "identical"):
            for position, (target, support) in enumerate(
                zip(targets, selected, strict=True)
            ):
                a, b = inputs[target]["product"], inputs[support]["product"]
                if mode == "role":
                    accepted[position] &= bool(
                        a["category_path"]
                        and b["category_path"]
                        and a["category_path"][-1] == b["category_path"][-1]
                    )
                elif mode == "model-veto" and source_labels[position] == "E":
                    accepted[position] &= numbers(
                        inputs[target]["request"]["query"]
                    ).issubset(numbers(titles[target]))
                elif mode == "identical":
                    accepted[position] = titles[target] == titles[support]
        emitted = np.where(accepted, source_labels, "")
        incremental = np.where(baseline == "", emitted, "")
        cascade = np.where(baseline != "", baseline, incremental)
        results.append(
            {
                "rule": name,
                "partitions": {
                    part: {
                        "support_prediction": metrics(
                            queries[mask], truth[mask], emitted[mask]
                        ),
                        "increment_after_exact095": metrics(
                            queries[mask], truth[mask], incremental[mask]
                        ),
                        "cascade": metrics(queries[mask], truth[mask], cascade[mask]),
                    }
                    for part in ("development", "check")
                    for mask in [partitions == part]
                },
            }
        )
    report = {
        "kind": plan["kind"],
        "plan_sha256": sha256((output / "plan.json").read_bytes()).hexdigest(),
        "input_pairs": len(inputs),
        "source_support_pairs": sum(map(len, supports.values())),
        "target_pairs": len(targets),
        "reference_labels_as_target_features": False,
        "all_predictions_remain_model_predictions": True,
        "gate_eligible": False,
        "results": results,
        "elapsed_seconds": time.monotonic() - started,
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "targets": len(targets),
                "support_pairs": report["source_support_pairs"],
                "seconds": report["elapsed_seconds"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path)
    arguments = parser.parse_args()
    run(arguments.development, arguments.output, arguments.embeddings)
