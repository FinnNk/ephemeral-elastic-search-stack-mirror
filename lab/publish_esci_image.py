"""Build the separate CUDA predictor and publish an immutable Nexus image digest."""

import argparse
import hashlib
import json
import os
import re

from publish_judgement_image import ROOT, STATE, call


def source_sha256() -> str:
    paths = [
        ROOT / "judgements" / name
        for name in ("predictor.py", "telemetry.py", "fetch_model.py")
    ]
    paths += [
        ROOT / "judgements/esci" / name
        for name in (
            "__init__.py",
            "contract.py",
            "engine.py",
            "model.py",
            "release.py",
            "serve.py",
            "Dockerfile",
            "requirements.lock",
        )
    ]
    checksum = hashlib.sha256()
    for path in sorted(paths):
        checksum.update(path.relative_to(ROOT).as_posix().encode() + b"\0")
        checksum.update(path.read_bytes())
    return checksum.hexdigest()


def publish() -> dict:
    credentials = json.loads((STATE / "nexus.json").read_text(encoding="utf-8"))[
        "publisher"
    ]
    config = STATE / "esci-docker-config"
    config.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, "DOCKER_CONFIG": str(config.resolve())}
    call(
        [
            "docker",
            "login",
            "127.0.0.1:18185",
            "--username",
            credentials["username"],
            "--password-stdin",
        ],
        environment,
        credentials["password"] + "\n",
    )
    source = source_sha256()
    tag = "127.0.0.1:18185/esci-judge:v3-" + source[:16] + "-amd64"
    call(
        [
            "docker",
            "buildx",
            "build",
            "--platform",
            "linux/amd64",
            "--provenance=false",
            "--load",
            "-t",
            tag,
            "-f",
            "judgements/esci/Dockerfile",
            ".",
        ],
        environment,
    )
    call(["docker", "push", tag], environment)
    digests = json.loads(
        call(
            ["docker", "image", "inspect", tag, "--format", "{{json .RepoDigests}}"],
            environment,
        )
    )
    matching = [
        d for d in digests if d.startswith("127.0.0.1:18185/esci-judge@sha256:")
    ]
    if len(matching) != 1 or not re.fullmatch(r".+@sha256:[a-f0-9]{64}", matching[0]):
        raise ValueError("Published image has no unambiguous registry digest.")
    receipt = {
        "image": matching[0].replace("127.0.0.1", "nexus.localhost", 1),
        "source_sha256": source,
        "platform": "linux/amd64",
        "gpu_qualification": "pending",
    }
    (STATE / "esci-image.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            {"source_sha256": source_sha256()} if args.source_only else publish()
        )
    )
