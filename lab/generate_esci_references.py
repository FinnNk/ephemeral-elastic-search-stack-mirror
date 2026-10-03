"""Freeze singleton references with the original research loader, never serving."""

import argparse
from importlib.metadata import version
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judgements"))
from esci.release import content_digest, read_json, sha256, verify_bundle, write_json
from esci.runtime import INFERENCE_PROTOCOL, configure_runtime, verify_backend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--exclusions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw_output = args.output.with_suffix(".jsonl")
    if args.output.exists() or raw_output.exists():
        raise FileExistsError("Preserve every independent reference attempt.")
    frozen = read_json(args.inputs)
    release = verify_bundle(args.bundle)
    settings = read_json(args.bundle / "inference.json")
    if (frozen["release_sha256"] != release["release_sha256"]
            or frozen["protocol"] != INFERENCE_PROTOCOL
            or frozen["exclusions_sha256"] != sha256(args.exclusions)):
        raise ValueError("Input, release, protocol or protected reservation changed.")
    if len({r["input_hash"] for r in frozen["rows"]}) != len(frozen["rows"]):
        raise ValueError("Duplicate reference input identities.")
    reserved = set(read_json(args.exclusions)["query_hashes"])
    if not reserved or any(row["query_hash"] in reserved for row in frozen["rows"]):
        raise ValueError("Reference inputs overlap protected queries.")
    for name, expected in settings["runtime"].items():
        if version(name).split("+")[0] != expected:
            raise RuntimeError(f"Unexpected reference runtime: {name}.")
    import torch
    configure_runtime(torch, settings)
    backend = verify_backend()
    sys.path.insert(0, str(args.research / "src"))
    from esci_gap_judge.model.inference import DeciderJudge
    from esci_gap_judge.model.schema import choice_question
    import joblib
    import numpy as np

    adapter = args.research / "artifacts/models/esci-decider-4b-role-cues-v3-pilot-8192/adapter"
    if sha256(adapter / "adapter.safetensors") != release["source"]["adapter_sha256"]:
        raise ValueError("Independent adapter bytes differ from the release.")
    source = args.research / "artifacts/evaluations/round-2/decision-fit/frozen-models.joblib"
    if sha256(source) != release["source"]["mapping_bundle_sha256"]:
        raise ValueError("Independent sklearn mapping bytes differ.")
    mapping = joblib.load(source)["models"][release["source"]["mapping_key"]]
    if mapping.classes_.tolist() != [0, 1, 2, 3]:
        raise ValueError("Independent mapping label order differs.")
    judge = DeciderJudge(args.bundle / "base", release["source"]["base_revision"],
                         adapter_path=adapter, question_schema="esci-choice-role-cues-v3")
    if judge.engine.m.lm.config._attn_implementation != "sdpa":
        raise RuntimeError("Reference attention differs from the declared protocol.")
    question = choice_question("esci-choice-role-cues-v3")
    if (question["question"] != settings["question"]
            or question["options"] != ["Exact", "Substitute", "Complement", "Irrelevant"]):
        raise ValueError("Independent question differs from the release.")
    source_hashes = {p.relative_to(args.research).as_posix(): sha256(p)
                     for p in sorted((args.research / "src").rglob("*.py"))}
    metadata = {"origin": "frozen-research-scores", "protocol": INFERENCE_PROTOCOL,
                "input_sha256": sha256(args.inputs), "release_sha256": release["release_sha256"],
                "generator_sha256": sha256(Path(__file__)), "research_source_sha256": source_hashes,
                "backend": backend, "runtime": {p: version(p) for p in settings["runtime"]},
                "cuda": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
                "gpu": torch.cuda.get_device_name(), "mapping_sha256": sha256(source)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    rows = []
    labels = ["E", "S", "C", "I"]
    with raw_output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"metadata": metadata}) + "\n")
        for i, row in enumerate(frozen["rows"]):
            answers = judge.engine.decide_batch([(row["state"], [question])], max_ctx_tokens=1536)
            raw = [float(answers[0][0]["probs"][option]) for option in question["options"]]
            mapped = mapping.predict_proba(np.log(np.clip([raw], 1e-6, 1)))[0].tolist()
            index = max(range(4), key=mapped.__getitem__)
            confidence = mapped[index]
            result = {**row, "reference_raw": raw,
                      "reference": {"probabilities": mapped, "confidence": confidence,
                                    "label": labels[index] if confidence >= 0.90 else None,
                                    "outcome": "labelled" if confidence >= 0.90 else "abstain"}}
            rows.append(result)
            stream.write(json.dumps(result) + "\n")
            stream.flush()
            if (i+1) % 256 == 0 or i+1 == len(frozen["rows"]):
                print(f"Independent references: {i+1}/{len(frozen['rows'])}; {time.monotonic()-started:.1f}s", flush=True)
    output = {**frozen, "origin": "frozen-research-scores", "provenance": metadata,
              "raw_capture_sha256": sha256(raw_output), "rows": rows,
              "singleton_indices": list(range(len(rows))), "seconds": time.monotonic()-started}
    output["reference_content_sha256"] = content_digest(output)
    write_json(args.output, output)
    print(json.dumps({"rows": len(rows), "reference_sha256": sha256(args.output)}), flush=True)


if __name__ == "__main__":
    main()
