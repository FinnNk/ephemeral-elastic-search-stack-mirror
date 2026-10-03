"""Retain raw scores and token fingerprints for controlled parity experiments.

Run after taking the research GPU hold. Research uses its original loader;
serving uses the pinned image's loader. Neither path changes registered assets.
"""

import argparse
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=("research", "serving"), required=True)
    parser.add_argument("--research", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fla-chunk", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Keep every probe attempt.")
    # In the image, /app holds the exact published serving implementation.
    if args.runtime == "research":
        sys.path.insert(0, str(args.research / "src"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judgements"))
        from esci_gap_judge.model.inference import DeciderJudge
        from esci_gap_judge.model.schema import choice_question
        judge = DeciderJudge(args.bundle / "base", "eb5fbdfc9448473ec25e399882912863afbdb70e",
            adapter_path=args.research / "artifacts/models/esci-decider-4b-role-cues-v3-pilot-8192/adapter",
            question_schema="esci-choice-role-cues-v3")
        decider = judge.engine
        question = choice_question("esci-choice-role-cues-v3")
    else:
        sys.path.insert(0, "/app")
        from esci.engine import Engine
        settings = json.loads((args.bundle / "inference.json").read_text(encoding='utf-8'))
        engine = Engine(args.bundle, settings)
        decider = engine.decider
        question = {"question": settings["question"],
                    "options": ["Exact", "Substitute", "Complement", "Irrelevant"]}
    from esci.contract import map_scores
    from esci.release import content_digest, sha256, verify_bundle
    import torch
    if args.fla_chunk:
        from fla.ops.gated_delta_rule import chunk_gated_delta_rule
        from transformers.models.qwen3_next import modeling_qwen3_next
        upstream_chunk = modeling_qwen3_next.torch_chunk_gated_delta_rule
        modeling_qwen3_next.torch_chunk_gated_delta_rule = chunk_gated_delta_rule
    frozen = json.loads(args.inputs.read_text(encoding='utf-8'))
    if verify_bundle(args.bundle)["release_sha256"] != frozen["release_sha256"]:
        raise ValueError("The probe loaded a different release.")
    if args.runtime == "research" and sha256(
        args.research / "artifacts/models/esci-decider-4b-role-cues-v3-pilot-8192/adapter/adapter.safetensors"
    ) != sha256(args.bundle / "adapter/adapter.safetensors"):
        raise ValueError("Research and registered adapter weights differ.")
    mapping = json.loads((args.bundle / "score-mapping.json").read_text(encoding='utf-8'))
    indices = [i for group in frozen["original_groups"] for i in group]
    tokens = {}
    for i in indices:
        _, items = decider._decide_items([(frozen["rows"][i]["state"], [question])], 1536)
        tokens[str(i)] = {"sha256": content_digest({key:items[0][key] for key in
                                                   ("ids", "slots", "nopts", "types")}),
                          "length": len(items[0]["ids"])}
    packages = {}
    for name in ("torch", "transformers", "peft", "decider-ai", "safetensors", "numpy",
                 "flash-linear-attention", "triton", "kernels"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    metadata = {"runtime": args.runtime, "input_sha256": sha256(args.inputs),
                "question_sha256": content_digest(question), "tokens": tokens,
                "dtype": str(next(decider.m.parameters()).dtype),
                "fla_chunk": args.fla_chunk,
                "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(),
                "tf32_matmul": torch.backends.cuda.matmul.allow_tf32,
                "tf32_cudnn": torch.backends.cudnn.allow_tf32,
                "cudnn_version": torch.backends.cudnn.version(),
                "cudnn_benchmark": torch.backends.cudnn.benchmark,
                "cudnn_deterministic": torch.backends.cudnn.deterministic,
                "float32_matmul_precision": torch.get_float32_matmul_precision(),
                "use_hub_kernels": getattr(decider.m.lm.config, "use_kernels", None),
                "bf16_reduced_precision_reduction": torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction,
                "attention_implementation": decider.m.lm.config._attn_implementation,
                "platform": platform.platform(), "python": platform.python_version(),
                "thread_settings": {name: os.environ.get(name) for name in
                                    ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
                "packages": packages}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"metadata": metadata})+"\n")
        phases = [("original", frozen["original_groups"]),
                  ("original-repeat", frozen["original_groups"]),
                  ("singletons", [[i] for i in indices])]
        if args.fla_chunk:
            phases.insert(0, ("upstream-original", frozen["original_groups"]))
        for name, batches in phases:
            if args.fla_chunk:
                modeling_qwen3_next.torch_chunk_gated_delta_rule = (
                    upstream_chunk if name == "upstream-original" else chunk_gated_delta_rule)
            started = time.monotonic()
            for n, batch in enumerate(batches):
                answers = decider.decide_batch([(frozen["rows"][i]["state"], [question]) for i in batch])
                raw = [[float(answer[0]["probs"][option]) for option in
                        ("Exact", "Substitute", "Complement", "Irrelevant")] for answer in answers]
                mapped = [map_scores(row, mapping) for row in raw]
                stream.write(json.dumps({"run": name, "indices": batch,
                                         "raw": raw, "mapped": mapped})+"\n")
                stream.flush()
                if (n+1) % 32 == 0 or n+1 == len(batches):
                    print(f"{args.runtime} {name}: {n+1}/{len(batches)}; {time.monotonic()-started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
