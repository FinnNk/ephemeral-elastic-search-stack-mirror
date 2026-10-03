"""Select canaries from independently generated singleton references."""

from pathlib import Path

from .release import content_digest, read_json, sha256, verify_bundle, write_json
from .runtime import INFERENCE_PROTOCOL


def export_canaries(reference: Path, bundle: Path, output: Path, count: int = 64) -> dict:
    frozen = read_json(reference)
    manifest = verify_bundle(bundle)
    content = {k: v for k, v in frozen.items() if k != "reference_content_sha256"}
    if (frozen.get("origin") != "frozen-research-scores"
            or frozen.get("protocol") != INFERENCE_PROTOCOL
            or content_digest(content) != frozen["reference_content_sha256"]
            or frozen["release_sha256"] != manifest["release_sha256"]):
        raise ValueError("Require intact independent references for this inference protocol.")
    rows = frozen["rows"]
    if not 8 <= count <= min(len(rows), 128):
        raise ValueError("Use 8–128 spread canaries.")
    indices = [round(i * (len(rows)-1) / (count-1)) for i in range(count)]
    value = {"origin": "frozen-research-scores", "protocol": INFERENCE_PROTOCOL,
             "release_sha256": manifest["release_sha256"],
             "reference_sha256": sha256(reference), "provenance": frozen["provenance"],
             "rows": [{"input": rows[i]["input"], "expected": rows[i]["reference"]}
                      for i in indices]}
    if output.exists():
        raise FileExistsError("Preserve existing canaries; choose a new output path.")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, value)
    return {"rows": count, "reference_sha256": sha256(output)}
