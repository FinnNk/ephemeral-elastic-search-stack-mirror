"""Create CPU-only query/title embeddings for an exploratory ESCI survey."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import time

MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def run(inputs, model_path, output):
    output.mkdir(parents=True, exist_ok=False)
    if model_path.name != MODEL_REVISION:
        raise ValueError("The registered MiniLM snapshot is required")
    plan = {
        "kind": "esci-input-embedding-survey-v1",
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "revision": MODEL_REVISION,
        "model_files_sha256": {
            name: sha256((model_path / name).read_bytes()).hexdigest()
            for name in ("config.json", "tokenizer.json", "model.safetensors")
        },
        "inputs_sha256": sha256(inputs.read_bytes()).hexdigest(),
        "device": "cpu",
        "torch_threads": 4,
        "max_tokens": 256,
        "batch_size": 16,
        "pooling": "attention-mask mean, L2 normalised",
        "fields": ["request.query", "product.title", "product.category_path"],
        "reference_labels_read": False,
        "gate_eligible": False,
    }
    (output / "plan.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8"
    )
    import numpy as np
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    started = time.monotonic()
    rows = [
        json.loads(line)
        for line in inputs.read_text(encoding="utf-8").splitlines()
        if line
    ]
    fields = {
        "query": [row["request"]["query"] for row in rows],
        "title": [row["product"]["title"] for row in rows],
        "category": [" > ".join(row["product"]["category_path"]) for row in rows],
    }
    texts = sorted(set(text for values in fields.values() for text in values))
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = (
        AutoModel.from_pretrained(model_path, local_files_only=True).to("cpu").eval()
    )
    all_embeddings = []
    truncated = 0
    for start in range(0, len(texts), 16):
        chunk = texts[start : start + 16]
        full = tokenizer(chunk, truncation=False)["input_ids"]
        truncated += sum(len(tokens) > 256 for tokens in full)
        encoded = tokenizer(
            chunk, padding=True, truncation=True, max_length=256, return_tensors="pt"
        )
        with torch.inference_mode():
            hidden = model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            embeddings = torch.nn.functional.normalize(pooled, p=2, dim=1)
        all_embeddings.append(embeddings.numpy())
        if start % 512 == 0:
            print(
                json.dumps(
                    {"completed": min(start + 16, len(texts)), "texts": len(texts)}
                ),
                flush=True,
            )
    matrix = np.vstack(all_embeddings)
    lookup = {text: i for i, text in enumerate(texts)}
    np.savez_compressed(
        output / "embeddings.npz",
        **{
            name: matrix[[lookup[text] for text in values]]
            for name, values in fields.items()
        },
    )
    receipt = {
        "kind": plan["kind"],
        "plan_sha256": sha256((output / "plan.json").read_bytes()).hexdigest(),
        "pairs": len(rows),
        "unique_texts": len(texts),
        "truncated_texts": truncated,
        "dimension": matrix.shape[1],
        "embeddings_sha256": sha256(
            (output / "embeddings.npz").read_bytes()
        ).hexdigest(),
        "torch_version": torch.__version__,
        "numpy_version": np.__version__,
        "seconds": time.monotonic() - started,
        "device": str(next(model.parameters()).device),
        "reference_labels_read": False,
    }
    (output / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs, args.model, args.output)
