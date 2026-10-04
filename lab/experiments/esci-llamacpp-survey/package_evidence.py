"""Package the completed CPU prompt pilot; never run models or change lab labels."""

from hashlib import sha256
import json
from pathlib import Path

import numpy as np

STATE = Path(r"D:\codex\Ephemeral Elasticsearch\.lab")
ROOT = STATE / "esci-fitted-specialists/llamacpp-survey"
DEVELOPMENT = STATE / "esci-packaging/label-calibration-20261003"
DESTINATION = (
    Path(__file__).resolve().parents[3]
    / "docs/research/evidence/esci-cpu-pair-judges-prompts.json"
)


def checksum(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def rows(path):
    return [json.loads(line) for line in Path(path).read_bytes().splitlines() if line]


def paired(left, right, truth, queries, repetitions, seed):
    if not (len(left) == len(right) == len(truth) == len(queries)) or not len(truth):
        raise ValueError("Exactly matched non-empty pilot records are required.")
    left, right, truth = np.array(left), np.array(right), np.array(truth)
    left_correct, right_correct = left == truth, right == truth
    _, groups = np.unique(queries, return_inverse=True)
    n = int(groups.max()) + 1
    sums = np.column_stack(
        [
            np.bincount(
                groups,
                weights=right_correct.astype(int) - left_correct.astype(int),
                minlength=n,
            ),
            np.bincount(groups, minlength=n),
        ]
    )
    rng = np.random.default_rng(seed)
    samples = sums[rng.integers(n, size=(repetitions, n))].sum(axis=1)
    interval = np.quantile(samples[:, 0] / samples[:, 1], [0.025, 0.975]).tolist()
    return {
        "pairs": len(truth),
        "query_groups": n,
        "changed": int((left != right).sum()),
        "unchanged": int((left == right).sum()),
        "both_right": int((left_correct & right_correct).sum()),
        "both_wrong": int((~left_correct & ~right_correct).sum()),
        "left_right_right_wrong": int((left_correct & ~right_correct).sum()),
        "left_wrong_right_right": int((~left_correct & right_correct).sum()),
        "accuracy_difference_right_minus_left": float(
            right_correct.mean() - left_correct.mean()
        ),
        "descriptive_query_bootstrap_95_interval": interval,
    }


def main():
    attempt = ROOT / "attempt-01"
    amendment = read(attempt / "paired-diagnostic-amendment.json")
    if (
        checksum(attempt / "scores.jsonl") != amendment["scores_sha256"]
        or checksum(DEVELOPMENT / "inputs.jsonl") != amendment["input_sha256"]
        or checksum(DEVELOPMENT / "references.jsonl") != amendment["reference_sha256"]
    ):
        raise ValueError("Frozen diagnostic source bytes changed.")
    plan, generation, report = (
        read(attempt / name) for name in ("plan.json", "generation.json", "report.json")
    )
    runtime = read(ROOT / "runtime-01/runtime.json")
    source_freeze = read(ROOT / "packaging-source-freeze/receipt.json")
    for name, receipt in source_freeze.items():
        if checksum(ROOT / "packaging-source-freeze" / name) != receipt["file_sha256"]:
            raise ValueError("Executed source snapshot changed.")
    scores = rows(attempt / "scores.jsonl")
    indices = sorted({row["input_index"] for row in scores})
    if (
        len(indices) != 32
        or set(indices) != set(plan["selected_input_indices"][:32])
        or len(scores) != 96
    ):
        raise ValueError("Only the completed matched 32-pair pilot may be assessed.")
    inputs = rows(DEVELOPMENT / "inputs.jsonl")
    selected_keys = {(inputs[i]["query_id"], inputs[i]["product_id"]) for i in indices}
    references = {}
    for raw in (DEVELOPMENT / "references.jsonl").read_bytes().splitlines():
        row = json.loads(raw)
        key = row["query_id"], row["product_id"]
        if key in selected_keys:
            if row["provenance"]["kind"] != "published":
                raise ValueError("Published, exposed development references only.")
            references[key] = row["label"]
    truth = [
        references[(inputs[i]["query_id"], inputs[i]["product_id"])] for i in indices
    ]
    queries = [inputs[i]["query_key"] for i in indices]
    grouped = {
        contract: {
            row["input_index"]: row["label"]
            for row in scores
            if row["contract"] == contract
        }
        for contract in plan["contracts"]
    }
    if any(set(values) != set(indices) for values in grouped.values()):
        raise ValueError("Every prompt contract must contain identical pilot pairs.")
    comparisons = []
    for left, right in amendment["pairs"]:
        comparisons.append(
            {
                "left": left,
                "right": right,
                **paired(
                    [grouped[left][i] for i in indices],
                    [grouped[right][i] for i in indices],
                    truth,
                    queries,
                    amendment["repetitions"],
                    amendment["seed"],
                ),
            }
        )
    diagnostic = {
        "kind": "esci-llamacpp-paired-development-diagnostic",
        "post_probe_analysis": True,
        "gate_eligible": False,
        "pairs": 32,
        "query_groups": len(set(queries)),
        "class_support": {label: truth.count(label) for label in ("E", "S", "C", "I")},
        "comparisons": comparisons,
        "amendment_sha256": checksum(attempt / "paired-diagnostic-amendment.json"),
        "bootstrap_repetitions": amendment["repetitions"],
        "bootstrap_seed": amendment["seed"],
        "limits": [
            "Descriptive whole-query intervals conditional on a small exposed development pilot; not adjusted for prompt comparisons or proof of significance.",
            "Only one Irrelevant reference; zero I-to-E errors do not establish safety.",
        ],
    }
    (attempt / "paired-diagnostic.json").write_text(
        json.dumps(diagnostic, sort_keys=True) + "\n", encoding="utf-8"
    )
    command = list(plan["command"])
    command[0] = "llama-server.exe"
    command[command.index("-m") + 1] = Path(runtime["model"]).name
    command[command.index("--port") + 1] = "<temporary-port>"
    evidence = {
        "kind": "esci-cpu-pair-judges-prompt-evidence",
        "schema_version": 1,
        "gate_eligible": False,
        "runtime": {
            "release": runtime["runtime_tag"],
            "commit": runtime["runtime_commit"],
            "archive_sha256": runtime["archive_sha256"],
            "files_sha256": runtime["runtime_files_sha256"],
            "cpu_only_asset": True,
            "executed_arguments": command,
        },
        "model": {
            "repository": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
            "revision": runtime["model_revision"],
            "file": Path(runtime["model"]).name,
            "file_sha256": runtime["model_sha256"],
            "quantisation": "Q4_K_M",
            "licence": "Apache-2.0",
        },
        "conditions": {
            "platform": "Windows x64",
            "threads": 4,
            "batch_threads": 4,
            "gpu_layers": 0,
            "server_slots": 1,
            "context": 1024,
            "input_token_budget": 512,
            "other_lab_and_research_work_running": True,
        },
        "prompt_contract": {
            "source_sha256": plan["original_prompt_source_sha256"],
            "contracts": plan["contracts"],
            "definitions_sha256": sha256(plan["definitions"].encode()).hexdigest(),
            "role_rules_sha256": sha256(plan["role_rules"].encode()).hexdigest(),
            "grammar": plan["grammar"],
            "sampling": plan["sampling"],
            "score_meaning": plan["score"],
            "selective_acceptance": None,
        },
        "generation": generation,
        "probe": read(attempt / "probe.json"),
        "contract_results": report["contracts"],
        "paired_diagnostic": diagnostic,
        "cleanup": {
            "owned_process_terminated": read(attempt / "cleanup.json")["terminated"],
            "port_closure_checked": True,
            "check_result": "closed"
            if read(attempt / "port-closure-check.json")["port_closed"]
            else "open",
        },
        "executed_sources": source_freeze,
        "artifact_sha256": {
            "input": plan["input_sha256"],
            "selected_256_input_membership": plan["selected_inputs_sha256"],
            "scored_32_input_membership": sha256(
                b"".join(
                    (
                        json.dumps(inputs[i], sort_keys=True, separators=(",", ":"))
                        + "\n"
                    ).encode()
                    for i in plan["selected_input_indices"][:32]
                )
            ).hexdigest(),
            "runtime_receipt": plan["runtime_receipt_sha256"],
            "generation_plan": checksum(attempt / "plan.json"),
            "scores": checksum(attempt / "scores.jsonl"),
            "report": checksum(attempt / "report.json"),
            "diagnostic_plan": checksum(attempt / "diagnostic-plan.json"),
            "paired_amendment": checksum(attempt / "paired-diagnostic-amendment.json"),
            "paired_diagnostic": checksum(attempt / "paired-diagnostic.json"),
            "development_references": amendment["reference_sha256"],
            "port_closure_check": checksum(attempt / "port-closure-check.json"),
            "source_snapshot_receipt": checksum(
                ROOT / "packaging-source-freeze/receipt.json"
            ),
        },
        "sources": read(ROOT / "source-references.json"),
        "limits": report["limits"]
        + diagnostic["limits"]
        + [
            "Nullable original catalogue fields were preserved in JSON. Rich product text was truncated in11of32pairs; title-only contracts were not truncated.",
            "The96-score throughput probe projected28.45minutes for768scores, exceeding the frozen15minute limit. No full survey was run.",
            "Quantisation, grammar-conditioned decoding, native chat formatting and backend caching differ from the earlier PyTorch pilot; no numerical parity claim.",
            "No labels were imported, activated or made gate eligible; no GPU or fresh/protected references used.",
        ],
    }
    DESTINATION.write_text(
        json.dumps(evidence, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "evidence": str(DESTINATION),
                "paired": comparisons,
                "query_groups": len(set(queries)),
            }
        )
    )


if __name__ == "__main__":
    main()
