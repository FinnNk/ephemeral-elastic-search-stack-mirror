"""Generate label-free CPU NLI features, then screen fixed development specialists."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import time

MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"
STATE = Path(
    os.environ.get("LAB_STATE_DIR", Path(__file__).resolve().parents[3] / ".lab")
)
DEVELOPMENT = STATE / "esci-packaging/label-calibration-20261003"
HYPOTHESES = (
    "This product is the {query} requested by the customer.",
    "This product is a usable alternative to the {query} requested by the customer.",
    "This product is an accessory used with the {query} requested by the customer.",
)


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def checksum(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def texts(pair):
    """Only request and product fields enter the frozen NLI premise/hypotheses."""
    product = pair["product"]
    category = " > ".join(str(part) for part in (product.get("category_path") or []))
    premise = "\n".join(
        [
            "Product: " + (product.get("title") or ""),
            "Brand: " + (product.get("brand") or ""),
            "Category: " + category,
            "Description: " + (product.get("description") or "")[:2000],
            "Details: " + (product.get("bullets") or "")[:1000],
        ]
    )
    return [
        (premise, template.format(query=pair["request"]["query"]))
        for template in HYPOTHESES
    ]


def generate(output):
    from huggingface_hub import snapshot_download
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    inputs = [
        json.loads(line)
        for line in (DEVELOPMENT / "inputs.jsonl").read_bytes().splitlines()
        if line
    ]
    if len(inputs) != 6525:
        raise ValueError(
            "Only the fixed 6,525 exposed development inputs are authorised."
        )
    ordered = sorted(
        range(len(inputs)), key=lambda i: sha256(canonical(inputs[i])).hexdigest()
    )
    plan = {
        "kind": "esci-nli-feature-plan",
        "source_sha256": checksum(__file__),
        "input_sha256": checksum(DEVELOPMENT / "inputs.jsonl"),
        "model": MODEL,
        "revision": REVISION,
        "hypotheses": list(HYPOTHESES),
        "labels": ["contradiction", "entailment", "neutral"],
        "device": "cpu",
        "threads": 4,
        "context": 256,
        "batch_pairs": 8,
        "pilot_pairs": 256,
        "maximum_seconds": 900,
        "pilot_order_sha256": sha256(canonical(ordered[:256])).hexdigest(),
        "reference_labels_read": False,
    }
    (output / "plan.json").write_bytes(canonical(plan))
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    local = snapshot_download(
        MODEL,
        revision=REVISION,
        cache_dir=str(STATE / "esci-gap-surveys/nli-cache"),
        token=False,
        max_workers=2,
        allow_patterns=[
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
        ],
    )
    tokenizer = AutoTokenizer.from_pretrained(
        local, local_files_only=True, trust_remote_code=False
    )
    model = (
        AutoModelForSequenceClassification.from_pretrained(
            local, local_files_only=True, trust_remote_code=False, use_safetensors=True
        )
        .to("cpu")
        .eval()
    )
    if model.config.num_labels != 3:
        raise ValueError("Pinned NLI model must return exactly three logits.")
    model_labels = {str(k): str(v).lower() for k, v in model.config.id2label.items()}
    if model_labels != {"0": "contradiction", "1": "entailment", "2": "neutral"}:
        raise ValueError("Pinned model labels differ from the declared NLI contract.")
    metadata = {
        "model_labels": model_labels,
        "parameters": sum(p.numel() for p in model.parameters()),
        "device": str(next(model.parameters()).device),
        "snapshot": str(local),
        "files": {p.name: checksum(p) for p in Path(local).iterdir() if p.is_file()},
        "startup_seconds": time.monotonic() - started,
    }
    (output / "model.json").write_bytes(canonical(metadata))
    infer_started, pilot_seconds = time.monotonic(), None
    complete, rows_written = False, 0
    with (output / "features.jsonl").open("xb") as destination:
        for offset in range(0, len(ordered), 8):
            if time.monotonic() - started >= 900:
                break
            batch_indices = ordered[offset : offset + 8]
            batch_text = [text for i in batch_indices for text in texts(inputs[i])]
            encoded = tokenizer(
                [value[0] for value in batch_text],
                [value[1] for value in batch_text],
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            with torch.inference_mode():
                logits = model(**encoded).logits
                probabilities = logits.softmax(dim=1)
            logits, probabilities = logits.cpu().tolist(), probabilities.cpu().tolist()
            for j, index in enumerate(batch_indices):
                pair = inputs[index]
                feature = {
                    "input_index": index,
                    "query_id": pair["query_id"],
                    "product_id": pair["product_id"],
                    "input_sha256": sha256(canonical(pair)).hexdigest(),
                    "logits": logits[j * 3 : (j + 1) * 3],
                    "probabilities": probabilities[j * 3 : (j + 1) * 3],
                }
                destination.write(canonical(feature))
                rows_written += 1
            if rows_written == 256:
                destination.flush()
                pilot_seconds = time.monotonic() - infer_started
                projected = pilot_seconds / 256 * len(ordered)
                (output / "pilot.json").write_bytes(
                    canonical(
                        {
                            "pairs": 256,
                            "seconds": pilot_seconds,
                            "pairs_per_second": 256 / pilot_seconds,
                            "projected_full_inference_seconds": projected,
                            "remaining_budget_seconds": 900
                            - (time.monotonic() - started),
                        }
                    )
                )
                if projected > 900 - metadata["startup_seconds"]:
                    break
        complete = rows_written == len(inputs)
    result = {
        "kind": "esci-nli-feature-receipt",
        "complete": complete,
        "pairs": rows_written,
        "seconds": time.monotonic() - started,
        "features_sha256": checksum(output / "features.jsonl"),
        "plan_sha256": checksum(output / "plan.json"),
        "reference_labels_read": False,
        "gate_eligible": False,
    }
    (output / "feature-receipt.json").write_bytes(canonical(result))
    print(json.dumps(result))


def evaluate(output):
    import numpy as np
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.preprocessing import MaxAbsScaler
    from sklearn.linear_model import LogisticRegression
    import specialist_survey as core

    receipt = json.loads((output / "feature-receipt.json").read_bytes())
    if not receipt["complete"] or receipt["features_sha256"] != checksum(
        output / "features.jsonl"
    ):
        raise ValueError(
            "The complete label-free feature artefact is required before fitting."
        )
    plan = {
        "kind": "esci-nli-classifier-plan",
        "features_sha256": receipt["features_sha256"],
        "source_sha256": checksum(__file__),
        "seed": "esci-gap-cpu-survey-20261003-v1",
        "candidates": ["nli-only", "nli-base", "nli-base-lexical-category"],
        "learner": {"C": 1, "max_iter": 2000, "solver": "lbfgs", "n_jobs": 1},
        "reference_sha256": checksum(DEVELOPMENT / "references.jsonl"),
        "base_prediction_sha256": checksum(
            DEVELOPMENT / "inference-01/predictions.jsonl"
        ),
        "thresholds": list(core.THRESHOLDS),
        "minimum_calibration_support": 20,
        "minimum_observed_calibration_precision": 0.98,
        "gate_eligible": False,
    }
    (output / "classifier-plan.json").write_bytes(canonical(plan))
    rows = core.load_development(DEVELOPMENT, plan["seed"])
    features = {
        int(row["input_index"]): row
        for row in map(
            json.loads, (output / "features.jsonl").read_bytes().splitlines()
        )
    }
    if set(features) != set(range(len(rows))):
        raise ValueError(
            "NLI features must cover every development input exactly once."
        )
    for i, row in enumerate(rows):
        original = {
            k: v
            for k, v in row.items()
            if k not in ("reference_label", "base_probabilities", "partition")
        }
        if features[i]["input_sha256"] != sha256(canonical(original)).hexdigest():
            raise ValueError("NLI features differ from development input bytes.")
    split = {
        name: np.array([i for i, row in enumerate(rows) if row["partition"] == name])
        for name in ("fit", "calibration", "evaluation")
    }
    fit, calibration, test = (split[k] for k in ("fit", "calibration", "evaluation"))
    truth = np.array([core.LABELS.index(row["reference_label"]) for row in rows])
    test_rows = [rows[i] for i in test]
    base = core.exact_base_stage(test_rows)
    report = {
        "kind": "esci-nli-specialist-development-survey",
        "gate_eligible": False,
        "partitions": {
            k: {
                "pairs": len(v),
                "queries": len(
                    {core.normalise(rows[i]["request"]["query"]) for i in v}
                ),
            }
            for k, v in split.items()
        },
        "baseline": core.evaluate(test_rows, np.zeros(len(test), dtype=int), base),
        "candidates": [],
        "limits": [
            "Exposed development queries only; evaluation is not independent confirmation.",
            "NLI probabilities are features, not ESCI labels.",
            "No inferred labels are activated or gate eligible.",
        ],
    }
    for candidate in plan["candidates"]:
        dictionaries = []
        for i, row in enumerate(rows):
            dictionary = {
                f"nli/{h}/{label}": value
                for h, values in enumerate(features[i]["probabilities"])
                for label, value in enumerate(values)
            }
            if candidate == "nli-base":
                dictionary.update(
                    {
                        f"base/{label}": value
                        for label, value in enumerate(row["base_probabilities"])
                    }
                )
            if candidate == "nli-base-lexical-category":
                dictionary.update(
                    core.relation_features(row, categories=True, probabilities=True)
                )
            dictionaries.append(dictionary)
        vectorizer, scaler = DictVectorizer(), MaxAbsScaler()
        xfit = scaler.fit_transform(
            vectorizer.fit_transform(dictionaries[i] for i in fit)
        )
        xcal = scaler.transform(
            vectorizer.transform(dictionaries[i] for i in calibration)
        )
        xtest = scaler.transform(vectorizer.transform(dictionaries[i] for i in test))
        learner = LogisticRegression(**plan["learner"])
        learner.fit(xfit, truth[fit])
        choices = core.choose_thresholds(
            truth[calibration], learner.predict_proba(xcal)
        )
        predicted, accepted = core.apply_thresholds(
            learner.predict_proba(xtest), choices
        )
        incremental = accepted & ~base
        cascade_labels = predicted.copy()
        cascade_labels[base] = 0
        report["candidates"].append(
            {
                "name": candidate,
                "thresholds": choices,
                "standalone": core.evaluate(test_rows, predicted, accepted),
                "incremental": core.evaluate(test_rows, predicted, incremental),
                "cascade": core.evaluate(test_rows, cascade_labels, accepted | base),
            }
        )
    (output / "report.json").write_bytes(canonical(report))
    print(json.dumps({"candidates": len(report["candidates"]), "output": str(output)}))


def decode_pilot(probabilities, acceptance_threshold=None):
    """Decode an exploratory entailment rule; scores are not ESCI probabilities."""
    entailments = [hypothesis[1] for hypothesis in probabilities]
    maximum = max(entailments)
    predicted = 3 if maximum < 0.5 else max(range(3), key=lambda i: entailments[i])
    proxy = 1 - maximum if predicted == 3 else maximum
    accepted = acceptance_threshold is None or proxy >= acceptance_threshold
    return predicted, accepted, proxy


def pilot_diagnostic(output):
    import numpy as np

    pilot = STATE / "esci-gap-surveys/nli-survey/attempt-02"
    output.mkdir(parents=True, exist_ok=False)
    receipt = json.loads((pilot / "feature-receipt.json").read_bytes())
    if receipt["pairs"] != 256 or receipt["features_sha256"] != checksum(
        pilot / "features.jsonl"
    ):
        raise ValueError("The frozen 256-pair feature pilot is required.")
    inference_plan = json.loads((pilot / "plan.json").read_bytes())
    model = json.loads((pilot / "model.json").read_bytes())
    if inference_plan["labels"] != ["contradiction", "entailment", "neutral"] or model[
        "model_labels"
    ] != {"0": "contradiction", "1": "entailment", "2": "neutral"}:
        raise ValueError(
            "Pilot entailment decoding differs from the frozen model contract."
        )
    plan = {
        "kind": "esci-nli-pilot-diagnostic-amendment",
        "source_sha256": checksum(__file__),
        "features_sha256": receipt["features_sha256"],
        "input_sha256": checksum(DEVELOPMENT / "inputs.jsonl"),
        "reference_sha256": checksum(DEVELOPMENT / "references.jsonl"),
        "rule": "E/S/C: greatest hypothesis entailment, unless all below0.5 then I. I proxy is1-max_entailment; E/S/C proxy ismax_entailment.",
        "acceptance_thresholds": [None, 0.8, 0.9],
        "gate_eligible": False,
        "purpose": "Fixed exploratory pilot quality signal, not calibrated ESCI probabilities or independent confirmation.",
    }
    (output / "amendment.json").write_bytes(canonical(plan))
    inputs = [
        json.loads(line)
        for line in (DEVELOPMENT / "inputs.jsonl").read_bytes().splitlines()
        if line
    ]
    features = [
        json.loads(line)
        for line in (pilot / "features.jsonl").read_bytes().splitlines()
        if line
    ]
    keys = {(feature["query_id"], feature["product_id"]) for feature in features}
    references = {
        (row["query_id"], row["product_id"]): row["label"]
        for line in (DEVELOPMENT / "references.jsonl").read_bytes().splitlines()
        if line
        and (row := json.loads(line))["query_id"] is not None
        and (row["query_id"], row["product_id"]) in keys
    }
    selected_inputs = []
    for feature in features:
        pair = inputs[feature["input_index"]]
        if sha256(canonical(pair)).hexdigest() != feature["input_sha256"] or (
            pair["query_id"],
            pair["product_id"],
        ) != (feature["query_id"], feature["product_id"]):
            raise ValueError("Pilot feature belongs to different input bytes.")
        selected_inputs.append(pair)
    if references.keys() != keys or len(keys) != 256:
        raise ValueError(
            "Exactly matching unique published development references are required."
        )
    labels = ("E", "S", "C", "I")
    truth = np.array(
        [
            labels.index(references[(feature["query_id"], feature["product_id"])])
            for feature in features
        ]
    )
    reports = []
    for threshold in plan["acceptance_thresholds"]:
        decoded = [
            decode_pilot(feature["probabilities"], threshold) for feature in features
        ]
        predicted, accepted = (
            np.array([row[0] for row in decoded]),
            np.array([row[1] for row in decoded]),
        )
        correct = accepted & (predicted == truth)
        per_class = {}
        for i, label in enumerate(labels):
            selected = accepted & (predicted == i)
            n, good, support = (
                int(selected.sum()),
                int((selected & (truth == i)).sum()),
                int((truth == i).sum()),
            )
            per_class[label] = {
                "reference_support": support,
                "accepted_predictions": n,
                "correct": good,
                "precision": good / n if n else None,
                "recall": good / support if support else None,
            }
        harmful = accepted & (predicted == 0) & (truth == 3)
        reports.append(
            {
                "threshold": threshold,
                "accepted": int(accepted.sum()),
                "coverage": float(accepted.mean()),
                "correct": int(correct.sum()),
                "accuracy": int(correct.sum()) / int(accepted.sum())
                if accepted.any()
                else None,
                "per_class": per_class,
                "confusion": {
                    label: {
                        other: int(((truth == i) & accepted & (predicted == j)).sum())
                        for j, other in enumerate(labels)
                    }
                    | {"abstain": int(((truth == i) & ~accepted).sum())}
                    for i, label in enumerate(labels)
                },
                "irrelevant_to_exact_errors": int(harmful.sum()),
                "irrelevant_to_exact_rate": int(harmful.sum()) / int((truth == 3).sum())
                if (truth == 3).any()
                else None,
                "accepted_exact_contamination": int(harmful.sum())
                / int((accepted & (predicted == 0)).sum())
                if (accepted & (predicted == 0)).any()
                else None,
            }
        )
    report = {
        "kind": "esci-nli-pilot-development-diagnostic",
        "gate_eligible": False,
        "pairs": 256,
        "queries": len({pair["query_key"] for pair in selected_inputs}),
        "category_available_pairs": sum(
            bool(pair["product"].get("category_path")) for pair in selected_inputs
        ),
        "amendment_sha256": checksum(output / "amendment.json"),
        "rules": reports,
        "limits": [
            "All labels are exposed development labels; this pilot is not confirmation.",
            "Three entailment scores and the1-max proxy are not four-class calibrated probabilities.",
            "Small hash-selected pilot supports a signal screen, not deployment, lab gap coverage or population-quality claims.",
        ],
    }
    (output / "report.json").write_bytes(canonical(report))
    print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("generate", "evaluate", "diagnostic"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        {"generate": generate, "evaluate": evaluate, "diagnostic": pilot_diagnostic}[
            args.mode
        ](args.output)
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = args.output / f"failure-{time.time_ns()}.json"
        failure.write_bytes(
            canonical(
                {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "mode": args.mode,
                    "gate_eligible": False,
                }
            )
        )
        raise


if __name__ == "__main__":
    main()
