"""Returned labels must match even when a predictor returns unchanged probabilities."""

import json

import pytest

from diagnose_esci_parity import predictions, report
from esci.release import sha256, write_json


def test_returned_abstention_cannot_hide_behind_matching_probabilities(tmp_path):
    expected = {"probabilities": [0.99, 0.004, 0.003, 0.003],
                "confidence": 0.99, "label": "E", "outcome": "labelled"}
    inputs = tmp_path / "inputs.json"
    write_json(inputs, {"pairs": 1, "queries": 1, "singleton_indices": [0],
                        "rows": [{"query_hash": "q", "reference": expected}]})
    capture = tmp_path / "batch.jsonl"
    records = [{"header": {"input_sha256": sha256(inputs), "arrangement": "batch"}},
               {"indices": [0], "predictions": [{**expected, "label": None,
                                                 "outcome": "abstain"}]}]
    capture.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    output = tmp_path / "report.json"
    with pytest.raises(SystemExit) as failure:
        report(inputs, {"batch": capture}, output)
    assert failure.value.code == 2
    result = json.loads(output.read_text(encoding="utf-8"))
    assert not result["passed"]
    assert result["decision_checks"]["batch"]["max_probability_delta"] == 0
    assert result["decision_checks"]["batch"]["changed_labels_or_abstentions"] == 1


def test_duplicate_http_pair_is_rejected(tmp_path):
    inputs = tmp_path / "inputs.json"
    write_json(inputs, {"pairs": 1, "singleton_indices": [0]})
    capture = tmp_path / "batch.jsonl"
    records = [{"header": {"input_sha256": sha256(inputs), "arrangement": "batch"}},
               {"indices": [0, 0], "predictions": [{}, {}]}]
    capture.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="more than once"):
        predictions(capture, inputs)
