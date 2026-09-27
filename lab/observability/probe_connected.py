"""Emit deterministic synthetic search outcomes through the configured OTLP endpoint."""

import os
import time

if not os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT'):
    raise SystemExit('Set OTEL_EXPORTER_OTLP_ENDPOINT to the lab gateway.')

from opentelemetry import metrics, trace  # noqa: E402
from telemetry import Telemetry  # noqa: E402

telemetry = Telemetry()
telemetry.configure()
for batch in range(2):
    for number, (status, duration) in enumerate(((200, 80), (200, 360), (502, 42)), 1):
        with telemetry.span('search.request'):
            with telemetry.span('search.query_understanding'):
                pass
            with telemetry.span('search.elasticsearch'):
                pass
            telemetry.record(status, duration, 'normal',
                             request_id=f'synthetic-connected-{batch}-{number}')
    assert metrics.get_meter_provider().force_flush(5000)
    if batch == 0:
        time.sleep(6)  # Give cumulative counters two distinct export timestamps.

assert trace.get_tracer_provider().force_flush(5000)
print('SYNTHETIC_CONNECTED_PROBE_SENT', flush=True)
trace.get_tracer_provider().shutdown()
metrics.get_meter_provider().shutdown()
