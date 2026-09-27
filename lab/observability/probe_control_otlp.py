"""Check control-operation OTLP output against a local mock receiver."""

from contextlib import redirect_stdout
import http.server
import io
import json
import os
import threading

received = []


class Receiver(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        payload = self.rfile.read(int(self.headers['Content-Length']))
        received.append((self.path, len(payload)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args):
        pass


server = http.server.HTTPServer(('127.0.0.1', 4318), Receiver)
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'] = 'http://127.0.0.1:4318'

from opentelemetry import metrics, trace  # noqa: E402
from operation_telemetry import configure, operation  # noqa: E402

configure('lab-control-probe')


@operation('environment.create', deadline_seconds=120)
def create():
    return {'id': 'synthetic-environment', 'state': 'ready',
            'fingerprint': 'a' * 64, 'query': 'never-export-this'}


output = io.StringIO()
with redirect_stdout(output):
    assert create()['state'] == 'ready'
assert trace.get_tracer_provider().force_flush(5000)
assert metrics.get_meter_provider().force_flush(5000)
event = json.loads(output.getvalue())
assert event['trace_id'] and event['span_id']
assert event['fingerprint'] == 'a' * 64
assert 'query' not in event
assert {'/v1/traces', '/v1/metrics'} <= {path for path, _ in received}
print('CONTROL_OTLP_RECEIVED', received)
trace.get_tracer_provider().shutdown()
metrics.get_meter_provider().shutdown()
server.shutdown()
