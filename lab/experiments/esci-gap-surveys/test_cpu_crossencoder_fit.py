"""Check feature isolation and whole-query splitting without running Torch."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "cpu_crossencoder_fit", Path(__file__).with_name("cpu_crossencoder_fit.py")
)
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)


def example(query="camera"):
    return {
        "request": {"query": query},
        "query_key": fit.query_key(query),
        "query_id": "q",
        "product_id": "p",
        "product": {
            "title": "camera case",
            "brand": "North",
            "category_path": ["Electronics", "Accessories"],
            "description": None,
            "bullets": "Fits camera",
            "price_minor": 1,
            "popularity": 999,
            "available": True,
        },
    }


def test_original_text_only_and_nullable_fields():
    row = example()
    a = fit.text(row)
    row.update({"query_id": "changed", "product_id": "changed", "label": "I"})
    row["product"].update({"price_minor": 99999, "popularity": 0, "available": False})
    assert fit.text(row) == a
    assert a[0] == "camera" and "Electronics > Accessories" in a[1]
    assert "999" not in a[1]


def test_authoritative_alias_groups_cannot_cross_split():
    a, b = example(" CAMERA "), example("camera")
    assert fit.group(a) == fit.group(b)
    split = fit.partitions([example(str(i)) for i in range(1000)] + [a, b])
    assert split[fit.group(a)] == split[fit.group(b)]
    a["query_key"] = "bad"
    with pytest.raises(ValueError, match="authoritative"):
        fit.group(a)


def test_published_reference_alignment_and_invalid_source_guard():
    row = example()
    ref = {
        "query_id": "q",
        "product_id": "p",
        "label": "C",
        "provenance": {"kind": "published"},
    }
    assert fit.truth_indices([row], [ref]) == [2]
    ref["provenance"]["kind"] = "model"
    with pytest.raises(ValueError, match="published"):
        fit.truth_indices([row], [ref])
