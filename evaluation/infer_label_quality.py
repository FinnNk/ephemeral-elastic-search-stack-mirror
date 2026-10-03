"""Run the pinned candidate on a frozen, independently reserved quality cohort."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib import request

from label_quality import canonical, checksum, indexed, query_key, read_json, read_rows

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judgements"))
from telemetry import telemetry  # noqa: E402


def infer(
    inputs_path,
    manifest_path,
    audit_path,
    policy_path,
    reservation_path,
    endpoint,
    output,
):
    manifest, audit = read_json(manifest_path), read_json(audit_path)
    if (
        manifest.get("kind") != "esci-label-quality-cohort"
        or manifest.get("reservation_confirmed") is not True
        or not manifest.get("reservation_sha256")
        or audit.get("kind") != "esci-query-independence-audit"
        or audit.get("audit_complete") is not True
        or audit.get("normalisation") != "nfkc_html_whitespace_v1"
    ):
        raise ValueError(
            "Freeze and independently reserve the quality cohort before inference."
        )
    for name, path in [
        ("inputs", inputs_path),
        ("audit", audit_path),
        ("policy", policy_path),
        ("reservation", reservation_path),
    ]:
        if checksum(path) != manifest[name + "_sha256"]:
            raise ValueError(
                "Frozen " + name + " bytes differ from the cohort manifest."
            )
    rows = read_rows(inputs_path)
    indexed(rows)
    identities = {query_key(row["request"]["query"]) for row in rows}
    if (
        identities != set(manifest["query_keys"])
        or identities & set(audit["excluded_query_keys"])
        or any(row["query_key"] != query_key(row["request"]["query"]) for row in rows)
    ):
        raise ValueError(
            "Input query membership differs or overlaps protected queries."
        )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    provenance = {
        "kind": "model",
        "model": manifest["model"],
        "release_sha256": manifest["release_sha256"],
        "runtime_image": manifest["runtime_image"],
        "policy_sha256": manifest["model_policy_sha256"],
        "pass_id": "quality-" + checksum(manifest_path)[:16],
        "source_id": hashlib.sha256(
            canonical({"manifest_sha256": checksum(manifest_path)})
        ).hexdigest(),
    }
    with (output / "predictions.jsonl").open("xb") as stream:
        for offset in range(0, len(rows), 64):
            batch = rows[offset : offset + 64]
            pairs = [
                {
                    key: row[key]
                    for key in ("query_id", "product_id", "request", "product")
                }
                for row in batch
            ]
            with telemetry.span("model.quality.batch", kind="client"):
                headers = {"Content-Type": "application/json"}
                telemetry.inject(headers)
                call = request.Request(
                    endpoint, canonical({"instances": pairs}), headers
                )
                with request.urlopen(call, timeout=130) as response:
                    result = json.load(response)
            if result["model"] != manifest["model"] or len(
                result["predictions"]
            ) != len(batch):
                raise ValueError(
                    "Serving model or prediction count differs from the frozen cohort."
                )
            for pair, predicted in zip(pairs, result["predictions"], strict=True):
                record = {
                    **predicted,
                    "query_id": pair["query_id"],
                    "product_id": pair["product_id"],
                    "input_sha256": hashlib.sha256(canonical(pair)).hexdigest(),
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "provenance": provenance,
                    "gate_eligible": False,
                }
                stream.write(canonical(record))
            stream.flush()
            print(f"Quality predictions: {offset + len(batch)}/{len(rows)}", flush=True)
    receipt = {
        "kind": "esci-label-quality-inference",
        "complete": True,
        "model": manifest["model"],
        "pairs": len(rows),
        "queries": len(identities),
        "seconds": time.monotonic() - started,
        "manifest_sha256": checksum(manifest_path),
        "predictions_sha256": checksum(output / "predictions.jsonl"),
        "gate_eligible": False,
    }
    # Publish completion only after all prediction bytes are durable to this process.
    temporary = output / "inference.json.tmp"
    temporary.write_bytes(canonical(receipt))
    temporary.rename(output / "inference.json")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "manifest", "audit", "policy", "reservation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    args = parser.parse_args()
    telemetry.configure("esci-label-quality")
    print(
        json.dumps(
            infer(
                args.inputs,
                args.manifest,
                args.audit,
                args.policy,
                args.reservation,
                args.endpoint,
                args.output,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
