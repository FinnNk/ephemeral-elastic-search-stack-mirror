import importlib.util
from pathlib import Path
import pytest

P = Path(__file__).with_name("instruction_survey.py")
spec = importlib.util.spec_from_file_location("instruction_survey", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def pair(i=0):
    return {
        "query_id": str(i),
        "product_id": str(i),
        "request": {"query": "camera"},
        "product": {
            "title": "camera case",
            "category": "Electronics",
            "category_path": ["Electronics", "Accessories"],
            "brand": "North",
            "bullets": "Fits camera",
            "description": "A protective case",
        },
    }


def test_matched_prompt_fields_and_explicit_role():
    a, b, c = [m.prompt_parts(pair(), x) for x in m.CONTRACTS]
    assert "accessory is not E" not in a[0] and "accessory is not E" in b[0]
    assert "Accessories" not in a[2] and "Accessories" in b[2]
    assert "North" not in b[2] and "North" in c[2]
    assert a[1] == b[1] == c[1]


def test_selection_is_label_free_and_deterministic():
    inputs = [pair(i) for i in range(30)]
    assert m.select(inputs, 5) == m.select(inputs, 5)
    assert len(set(m.select(inputs, 5))) == 5
    with pytest.raises(ValueError):
        m.select([dict(pair(), label="E")])


def test_answer_token_contract_rejects_multiple_or_colliding_tokens():
    class Tokenizer:
        def encode(self, x, **kwargs):
            return [ord(x)]

        def decode(self, x):
            return chr(x[0])

    assert m.token_contract(Tokenizer()) == [ord(x) for x in m.LABELS]

    class Broken(Tokenizer):
        def encode(self, x, **kwargs):
            return [1, 2]

    with pytest.raises(ValueError):
        m.token_contract(Broken())


def test_selective_metrics_preserve_i_to_e_and_abstentions():
    rows = [
        {
            "input_index": 0,
            "constrained_label": "E",
            "probabilities": {"E": 0.95, "S": 0.02, "C": 0.02, "I": 0.01},
        },
        {
            "input_index": 1,
            "constrained_label": "I",
            "probabilities": {"E": 0.1, "S": 0.1, "C": 0.1, "I": 0.7},
        },
    ]
    r = m.metrics(rows, {0: "I", 1: "I"}, 0.9)
    assert r["accepted"] == 1 and r["abstained"] == 1 and r["i_to_e_count"] == 1
    assert r["i_to_e_rate"] == 0.5 and r["accepted_e_contamination"] == 1


def test_prompt_budget_truncates_only_product_fields():
    class Tokenizer:
        def encode(self, x, **kwargs):
            return list(x.encode())

        def decode(self, x):
            return bytes(x).decode()

        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["return_dict"] is True
            return {
                "input_ids": list(
                    (messages[0]["content"] + messages[1]["content"]).encode()
                )
            }

    row = pair()
    row["product"]["description"] = "x" * 2000
    ids, original, truncated = m.encode_prompt(
        Tokenizer(), row, m.CONTRACTS[2], budget=900
    )
    assert len(ids) <= 900 and original > 900 and truncated
    text = bytes(ids).decode()
    assert 'Query: "camera"' in text and "accessory is not E" in text
