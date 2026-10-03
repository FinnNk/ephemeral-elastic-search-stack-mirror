import importlib.util
from pathlib import Path
import pytest

MODULE = Path(__file__).with_name("residual_audit.py")
spec = importlib.util.spec_from_file_location("residual_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture():
    observations = {
        "kind": "search-variant-observation-set",
        "schema_version": 1,
        "errors": [],
        "variants": {"baseline": {}, "candidate": {}},
        "baseline_variant": "baseline",
        "captured_depth": 2,
        "observations": [
            {
                "query_id": "q1",
                "request": {"query": " Shoes "},
                "results": {
                    "baseline": {"ids": ["a", "b"]},
                    "candidate": {"ids": ["a", "b"]},
                },
            },
            {
                "query_id": "q2",
                "request": {"query": "lamp"},
                "results": {"baseline": {"ids": ["c"]}, "candidate": {"ids": ["c"]}},
            },
        ],
    }
    judgements = [
        {
            "query_id": "q1",
            "product_id": "a",
            "grade": 3,
            "gate_eligible": True,
            "provenance": {"kind": "published"},
        }
    ]
    metadata = [
        {
            "example_id": 1,
            "query": "shoes",
            "query_id": "alias",
            "product_id": "b",
            "product_locale": "us",
            "split": "train",
        },
        {
            "example_id": 2,
            "query": "lamp",
            "query_id": "q2",
            "product_id": "different-product",
            "product_locale": "us",
            "split": "test",
        },
        {
            "example_id": 3,
            "query": "lamp",
            "query_id": "q2",
            "product_id": "c",
            "product_locale": "jp",
            "split": "test",
        },
    ]
    products = [
        {"product_id": p, "category": "shoes" if p != "c" else "home"}
        for p in ("a", "b", "c")
    ]
    return (
        observations,
        judgements,
        metadata,
        products,
        {"query_ids": ["q1", "q2"]},
        {"query_ids": ["q2"]},
    )


def test_normalised_source_match_never_substitutes_product_or_locale():
    result = audit.analyse(*fixture())
    assert result["pooled_residual_pairs"] == 2
    assert result["published_source_metadata"]["additional_residual_pairs"] == 1
    assert result["published_source_metadata"]["exact_query_id_pairs"] == 0
    assert result["variants"]["candidate"]["gate_fraction"] == pytest.approx(1 / 3)
    assert result["variants"]["candidate"][
        "conditional_metadata_coverage_upper_bound"
    ] == pytest.approx(2 / 3)
    assert result["minimum_unique_labels_for_both_variants"] == 2
    assert result["reservation_constraints"]["specialist_excluded_pairs"] == 1
    assert result["label_values_read_from_source"] is False
    assert result["gate_eligible"] is False


def test_unqualified_model_records_cannot_raise_gate_coverage():
    values = fixture()
    values[1][0].update(gate_eligible=False, provenance={"kind": "model"})
    with pytest.raises(ValueError, match="gate references"):
        audit.analyse(*values)


def test_unequal_variant_pools_count_shared_labels_once():
    values = fixture()
    values[0]["observations"][0]["results"]["candidate"]["ids"] = ["a", "d"]
    values[3].append({"product_id": "d", "category": "shoes"})
    result = audit.analyse(*values)
    assert result["pooled_residual_pairs"] == 3
    assert result["minimum_unique_labels_for_both_variants"] == 3


def test_parquet_reader_excludes_label_columns(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / "source.parquet"
    records = fixture()[2]
    for row in records:
        row["esci_label"] = "DO-NOT-READ"
    pq.write_table(pa.Table.from_pylist(records), path)
    actual = list(audit.metadata_rows(path))
    assert len(actual) == 2
    assert all(set(row) == set(audit.METADATA_COLUMNS) for row in actual)
    assert "esci_label" not in audit.METADATA_COLUMNS
