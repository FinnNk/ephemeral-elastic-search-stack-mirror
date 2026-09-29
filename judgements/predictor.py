"""Small KServe-compatible HTTP predictor for the pinned MLflow pyfunc model."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import time

from telemetry import telemetry


def predict(model, instances):
    import pandas as pd
    if not isinstance(instances, list) or len(instances) > 128:
        raise ValueError('Inference accepts a batch of at most 128 pairs.')
    frame = pd.DataFrame({'payload': [json.dumps(item, sort_keys=True,
                                                 separators=(',', ':'))
                                      for item in instances]})
    output = model.predict(frame)
    rows = output.to_dict(orient='records')
    if len(rows) != len(instances):
        raise ValueError('Model output count differs from input count.')
    for row in rows:
        if row.get('outcome') not in ('abstain', 'labelled'):
            raise ValueError('Model outcome is invalid.')
        if row['outcome'] == 'labelled' and row.get('label') not in ('E', 'S', 'C', 'I'):
            raise ValueError('Model ESCI label is invalid.')
    return rows


def serve(model, identity, host='0.0.0.0', port=8080):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ('/health', '/v1/models/judgement-model'):
                self.send_error(404)
                return
            self.reply(200, {'name': 'judgement-model', 'ready': True,
                             'model': identity})

        def do_POST(self):
            if self.path != '/v1/models/judgement-model:predict':
                self.send_error(404)
                return
            with telemetry.span('model.http', self.headers, kind='server'):
                started = time.monotonic()
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if length < 1 or length > 2_000_000:
                        raise ValueError('Inference payload size is invalid.')
                    value = json.loads(self.rfile.read(length))
                    with telemetry.span('model.predict'):
                        rows = predict(model, value['instances'])
                    duration_ms = (time.monotonic() - started) * 1000
                    telemetry.count_predictions(identity['version'], rows, duration_ms)
                    telemetry.count_request(identity['version'], 'success')
                    telemetry.attributes(http_response_status_code=200,
                                         lab_model_version=str(identity['version']),
                                         lab_model_batch_size=len(rows))
                    self.reply(200, {'predictions': rows, 'model': identity})
                except (ValueError, KeyError, TypeError) as error:
                    telemetry.count_request(identity['version'], 'error')
                    telemetry.attributes(http_response_status_code=400,
                                         error_type=type(error).__name__)
                    self.reply(400, {'error': str(error)})
                except Exception as error:
                    telemetry.count_request(identity['version'], 'error')
                    telemetry.attributes(http_response_status_code=500,
                                         error_type=type(error).__name__)
                    self.reply(500, {'error': 'Model inference failed.'})

        def reply(self, status, value):
            body = json.dumps(value, sort_keys=True).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == '__main__':
    import mlflow

    telemetry.configure('judgement-predictor')
    directory = Path(os.environ.get('MODEL_DIR', '/mnt/models'))
    identity = json.loads((directory / '.model-identity.json').read_bytes())
    model = mlflow.pyfunc.load_model(str(directory))
    serve(model, identity, port=int(os.environ.get('PORT', '8080')))
