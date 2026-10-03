"""Exercise both quality CLIs without GPU inference or real quality claims."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

from label_quality import canonical, checksum
from test_label_quality import fixture


def test_frozen_input_cli_round_trip_hides_reference_labels(tmp_path):
    inputs, references, _, manifest, audit, policy = fixture(20)
    for name, rows in [("inputs", inputs), ("references", references)]:
        (tmp_path / (name + ".jsonl")).write_bytes(
            b"".join(canonical(row) for row in rows)
        )
    for name, value in [
        ("audit", audit),
        ("policy", policy),
        ("reservation", {"kind": "fixture-reservation"}),
    ]:
        (tmp_path / (name + ".json")).write_bytes(canonical(value))
    for name in ("inputs", "references", "audit", "policy", "reservation"):
        suffix = ".jsonl" if name in ("inputs", "references") else ".json"
        manifest[name + "_sha256"] = checksum(tmp_path / (name + suffix))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(canonical(manifest))
    requests = []

    class Model(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            predictions = []
            for pair in body["instances"]:
                exact = pair["product_id"] != "c"
                predictions.append(
                    {
                        "outcome": "labelled" if exact else "abstain",
                        "label": "E" if exact else None,
                        "confidence": 0.96 if exact else 0.6,
                        "probabilities": [0.96, 0.02, 0.01, 0.01]
                        if exact
                        else [0.6, 0.2, 0.1, 0.1],
                    }
                )
            payload = canonical(
                {"model": manifest["model"], "predictions": predictions}
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Model)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    environment = dict(os.environ)
    environment.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    shared = [
        "--inputs",
        str(tmp_path / "inputs.jsonl"),
        "--manifest",
        str(manifest_path),
        "--audit",
        str(tmp_path / "audit.json"),
        "--policy",
        str(tmp_path / "policy.json"),
        "--reservation",
        str(tmp_path / "reservation.json"),
    ]
    try:
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("infer_label_quality.py")),
                *shared,
                "--endpoint",
                f"http://127.0.0.1:{server.server_port}/predict",
                "--output",
                str(tmp_path / "inference"),
            ],
            check=True,
            capture_output=True,
            env=environment,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert requests
    for request in requests:
        assert set(request) == {"instances"}
        for pair in request["instances"]:
            assert set(pair) == {"query_id", "product_id", "request", "product"}
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("label_quality.py")),
            *shared,
            "--references",
            str(tmp_path / "references.jsonl"),
            "--predictions",
            str(tmp_path / "inference/predictions.jsonl"),
            "--output",
            str(tmp_path / "report.json"),
        ],
        check=True,
        capture_output=True,
        env=environment,
    )
    result = json.loads((tmp_path / "report.json").read_bytes())
    assert result["status"] == "inconclusive" and result["accepted"] == 40
    assert result["hashes"]["reservation"] == manifest["reservation_sha256"]
    assert json.loads((tmp_path / "inference/inference.json").read_bytes())["complete"]
