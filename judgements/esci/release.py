"""Build and verify portable, immutable model bundles; never ship research rows."""

import hashlib
import json
from pathlib import Path
import shutil

from .contract import LABELS, QUESTION, validate_mapping, validate_policy
from .runtime import INFERENCE_PROTOCOL
from .kernels import read_profile

BASE_REVISION = "eb5fbdfc9448473ec25e399882912863afbdb70e"
ADAPTER_SHA256 = "227cfbeb71dc40c0737c372fb3bebb03738cf5b71e54e8be7d7a668678d71fee"
MAPPING_BUNDLE_SHA256 = (
    "61d9c2a07c0ff153cfabd866c2d67cd82b78b021cc2046cd718777b336e05b66"
)
MAPPING_KEY = "v3_8192:scores:C0.1"
BASE_FILES = (
    "model.safetensors",
    "config.json",
    "decider_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "chat_template.jinja",
    "generation_config.json",
)
RUNTIME = {
    "decider-ai": "1.4.0",
    "torch": "2.6.0",
    "transformers": "5.17.0",
    "peft": "0.14.0",
    "safetensors": "0.8.0",
    "numpy": "1.26.4",
    "flash-linear-attention": "0.5.2",
    "fla-core": "0.5.2",
    "triton": "3.2.0",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def content_digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def file_inventory(root: Path) -> dict:
    inventory = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Release bundles cannot contain symbolic links.")
        if path.is_file() and path != root / "release.json":
            inventory[path.relative_to(root).as_posix()] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    return inventory


def verify_bundle(root: Path) -> dict:
    manifest = read_json(root / "release.json")
    if manifest.get("format") != "esci-release-v1":
        raise ValueError("Unsupported release format.")
    payload = {key: value for key, value in manifest.items() if key != "release_sha256"}
    if content_digest(payload) != manifest["release_sha256"]:
        raise ValueError("Release manifest digest differs.")
    if file_inventory(root) != manifest["files"]:
        raise ValueError("Missing, changed or unexpected release files.")
    validate_mapping(read_json(root / "score-mapping.json"))
    validate_policy(read_json(root / "policy.json"))
    settings = read_json(root / "inference.json")
    if settings.get("protocol") != INFERENCE_PROTOCOL:
        raise ValueError("Release inference protocol differs.")
    read_profile(root, INFERENCE_PROTOCOL["kernel_profile_sha256"])
    if settings["question"] != QUESTION:
        raise ValueError("The v3 question changed.")
    return manifest


def export_mapping(path: Path) -> dict:
    """Read only the explicitly pinned, locally generated sklearn experiment."""
    if sha256(path) != MAPPING_BUNDLE_SHA256:
        raise ValueError(
            "The research mapping bundle is not the selected frozen source."
        )
    import joblib

    bundle = joblib.load(path)
    definition = bundle["definitions"][MAPPING_KEY]
    if definition != {"kind": "logistic", "signal": "v3_8192", "text": False, "C": 0.1}:
        raise ValueError("Selected score mapping definition differs.")
    scaler, model = (
        bundle["models"][MAPPING_KEY].steps[0][1],
        bundle["models"][MAPPING_KEY].steps[1][1],
    )
    if model.classes_.tolist() != [0, 1, 2, 3]:
        raise ValueError("Selected score mapping label order differs.")
    mapping = {
        "format": "esci-logistic-scores-v1",
        "labels": list(LABELS),
        "clip_min": 1e-6,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": model.coef_.tolist(),
        "intercept": model.intercept_.tolist(),
    }
    validate_mapping(mapping)
    return mapping


def build_bundle(research: Path, output: Path) -> dict:
    base = research / "artifacts/models/decider-4b-v2.1"
    trained = research / "artifacts/models/esci-decider-4b-role-cues-v3-pilot-8192"
    provenance = read_json(trained / "training-manifest.json")
    if (
        provenance["base_revision"] != BASE_REVISION
        or provenance["question_definition"] != QUESTION
        or provenance["feature_profile"] != "title_leaf_category"
        or provenance["config"]["max_records"] != 8192
    ):
        raise ValueError("Unexpected v3 training provenance.")
    if sha256(trained / "adapter/adapter.safetensors") != ADAPTER_SHA256:
        raise ValueError("Unexpected adapter weights.")
    mapping = export_mapping(
        research / "artifacts/evaluations/round-2/decision-fit/frozen-models.joblib"
    )
    if output.exists():
        existing = verify_bundle(output)
        if (existing["source"]["mapping_bundle_sha256"] != MAPPING_BUNDLE_SHA256
            or read_json(output / "inference.json").get("protocol") != INFERENCE_PROTOCOL):
            raise ValueError("Output contains a different release.")
        return existing
    output.mkdir(parents=True)
    for folder in ("base", "adapter"):
        (output / folder).mkdir()
    for name in BASE_FILES:
        shutil.copy2(base / name, output / "base" / name)
    for name in ("adapter.safetensors", "adapter_config.json"):
        shutil.copy2(trained / "adapter" / name, output / "adapter" / name)
    shutil.copy2(Path(__file__).with_name("kernel-profile.json"), output / "kernel-profile.json")
    (output / "kernel-configs").mkdir()
    for name, definition in read_json(output / "kernel-profile.json")["kernels"].items():
        write_json(output / "kernel-configs" / (name + ".json"), definition)
    write_json(output / "score-mapping.json", mapping)
    write_json(
        output / "policy.json",
        {
            "format": "esci-abstention-v1",
            "labels": list(LABELS),
            "thresholds": dict.fromkeys(LABELS, 0.90),
            "qualification": "candidate; historical Amazon result, not validated lab precision",
            "target": "greater than 95% accuracy among accepted pairs; maximise coverage",
        },
    )
    write_json(
        output / "inference.json",
        {
            "question": QUESTION,
            "feature_profile": "title_leaf_category",
            "protocol": INFERENCE_PROTOCOL,
            "max_batch_size": 128,
            "runtime": RUNTIME,
        },
    )
    source = {
        "base_model": provenance["base_model"],
        "base_revision": BASE_REVISION,
        "adapter_sha256": ADAPTER_SHA256,
        "mapping_key": MAPPING_KEY,
        "mapping_bundle_sha256": MAPPING_BUNDLE_SHA256,
        "training_manifest_sha256": sha256(trained / "training-manifest.json"),
    }
    manifest = {
        "format": "esci-release-v1",
        "name": "esci-v3-frozen-fla",
        "source": source,
        "files": file_inventory(output),
    }
    manifest["release_sha256"] = content_digest(manifest)
    write_json(output / "release.json", manifest)
    return verify_bundle(output)
