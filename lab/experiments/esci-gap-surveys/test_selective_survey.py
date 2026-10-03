"""Fixed survey rules must use observable inputs, never ground-truth features."""

from hashlib import sha256
import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location(
    "selective_survey", Path(__file__).with_name("selective_survey.py")
)
survey_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey_module)


def test_features_ignore_reference_label_and_handle_missing_category():
    pair = {
        "request": {"query": "charger for iphone 14"},
        "product": {
            "title": "Apple iPhone 13 case",
            "brand": "Apple",
            "category_path": [],
        },
    }
    first = survey_module.features(pair)
    pair["label"] = "E"
    pair["reference_label"] = "I"
    assert first == survey_module.features(pair)
    assert first["model_query"]
    assert not first["model_compatible"]
    assert not first["category_available"]


def test_exact_veto_abstains_instead_of_emitting_irrelevant():
    pair = {
        "request": {"query": "iphone 14"},
        "product": {"title": "iphone 13", "brand": "Apple"},
    }
    features = survey_module.features(pair)
    rule = {"thresholds": [0.9] * 4, "exact_veto": "model-mismatch"}
    assert not survey_module.accepts([0.95, 0.02, 0.01, 0.02], features, rule)
    assert survey_module.accepts([0.01, 0.02, 0.95, 0.02], features, rule)


def test_nonexact_specialist_accepts_only_its_winning_class():
    features = survey_module.features({"request": {"query": "shoe"}, "product": {}})
    rule = {"thresholds": [None, 0.7, None, None]}
    assert survey_module.accepts([0.1, 0.75, 0.1, 0.05], features, rule)
    assert not survey_module.accepts([0.75, 0.1, 0.1, 0.05], features, rule)


def test_same_query_pairs_remain_one_independent_cluster():
    queries = np.array(["a"] * 20 + ["b"] * 20)
    correct = np.array([True] * 20 + [False] * 20)
    bounds = survey_module.intervals(queries, correct, np.ones(40), 1000)
    assert bounds == [0, 1]


def test_metrics_include_harmful_errors_and_added_label_quality():
    result = survey_module.metrics(
        np.array(["a", "b", "c", "d"]),
        np.array([3, 1, 1, 0]),
        np.array([0, 1, 1, -1]),
        np.array([0, -1, -1, -1]),
    )
    assert result["harmful_I_to_E"] == 1
    assert result["exact_contamination"] == 1
    assert result["extra_correct_vs_095"] == 2
    assert result["precision"] == 2 / 3


def test_fixed_rule_plan_has_no_duplicates_or_label_dependent_fields():
    rules = survey_module.rules()
    assert len({rule["name"] for rule in rules}) == len(rules)
    assert len(rules) == 44
    assert rules[0]["name"] == "baseline-090"
    assert rules[1]["name"] == "baseline-095"


def test_survey_rejects_mismatched_input_and_incomplete_predictions():
    query = "shoe"
    pair = {
        "query_id": "q",
        "product_id": "p",
        "request": {"query": query},
        "product": {},
        "query_key": survey_module.query_key(query),
    }
    reference = {
        "query_id": "q",
        "product_id": "p",
        "label": "E",
        "provenance": {"kind": "published"},
    }
    prediction = {
        "query_id": "q",
        "product_id": "p",
        "input_sha256": "wrong",
        "probabilities": [0.95, 0.02, 0.02, 0.01],
    }
    with pytest.raises(ValueError, match="input differs"):
        survey_module.survey([pair], [reference], [prediction], survey_module.rules())
    actual = {
        name: pair[name] for name in ("query_id", "product_id", "request", "product")
    }
    prediction["input_sha256"] = sha256(survey_module.canonical(actual)).hexdigest()
    prediction["probabilities"] = [float("nan"), 0, 0, 0]
    with pytest.raises(ValueError, match="probabilities"):
        survey_module.survey([pair], [reference], [prediction], survey_module.rules())


def test_followup_brand_conflict_and_missing_metadata_remain_distinct():
    mismatch = survey_module.features(
        {
            "request": {"query": "apple iphone 14"},
            "product": {
                "title": "Samsung phone 14",
                "brand": "Samsung",
                "category_path": ["Electronics", "Phones"],
            },
        }
    )
    assert mismatch["brand_conflict"]
    rule = {"thresholds": [0.95, None, None, None], "exact_veto": "numeric-brand"}
    assert not survey_module.accepts([0.97, 0.01, 0.01, 0.01], mismatch, rule)
    missing = survey_module.features(
        {
            "request": {"query": "apple iphone 14"},
            "product": {"title": "Apple iphone 14"},
        }
    )
    assert missing["brand_missing"]
    assert not missing["brand_conflict"]
    assert survey_module.accepts([0.97, 0.01, 0.01, 0.01], missing, rule)


def test_category_required_rule_abstains_when_category_is_unsupported():
    feature = survey_module.features(
        {"request": {"query": "shoe"}, "product": {"title": "shoe"}}
    )
    rule = {
        "thresholds": [0.95, None, None, None],
        "exact_veto": "numeric-brand-category",
    }
    assert not survey_module.accepts([0.97, 0.01, 0.01, 0.01], feature, rule)
    feature = survey_module.features(
        {
            "request": {"query": "shoes"},
            "product": {"title": "shoes", "category_path": ["Fashion", "Shoes"]},
        }
    )
    assert survey_module.accepts([0.97, 0.01, 0.01, 0.01], feature, rule)


def test_followup_does_not_change_initial_rule_plan():
    assert len(survey_module.rules()) == 44
    assert len(survey_module.followup_rules()) == 16
    assert all(
        rule["thresholds"][1:] == [None, None, None]
        for rule in survey_module.followup_rules()
    )


def test_gap_projection_rejects_partial_saved_pass_before_accessing_labels():
    with pytest.raises(ValueError, match="complete"):
        survey_module.gap_projection(
            {"pairs": []},
            {"complete": False, "records": []},
            survey_module.followup_rules(),
        )
