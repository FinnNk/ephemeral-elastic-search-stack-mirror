"""Small KServe-compatible HTTP predictor for the pinned MLflow pyfunc model."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path


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
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 2_000_000:
                    raise ValueError('Inference payload size is invalid.')
                value = json.loads(self.rfile.read(length))
                self.reply(200, {'predictions': predict(model, value['instances']),
                                 'model': identity})
            except (ValueError, KeyError, TypeError) as error:
                self.reply(400, {'error': str(error)})

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
    directory = Path(os.environ.get('MODEL_DIR', '/mnt/models'))
    identity = json.loads((directory / '.model-identity.json').read_bytes())
    model = mlflow.pyfunc.load_model(str(directory))
    serve(model, identity, port=int(os.environ.get('PORT', '8080')))
