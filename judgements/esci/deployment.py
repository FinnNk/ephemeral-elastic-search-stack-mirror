"""Render a candidate GPU service and guarded live model pins."""

from .release import content_digest
from .runtime import INFERENCE_PROTOCOL

NAMESPACE = "lab-models"


def checked_identity(receipt: dict) -> dict:
    identity = {key: receipt[key] for key in ("name", "version", "artifact_sha256")}
    if not str(identity["version"]).isdecimal() or int(identity["version"]) < 1:
        raise ValueError("Pin a numbered MLflow version.")
    digest = identity["artifact_sha256"]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Pin the model artefact SHA-256.")
    return identity


def render(receipt: dict, image: str, qualification: dict | None = None) -> dict:
    identity = checked_identity(receipt)
    digest = image.rsplit("@sha256:", 1)[-1]
    if (
        "@sha256:" not in image
        or len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest)
    ):
        raise ValueError("Pin the CUDA serving image by digest.")
    runtime_name = "esci-v3-" + digest[:16]
    live = qualification is not None
    if live:
        evidence = {k: v for k, v in qualification.items() if k != "evidence_sha256"}
        if (
            content_digest(evidence) != qualification["evidence_sha256"]
            or not qualification["passed"]
            or qualification["model"] != identity
            or qualification["release_sha256"] != receipt["release_sha256"]
            or qualification["runtime_image"] != image
            or set(qualification["checks"]) != {"batch", "singletons", "reversed"}
            or not all(
                c["passed"]
                and c["rows"] >= 8
                and c["max_probability_delta"] <= 1e-4
                and c["changed_labels_or_abstentions"] == 0
                for c in qualification["checks"].values()
            )
        ):
            raise ValueError(
                "A matching, passing runtime qualification is required for live pins."
            )
    runtime = {
        "apiVersion": "serving.kserve.io/v1alpha1",
        "kind": "ServingRuntime",
        "metadata": {"name": runtime_name, "namespace": NAMESPACE},
        "spec": {
            "supportedModelFormats": [
                {"name": "esci-v3-pyfunc", "version": "1", "autoSelect": False}
            ],
            "containers": [
                {
                    "name": "kserve-container",
                    "image": image,
                    "command": ["python", "/app/serve_esci.py"],
                    "env": [
                        {"name": "MODEL_DIR", "value": "/mnt/models"},
                        {
                            "name": "OTEL_EXPORTER_OTLP_ENDPOINT",
                            "value": "http://lab-otel-gateway.lab-observability.svc.cluster.local:4318",
                        },
                    ],
                    "ports": [{"containerPort": 8080, "name": "http1"}],
                    "readinessProbe": {
                        "httpGet": {"path": "/health", "port": 8080},
                        "periodSeconds": 10,
                    },
                    "resources": {
                        "requests": {
                            "cpu": "2",
                            "memory": "16Gi",
                            "nvidia.com/gpu": "1",
                        },
                        "limits": {"cpu": "4", "memory": "24Gi", "nvidia.com/gpu": "1"},
                    },
                }
            ],
        },
    }
    service = {
        "apiVersion": "serving.kserve.io/v1beta1",
        "kind": "InferenceService",
        "metadata": {
            "name": "synthetic-esci-judge" if live else "esci-v3-candidate",
            "namespace": NAMESPACE,
            "annotations": {"serving.kserve.io/deploymentMode": "Standard"},
        },
        "spec": {
            "predictor": {
                "serviceAccountName": "judgement-predictor",
                "nodeSelector": {"lab.relevance/gpu-worker": "true"},
                "tolerations": [
                    {"key": "lab.relevance/gpu", "operator": "Equal", "value": "reserved", "effect": "NoSchedule"}
                ],
                "model": {
                    "modelFormat": {"name": "esci-v3-pyfunc", "version": "1"},
                    "runtime": runtime_name,
                    "storageUri": f"mlflow-registry://{identity['name']}/{identity['version']}?sha256={identity['artifact_sha256']}",
                },
            }
        },
    }
    items = [runtime, service]
    if live:
        import json

        for name in ("judgement-model-pin",):
            items.append(
                {
                    "apiVersion": "v1",
                    "kind": "ConfigMap",
                    "metadata": {"name": name, "namespace": NAMESPACE},
                    "data": {"model.json": json.dumps(identity, sort_keys=True),
                             "inference.json": json.dumps({"runtime_image": image,
                                 "protocol_sha256": content_digest(INFERENCE_PROTOCOL),
                                 "input_contract": "judgement-pair-v1"}, sort_keys=True)},
                }
            )
    return {"apiVersion": "v1", "kind": "List", "items": items}
