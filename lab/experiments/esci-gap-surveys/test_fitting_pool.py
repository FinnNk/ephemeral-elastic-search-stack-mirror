"""Boundary tests for fitting selection and selected-reference materialisation."""

import gzip
import importlib.util
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

spec = importlib.util.spec_from_file_location(
    "fitting_pool", Path(__file__).with_name("fitting_pool.py")
)
pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pool)


def metadata(query="camera", count=30):
    return [
        {"query": query, "query_id": 1, "product_id": f"p{i}", "example_id": i}
        for i in range(count)
    ]


def test_selection_is_bounded_deterministic_label_free_and_normalised():
    rows = metadata()
    key = pool.query_key(" camera ")
    a = pool.sample_pairs(rows, {key})
    b = pool.sample_pairs(list(reversed(rows)), {key})
    assert a == b and len(a) == 25
    with pytest.raises(ValueError, match="reference labels"):
        pool.sample_pairs([dict(rows[0], esci_label="E")], {key})
    with pytest.raises(ValueError, match="no eligible"):
        pool.sample_pairs(rows, {pool.query_key("different")})


def test_alias_products_deduplicate_by_lowest_example_without_labels():
    rows = [
        {"query": " camera ", "query_id": 2, "product_id": "p", "example_id": 9},
        {"query": "camera", "query_id": 1, "product_id": "p", "example_id": 3},
    ]
    selected = pool.sample_pairs(rows, {pool.query_key("camera")})
    assert len(selected) == 1 and selected[0]["source_example_id"] == 3


def test_metadata_scan_filters_test_locale_and_never_reads_label_column(tmp_path):
    rows = [
        dict(
            metadata(count=1)[0],
            split="train",
            large_version=1,
            product_locale="us",
            esci_label="DO-NOT-READ",
        ),
        dict(
            metadata(count=1)[0],
            split="test",
            large_version=1,
            product_locale="us",
            esci_label="SEALED",
        ),
        dict(
            metadata(count=1)[0],
            split="train",
            large_version=1,
            product_locale="es",
            esci_label="OTHER",
        ),
    ]
    path = tmp_path / "source.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    found = list(pool.scan_metadata(path, 1))
    assert len(found) == 1 and "esci_label" not in found[0]


def test_gold_scan_reads_only_selected_training_example_identity(tmp_path):
    rows = [
        dict(
            metadata(count=1)[0],
            split="train",
            large_version=1,
            product_locale="us",
            esci_label="C",
        ),
        dict(
            metadata(count=1)[0],
            example_id=12,
            split="train",
            large_version=1,
            product_locale="us",
            esci_label="DO-NOT-READ",
        ),
        dict(
            metadata(count=1)[0],
            example_id=13,
            split="test",
            large_version=1,
            product_locale="us",
            esci_label="SEALED",
        ),
    ]
    path = tmp_path / "source.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    selected = pool.sample_pairs(metadata(count=1), {pool.query_key("camera")})
    refs = pool.selected_references(path, selected, "source-sha")
    assert refs[0]["label"] == "C" and len(refs) == 1
    assert refs[0]["provenance"] == {
        "kind": "published",
        "source_id": "source-sha",
        "source_split": "train",
    }


def test_actual_catalogue_nullable_fields_preserved_and_missing_rejected(tmp_path):
    path = tmp_path / "catalogue.gz"
    product = {
        "product_id": "p0",
        "title": "camera",
        "description": None,
        "category_path": [],
    }
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(json.dumps(product) + "\n")
    selected = pool.sample_pairs(metadata(count=1), {pool.query_key("camera")})
    inputs = pool.materialise_catalogue(path, selected)
    assert inputs[0]["product"] == product and "label" not in inputs[0]
    selected[0]["product_id"] = "missing"
    with pytest.raises(ValueError, match="absent"):
        pool.materialise_catalogue(path, selected)


def test_immutable_freeze_cannot_be_overwritten(tmp_path):
    path = tmp_path / "selection.json"
    pool.write_new(path, {"references_opened": False})
    with pytest.raises(FileExistsError):
        pool.write_new(path, {"references_opened": True})
