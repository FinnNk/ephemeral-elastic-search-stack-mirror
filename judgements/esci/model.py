"""MLflow pyfunc contract; GPU loading is lazy so registration works on the CPU."""

import json
from pathlib import Path
import threading

import mlflow
import pandas as pd

from esci.contract import map_scores, model_state, outcome
from esci.release import read_json, verify_bundle


class EsciModel(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        self.bundle = Path(context.artifacts["bundle"])
        self.manifest = verify_bundle(self.bundle)
        self.settings = read_json(self.bundle / "inference.json")
        self.mapping = read_json(self.bundle / "score-mapping.json")
        self.policy = read_json(self.bundle / "policy.json")
        self.engine = None
        self.lock = threading.Lock()

    def predict(self, context, model_input, params=None):
        if not isinstance(model_input, pd.DataFrame) or list(model_input.columns) != [
            "payload"
        ]:
            raise ValueError(
                "Expected a DataFrame with one payload JSON-string column."
            )
        if len(model_input) > self.settings["max_batch_size"]:
            raise ValueError("Inference accepts a batch of at most 128 pairs.")
        states = [
            model_state(json.loads(payload)) for payload in model_input["payload"]
        ]
        if not states:
            return pd.DataFrame(
                columns=["outcome", "label", "confidence", "probabilities"]
            )
        # ThreadingHTTPServer must not concurrently allocate several GPU batches.
        with self.lock:
            if self.engine is None:
                from esci.engine import Engine

                self.engine = Engine(self.bundle, self.settings)
            raw = self.engine.predict(states)
        if len(raw) != len(states):
            raise RuntimeError("Model result count differs from request count.")
        return pd.DataFrame(
            [outcome(map_scores(row, self.mapping), self.policy) for row in raw]
        )


mlflow.models.set_model(EsciModel())
