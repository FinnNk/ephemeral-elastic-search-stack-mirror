"""Review packets preserve sampling/exclusions without exposing model evidence."""

import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from label_quality import canonical, query_key
from prepare_gap_review import prepare


def source(tmp_path):
    rows = []
    for query_id, query in [
        ("1", "Phone"),
        ("alias", " PHONE "),
        ("2", "shoe"),
        ("3", "bag"),
    ]:
        for product in ("a", "b"):
            rows.append(
                {
                    "query_id": query_id,
                    "product_id": product,
                    "request": {
                        "query": query,
                        "country": "GB",
                        "currency": "GBP",
                        "filters": {"category": ["Retail"]},
                    },
                    "product": {
                        "product_id": product,
                        "title": "Product £19.99",
                        "brand": "Retail",
                        "description": "Original text",
                        "bullets": ["Original feature"],
                        "category_path": ["Retail", "Accessories"],
                        "rating": 4.9,
                        "prediction": "LEAK",
                        "score": "LEAK",
                        "attrs": {"label": "LEAK"},
                    },
                    "label": "LEAK",
                    "prediction": "LEAK",
                    "confidence": "LEAK",
                    "stage": "LEAK",
                }
            )
    inputs = tmp_path / "inputs.json"
    inputs.write_bytes(
        canonical(
            {
                "kind": "judgement-pass-inputs",
                "context": {"rubric": "esci-v1"},
                "pairs": rows,
            }
        )
    )
    audit = tmp_path / "audit.json"
    audit.write_bytes(
        canonical(
            {
                "inputs_sha256": hashlib.sha256(inputs.read_bytes()).hexdigest(),
                "audit_complete": True,
                "query_ids": ["1"],
            }
        )
    )
    return inputs, audit


def test_protected_aliases_are_excluded_and_selected_queries_keep_all_pairs(tmp_path):
    inputs, audit = source(tmp_path)
    report = prepare(inputs, audit, tmp_path / "packet", 2, "frozen-seed")
    manifest = json.loads((tmp_path / "packet/operator/manifest.json").read_bytes())
    assert report["queries"] == 2 and report["pairs"] == 4
    assert manifest["selection"]["eligible_queries"] == 2
    assert manifest["selection"]["excluded_pairs"] == 4
    assert query_key("phone") not in manifest["selection"]["query_keys"]
    assert report["reference_labels_created"] == 0 and report["gate_eligible"] is False
    assert manifest["confirmation_reservation_confirmed"] is False


def test_reviewer_packet_is_allowlisted_utf8_and_has_only_blank_answers(tmp_path):
    inputs, audit = source(tmp_path)
    prepare(inputs, audit, tmp_path / "packet", 2, "frozen-seed")
    reviewer = tmp_path / "packet/reviewer"
    text = (reviewer / "items.jsonl").read_text(encoding="utf-8")
    assert "LEAK" not in text
    item = json.loads(text.splitlines()[0])
    assert set(item) == {"pair_id", "query", "market", "filters", "product"}
    assert "£19.99" in item["product"]["title"]
    assert item["filters"] == {"category": ["Retail"]}
    with (reviewer / "labels.csv").open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    assert len(records) == 4 and all(
        not row[k] for row in records for k in ("label", "uncertain", "reason")
    )


def test_selection_is_stable_when_input_order_changes(tmp_path):
    inputs, audit = source(tmp_path)
    prepare(inputs, audit, tmp_path / "one", 1, "frozen-seed")
    frozen = json.loads(inputs.read_bytes())
    frozen["pairs"].reverse()
    inputs.write_bytes(canonical(frozen))
    exclusion = json.loads(audit.read_bytes())
    exclusion["inputs_sha256"] = hashlib.sha256(inputs.read_bytes()).hexdigest()
    audit.write_bytes(canonical(exclusion))
    prepare(inputs, audit, tmp_path / "two", 1, "frozen-seed")
    assert (tmp_path / "one/reviewer/items.jsonl").read_bytes() == (
        tmp_path / "two/reviewer/items.jsonl"
    ).read_bytes()


@pytest.mark.parametrize(
    "change", ["hash", "incomplete", "unknown", "duplicate", "identity"]
)
def test_invalid_frozen_inputs_or_exclusions_fail_before_output(tmp_path, change):
    inputs, audit = source(tmp_path)
    frozen, exclusion = json.loads(inputs.read_bytes()), json.loads(audit.read_bytes())
    if change == "hash":
        exclusion["inputs_sha256"] = "f" * 64
    elif change == "incomplete":
        exclusion["audit_complete"] = False
    elif change == "unknown":
        exclusion["query_ids"] = ["missing"]
    else:
        if change == "duplicate":
            frozen["pairs"].append(frozen["pairs"][0])
        else:
            frozen["pairs"][0]["product"]["product_id"] = "another"
        inputs.write_bytes(canonical(frozen))
        exclusion["inputs_sha256"] = hashlib.sha256(inputs.read_bytes()).hexdigest()
    audit.write_bytes(canonical(exclusion))
    with pytest.raises(ValueError):
        prepare(inputs, audit, tmp_path / "packet", 1, "frozen-seed")
    assert not (tmp_path / "packet").exists()


def test_packet_never_overwrites_an_existing_attempt(tmp_path):
    inputs, audit = source(tmp_path)
    prepare(inputs, audit, tmp_path / "packet", 2, "frozen-seed")
    before = (tmp_path / "packet/operator/manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        prepare(inputs, audit, tmp_path / "packet", 2, "other-seed")
    assert (tmp_path / "packet/operator/manifest.json").read_bytes() == before


@pytest.mark.parametrize(
    "field", ["filters", "market", "brand", "bullets", "category_path", "context"]
)
def test_nested_evidence_and_missing_context_fail_before_writing(tmp_path, field):
    inputs, audit = source(tmp_path)
    frozen, exclusion = json.loads(inputs.read_bytes()), json.loads(audit.read_bytes())
    if field == "filters":
        frozen["pairs"][0]["request"]["filters"] = {"prediction": "LEAK"}
    elif field == "market":
        frozen["pairs"][0]["request"]["country"] = {"score": "LEAK"}
    elif field == "context":
        del frozen["context"]
    else:
        frozen["pairs"][0]["product"][field] = (
            [{"label": "LEAK"}] if field != "brand" else {"label": "LEAK"}
        )
    inputs.write_bytes(canonical(frozen))
    exclusion["inputs_sha256"] = hashlib.sha256(inputs.read_bytes()).hexdigest()
    audit.write_bytes(canonical(exclusion))
    with pytest.raises(ValueError):
        prepare(inputs, audit, tmp_path / "packet", 1, "frozen-seed")
    assert not (tmp_path / "packet").exists()
