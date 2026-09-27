"""Receive one local trace and metric batch from the instrumented Search API image."""

import http.server
import os
import threading

seen = []


class Receiver(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers['Content-Length'])
        payload = self.rfile.read(size)
        seen.append((self.path, len(payload)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args):
        pass


server = http.server.HTTPServer(('127.0.0.1', 4318), Receiver)
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'] = 'http://127.0.0.1:4318'

from telemetry import Telemetry  # noqa: E402 - load after setting the local endpoint
from opentelemetry import metrics, trace  # noqa: E402

telemetry = Telemetry()
telemetry.configure()
with telemetry.span('search.request'):
    with telemetry.span('search.elasticsearch'):
        pass
    telemetry.record(200, 260, 'normal', request_id='synthetic-probe')
assert trace.get_tracer_provider().force_flush(5000)
assert metrics.get_meter_provider().force_flush(5000)
assert {'/v1/traces', '/v1/metrics'} <= {path for path, _ in seen}, seen
print('OTLP_RECEIVED', seen)
trace.get_tracer_provider().shutdown()
metrics.get_meter_provider().shutdown()
server.shutdown()
