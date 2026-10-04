"""Synthetic CPU checks; no model, GPU, reference labels or owner controls."""

import copy
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "role_check", Path(__file__).with_name("role_check.py")
)
role = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = role
SPEC.loader.exec_module(role)


class Tokenizer:
    """A character-count fixture, not a measurement of the real tokenizer."""

    def __init__(self):
        self.pieces = []

    def encode(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        self.pieces.append(text)
        return list(range(len(text)))


class Backend:
    """Match the observed Decider 1.6.0 interface without importing it."""

    def __init__(self, vectors=None):
        self.T = 1.145
        self.T_by_type = {"choice": 1.164, "noul": 1.624, "score": 1.124}
        self.eng = None
        self.layout = "plain"
        self.abstain_below = 0.0
        self.m = SimpleNamespace(tok=Tokenizer())
        self.calls = []
        self.vectors = vectors or [[0.95, 0.03, 0.02], [0.01, 0.96, 0.01, 0.02]]
        self.change_result = lambda result: result

    def decide_batch(self, requests, *, max_ctx_tokens):
        self.calls.append((copy.deepcopy(requests), max_ctx_tokens))
        options = requests[0][1][0]["options"]
        values = self.vectors[len(self.calls) - 1]
        winner = max(range(len(values)), key=values.__getitem__)
        answer = {
            "choice": options[winner],
            "confidence": values[winner],
            "probs": dict(zip(options, values)),
            "probs_list": values,
        }
        return self.change_result([[answer]])


@pytest.fixture
def pair():
    return {
        "query_id": "query-identity",
        "product_id": "product-identity",
        "query_key": "normalised-identity",
        "request": {"query": " phone case\r\n", "filters": {"ignored": True}},
        "product": {
            "title": "A phone case\rwith a stand",
            "category_path": [" Electronics ", " ", "Cases"],
            "category": "Electronics",
            "brand": "ignored-brand",
            "description": "ignored-description",
            "attrs": {"sku": "ignored-sku"},
        },
    }


def test_renderer_matches_full_hierarchy_projection_and_omits_metadata(pair):
    state = role.model_state(pair)
    assert state == (
        "Query:\nphone case\n\nProduct title:\nA phone case\nwith a stand\n\n"
        "Product category:\nElectronics > Cases"
    )
    assert "identity" not in state and "ignored" not in state
    pair["product"]["category_path"] = []
    assert role.model_state(pair).endswith("Product category:\nUncategorised")


@pytest.mark.parametrize(
    "field", ["label", "prediction", "role_probabilities", "references"]
)
def test_reference_and_prediction_fields_rejected_even_when_nested(pair, field):
    pair["product"]["attrs"][field] = "forbidden"
    with pytest.raises(ValueError, match="reference or prediction"):
        role.model_state(pair)


@pytest.mark.parametrize(
    "change", ["missing_path", "string_path", "bad_path_item", "empty_query", "legacy"]
)
def test_renderer_rejects_missing_or_ambiguous_input_contract(pair, change):
    if change == "missing_path":
        pair["product"].pop("category_path")
    elif change == "string_path":
        pair["product"]["category_path"] = "Electronics > Cases"
    elif change == "bad_path_item":
        pair["product"]["category_path"] = ["Electronics", 3]
    elif change == "empty_query":
        pair["request"]["query"] = " "
    else:
        pair["product"]["taxonomy_path"] = ["Other"]
    with pytest.raises(ValueError):
        role.model_state(pair)


@pytest.mark.parametrize(
    "values",
    [
        [1, 0],
        [],
        [0.5, 0.4, 0],
        [1.1, -0.1, 0],
        [float("nan"), 0, 1],
        [float("inf"), 0, 0],
        [True, 0, 0],
        [[1], 0, 0],
        ["1", 0, 0],
        "100",
        {0: 1},
    ],
)
def test_probability_validation_rejects_bad_shape_numbers_or_sum(values):
    with pytest.raises(ValueError):
        role.validate_probabilities(values, role.ROLE_OPTIONS)


def test_singleton_questions_use_actual_type_map_and_exact_api_shape(pair):
    backend = Backend()
    record = role.score_pair(pair, backend)
    assert record == {
        "query_id": pair["query_id"],
        "product_id": pair["product_id"],
        "query_key": pair["query_key"],
        "role_probabilities": [0.95, 0.03, 0.02],
        "non_exact_probabilities": [0.01, 0.96, 0.01, 0.02],
        "gate_eligible": False,
    }
    assert len(backend.calls) == 2
    for (requests, budget), (question, options) in zip(backend.calls, role.QUESTIONS):
        assert budget == 1536 and len(requests) == 1 and len(requests[0][1]) == 1
        assert requests[0][1] == [{"question": question, "options": list(options)}]
    assert backend.calls[0][0][0][0] == backend.calls[1][0][0][0]
    assert len(backend.m.tok.pieces) == 3
    assert all("Insufficient evidence" in piece for piece in backend.m.tok.pieces[1:])


def test_scalar_choice_temperature_is_also_supported(pair):
    backend = Backend()
    backend.T, backend.T_by_type = 1.164, {}
    assert role.score_pair(pair, backend)["gate_eligible"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("T_by_type", {"choice": 1.624}),
        ("T_by_type", None),
        ("eng", object()),
        ("layout", "chat"),
        ("abstain_below", 0.9),
    ],
)
def test_backend_contract_failures_precede_calls(pair, field, value):
    backend = Backend()
    setattr(backend, field, value)
    with pytest.raises(ValueError):
        role.score_pair(pair, backend)
    assert backend.calls == []


def test_absent_pinned_backend_property_fails_without_fallback(pair):
    backend = Backend()
    del backend.T
    with pytest.raises(ValueError):
        role.score_pair(pair, backend)
    assert backend.calls == []


@pytest.mark.parametrize(
    "failure", ["rows", "questions", "order", "named", "choice", "confidence", "shape"]
)
def test_backend_output_rejections(pair, failure):
    backend = Backend()

    def change(result):
        answer = result[0][0]
        if failure == "rows":
            return result + result
        if failure == "questions":
            return [[answer, answer]]
        if failure == "order":
            answer["probs"] = dict(reversed(list(answer["probs"].items())))
        elif failure == "named":
            answer["probs"] = dict(zip(role.ROLE_OPTIONS, [0.96, 0.02, 0.02]))
        elif failure == "choice":
            answer["choice"] = role.ROLE_OPTIONS[1]
        elif failure == "confidence":
            answer["confidence"] = float("nan")
        else:
            answer["probs_list"] = [1.0, 0.0]
        return result

    backend.change_result = change
    with pytest.raises(ValueError):
        role.score_pair(pair, backend)
    assert len(backend.calls) == 1


@pytest.mark.parametrize(
    "title,match",
    [("x" * 1600, "State would be truncated"), ("x" * 1430, "Complete question")],
)
def test_token_budgets_reject_silent_truncation_before_inference(pair, title, match):
    pair["product"]["title"] = title
    backend = Backend()
    with pytest.raises(ValueError, match=match):
        role.score_pair(pair, backend)
    assert backend.calls == []


def test_changed_context_budget_fails(pair):
    backend = Backend()
    with pytest.raises(ValueError, match="token budget changed"):
        role.score_pair(pair, backend, max_context_tokens=32768)
    assert backend.calls == []


def test_exact_veto_retains_only_prior_a_claim_despite_conditional_q2():
    role_values, q2 = [0.9, 0.05, 0.05], [0.01, 0.01, 0.97, 0.01]
    assert role.route_decision(role_values, q2, a_additional_exact=True)["label"] == "E"
    assert (
        role.route_decision(role_values, q2, a_additional_exact=False)["label"] is None
    )


@pytest.mark.parametrize("index,label", [(0, "S"), (1, "C"), (2, "I")])
@pytest.mark.parametrize("a_claim", [True, False])
def test_non_exact_route_supports_corrections_and_new_labels(index, label, a_claim):
    q2 = [0.0] * 4
    q2[index] = 1.0
    result = role.route_decision([0, 1, 0], q2, a_additional_exact=a_claim)
    assert result == {
        "label": label,
        "outcome": "labelled",
        "deciding_route": "non_exact",
        "gate_eligible": False,
    }


@pytest.mark.parametrize(
    "role_values,q2",
    [
        ([0.05, 0.05, 0.9], [1, 0, 0, 0]),
        ([0, 1, 0], [0, 0, 0, 1]),
        ([0.05, 0.85, 0.1], [1, 0, 0, 0]),
        ([0, 1, 0], [0.85, 0.05, 0.05, 0.05]),
    ],
)
def test_insufficient_or_low_confidence_routes_abstain(role_values, q2):
    assert (
        role.route_decision(role_values, q2, a_additional_exact=True)["outcome"]
        == "abstain"
    )


def test_prefix_preserved_before_scores_and_returned_independently():
    prefix = {"label": "C", "outcome": "labelled", "source": {"id": "retained"}}
    result = role.route_decision(
        [], [], a_additional_exact=False, prefix_decision=prefix
    )
    assert result == prefix
    result["source"]["id"] = "changed"
    assert prefix["source"]["id"] == "retained"


def test_prediction_record_and_route_status_reject_unqualified_inputs(pair):
    record = role.score_pair(pair, Backend())
    for change in (
        {"gate_eligible": True},
        {"label": "E"},
        {"query_key": ""},
        {"role_probabilities": [1, 0]},
    ):
        with pytest.raises(ValueError):
            role.validate_prediction(record | change)
    with pytest.raises(ValueError, match="status must be explicit"):
        role.route_decision([1, 0, 0], [1, 0, 0, 0], a_additional_exact="true")
    with pytest.raises(ValueError, match="frozen prefix"):
        role.route_decision(
            [1, 0, 0],
            [1, 0, 0, 0],
            a_additional_exact=True,
            prefix_decision={"label": "E", "outcome": "abstain"},
        )
