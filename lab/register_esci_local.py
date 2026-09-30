"""Register a large release without sending its bytes through kubectl port-forward."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def inside(bundle: Path, receipt: Path) -> None:
    Path(os.environ["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judgements"))
    from esci.registration import register

    result = register(bundle, "http://mlflow-mlflow.lab-models.svc:5000")
    result["transport"] = "k3d network; direct presigned multipart; CPU-only helper"
    receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--image", help="Previously published runtime image, pinned by digest"
    )
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        inside(args.bundle, args.receipt)
        return
    from common import ROOT, guard, k

    guard()
    if not args.image or "@sha256:" not in args.image:
        parser.error("Supply the published runtime image digest with --image.")
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    output = args.receipt.parent.resolve()
    hosts = output / "cluster-hosts"
    entries = ["127.0.0.1 localhost"]
    for name in ("mlflow-mlflow", "model-artifacts"):
        service = json.loads(
            k("get", "service/" + name, "-n", "lab-models", "-o", "json").stdout
        )
        entries.append(f"{service['spec']['clusterIP']} {name}.lab-models.svc")
    # A bind mount shadows /etc/hosts in this helper only; the node is unchanged.
    hosts.write_text("\n".join(entries) + "\n", encoding="utf-8")
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "container:k3d-observability-0",
        "--mount",
        f"type=bind,source={ROOT},target=/repo,readonly",
        "--mount",
        f"type=bind,source={args.bundle.resolve()},target=/bundle,readonly",
        "--mount",
        f"type=bind,source={output},target=/output",
        "--mount",
        f"type=bind,source={hosts},target=/etc/hosts,readonly",
        "-e",
        "TMPDIR=/output/registration-tmp",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "MLFLOW_HTTP_REQUEST_TIMEOUT=600",
        "-e",
        "MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR=false",
        "-e",
        "MLFLOW_DISABLE_AGENT_HINT=1",
        "-e",
        "MLFLOW_ENABLE_PROXY_MULTIPART_UPLOAD=true",
        "-e",
        "MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD=true",
        "-e",
        "GIT_PYTHON_REFRESH=quiet",
        args.image.replace("nexus.localhost:", "127.0.0.1:", 1),
        "/repo/lab/register_esci_local.py",
        "--inside",
        "--bundle",
        "/bundle",
        "--receipt",
        "/output/" + args.receipt.name,
    ]
    # No --gpus flag: model registration and byte verification use no GPU.
    subprocess.run(command, check=True)
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    downloaded = Path(receipt["verified_local_path"]).as_posix()
    if not downloaded.startswith("/output/"):
        raise ValueError(
            "Verified model download was not retained in the mounted output directory."
        )
    receipt["verified_local_path"] = str(output / downloaded.removeprefix("/output/"))
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
