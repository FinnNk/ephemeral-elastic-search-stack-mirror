"""Build, inspect or register the selected v3 model without allocating a GPU."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judgements"))
from esci.release import build_bundle, read_json, verify_bundle, write_json


def main():
    # MLflow emits Unicode run links, including when PowerShell redirects output.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser(
        "build", help="Copy selected assets from the local research checkout"
    )
    build.add_argument("--research-root", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    inspect = commands.add_parser(
        "inspect", help="Check every file and show aggregate release metadata"
    )
    inspect.add_argument("--bundle", type=Path, required=True)
    register = commands.add_parser(
        "register", help="Upload and register; the serving pin is not changed"
    )
    register.add_argument("--bundle", type=Path, required=True)
    register.add_argument("--tracking-uri", required=True)
    register.add_argument("--name", default="synthetic-esci-judge")
    register.add_argument("--receipt", type=Path, required=True)
    canaries = commands.add_parser(
        "canaries",
        help="Export ignored local runtime references from old research scores",
    )
    canaries.add_argument("--research-root", type=Path, required=True)
    canaries.add_argument("--bundle", type=Path, required=True)
    canaries.add_argument("--output", type=Path, required=True)
    canaries.add_argument("--count", type=int, default=64)
    qualify = commands.add_parser(
        "qualify", help="Compare a running candidate against independent canary scores"
    )
    qualify.add_argument("--endpoint", required=True)
    qualify.add_argument("--canaries", type=Path, required=True)
    qualify.add_argument("--receipt", type=Path, required=True)
    qualify.add_argument("--image", required=True)
    qualify.add_argument("--output", type=Path, required=True)
    render = commands.add_parser(
        "render", help="Create candidate manifests or qualified live pins"
    )
    render.add_argument("--receipt", type=Path, required=True)
    render.add_argument("--image", required=True)
    render.add_argument("--qualification", type=Path)
    render.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        from esci.registration import register as register_model

        result = register_model(args.bundle, args.tracking_uri, args.name)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.receipt, result)
    elif args.command == "canaries":
        from esci.canaries import export_canaries

        result = export_canaries(
            args.research_root, args.bundle, args.output, args.count
        )
    elif args.command == "qualify":
        from esci.qualification import qualify as qualify_model

        result = qualify_model(
            args.endpoint, args.canaries, args.receipt, args.image, args.output
        )
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit(2)
        return
    elif args.command == "render":
        from esci.deployment import render as render_model

        rendered = render_model(
            read_json(args.receipt),
            args.image,
            read_json(args.qualification) if args.qualification else None,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.output, rendered)
        result = {
            "output": str(args.output),
            "live_pins": args.qualification is not None,
        }
    else:
        result = (
            build_bundle(args.research_root, args.output)
            if args.command == "build"
            else verify_bundle(args.bundle)
        )
        result = {
            "release_sha256": result["release_sha256"],
            "source": result["source"],
            "files": len(result["files"]),
            "bytes": sum(f["bytes"] for f in result["files"].values()),
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
