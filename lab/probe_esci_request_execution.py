"""Isolate raw inference, MLflow calls and request-thread execution on one model."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time

from probe_esci_kernel_selection import configurations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model", "registration", "references", "exclusions", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=256)
    parser.add_argument("--phase", action="append", choices=("engine-main", "pyfunc-main",
                        "predictor-main", "predictor-threads", "engine-threads"))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve every request-execution diagnostic.")
    sys.path.insert(0, "/app")
    from esci.contract import map_scores, model_state, outcome
    from esci.release import read_json, sha256, write_json
    from fetch_model import tree_digest
    import mlflow
    import pandas as pd
    import torch
    from predictor import predict

    frozen, receipt = read_json(args.references), read_json(args.registration)
    if (tree_digest(args.model) != receipt["artifact_sha256"]
            or frozen["release_sha256"] != receipt["release_sha256"]
            or frozen["exclusions_sha256"] != sha256(args.exclusions)):
        raise ValueError("Model, references or reservations changed.")
    reserved = set(read_json(args.exclusions)["query_hashes"])
    if not reserved or any(row["query_hash"] in reserved for row in frozen["rows"]):
        raise ValueError("Diagnostic input overlaps protected queries.")
    if any(model_state(row["input"]) != row["state"] for row in frozen["rows"]):
        raise ValueError("Rendered input differs.")
    if not 0 < args.pairs <= len(frozen["rows"]):
        raise ValueError("Invalid diagnostic size.")
    import hashlib
    if hashlib.sha256(b"desk lamp").hexdigest() in reserved:
        raise ValueError("Warmup query is protected.")
    model = mlflow.pyfunc.load_model(str(args.model))
    warmup = {"request": {"query": "desk lamp"},
              "product": {"title": "Desk lamp", "category": "Lighting"}}
    predict(model, [warmup])
    loaded = model.unwrap_python_model()
    rows = frozen["rows"][:args.pairs]
    results = {}

    def context():
        return {"float32": torch.get_float32_matmul_precision(),
                "tf32_matmul": torch.backends.cuda.matmul.allow_tf32,
                "tf32_cudnn": torch.backends.cudnn.allow_tf32,
                "bf16_reduction": torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction,
                "grad_enabled": torch.is_grad_enabled(),
                "autocast_enabled": torch.is_autocast_enabled("cuda")}

    def call(kind, batch):
        settings = context()
        if kind == "engine":
            raw = loaded.engine.predict([row["state"] for row in batch])
            outputs = [outcome(map_scores(r, loaded.mapping), loaded.policy) for r in raw]
        elif kind == "pyfunc":
            frame = pd.DataFrame({"payload": [json.dumps(r["input"]) for r in batch]})
            outputs = model.predict(frame).to_dict(orient="records")
        else:
            outputs = predict(model, [r["input"] for r in batch])
        return outputs, settings

    for name, kind, threaded in [("engine-main", "engine", False),
                                  ("pyfunc-main", "pyfunc", False),
                                  ("predictor-main", "predictor", False),
                                  ("predictor-threads", "predictor", True),
                                  ("engine-threads", "engine", True)]:
        if args.phase and name not in args.phase:
            continue
        started = time.monotonic()
        outputs, contexts = [], []
        for start in range(0, len(rows), 128):
            batch = rows[start:start+128]
            if threaded:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    result, settings = pool.submit(call, kind, batch).result()
            else:
                result, settings = call(kind, batch)
            outputs.extend(result)
            contexts.append(settings)
            if len(outputs) % 1024 == 0 or len(outputs) == len(rows):
                print(f"{name}: {len(outputs)}/{len(rows)}; {time.monotonic()-started:.1f}s", flush=True)
        results[name] = {"outputs": outputs, "contexts": contexts,
                         "configurations": configurations(), "seconds": time.monotonic()-started}
        print(f"Completed {name}: {len(outputs)} pairs; {time.monotonic()-started:.1f}s", flush=True)
    write_json(args.output, {"reference_sha256": sha256(args.references),
               "model": {k:receipt[k] for k in ("name", "version", "artifact_sha256")},
               "generator_sha256": sha256(Path(__file__)), "pairs": len(rows), "runs": results})


if __name__ == "__main__":
    main()
