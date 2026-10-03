"""Canaries cannot reuse another protocol or altered independent evidence."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esci.canaries import export_canaries
from esci.release import content_digest, write_json
from esci.runtime import INFERENCE_PROTOCOL


def test_independent_reference_integrity(tmp_path, monkeypatch):
    import esci.canaries as module
    monkeypatch.setattr(module, "verify_bundle", lambda _: {"release_sha256": "new-release"})
    source = tmp_path / "references.json"
    rows = [{"input": {"product_id": str(i)}, "reference": {"label": None}}
            for i in range(20)]
    value = {"origin": "frozen-research-scores", "protocol": INFERENCE_PROTOCOL,
             "release_sha256": "new-release", "provenance": {"loader": "research"},
             "rows": rows}
    value["reference_content_sha256"] = content_digest(value)
    write_json(source, value)
    result = export_canaries(source, tmp_path, tmp_path / "canaries.json", 8)
    assert result["rows"] == 8
    value["rows"][0]["reference"]["label"] = "E"
    write_json(source, value)
    with pytest.raises(ValueError, match="intact independent"):
        export_canaries(source, tmp_path, tmp_path / "tampered.json", 8)
    value["protocol"] = {"internal_batch_size": 8}
    value["reference_content_sha256"] = content_digest(
        {k:v for k,v in value.items() if k != "reference_content_sha256"})
    write_json(source, value)
    with pytest.raises(ValueError, match="this inference protocol"):
        export_canaries(source, tmp_path, tmp_path / "old-protocol.json", 8)
