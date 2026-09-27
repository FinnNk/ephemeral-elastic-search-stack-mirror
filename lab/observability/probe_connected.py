"""Emit deterministic synthetic search outcomes through the configured OTLP endpoint."""

import os

if not os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT'):
    raise SystemExit('Set OTEL_EXPORTER_OTLP_ENDPOINT to the lab gateway.')

from opentelemetry import metrics, trace  # noqa: E402
from telemetry import Telemetry  # noqa: E402

telemetry = Telemetry()
telemetry.configure()
for number, (status, duration) in enumerate(((200, 80), (200, 360), (502, 42)), 1):
    with telemetry.span('search.request'):
        with telemetry.span('search.query_understanding'):
            pass
        with telemetry.span('search.elasticsearch'):
            pass
        telemetry.record(status, duration, 'normal', request_id=f'synthetic-connected-{number}')

assert trace.get_tracer_provider().force_flush(5000)
assert metrics.get_meter_provider().force_flush(5000)
print('SYNTHETIC_CONNECTED_PROBE_SENT', flush=True)
trace.get_tracer_provider().shutdown()
metrics.get_meter_provider().shutdown()
