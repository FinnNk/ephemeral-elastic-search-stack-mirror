"""Warm the GPU before exposing the existing KServe-compatible HTTP contract."""

import json
import os
from pathlib import Path

import mlflow
import pandas as pd

from predictor import serve
from telemetry import telemetry


def main():
    directory = Path(os.environ.get("MODEL_DIR", "/mnt/models"))
    identity = json.loads(
        (directory / ".model-identity.json").read_text(encoding="utf-8")
    )
    model = mlflow.pyfunc.load_model(str(directory))
    model.predict(
        pd.DataFrame(
            {
                "payload": [
                    json.dumps(
                        {
                            "request": {"query": "desk lamp"},
                            "product": {"title": "Desk lamp", "category": "Lighting"},
                        }
                    )
                ]
            }
        )
    )
    telemetry.configure("esci-judgement-predictor")
    serve(model, identity, port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
