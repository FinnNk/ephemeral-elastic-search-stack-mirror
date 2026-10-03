"""NLI hypotheses contain observable product/request fields, never ESCI labels."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "nli_survey", Path(__file__).with_name("nli_survey.py")
)
nli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nli)


def test_nullable_source_fields_and_full_category_hierarchy():
    pair = {
        "request": {"query": "phone charger"},
        "product": {
            "title": "USB Charger",
            "brand": None,
            "description": None,
            "bullets": None,
            "category_path": ["Electronics", "Accessories", "Chargers"],
        },
    }
    values = nli.texts(pair)
    assert len(values) == 3
    assert all(
        "Electronics > Accessories > Chargers" in premise for premise, _ in values
    )
    assert all("phone charger" in hypothesis for _, hypothesis in values)
    assert all("None" not in premise for premise, _ in values)


def test_reference_labels_do_not_enter_nli_features():
    pair = {"request": {"query": "shoe"}, "product": {"title": "shoe"}}
    expected = nli.texts(pair)
    pair["reference_label"] = "I"
    pair["base_probabilities"] = [0, 0, 0, 1]
    assert nli.texts(pair) == expected


def test_source_contract_pins_one_model_three_hypotheses_and_cpu_plan():
    assert nli.REVISION == "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"
    assert len(nli.HYPOTHESES) == 3
    assert nli.canonical({"b": 1, "a": 2}) == b'{"a":2,"b":1}\n'


def test_pilot_decode_uses_declared_entailment_index_and_preserves_abstention():
    values = [[0.05, 0.9, 0.05], [0.2, 0.7, 0.1], [0.4, 0.3, 0.3]]
    assert nli.decode_pilot(values, 0.9) == (0, True, 0.9)
    values = [[0.4, 0.3, 0.3], [0.4, 0.2, 0.4], [0.5, 0.1, 0.4]]
    assert nli.decode_pilot(values, 0.8) == (3, False, 0.7)
    assert nli.decode_pilot(values)[0] == 3
    values = [[0.1, 0.4, 0.5], [0.1, 0.5, 0.4], [0.1, 0.49, 0.41]]
    assert nli.decode_pilot(values)[0] == 1
