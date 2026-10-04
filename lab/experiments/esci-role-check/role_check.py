"""Prepare the fixed role survey; only an authorised owner injects its backend.

No model loader or execution CLI is provided. Before constructing a direct
Decider backend, the owner must verify the cached checkpoint revision/file hashes,
decider-ai version, source-bound grant, singleton numerical profile and deadlines.
Use Decider(local_path, use_graphs=False, abstain_below=0.0), with the verified
effective choice temperature 1.164 and without an additional ESCI adapter or
external score mapping. The upstream v11
checkpoint already contains its own merged adapter. Synthetic tests exercise this
module without importing Decider, Torch or model weights.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from numbers import Real

MODEL_ID = "Mapika/decider-2b"
MODEL_REVISION = "533964dae8be954c5b5e19fa4948e48408094c1e"
PACKAGE_VERSION = "1.6.0"
PROPOSAL_SHA256 = "9bade8cd69eddcc984cf38138128a5318d47239ffa70b2263e32493c253ff9ed"
TEMPERATURE = 1.164
CONFIDENCE = 0.9
MAX_CONTEXT_TOKENS = 1536
MAX_PROMPT_TOKENS = 2048
PROBABILITY_TOLERANCE = 1e-5
STATE_FIELDS = ("request.query", "product.title", "product.category_path")
ROLE_QUESTION = (
    "Does the offered product itself meet the role and all explicit requirements of the shopping query? "
    "Treat an accessory for a requested main product as not meeting that role. "
    "Distinguish explicitly different models, sizes, materials and intended uses. "
    "Do not invent a preferred meaning for an ambiguous query; choose insufficient evidence "
    "when the supplied text does not support a decision."
)
ROLE_OPTIONS = (
    "Meets the requested role and every explicit requirement",
    "Does not meet the requested role or at least one explicit requirement",
    "Insufficient evidence",
)
NON_EXACT_QUESTION = (
    "For the shopping query, if the offered product is not an exact match, which relationship "
    "is supported by the supplied text? A substitute fulfils the same main role with a difference; "
    "a complement is used with the requested product without fulfilling its role; irrelevant "
    "does neither. Do not infer compatibility or an unstated intended use. "
    "Choose insufficient evidence when a relationship is unsupported."
)
NON_EXACT_OPTIONS = ("Substitute", "Complement", "Irrelevant", "Insufficient evidence")
QUESTIONS = (
    (ROLE_QUESTION, ROLE_OPTIONS),
    (NON_EXACT_QUESTION, NON_EXACT_OPTIONS),
)
FORBIDDEN_FIELDS = frozenset(
    (
        "label",
        "labels",
        "esci_label",
        "assessment",
        "grade",
        "reference",
        "references",
        "reference_label",
        "prediction",
        "predictions",
        "probabilities",
        "role_probabilities",
        "non_exact_probabilities",
    )
)
PREDICTION_FIELDS = frozenset(
    (
        "query_id",
        "product_id",
        "query_key",
        "role_probabilities",
        "non_exact_probabilities",
        "gate_eligible",
    )
)


def _reject_reference_fields(value):
    if isinstance(value, Mapping):
        if any(str(key).lower() in FORBIDDEN_FIELDS for key in value):
            raise ValueError(
                "Model inputs must not contain reference or prediction fields"
            )
        for child in value.values():
            _reject_reference_fields(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_reference_fields(child)


def _clean(value):
    if not isinstance(value, str):
        raise ValueError("Query, title and category values must be strings")
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def model_state(pair):
    """Match the category C/D projection, without IDs or extra catalogue fields.

    The actual broad-to-specific path is required. An empty path renders as
    Uncategorised; missing or malformed paths fail rather than being inferred.
    No character clipping is performed. The complete token audit occurs before
    backend inference, including the Decider Context prefix and both question
    and option blocks.
    """
    if not isinstance(pair, Mapping):
        raise ValueError("A product/query input object is required")
    _reject_reference_fields(pair)
    try:
        product = pair["product"]
        query = _clean(pair["request"]["query"])
        title = _clean(product["title"])
        path = product["category_path"]
    except (KeyError, TypeError) as error:
        raise ValueError(
            "Query, title and actual category_path are required"
        ) from error
    if not query or not title:
        raise ValueError("A non-empty query and title are required")
    if "taxonomy_path" in product:
        raise ValueError("Use the imported category_path contract")
    if not isinstance(path, list) or any(not isinstance(value, str) for value in path):
        raise ValueError("category_path must be the imported string array")
    category = " > ".join(_clean(value) for value in path if _clean(value))
    return f"Query:\n{query}\n\nProduct title:\n{title}\n\nProduct category:\n{category or 'Uncategorised'}"


def validate_probabilities(values, options):
    """Reject malformed raw option vectors; never normalise or remap scores."""
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError("Probabilities must be a flat option sequence")
    if len(values) != len(options):
        raise ValueError("Probability shape differs from the fixed options")
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
        raise ValueError("Probabilities must be finite numbers")
    result = tuple(float(value) for value in values)
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in result):
        raise ValueError("Probabilities must be finite and within [0, 1]")
    if abs(math.fsum(result) - 1) > PROBABILITY_TOLERANCE:
        raise ValueError("Raw probabilities must sum to one")
    return result


def validate_prediction(record):
    """Validate the six-field exploratory prediction record used by analysis."""
    if not isinstance(record, Mapping) or set(record) != PREDICTION_FIELDS:
        raise ValueError("Unexpected prediction record fields")
    if record["gate_eligible"] is not False:
        raise ValueError("The role survey cannot qualify labels")
    for key in ("query_id", "product_id", "query_key"):
        if not isinstance(record[key], str) or not record[key].strip():
            raise ValueError("Prediction identities must be non-empty strings")
    return dict(record) | {
        "role_probabilities": list(
            validate_probabilities(record["role_probabilities"], ROLE_OPTIONS)
        ),
        "non_exact_probabilities": list(
            validate_probabilities(record["non_exact_probabilities"], NON_EXACT_OPTIONS)
        ),
    }


def token_audit(state, tokenizer):
    """Count the complete pinned plain-layout prompt before any truncating API.

    The owner must retain these counts and bind the tokenizer bytes/profile in
    its registration. This mirrors decider-ai 1.6.0 prompt.build for one question
    per row; questions and options are appended after the Context token budget.
    """
    context = tokenizer.encode("Context:\n" + state, add_special_tokens=False)
    if len(context) > MAX_CONTEXT_TOKENS:
        raise ValueError("State would be truncated by the fixed context budget")
    lengths = []
    for question, options in QUESTIONS:
        piece = "\n\nQuestion: " + question + "\nOptions:"
        piece += "".join(
            f"\n({letter}) {option}" for letter, option in zip("ABCD", options)
        )
        piece += "\nAnswer: ("
        full = len(context) + len(tokenizer.encode(piece, add_special_tokens=False))
        if full > MAX_PROMPT_TOKENS:
            raise ValueError(
                "Complete question/options prompt exceeds the fixed budget"
            )
        lengths.append(full)
    return {
        "context_tokens": len(context),
        "role_prompt_tokens": lengths[0],
        "non_exact_prompt_tokens": lengths[1],
    }


def _answer(result, options):
    if not isinstance(result, list) or len(result) != 1:
        raise ValueError("Backend must return exactly one singleton row")
    if not isinstance(result[0], list) or len(result[0]) != 1:
        raise ValueError("Backend must return exactly one question answer")
    answer = result[0][0]
    if not isinstance(answer, Mapping) or set(answer) != {
        "choice",
        "confidence",
        "probs",
        "probs_list",
    }:
        raise ValueError("Backend answer differs from the pinned Decider API")
    probs = answer["probs"]
    if not isinstance(probs, Mapping) or tuple(probs) != options:
        raise ValueError("Backend option order differs from the fixed question")
    values = validate_probabilities(answer["probs_list"], options)
    named = validate_probabilities(list(probs.values()), options)
    if values != named:
        raise ValueError("Named and positional probabilities differ")
    winner = max(range(len(values)), key=values.__getitem__)
    confidence = answer["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, Real)
        or not math.isfinite(confidence)
        or confidence != values[winner]
        or answer["choice"] != options[winner]
    ):
        raise ValueError("Backend winner or confidence differs from raw probabilities")
    return list(values)


def score_pair(pair, backend, *, max_context_tokens=MAX_CONTEXT_TOKENS):
    """Score two separate singleton choice calls on an owner-verified backend.

    This function creates no backend and grants no execution permission. The
    owner verifies checkpoint/package/source ownership before injection. Its
    existing worker enforces grants, deadlines, call counts and numerical repeats.
    """
    if max_context_tokens != MAX_CONTEXT_TOKENS:
        raise ValueError("The fixed context token budget changed")
    temperatures = getattr(backend, "T_by_type", None)
    base_temperature = getattr(backend, "T", None)
    if not isinstance(temperatures, Mapping) or not isinstance(base_temperature, Real):
        raise ValueError("Pinned backend temperature properties are required")
    choice_temperature = temperatures.get("choice", base_temperature)
    if (
        isinstance(choice_temperature, bool)
        or choice_temperature != TEMPERATURE
        or getattr(backend, "eng", True) is not None
        or getattr(backend, "layout", None) != "plain"
        or getattr(backend, "abstain_below", None) != 0.0
    ):
        raise ValueError("Backend temperature, layout or execution contract changed")
    state = model_state(pair)
    identities = {key: pair.get(key) for key in ("query_id", "product_id", "query_key")}
    for value in identities.values():
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Input identities must be non-empty strings")
    token_audit(state, backend.m.tok)
    vectors = []
    for question, options in QUESTIONS:
        result = backend.decide_batch(
            [(state, [{"question": question, "options": list(options)}])],
            max_ctx_tokens=MAX_CONTEXT_TOKENS,
        )
        vectors.append(_answer(result, options))
    return validate_prediction(
        identities
        | {
            "role_probabilities": vectors[0],
            "non_exact_probabilities": vectors[1],
            "gate_eligible": False,
        }
    )


def route_decision(
    role_probabilities,
    non_exact_probabilities,
    *,
    a_additional_exact,
    prefix_decision=None,
):
    """Apply proposal 03 without overwriting an accepted prefix decision.

    A high-confidence role match can retain an A additional Exact, even when
    the conditional non-Exact question chooses another class. The 48-pair
    A-abstained stratum can never emit Exact. Unsupported/conflicting routes
    abstain; no model answer becomes an independent reference.
    """
    if type(a_additional_exact) is not bool:
        raise ValueError("A additional Exact status must be explicit")
    if prefix_decision is not None:
        if not isinstance(prefix_decision, Mapping):
            raise ValueError("Prefix decision must be an outcome object")
        outcome, label = prefix_decision.get("outcome"), prefix_decision.get("label")
        if outcome == "labelled" and label in ("E", "S", "C", "I"):
            return copy.deepcopy(dict(prefix_decision))
        if outcome != "abstain" or label is not None:
            raise ValueError("Invalid frozen prefix decision")
    role = validate_probabilities(role_probabilities, ROLE_OPTIONS)
    non_exact = validate_probabilities(non_exact_probabilities, NON_EXACT_OPTIONS)
    role_index = max(range(3), key=role.__getitem__)
    other_index = max(range(4), key=non_exact.__getitem__)
    label, route = None, "abstain"
    if role[role_index] >= CONFIDENCE:
        if role_index == 0 and a_additional_exact:
            label, route = "E", "exact_veto"
        elif (
            role_index == 1 and other_index < 3 and non_exact[other_index] >= CONFIDENCE
        ):
            label, route = ("S", "C", "I")[other_index], "non_exact"
    return {
        "label": label,
        "outcome": "labelled" if label else "abstain",
        "deciding_route": route,
        "gate_eligible": False,
    }
