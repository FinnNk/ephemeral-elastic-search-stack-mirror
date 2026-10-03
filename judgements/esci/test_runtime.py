"""Reject silent dispatch changes and prevent caller-dependent tensor batches."""

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esci.engine import Engine
from esci.runtime import INFERENCE_PROTOCOL, configure_runtime, selected_implementation


def test_dispatch_inspection_requires_declared_selection():
    def implementation():
        pass

    def wrapped():
        return implementation()

    assert selected_implementation(wrapped) is implementation
    with pytest.raises(RuntimeError, match="Cannot verify"):
        selected_implementation(implementation)


def test_undeclared_protocol_rejected_before_configuration():
    with pytest.raises(RuntimeError, match="singleton-fla-frozen-v1"):
        configure_runtime(None, {"protocol": {"internal_batch_size": 8}}, None)


def test_http_companions_cannot_change_decider_batch(monkeypatch):
    monkeypatch.setattr("esci.engine.read_profile", lambda *args: None)
    monkeypatch.setattr("esci.engine.verify_selections", lambda *args, **kwargs: {})
    seen = []

    def decide(requests, max_ctx_tokens):
        seen.append((requests, max_ctx_tokens))
        return [[{"probs": {"Exact": 0.95, "Substitute": 0.02,
                            "Complement": 0.02, "Irrelevant": 0.01}}]]

    engine = Engine.__new__(Engine)
    engine.bundle = Path("unused-in-test")
    engine.settings = {"question": "ESCI", "protocol": INFERENCE_PROTOCOL}
    engine.decider = SimpleNamespace(decide_batch=decide)
    batch = engine.predict(["short", "a much longer companion"])
    alone = engine.predict(["short"])
    assert batch[0] == alone[0]
    assert [len(requests) for requests, _ in seen] == [1, 1, 1]
    assert all(maximum == 1536 for _, maximum in seen)
    assert engine.predict([]) == []
