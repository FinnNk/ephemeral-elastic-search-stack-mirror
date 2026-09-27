"""Verify the alternate Collector export profile against a local OTLP receiver.

No New Relic endpoint or credential is used. Docker Desktop must be running.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name('gateway-newrelic.yaml')
RECEIVER_PORT = 14320
GATEWAY_PORT = 14321
HEALTH_PORT = 14322
received = []


class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        received.append((self.path, len(body), self.headers.get('api-key')))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args):
        pass


PROBE = '''from opentelemetry import metrics, trace
from operation_telemetry import configure, operation
configure('lab-export-profile-probe')
@operation('environment.create', deadline_seconds=120)
def create():
    return {'id': 'synthetic-profile-probe', 'state': 'ready'}
create()
metrics.get_meter_provider().force_flush(5000)
create()
trace.get_tracer_provider().force_flush(5000)
metrics.get_meter_provider().force_flush(5000)
trace.get_tracer_provider().shutdown()
metrics.get_meter_provider().shutdown()
'''


def main():
    server = ThreadingHTTPServer(('0.0.0.0', RECEIVER_PORT), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    container_name = 'lab-nr-profile-probe-' + uuid.uuid4().hex[:8]
    collector = subprocess.Popen([
        'docker', 'run', '--rm', '--name', container_name,
        '--add-host=host.docker.internal:host-gateway',
        '-p', f'127.0.0.1:{GATEWAY_PORT}:4318',
        '-p', f'127.0.0.1:{HEALTH_PORT}:13133',
        '-v', f'{CONFIG}:/etc/otel/config.yaml:ro',
        '-e', f'NEW_RELIC_OTLP_ENDPOINT=http://host.docker.internal:{RECEIVER_PORT}',
        '-e', 'NEW_RELIC_LICENSE_KEY=synthetic-validation-key',
        'otel/opentelemetry-collector-contrib:0.161.0',
        '--config=/etc/otel/config.yaml',
    ], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if collector.poll() is not None:
                raise RuntimeError('Collector exited: ' + collector.stderr.read()[-1200:])
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{HEALTH_PORT}/', timeout=1):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            raise TimeoutError('Collector health endpoint did not open.')
        subprocess.run([
            'docker', 'run', '--rm', '-i', '--add-host=host.docker.internal:host-gateway',
            '-e', 'PYTHONPATH=/app/lab',
            '-e', f'OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:{GATEWAY_PORT}',
            '--entrypoint', 'python', 'lab-control-observability:local', '-'
        ], cwd=ROOT, input=PROBE, text=True, check=True, capture_output=True)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not {'/v1/traces', '/v1/metrics'} <= {
                path for path, _, _ in received}:
            time.sleep(0.25)
        assert {'/v1/traces', '/v1/metrics'} <= {path for path, _, _ in received}, received
        assert all(key == 'synthetic-validation-key' for _, _, key in received), received
        print('LOCAL_EXPORT_PROFILE_RECEIVED', [(path, size) for path, size, _ in received])
    finally:
        subprocess.run(['docker', 'stop', container_name], cwd=ROOT,
                       capture_output=True, text=True)
        collector.terminate()
        try:
            collector.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            collector.kill()
            collector.communicate()
        server.shutdown()


if __name__ == '__main__':
    sys.exit(main())
