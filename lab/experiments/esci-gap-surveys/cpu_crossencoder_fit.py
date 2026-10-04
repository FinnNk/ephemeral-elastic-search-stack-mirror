"""One bounded CPU adaptation of a pinned retrieval encoder to ESCI classes."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evaluation"))
from label_quality import query_key

MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
LABELS = ("E", "S", "C", "I")
SEED = "esci-fitted-specialists-20261004-v1"


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def rows(path):
    return [
        json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x
    ]


def write(path, value):
    with Path(path).open("xb") as f:
        f.write(canonical(value))


def group(row):
    q = query_key(row["request"]["query"])
    if row.get("query_key") != q:
        raise ValueError(
            "Fitting/development query key differs from the authoritative contract."
        )
    return q


def partitions(inputs):
    keys = sorted(
        {group(r) for r in inputs},
        key=lambda q: hashlib.sha256(f"{SEED}\0{q}".encode()).hexdigest(),
    )
    cut = math.floor(len(keys) * 0.7)
    return {q: "fit" if i < cut else "calibration" for i, q in enumerate(keys)}


def text(row):
    p = row["product"]
    return (
        row["request"]["query"],
        "\n".join(
            [
                p.get("title") or "",
                "Brand: " + (p.get("brand") or ""),
                "Category: " + " > ".join(p.get("category_path") or []),
                p.get("bullets") or "",
                p.get("description") or "",
            ]
        ),
    )


def truth_indices(inputs, references):
    mapping = {(r["query_id"], r["product_id"]): r for r in references}
    if len(mapping) != len(references):
        raise ValueError("Duplicate published references.")
    truth = []
    for row in inputs:
        ref = mapping[(row["query_id"], row["product_id"])]
        if ref["provenance"]["kind"] != "published" or ref["label"] not in LABELS:
            raise ValueError("Only published references are permitted.")
        truth.append(LABELS.index(ref["label"]))
    return truth


def train(args):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    started = time.monotonic()
    inputs = rows(args.pool / "inputs.jsonl")
    manifest = json.loads((args.pool / "manifest.json").read_bytes())
    for name, expected in manifest["files_sha256"].items():
        if sha(args.pool / name) != expected:
            raise ValueError("Frozen fitting-pool bytes changed.")
    split = partitions(inputs)
    if Counter(split.values()) != {"fit": 700, "calibration": 300}:
        raise ValueError("Expected the authoritative 1,000-query pool.")
    development = rows(args.development / "inputs.jsonl")
    if {group(r) for r in inputs} & {group(r) for r in development}:
        raise ValueError("Fitting queries overlap exposed development.")
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {
        "kind": "esci-cpu-crossencoder-adaptation-plan",
        "gate_eligible": False,
        "model": MODEL,
        "revision": REVISION,
        "source_sha256": sha(__file__),
        "pool_manifest_sha256": sha(args.pool / "manifest.json"),
        "pool_files_sha256": manifest["files_sha256"],
        "development_input_sha256": sha(args.development / "inputs.jsonl"),
        "partitions": split,
        "seed": SEED,
        "torch_seed": 20261004,
        "device": "cpu",
        "threads": 4,
        "head": "new four-class classification head; all encoder weights trainable",
        "labels": LABELS,
        "max_tokens": 128,
        "batch_size": 16,
        "epochs": 1,
        "optimizer": "AdamW",
        "learning_rate": 3e-5,
        "weight_decay": 0.01,
        "loss": "unweighted cross entropy",
        "gradient_clip": 1.0,
        "training_seconds_cap": 1800,
        "probe_updates": 64,
        "threshold_grid": [0.7, 0.8, 0.9, 0.95, 0.975, 0.99, 0.995],
        "calibration_support_minimum": 30,
        "calibration_precision_minimum": 0.98,
        "fields": [
            "request.query",
            "product.title",
            "product.brand",
            "product.category_path",
            "product.bullets",
            "product.description",
        ],
        "labels_opened": False,
        "limits": [
            "One candidate and one epoch; no model-selection search.",
            "Calibration is whole-query disjoint. Exposed development is a screen, not confirmation.",
            "Only original textual fields enter model input; identifiers and synthetic serving fields are excluded.",
        ],
    }
    write(args.output / "plan.json", plan)
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.manual_seed(20261004)
    tokenizer = AutoTokenizer.from_pretrained(
        args.snapshot, local_files_only=True, trust_remote_code=False
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        args.snapshot,
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        num_labels=4,
        ignore_mismatched_sizes=True,
        torch_dtype=torch.float32,
    ).to("cpu")
    if any(p.device.type != "cpu" for p in model.parameters()):
        raise ValueError("CPU model required.")
    strings = [text(r) for r in inputs]
    encoded = tokenizer(
        [x[0] for x in strings],
        [x[1] for x in strings],
        padding="max_length",
        truncation=True,
        max_length=128,
        return_tensors="pt",
    )
    # The only training-label access follows the immutable candidate/input/split plan.
    truth = torch.tensor(
        truth_indices(inputs, rows(args.pool / "references.jsonl")), dtype=torch.long
    )
    fit = [i for i, r in enumerate(inputs) if split[group(r)] == "fit"]
    generator = torch.Generator().manual_seed(20261004)
    order = [fit[i] for i in torch.randperm(len(fit), generator=generator).tolist()]
    steps = math.ceil(len(order) / 16)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-5, weight_decay=0.01)
    model.train()
    updates, loss_sum, status = 0, 0.0, "completed-one-epoch"
    learning_started = time.monotonic()
    with (args.output / "training.jsonl").open("x", encoding="utf-8") as f:
        for offset in range(0, len(order), 16):
            if time.monotonic() - started >= 1800:
                status = "training-time-cap"
                break
            batch = order[offset : offset + 16]
            optimizer.zero_grad(set_to_none=True)
            output = model(
                **{k: v[batch].to("cpu") for k, v in encoded.items()},
                labels=truth[batch],
            )
            if not torch.isfinite(output.loss):
                raise ValueError("Non-finite training loss.")
            output.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            updates += 1
            loss_sum += float(output.loss.detach())
            f.write(
                canonical(
                    {
                        "update": updates,
                        "loss": float(output.loss.detach()),
                        "seconds": time.monotonic() - learning_started,
                    }
                ).decode()
            )
            f.flush()
            if updates == 64:
                elapsed = time.monotonic() - learning_started
                projection = elapsed / updates * steps + learning_started - started
                write(
                    args.output / "probe.json",
                    {
                        "updates": updates,
                        "seconds": elapsed,
                        "planned_updates": steps,
                        "projected_seconds": projection,
                    },
                )
                if projection > 1800:
                    status = "probe-projected-training-time-cap"
                    break
    model.eval().save_pretrained(args.output / "weights", safe_serialization=True)
    tokenizer.save_pretrained(args.output / "weights")
    receipt = {
        "kind": "esci-cpu-crossencoder-training-receipt",
        "status": status,
        "updates": updates,
        "planned_updates": steps,
        "fit_pairs": len(fit),
        "fit_queries": 700,
        "calibration_queries": 300,
        "mean_training_loss": loss_sum / updates if updates else None,
        "elapsed_seconds": time.monotonic() - started,
        "device": "cpu",
        "gate_eligible": False,
        "plan_sha256": sha(args.output / "plan.json"),
        "weights_sha256": sha(args.output / "weights/model.safetensors"),
    }
    write(args.output / "training-receipt.json", receipt)
    print(json.dumps(receipt), flush=True)


def score(args):
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    path = Path(__file__).parents[1] / "esci-fitted-specialists/fit_specialists.py"
    plan = json.loads((args.output / "plan.json").read_bytes())
    receipt = json.loads((args.output / "training-receipt.json").read_bytes())
    if (
        receipt["status"] != "completed-one-epoch"
        or receipt["plan_sha256"] != sha(args.output / "plan.json")
        or receipt["weights_sha256"] != sha(args.output / "weights/model.safetensors")
    ):
        raise ValueError(
            "A completed, frozen one-epoch model is required for assessment."
        )
    for name, expected in plan["pool_files_sha256"].items():
        if sha(args.pool / name) != expected:
            raise ValueError(
                "Frozen fitting inputs or references changed before assessment."
            )
    if sha(args.development / "inputs.jsonl") != plan["development_input_sha256"]:
        raise ValueError("Exposed development inputs changed before assessment.")
    assessment_plan = {
        "kind": "esci-cpu-crossencoder-assessment-plan",
        "gate_eligible": False,
        "source_sha256": sha(__file__),
        "training_plan_sha256": sha(args.output / "plan.json"),
        "training_receipt_sha256": sha(args.output / "training-receipt.json"),
        "development_reference_sha256": sha(args.development / "references.jsonl"),
        "metrics_helper_sha256": sha(path),
    }
    if args.prefix is not None:
        prefix_receipt_path = args.prefix.with_suffix(".receipt.json")
        prefix_receipt = json.loads(prefix_receipt_path.read_bytes())
        if (
            prefix_receipt["predictions_sha256"] != sha(args.prefix)
            or prefix_receipt["original_inputs_sha256"]
            != plan["development_input_sha256"]
        ):
            raise ValueError(
                "Prior-stage prediction provenance differs from development."
            )
        assessment_plan["prefix_sha256"] = sha(args.prefix)
        assessment_plan["prefix_receipt_sha256"] = sha(prefix_receipt_path)
    write(args.output / "assessment-plan.json", assessment_plan)
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    model = (
        AutoModelForSequenceClassification.from_pretrained(
            args.output / "weights", local_files_only=True, use_safetensors=True
        )
        .to("cpu")
        .eval()
    )
    tokenizer = AutoTokenizer.from_pretrained(
        args.output / "weights", local_files_only=True
    )
    pool = rows(args.pool / "inputs.jsonl")
    cal_indices = [
        i for i, r in enumerate(pool) if plan["partitions"][group(r)] == "calibration"
    ]
    calibration = [pool[i] for i in cal_indices]
    development = rows(args.development / "inputs.jsonl")

    def probabilities(data, name):
        values = []
        for offset in range(0, len(data), 32):
            strings = [text(r) for r in data[offset : offset + 32]]
            encoded = tokenizer(
                [x[0] for x in strings],
                [x[1] for x in strings],
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            with torch.inference_mode():
                values.extend(torch.softmax(model(**encoded).logits, dim=1).tolist())
        result = np.asarray(values)
        with (args.output / (name + "-probabilities.npy")).open("xb") as f:
            np.save(f, result, allow_pickle=False)
        return result

    started = time.monotonic()
    probabilities(calibration, "calibration")
    probabilities(development, "development")
    scoring = {
        "kind": "esci-cpu-crossencoder-scoring-receipt",
        "gate_eligible": False,
        "assessment_plan_sha256": sha(args.output / "assessment-plan.json"),
        "calibration_pairs": len(calibration),
        "development_pairs": len(development),
        "elapsed_seconds": time.monotonic() - started,
        "device": "cpu",
        "assessment_references_opened": False,
        "files_sha256": {
            n: sha(args.output / n)
            for n in ("calibration-probabilities.npy", "development-probabilities.npy")
        },
    }
    write(args.output / "scoring-receipt.json", scoring)
    print(json.dumps(scoring), flush=True)


def evaluate(args):
    import numpy as np

    path = Path(__file__).parents[1] / "esci-fitted-specialists/fit_specialists.py"
    spec = importlib.util.spec_from_file_location("fitted_metric_helpers", path)
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    started = time.monotonic()
    scoring = json.loads((args.output / "scoring-receipt.json").read_bytes())
    plan = json.loads((args.output / "plan.json").read_bytes())
    assessment = json.loads((args.output / "assessment-plan.json").read_bytes())
    if scoring["assessment_plan_sha256"] != sha(
        args.output / "assessment-plan.json"
    ) or assessment["metrics_helper_sha256"] != sha(path):
        raise ValueError("Frozen assessment plan or metric implementation changed.")
    for name, expected in scoring["files_sha256"].items():
        if sha(args.output / name) != expected:
            raise ValueError("Frozen prediction bytes changed before gold assessment.")
    for name, expected in plan["pool_files_sha256"].items():
        if sha(args.pool / name) != expected:
            raise ValueError("Frozen fitting pool changed before gold assessment.")
    if (
        sha(args.development / "inputs.jsonl") != plan["development_input_sha256"]
        or sha(args.development / "references.jsonl")
        != assessment["development_reference_sha256"]
    ):
        raise ValueError("Frozen development data changed before gold assessment.")
    pool = rows(args.pool / "inputs.jsonl")
    calibration = [r for r in pool if plan["partitions"][group(r)] == "calibration"]
    development = rows(args.development / "inputs.jsonl")
    cal = np.load(args.output / "calibration-probabilities.npy", allow_pickle=False)
    dev = np.load(args.output / "development-probabilities.npy", allow_pickle=False)
    if (
        cal.shape != (len(calibration), 4)
        or dev.shape != (len(development), 4)
        or not np.isfinite(cal).all()
        or not np.isfinite(dev).all()
    ):
        raise ValueError("Invalid probability shapes or non-finite predictions.")
    # Gold used for calibration and development assessment only after predictions are frozen.
    cal_truth = np.array(
        truth_indices(calibration, rows(args.pool / "references.jsonl"))
    )
    dev_truth = np.array(
        truth_indices(development, rows(args.development / "references.jsonl"))
    )
    choices = helpers.thresholds(cal_truth, cal)
    pred = dev.argmax(axis=1)
    accepted = np.array(
        [
            choices[LABELS[i]]["threshold"] is not None
            and p[i] >= choices[LABELS[i]]["threshold"]
            for i, p in zip(pred, dev)
        ]
    )
    report = {
        "kind": "esci-cpu-crossencoder-development-screen",
        "gate_eligible": False,
        "thresholds": choices,
        "argmax": helpers.statistics(
            development, dev_truth, pred, np.ones(len(pred), dtype=bool)
        ),
        "selected": helpers.statistics(development, dev_truth, pred, accepted),
        "prediction_files_sha256": {
            n: sha(args.output / n)
            for n in ("calibration-probabilities.npy", "development-probabilities.npy")
        },
        "elapsed_seconds": time.monotonic() - started,
        "limits": [
            "Exposed development screen only; no independent confirmation or actual gap qualification.",
            "Zero-event bootstrap cannot establish harmful-error upper bounds.",
        ],
    }
    if args.prefix is not None:
        if assessment.get("prefix_sha256") != sha(args.prefix):
            raise ValueError("Frozen prior-stage predictions changed before assessment.")
        prefix = rows(args.prefix)
        if len(prefix) != len(development):
            raise ValueError("Frozen prefix must cover every development pair.")
        existing = np.array([r["prefix_accepted"] for r in prefix], dtype=bool)
        prior = np.array([LABELS.index(r["prediction"]) for r in prefix], dtype=int)
        for a, b in zip(prefix, development):
            if (a["query_id"], a["product_id"]) != (b["query_id"], b["product_id"]):
                raise ValueError("Frozen prefix order differs from development.")
        combined = pred.copy()
        combined[existing] = prior[existing]
        report.update(
            {
                "prefix_sha256": sha(args.prefix),
                "incremental": helpers.statistics(
                    development, dev_truth, pred, accepted & ~existing
                ),
                "cascade": helpers.statistics(
                    development, dev_truth, combined, accepted | existing
                ),
            }
        )
    write(args.output / "report.json", report)
    print(
        json.dumps(
            {
                "selected": int(accepted.sum()),
                "pairs": len(pred),
                "seconds": report["elapsed_seconds"],
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("train", "score", "evaluate"))
    for field in ("pool", "development", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--prefix", type=Path)
    args = parser.parse_args()
    {"train": train, "score": score, "evaluate": evaluate}[args.mode](args)


if __name__ == "__main__":
    main()
