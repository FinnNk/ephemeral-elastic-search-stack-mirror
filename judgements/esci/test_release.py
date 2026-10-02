"""Contract, numerical, integrity and activation checks without a GPU."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esci.contract import (
    LABELS,
    QUESTION,
    map_scores,
    model_state,
    outcome,
    validate_mapping,
)
from esci.deployment import render
from esci.model import EsciModel
from esci.qualification import compare
from esci.release import content_digest, file_inventory, verify_bundle, write_json


@pytest.fixture
def mapping():
    return {
        "format": "esci-logistic-scores-v1",
        "labels": list(LABELS),
        "clip_min": 1e-6,
        "mean": [0.0] * 4,
        "scale": [1.0] * 4,
        "coef": np.eye(4).tolist(),
        "intercept": [0.0] * 4,
    }


@pytest.fixture
def policy():
    return {
        "format": "esci-abstention-v1",
        "labels": list(LABELS),
        "thresholds": dict.fromkeys(LABELS, 0.9),
    }


@pytest.fixture
def bundle(tmp_path, mapping, policy):
    tmp_path = tmp_path / "bundle"
    tmp_path.mkdir()
    write_json(tmp_path / "score-mapping.json", mapping)
    write_json(tmp_path / "policy.json", policy)
    write_json(
        tmp_path / "inference.json", {"question": QUESTION, "max_batch_size": 128}
    )
    manifest = {
        "format": "esci-release-v1",
        "files": file_inventory(tmp_path),
        "source": {"mapping_key": "synthetic-test-only"},
    }
    manifest["release_sha256"] = content_digest(manifest)
    write_json(tmp_path / "release.json", manifest)
    return tmp_path


def test_mapping_matches_sklearn():
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(42)
    raw = rng.dirichlet([1.0, 1.0, 1.0, 1.0], size=120)
    labels = np.arange(120) % 4
    fitted = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, random_state=42))
    features = np.log(np.clip(raw, 1e-6, 1))
    fitted.fit(features, labels)
    scaler, model = fitted.steps[0][1], fitted.steps[1][1]
    exported = {
        "format": "esci-logistic-scores-v1",
        "labels": list(LABELS),
        "clip_min": 1e-6,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": model.coef_.tolist(),
        "intercept": model.intercept_.tolist(),
    }
    validate_mapping(exported)
    np.testing.assert_allclose(
        [map_scores(row.tolist(), exported) for row in raw],
        fitted.predict_proba(features),
        atol=1e-14,
        rtol=0,
    )


def test_input_format_and_leaf():
    pair = {
        "request": {"query": " lamp\r\nblue "},
        "product": {"title": " blue lamp ", "taxonomy_path": ["Home", "Lights"]},
    }
    assert (
        model_state(pair)
        == "Query:\nlamp\nblue\n\nProduct title:\nblue lamp\n\nProduct category:\nLights"
    )
    pair["product"] = {"title": " lamp ", "category": "Lighting"}
    assert model_state(pair).endswith("Product category:\nLighting")
    pair["product"]["taxonomy_path"] = ["Home", " "]
    assert model_state(pair).endswith("Unknown")


def test_abstention_boundary_and_invalid_probabilities(policy):
    assert outcome([0.9, 0.05, 0.025, 0.025], policy)["label"] == "E"
    result = outcome([0.899, 0.051, 0.025, 0.025], policy)
    assert result["outcome"] == "abstain" and result["label"] is None
    with pytest.raises(ValueError):
        outcome([float("nan"), 0.0, 0.0, 0.0], policy)
    with pytest.raises(ValueError):
        outcome([0.5, 0.5, 0.5, 0.5], policy)


def test_bundle_tampering_and_unexpected_files(bundle):
    verify_bundle(bundle)
    (bundle / "untracked.json").write_text("{}")
    with pytest.raises(ValueError, match="unexpected"):
        verify_bundle(bundle)
    (bundle / "untracked.json").unlink()
    (bundle / "policy.json").write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        verify_bundle(bundle)


def test_pyfunc_round_trip_without_gpu(bundle):
    model = EsciModel()
    model.load_context(SimpleNamespace(artifacts={"bundle": str(bundle)}))
    assert model.engine is None
    model.engine = SimpleNamespace(
        predict=lambda rows: [[0.95, 0.02, 0.02, 0.01] for _ in rows]
    )
    frame = pd.DataFrame(
        {
            "payload": [
                json.dumps(
                    {"request": {"query": "lamp"}, "product": {"title": "Desk lamp"}}
                )
            ]
        }
    )
    assert model.predict(None, frame).iloc[0].label == "E"
    assert len(model.predict(None, frame.iloc[:0])) == 0
    with pytest.raises(ValueError, match="128"):
        model.predict(None, pd.concat([frame] * 129))
    with pytest.raises(ValueError, match="payload"):
        model.predict(None, pd.DataFrame({"wrong": [1]}))


def test_numerical_gate_catches_abstention_change(policy):
    first = outcome([0.9, 0.05, 0.025, 0.025], policy)
    second = outcome([0.89999, 0.05001, 0.025, 0.025], policy)
    result = compare([first], [second])
    assert result["max_probability_delta"] < 1e-4
    assert not result["passed"] and result["changed_labels_or_abstentions"] == 1


def test_live_pins_require_matching_qualification():
    receipt = {
        "name": "synthetic-esci-judge",
        "version": "2",
        "artifact_sha256": "a" * 64,
        "release_sha256": "b" * 64,
    }
    image = "registry/esci@sha256:" + "c" * 64
    candidate = render(receipt, image)["items"][1]
    assert candidate["metadata"]["name"] == "esci-v3-candidate"
    assert candidate["spec"]["predictor"]["nodeSelector"] == {"lab.relevance/gpu-worker": "true"}
    assert candidate["spec"]["predictor"]["tolerations"] == [
        {"key": "lab.relevance/gpu", "operator": "Equal", "value": "reserved", "effect": "NoSchedule"}
    ]
    qualification = {
        "format": "esci-runtime-qualification-v1",
        "model": {k: receipt[k] for k in ("name", "version", "artifact_sha256")},
        "release_sha256": receipt["release_sha256"],
        "runtime_image": image,
        "passed": True,
        "checks": {
            k: {
                "rows": 64,
                "max_probability_delta": 0.0,
                "changed_labels_or_abstentions": 0,
                "passed": True,
            }
            for k in ("batch", "singletons", "reversed")
        },
    }
    qualification["evidence_sha256"] = content_digest(qualification)
    items = render(receipt, image, qualification)["items"]
    assert items[1]["metadata"]["name"] == "synthetic-esci-judge"
    assert items[-1]["metadata"]["name"] == "judgement-model-pin"
    with pytest.raises(ValueError, match="qualification"):
        render({**receipt, "version": "3"}, image, qualification)
    qualification["passed"] = False
    with pytest.raises(ValueError, match="qualification"):
        render(receipt, image, qualification)


def test_mlflow_registration_download_reload_and_reuse(bundle, tmp_path, monkeypatch):
    import mlflow
    from esci.registration import register

    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.chdir(tmp_path)
    previous = mlflow.get_tracking_uri()
    uri = "sqlite:///" + str(tmp_path / "registry.sqlite").replace("\\", "/")
    try:
        first = register(bundle, uri, "test-esci")
        second = register(bundle, uri, "test-esci")
        assert not first["reused"] and second["reused"]
        assert first["artifact_sha256"] == second["artifact_sha256"]
        wrapped = mlflow.pyfunc.load_model(first["model_uri"])
        model = wrapped.unwrap_python_model()
        assert model.engine is None
        model.engine = SimpleNamespace(
            predict=lambda states: [[0.95, 0.02, 0.02, 0.01] for _ in states]
        )
        result = wrapped.predict(
            pd.DataFrame(
                {
                    "payload": [
                        json.dumps(
                            {
                                "request": {"query": "lamp"},
                                "product": {"title": "Desk lamp"},
                            }
                        )
                    ]
                }
            )
        )
        assert result.iloc[0]["label"] == "E"
    finally:
        mlflow.set_tracking_uri(previous)
