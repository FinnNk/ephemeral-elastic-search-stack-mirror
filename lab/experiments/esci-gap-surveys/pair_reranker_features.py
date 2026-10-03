"""Measure pinned retrieval-model features on CPU, without reading ESCI labels.

The model produces a passage relevance logit, not an ESCI label or calibrated
probability. A separately fitted classifier must learn any use of that feature.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import time

MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
CONTRACTS = ("title-category", "catalogue-text")
MAX_TOKENS = 256


def product_text(row: dict, contract: str) -> str:
    """Use only original catalogue text; keep lab-only fields out of features."""
    if contract not in CONTRACTS:
        raise ValueError("Unknown field contract")
    product = row["product"]
    fields = [
        product.get("title") or "",
        "Brand: " + (product.get("brand") or ""),
        "Category: " + " > ".join(product.get("category_path") or []),
    ]
    if contract == "catalogue-text":
        fields.extend(
            [
                product.get("bullets") or "",
                product.get("description") or "",
            ]
        )
    return "\n".join(fields)


def probe_projection(completed: int, seconds: float, planned: int) -> float:
    if completed <= 0 or seconds <= 0:
        raise ValueError("A completed probe with positive duration is required")
    return planned * seconds / completed


def run(
    inputs: Path,
    output: Path,
    cache: Path,
    budget: float,
    pilot: int | None,
    quantise_linear: bool = False,
):
    output.mkdir(parents=True, exist_ok=False)
    rows = [
        json.loads(line)
        for line in inputs.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if pilot:
        # Selection uses text and identifiers, never labels, probabilities or scores.
        rows = sorted(
            rows,
            key=lambda row: sha256(
                (row["request"]["query"] + "\0" + row["product_id"]).encode()
            ).hexdigest(),
        )[:pilot]
    plan = {
        "kind": "esci-pair-reranker-features-v1",
        "source_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "model": MODEL,
        "revision": REVISION,
        "contracts": list(CONTRACTS),
        "input_sha256": sha256(inputs.read_bytes()).hexdigest(),
        "pairs": len(rows),
        "selection": "full input order"
        if not pilot
        else "label-free text/product hash pilot",
        "max_tokens": MAX_TOKENS,
        "batch_size": 16,
        "torch_threads": 4,
        "device": "cpu",
        "linear_weights": "torch dynamic int8" if quantise_linear else "float32",
        "budget_seconds": budget,
        "reference_labels_read": False,
        "gate_eligible": False,
        "output_meaning": "raw retrieval relevance logit; not an ESCI confidence",
    }
    (output / "plan.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8"
    )
    (output / "executed-source.py").write_bytes(Path(__file__).read_bytes())

    from huggingface_hub import snapshot_download
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    snapshot = Path(
        snapshot_download(
            MODEL,
            revision=REVISION,
            cache_dir=cache,
            allow_patterns=[
                "config.json",
                "model.safetensors",
                "tokenizer.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
                "vocab.txt",
                "README.md",
            ],
        )
    )
    file_hashes = {
        p.name: sha256(p.read_bytes()).hexdigest()
        for p in snapshot.iterdir()
        if p.is_file()
    }
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    model = (
        AutoModelForSequenceClassification.from_pretrained(
            snapshot, local_files_only=True
        )
        .to("cpu")
        .eval()
    )
    if quantise_linear:
        model = torch.ao.quantization.quantize_dynamic(
            model, {torch.nn.Linear}, dtype=torch.qint8
        )
    started = time.monotonic()
    truncated = 0
    result = []
    status = "completed"
    output_file = output / "features.jsonl"
    with output_file.open("w", encoding="utf-8") as handle:
        for start in range(0, len(rows), 16):
            chunk = rows[start : start + 16]
            # Both contracts for a pair stay in the same batch/probe.
            queries = [row["request"]["query"] for row in chunk for _ in CONTRACTS]
            products = [product_text(row, c) for row in chunk for c in CONTRACTS]
            full = tokenizer(queries, products, truncation=False)["input_ids"]
            truncated += sum(len(tokens) > MAX_TOKENS for tokens in full)
            encoded = tokenizer(
                queries,
                products,
                max_length=MAX_TOKENS,
                truncation=True,
                padding=True,
                return_tensors="pt",
            )
            with torch.inference_mode():
                logits = (
                    model(**encoded).logits.numpy().reshape(len(chunk), len(CONTRACTS))
                )
            for row, values in zip(chunk, logits):
                record = {
                    "query_id": row["query_id"],
                    "product_id": row["product_id"],
                    "logits": {
                        name: float(value) for name, value in zip(CONTRACTS, values)
                    },
                }
                handle.write(json.dumps(record) + "\n")
                result.append(values)
            handle.flush()
            seconds = time.monotonic() - started
            if len(result) == 64:
                projected = probe_projection(len(result), seconds, len(rows))
                (output / "probe.json").write_text(
                    json.dumps(
                        {
                            "pairs": len(result),
                            "seconds": seconds,
                            "projected_seconds": projected,
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                if projected > budget:
                    status = "stopped_projected_budget"
                    break
            if seconds > budget:
                status = "stopped_elapsed_budget"
                break
            if len(result) % 512 == 0:
                print(
                    json.dumps(
                        {"completed_pairs": len(result), "planned_pairs": len(rows)}
                    ),
                    flush=True,
                )
    if status == "completed":
        np.savez_compressed(output / "features.npz", logits=np.asarray(result))
    receipt = {
        **plan,
        "plan_sha256": sha256((output / "plan.json").read_bytes()).hexdigest(),
        "status": status,
        "completed_pairs": len(result),
        "seconds": time.monotonic() - started,
        "truncated_contract_inputs": truncated,
        "model_files_sha256": file_hashes,
        "features_sha256": sha256(output_file.read_bytes()).hexdigest(),
        "torch_version": torch.__version__,
        "transformers_version": __import__("transformers").__version__,
    }
    (output / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: receipt[k]
                for k in (
                    "status",
                    "completed_pairs",
                    "seconds",
                    "truncated_contract_inputs",
                )
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--budget-seconds", type=float, default=900)
    parser.add_argument("--pilot-pairs", type=int)
    parser.add_argument("--quantise-linear", action="store_true")
    args = parser.parse_args()
    run(
        args.inputs,
        args.output,
        args.cache,
        args.budget_seconds,
        args.pilot_pairs,
        args.quantise_linear,
    )
