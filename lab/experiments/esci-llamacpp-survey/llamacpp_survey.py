"""Bounded CPU-only llama.cpp prompt survey on exposed ESCI development inputs."""

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.request
import zipfile

STATE = Path(r"D:\codex\Ephemeral Elasticsearch\.lab")
DEVELOPMENT = STATE / "esci-packaging/label-calibration-20261003"
RUNTIME_TAG = "b11146"
RUNTIME_COMMIT = "7fe450e19305b828c199d602c23a8337aaa1f03b"
ARCHIVE_SHA = "14cf1303ca9ac3abd94816850532f9f9a69ac66fbaca3776fc6f9061c2fac1d1"
ARCHIVE_SIZE = 18560055
MODEL_REVISION = "91cad51170dc346986eccefdc2dd33a9da36ead9"
MODEL_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_SHA = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
MODEL_SIZE = 1117320736
MODEL_URL = f"https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/{MODEL_REVISION}/{MODEL_FILE}"
ARCHIVE_URL = f"https://github.com/ggml-org/llama.cpp/releases/download/{RUNTIME_TAG}/llama-{RUNTIME_TAG}-bin-win-cpu-x64.zip"
GRAMMAR = 'root ::= "E" | "S" | "C" | "I"'


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def checksum(path):
    digest = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def original_contracts():
    path = (
        Path(__file__).resolve().parents[1] / "esci-gap-surveys/instruction_survey.py"
    )
    spec = importlib.util.spec_from_file_location("original_instruction", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def download(url, destination, expected_sha, expected_size):
    if destination.exists():
        if (
            destination.stat().st_size != expected_size
            or checksum(destination) != expected_sha
        ):
            raise ValueError(
                "Existing download differs from its pinned publisher bytes."
            )
        return
    partial = destination.with_suffix(destination.suffix + ".partial")
    if partial.exists():
        raise ValueError(
            "Preserve the interrupted download; choose a new runtime directory."
        )
    request = urllib.request.Request(
        url, headers={"User-Agent": "ephemeral-elastic-lab"}
    )
    with (
        urllib.request.urlopen(request, timeout=120) as response,
        partial.open("xb") as output,
    ):
        total = 0
        while block := response.read(1024 * 1024):
            total += len(block)
            if total > expected_size:
                raise ValueError("Download exceeds the pinned publisher size.")
            output.write(block)
    if partial.stat().st_size != expected_size or checksum(partial) != expected_sha:
        raise ValueError("Download differs from the pinned publisher checksum.")
    partial.rename(destination)


def safe_archive_target(root, name):
    if (
        "\\" in name
        or Path(name).is_absolute()
        or any(part in ("..", "") for part in name.split("/") if part != "")
    ):
        raise ValueError("Unsafe archive member.")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Archive member escapes its isolated runtime directory.")
    return target


def prepare(destination):
    destination.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(destination).free
    if free < 5 * 1024**3 or ARCHIVE_SIZE + MODEL_SIZE > 1500 * 1024**2:
        raise ValueError("Insufficient disk headroom or download budget.")
    release = json.load(
        urllib.request.urlopen(
            urllib.request.Request(
                f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{RUNTIME_TAG}",
                headers={"User-Agent": "ephemeral-elastic-lab"},
            )
        )
    )
    asset = next(
        a for a in release["assets"] if a["browser_download_url"] == ARCHIVE_URL
    )
    if (
        release["target_commitish"] != RUNTIME_COMMIT
        or asset["digest"] != "sha256:" + ARCHIVE_SHA
        or asset["size"] != ARCHIVE_SIZE
    ):
        raise ValueError(
            "Official release metadata differs from the selected CPU asset."
        )
    (destination / "download-plan.json").write_bytes(
        canonical(
            {
                "runtime_tag": RUNTIME_TAG,
                "runtime_commit": RUNTIME_COMMIT,
                "asset_url": ARCHIVE_URL,
                "asset_sha256": ARCHIVE_SHA,
                "model_url": MODEL_URL,
                "model_revision": MODEL_REVISION,
                "model_sha256": MODEL_SHA,
                "expected_total_bytes": ARCHIVE_SIZE + MODEL_SIZE,
                "disk_free_before": free,
                "source_sha256": checksum(__file__),
            }
        )
    )
    archive = destination / "runtime.zip"
    download(ARCHIVE_URL, archive, ARCHIVE_SHA, ARCHIVE_SIZE)
    runtime = destination / "runtime"
    if not runtime.exists():
        runtime.mkdir()
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                target = safe_archive_target(runtime, member.filename)
                if any(
                    word in member.filename.lower()
                    for word in ("cuda", "vulkan", "sycl", "rocm", "openvino")
                ):
                    raise ValueError("GPU/accelerator backend in CPU-only asset.")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(member) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
    server = next(runtime.rglob("llama-server.exe"))
    model = destination / MODEL_FILE
    download(MODEL_URL, model, MODEL_SHA, MODEL_SIZE)
    receipt = {
        "kind": "esci-llamacpp-runtime",
        "runtime_tag": RUNTIME_TAG,
        "runtime_commit": RUNTIME_COMMIT,
        "archive_sha256": checksum(archive),
        "server": str(server),
        "model": str(model),
        "model_sha256": checksum(model),
        "model_revision": MODEL_REVISION,
        "runtime_files_sha256": {
            str(p.relative_to(runtime)): checksum(p)
            for p in runtime.rglob("*")
            if p.is_file()
        },
        "cpu_only_asset": True,
        "gate_eligible": False,
    }
    (destination / "runtime.json").write_bytes(canonical(receipt))
    print(
        json.dumps(
            {
                "runtime": RUNTIME_TAG,
                "download_bytes": ARCHIVE_SIZE + MODEL_SIZE,
                "model_sha256": MODEL_SHA,
            }
        )
    )


def request(port, path, value=None):
    data = None if value is None else canonical(value)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=120))


def prompt(port, row, contract, original):
    system, query, product = original.prompt_parts(row, contract)

    def chat(value):
        result = request(
            port,
            "/apply-template",
            {
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": query + "\nProduct: " + value},
                ],
                "add_generation_prompt": True,
            },
        )
        return result["prompt"]

    full = chat(product)
    tokens = request(port, "/tokenize", {"content": full, "add_special": False})[
        "tokens"
    ]
    length = len(tokens)
    if length <= 512:
        return full, length, length, False
    empty_length = len(
        request(port, "/tokenize", {"content": chat(""), "add_special": False})[
            "tokens"
        ]
    )
    remaining = 512 - empty_length - 4
    product_tokens = request(
        port, "/tokenize", {"content": product, "add_special": False}
    )["tokens"]
    while remaining >= 16:
        shortened = request(
            port, "/detokenize", {"tokens": product_tokens[:remaining]}
        )["content"]
        text = chat(shortened)
        actual = len(
            request(port, "/tokenize", {"content": text, "add_special": False})[
                "tokens"
            ]
        )
        if actual <= 512:
            return text, actual, length, True
        remaining -= max(1, actual - 512)
    raise ValueError("Instructions/query exhaust the frozen token budget.")


def generate(runtime_directory, output):
    original, original_path = original_contracts()
    runtime = json.loads((runtime_directory / "runtime.json").read_bytes())
    if checksum(runtime["model"]) != MODEL_SHA:
        raise ValueError("Pinned model bytes changed.")
    for name, expected in runtime["runtime_files_sha256"].items():
        if checksum(runtime_directory / "runtime" / name) != expected:
            raise ValueError("Pinned runtime bytes changed.")
    inputs = original.load_rows(DEVELOPMENT / "inputs.jsonl")
    selected = original.select(inputs, 256)
    output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    command = [
        runtime["server"],
        "-m",
        runtime["model"],
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "-ngl",
        "0",
        "-t",
        "4",
        "-tb",
        "4",
        "-c",
        "1024",
        "-np",
        "1",
        "--no-webui",
        "--no-context-shift",
    ]
    plan = {
        "kind": "esci-llamacpp-prompt-plan",
        "input_sha256": checksum(DEVELOPMENT / "inputs.jsonl"),
        "source_sha256": checksum(__file__),
        "original_prompt_source_sha256": checksum(original_path),
        "runtime_receipt_sha256": checksum(runtime_directory / "runtime.json"),
        "selected_input_indices": selected,
        "selected_inputs_sha256": sha256(
            b"".join(original.canonical(inputs[i]) for i in selected)
        ).hexdigest(),
        "definitions": original.DEFINITIONS,
        "role_rules": original.ROLE_RULES,
        "contracts": list(original.CONTRACTS),
        "command": command,
        "grammar": GRAMMAR,
        "sampling": {
            "temperature": 0,
            "seed": 20261004,
            "n_predict": 1,
            "cache_prompt": False,
        },
        "input_token_budget": 512,
        "probe_pairs": 32,
        "time_cap_seconds": 900,
        "score": "grammar-constrained greedy one-letter choice; no calibrated confidence",
        "selective_acceptance": None,
        "gate_eligible": False,
        "references_opened": False,
    }
    (output / "plan.json").write_bytes(canonical(plan))
    process = None
    started = time.monotonic()
    count, pairs, status = 0, 0, "completed"
    with (output / "server.log").open("wb") as log:
        try:
            process = subprocess.Popen(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            (output / "process.json").write_bytes(
                canonical({"pid": process.pid, "port": port, "started": time.time()})
            )
            for _ in range(120):
                if process.poll() is not None:
                    raise ValueError("Owned CPU server exited during startup.")
                try:
                    if request(port, "/health")["status"] == "ok":
                        break
                except Exception:
                    time.sleep(0.5)
            else:
                raise TimeoutError("Owned CPU server did not become healthy.")
            inference_started = time.monotonic()
            with (output / "scores.jsonl").open("xb") as scores:
                for index in selected:
                    if time.monotonic() - inference_started >= 900:
                        status = "inference-time-cap"
                        break
                    for contract in original.CONTRACTS:
                        text, token_count, full_length, truncated = prompt(
                            port, inputs[index], contract, original
                        )
                        result = request(
                            port,
                            "/completion",
                            {**plan["sampling"], "prompt": text, "grammar": GRAMMAR},
                        )
                        label = result.get("content", "").strip()
                        row = {
                            "input_index": index,
                            "contract": contract,
                            "input_sha256": sha256(
                                original.canonical(inputs[index])
                            ).hexdigest(),
                            "label": label if label in original.LABELS else None,
                            "raw_output": result.get("content"),
                            "tokens": token_count,
                            "untruncated_tokens": full_length,
                            "truncated": truncated,
                            "timings": result.get("timings"),
                            "gate_eligible": False,
                        }
                        scores.write(canonical(row))
                        scores.flush()
                        count += 1
                    pairs += 1
                    if pairs == 32:
                        elapsed = time.monotonic() - inference_started
                        projected = elapsed * len(selected) / pairs
                        (output / "probe.json").write_bytes(
                            canonical(
                                {
                                    "pairs": pairs,
                                    "scores": count,
                                    "seconds": elapsed,
                                    "projected_full_768_score_seconds": projected,
                                }
                            )
                        )
                        if projected > 900:
                            status = "probe-projected-time-cap"
                            break
            receipt = {
                "kind": "esci-llamacpp-generation",
                "status": status,
                "pairs": pairs,
                "scores": count,
                "inference_seconds": time.monotonic() - inference_started,
                "total_seconds": time.monotonic() - started,
                "scores_sha256": checksum(output / "scores.jsonl"),
                "plan_sha256": checksum(output / "plan.json"),
                "gate_eligible": False,
                "references_opened": False,
            }
            (output / "generation.json").write_bytes(canonical(receipt))
            print(json.dumps(receipt))
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=15)
                (output / "cleanup.json").write_bytes(
                    canonical(
                        {
                            "owned_pid": process.pid,
                            "returncode": process.returncode,
                            "terminated": process.poll() is not None,
                            "port": port,
                        }
                    )
                )


def evaluate(output):
    original, _ = original_contracts()
    plan = json.loads((output / "plan.json").read_bytes())
    generation = json.loads((output / "generation.json").read_bytes())
    if (
        checksum(DEVELOPMENT / "inputs.jsonl") != plan["input_sha256"]
        or checksum(output / "scores.jsonl") != generation["scores_sha256"]
    ):
        raise ValueError("Frozen development inputs or completed outputs differ.")
    amendment = {
        "kind": "esci-llamacpp-diagnostic-plan",
        "reference_sha256": checksum(DEVELOPMENT / "references.jsonl"),
        "decoder": "exact grammar-constrained E/S/C/I or unknown",
        "thresholds": None,
        "gate_eligible": False,
    }
    (output / "diagnostic-plan.json").write_bytes(canonical(amendment))
    inputs = original.load_rows(DEVELOPMENT / "inputs.jsonl")
    references = {
        (row["query_id"], row["product_id"]): row
        for row in original.load_rows(DEVELOPMENT / "references.jsonl")
    }
    scores = original.load_rows(output / "scores.jsonl")
    grouped = {
        contract: [row for row in scores if row["contract"] == contract]
        for contract in original.CONTRACTS
    }
    if (
        len(
            {tuple(row["input_index"] for row in values) for values in grouped.values()}
        )
        != 1
    ):
        raise ValueError("Matched prompt comparison requires identical scored pairs.")
    report = {
        "kind": "esci-llamacpp-development-prompt-diagnostic",
        "gate_eligible": False,
        "generation": generation,
        "contracts": {},
        "limits": [
            "Exposed development labels only, not confirmation or actual-gap transfer.",
            "Quantised llama.cpp grammar choices are not parity-equivalent to PyTorch four-token logits.",
            "No calibrated confidence or selective label acceptance is available.",
        ],
    }
    for contract, values in grouped.items():
        matrix = Counter()
        for row in values:
            pair = inputs[row["input_index"]]
            if sha256(original.canonical(pair)).hexdigest() != row["input_sha256"]:
                raise ValueError("Score belongs to different frozen input.")
            reference = references[(pair["query_id"], pair["product_id"])]
            if reference["provenance"]["kind"] != "published":
                raise ValueError("Only published development labels are authorised.")
            matrix[(reference["label"], row["label"])] += 1
        correct = sum(matrix[(label, label)] for label in original.LABELS)
        irrelevant = sum(n for (gold, _), n in matrix.items() if gold == "I")
        exact = sum(n for (_, predicted), n in matrix.items() if predicted == "E")
        report["contracts"][contract] = {
            "pairs": len(values),
            "correct": correct,
            "accuracy": correct / len(values) if values else None,
            "unknown": sum(row["label"] is None for row in values),
            "truncated": sum(row["truncated"] for row in values),
            "confusion": {
                gold: {
                    predicted or "unknown": matrix[(gold, predicted)]
                    for predicted in (*original.LABELS, None)
                }
                for gold in original.LABELS
            },
            "irrelevant_to_exact_errors": matrix[("I", "E")],
            "reference_irrelevant_pairs": irrelevant,
            "irrelevant_to_exact_rate": matrix[("I", "E")] / irrelevant
            if irrelevant
            else None,
            "exact_contamination": matrix[("I", "E")] / exact if exact else None,
        }
    (output / "report.json").write_bytes(canonical(report))
    print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "generate", "evaluate"))
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            prepare(args.runtime)
        elif args.mode == "generate":
            generate(args.runtime, args.output)
        else:
            evaluate(args.output)
    except Exception as exc:
        directory = args.output or args.runtime
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"failure-{time.time_ns()}.json").write_bytes(
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
