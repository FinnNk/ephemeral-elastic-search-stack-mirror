"""Idempotent MLflow registration of an immutable local release bundle."""

from pathlib import Path
import os
import shutil
import tempfile

from .release import content_digest, read_json, sha256, verify_bundle

RUNTIME_FILES = ("__init__.py", "contract.py", "engine.py", "model.py", "release.py")


def implementation_digest(folder: Path) -> str:
    return content_digest(
        {name: sha256(folder / name) for name in (*RUNTIME_FILES, "requirements.lock")}
    )


def register(
    bundle: Path, tracking_uri: str, name: str = "synthetic-esci-judge"
) -> dict:
    import mlflow
    from mlflow.models import ModelSignature
    from mlflow.types.schema import Array, ColSpec, DataType, Schema
    from fetch_model import tree_digest

    if not name or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for c in name
    ):
        raise ValueError("Use a simple registered model name.")
    manifest = verify_bundle(bundle)
    identity = manifest["release_sha256"]
    folder = Path(__file__).parent
    implementation = implementation_digest(folder)
    # The laptop can reach the tracking proxy, not Kubernetes-only presigned S3 URLs.
    os.environ.setdefault("MLFLOW_ENABLE_PROXY_MULTIPART_UPLOAD", "false")
    os.environ.setdefault("MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD", "false")
    mlflow.set_tracking_uri(tracking_uri)
    client = mlflow.MlflowClient()
    versions = [
        v
        for v in client.search_model_versions(f"name='{name}'")
        if v.tags.get("esci_release_sha256") == identity
        and v.tags.get("esci_implementation_sha256") == implementation
    ]
    if len(versions) > 1:
        raise ValueError(
            "Multiple versions contain the release; resolve this before installing."
        )
    reused = bool(versions)
    if not versions:
        requirements = (
            (folder / "requirements.lock").read_text(encoding="utf-8").splitlines()
        )
        signature = ModelSignature(
            inputs=Schema([ColSpec("string", "payload")]),
            outputs=Schema(
                [
                    ColSpec("string", "outcome"),
                    ColSpec("string", "label", required=False),
                    ColSpec("double", "confidence"),
                    ColSpec(Array(DataType.double), "probabilities"),
                ]
            ),
        )
        with (
            tempfile.TemporaryDirectory(prefix="esci-code-") as temporary,
            mlflow.start_run(run_name="esci-v3-score-map"),
        ):
            code = Path(temporary) / "esci"
            code.mkdir()
            for filename in RUNTIME_FILES:
                shutil.copyfile(folder / filename, code / filename)
            info = mlflow.pyfunc.log_model(
                name="judge",
                python_model=str(folder / "model.py"),
                code_paths=[str(code)],
                artifacts={"bundle": str(bundle.resolve())},
                signature=signature,
                pip_requirements=requirements,
                metadata={"esci_release_sha256": identity, "qualification": "pending"},
            )
            registered = mlflow.register_model(
                info.model_uri,
                name,
                tags={
                    "esci_release_sha256": identity,
                    "esci_qualification": "pending",
                    "esci_implementation_sha256": implementation,
                    "esci_mapping": manifest["source"]["mapping_key"],
                },
            )
        versions = [registered]
    version = str(versions[0].version)
    uri = f"models:/{name}/{version}"
    path = Path(mlflow.artifacts.download_artifacts(artifact_uri=uri))
    stored = list((path / "artifacts").glob("*/release.json"))
    if len(stored) != 1 or read_json(stored[0])["release_sha256"] != identity:
        raise ValueError("Registered model does not contain the expected release.")
    verify_bundle(stored[0].parent)
    digest = tree_digest(path)
    recorded = client.get_model_version(name, version).tags.get("model_artifact_sha256")
    if recorded and recorded != digest:
        raise ValueError("Registered artefact bytes changed after registration.")
    client.set_model_version_tag(name, version, "model_artifact_sha256", digest)
    return {
        "name": name,
        "version": version,
        "model_uri": uri,
        "artifact_sha256": digest,
        "release_sha256": identity,
        "implementation_sha256": implementation,
        "qualification": "pending",
        "reused": reused,
        "verified_local_path": str(path),
    }
