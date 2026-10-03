"""Record singleton outputs and selected Triton configurations without patching kernels."""

import argparse
import gc
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys
import time


def configurations():
    from triton.runtime.autotuner import Autotuner

    found = {}
    seen = set()
    for name, module in list(sys.modules.items()):
        if not name.startswith("fla.") or module is None:
            continue
        for value in list(vars(module).values()):
            current = value
            while current is not None and id(current) not in seen:
                seen.add(id(current))
                if isinstance(current, Autotuner):
                    kernel = getattr(current, "kernel_name", None)
                    if kernel is None:
                        kernel = getattr(getattr(current, "fn", None), "__name__", None)
                    if kernel is None:
                        kernel = str(type(current.fn))
                    entries = []
                    for key, config in current.cache.items():
                        entries.append({"key": list(key), "config": {
                            "kwargs": config.kwargs,
                            "num_warps": config.num_warps,
                            "num_stages": config.num_stages,
                        }})
                    if entries:
                        found[kernel] = sorted(entries, key=lambda row: json.dumps(row["key"]))
                current = getattr(current, "fn", None)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loader", choices=("research", "serving"), required=True)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--exclusions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", action="store_true")
    parser.add_argument("--pairs", type=int, default=256)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve every kernel-selection attempt.")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judgements"))
    from esci.contract import map_scores, model_state
    from esci.release import read_json, sha256, verify_bundle, write_json
    from esci.runtime import configure_runtime, verify_backend
    frozen = read_json(args.references)
    settings = read_json(args.bundle / "inference.json")
    release = verify_bundle(args.bundle)
    if (frozen["release_sha256"] != release["release_sha256"]
            or frozen["protocol"] != settings["protocol"]
            or frozen["exclusions_sha256"] != sha256(args.exclusions)):
        raise ValueError("Reference, protocol or protected reservation changed.")
    reserved = set(read_json(args.exclusions)["query_hashes"])
    if not reserved or any(row["query_hash"] in reserved for row in frozen["rows"]):
        raise ValueError("Diagnostic inputs overlap protected queries.")
    if any(model_state(row["input"]) != row["state"] for row in frozen["rows"]):
        raise ValueError("Reference state differs from the serving input contract.")
    if not 0 < args.pairs <= len(frozen["rows"]):
        raise ValueError("Invalid diagnostic size.")
    if args.warmup and hashlib.sha256(b"desk lamp").hexdigest() in reserved:
        raise ValueError("Warmup query is protected.")
    for package, expected in settings["runtime"].items():
        if version(package).split("+")[0] != expected:
            raise RuntimeError(f"Unexpected diagnostic runtime: {package}.")
    import torch
    configure_runtime(torch, settings, args.bundle)
    backend = verify_backend()
    if args.loader == "research":
        sys.path.insert(0, str(args.research / "src"))
        from esci_gap_judge.model.inference import DeciderJudge
        from esci_gap_judge.model.schema import choice_question
        adapter = args.research / "artifacts/models/esci-decider-4b-role-cues-v3-pilot-8192/adapter"
        if sha256(adapter / "adapter.safetensors") != release["source"]["adapter_sha256"]:
            raise ValueError("Original adapter bytes differ.")
        judge = DeciderJudge(args.bundle / "base", release["source"]["base_revision"],
                             adapter_path=adapter, question_schema="esci-choice-role-cues-v3")
        decider = judge.engine
        question = choice_question("esci-choice-role-cues-v3")
    else:
        from esci.engine import Engine
        judge = Engine(args.bundle, settings)
        decider = judge.decider
        question = {"question": settings["question"],
                    "options": ["Exact", "Substitute", "Complement", "Irrelevant"]}
    if question != {"question": settings["question"],
                    "options": ["Exact", "Substitute", "Complement", "Irrelevant"]}:
        raise ValueError("Question differs.")
    mapping = read_json(args.bundle / "score-mapping.json")
    if args.warmup:
        state = model_state({"request": {"query": "desk lamp"},
                             "product": {"title": "Desk lamp", "category": "Lighting"}})
        decider.decide_batch([(state, [question])], max_ctx_tokens=1536)
    outputs = []
    started = time.monotonic()
    for i, row in enumerate(frozen["rows"][:args.pairs]):
        answers = decider.decide_batch([(row["state"], [question])], max_ctx_tokens=1536)
        raw = [float(answers[0][0]["probs"][option]) for option in question["options"]]
        outputs.append({"index": i, "raw": raw, "mapped": map_scores(raw, mapping)})
        if (i+1) % 64 == 0:
            print(f"{args.loader}: {i+1}/{args.pairs}; {time.monotonic()-started:.1f}s", flush=True)
    write_json(args.output, {"loader": args.loader, "warmup": args.warmup,
               "reference_sha256": sha256(args.references), "backend": backend,
               "configurations": configurations(), "outputs": outputs,
               "seconds": time.monotonic()-started,
               "precision_after_load": {"float32": torch.get_float32_matmul_precision(),
                   "tf32_matmul": torch.backends.cuda.matmul.allow_tf32,
                   "tf32_cudnn": torch.backends.cudnn.allow_tf32,
                   "bf16_reduction": torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction}})
    del judge, decider
    gc.collect()
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
