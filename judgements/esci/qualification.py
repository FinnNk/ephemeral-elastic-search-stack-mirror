"""Compare a running candidate with independent, locally retained canary scores."""

import json
from pathlib import Path
import urllib.request

from .contract import probabilities
from .release import content_digest, read_json, sha256, write_json
from .runtime import INFERENCE_PROTOCOL


def compare(expected: list[dict], actual: list[dict]) -> dict:
    if len(expected) != len(actual) or not expected:
        raise ValueError("Expected one outcome per canary, with at least one canary.")
    maximum, changed = 0.0, 0
    for first, second in zip(expected, actual, strict=True):
        a, b = (
            probabilities(first["probabilities"]),
            probabilities(second["probabilities"]),
        )
        maximum = max(maximum, *(abs(x - y) for x, y in zip(a, b, strict=True)))
        changed += (first["outcome"], first["label"]) != (
            second["outcome"],
            second["label"],
        )
    return {
        "rows": len(actual),
        "max_probability_delta": maximum,
        "changed_labels_or_abstentions": changed,
        "passed": maximum <= 1e-4 and changed == 0,
    }


def qualify(
    endpoint: str, reference: Path, registration: Path, image: str, output: Path
) -> dict:
    receipt, canaries = read_json(registration), read_json(reference)
    if canaries["release_sha256"] != receipt["release_sha256"]:
        raise ValueError("Canaries describe a different release.")
    if (canaries.get("origin") != "frozen-research-scores"
            or canaries.get("protocol") != INFERENCE_PROTOCOL):
        raise ValueError(
            "Canaries must come from the independent frozen research scores."
        )
    if "@sha256:" not in image:
        raise ValueError("Pin the tested image by digest.")
    identity = {k: receipt[k] for k in ("name", "version", "artifact_sha256")}
    rows = canaries["rows"]
    if not 8 <= len(rows) <= 128:
        raise ValueError("Use 8–128 canaries from the already-exposed research cohort.")

    def call(indices):
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(
                {"instances": [rows[i]["input"] for i in indices]}
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.load(response)
        if result["model"] != identity:
            raise ValueError("Serving endpoint has the wrong model identity.")
        return result["predictions"]

    expected = [r["expected"] for r in rows]
    arrangements = {"batch": call(list(range(len(rows))))}
    arrangements["singletons"] = [call([i])[0] for i in range(len(rows))]
    arrangements["reversed"] = list(reversed(call(list(reversed(range(len(rows)))))))
    checks = {key: compare(expected, value) for key, value in arrangements.items()}
    result = {
        "format": "esci-runtime-qualification-v1",
        "model": identity,
        "release_sha256": receipt["release_sha256"],
        "runtime_image": image,
        "reference_sha256": sha256(reference),
        "checks": checks,
        "passed": all(c["passed"] for c in checks.values()),
        "scope": "Numerical agreement only; not confirmation of lab accuracy.",
    }
    result["evidence_sha256"] = content_digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(
            "Preserve previous qualification attempts; choose a new output path."
        )
    write_json(output, result)
    return result
