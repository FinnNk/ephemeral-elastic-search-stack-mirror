"""Field separation and incomplete-probe safety for a retrieval-model survey."""

import pytest
from pair_reranker_features import product_text, probe_projection


def test_lab_fields_and_references_never_enter_model_text():
    row = {
        "product": {
            "title": "phone case",
            "brand": "Acme",
            "category_path": ["Cases"],
            "description": "fits Model 8",
            "bullets": "soft shell",
            "price": 999,
            "popularity": 200,
            "stock": "private-stock",
        },
        "reference_label": "private-label",
        "query_id": "private-query",
    }
    text = product_text(row, "catalogue-text")
    assert "phone case" in text and "fits Model 8" in text
    for value in ("999", "200", "private-stock", "private-label", "private-query"):
        assert value not in text


def test_nullable_published_text_does_not_fail():
    row = {
        "product": {
            "title": None,
            "brand": None,
            "category_path": None,
            "description": None,
            "bullets": None,
        }
    }
    assert isinstance(product_text(row, "catalogue-text"), str)


def test_unknown_contract_fails_instead_of_using_more_fields():
    with pytest.raises(ValueError):
        product_text({"product": {}}, "all-fields")


def test_empty_probe_cannot_claim_feasible_runtime():
    with pytest.raises(ValueError):
        probe_projection(0, 5, 100)
    assert probe_projection(10, 5, 100) == 50
