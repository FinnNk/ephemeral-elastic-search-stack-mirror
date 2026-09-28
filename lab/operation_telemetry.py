"""Bounded, optional OTLP signals for lab control operations.

Operation IDs and immutable references belong in spans and structured logs, not
in metric dimensions. Export failures must never affect an operation's result.
"""

from contextlib import nullcontext
from datetime import datetime, timezone
from functools import wraps
import json
import os
import time

_tracer = None
_eligible = None
_good = None
_deadline_good = None
_duration = None
_service_name = 'lab-control'

SAFE_RESULT_FIELDS = (
    'id', 'state', 'fingerprint', 'report_sha256', 'source_sha',
    'dataset_sha256', 'baseline_id', 'candidate_id', 'comparison_id',
    'baseline_fingerprint', 'candidate_fingerprint',
    'index_recipe_sha256', 'query_manifest_sha256', 'judgement_manifest_sha256',
)
GOOD_TERMINAL_STATES = frozenset({'complete', 'ready', 'deleted', 'verified'})


def configure(service_name):
    """Enable OTLP/HTTP only when a gateway endpoint is configured."""
    global _tracer, _eligible, _good, _deadline_good, _duration, _service_name
    _service_name = service_name
    endpoint = os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', '').rstrip('/')
    if not endpoint or _tracer is not None:
        return
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({
        'service.name': service_name,
        'service.namespace': 'relevance-lab',
        'service.version': os.environ.get('LAB_RELEASE_SHA', 'local'),
        'deployment.environment.name': os.environ.get('LAB_DEPLOYMENT_TIER', 'lab'),
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=endpoint + '/v1/traces', timeout=2),
        max_queue_size=256, max_export_batch_size=64, schedule_delay_millis=1000))
    trace.set_tracer_provider(provider)
    meter_provider = MeterProvider(resource=resource, metric_readers=[
        PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint + '/v1/metrics', timeout=2),
            export_interval_millis=5000)])
    metrics.set_meter_provider(meter_provider)
    _tracer = trace.get_tracer('relevance-lab.operations', '1')
    meter = metrics.get_meter('relevance-lab.operations', '1')
    _eligible = meter.create_counter('lab.operation.eligible', unit='{operation}')
    _good = meter.create_counter('lab.operation.good', unit='{operation}')
    _deadline_good = meter.create_counter('lab.operation.deadline_good', unit='{operation}')
    _duration = meter.create_histogram('lab.operation.duration', unit='ms')


def request_span(method, path, headers):
    """Extract W3C request context without recording a query string or headers."""
    if _tracer is None:
        return nullcontext()
    from opentelemetry import propagate, trace
    parent = propagate.extract({key.lower(): value for key, value in headers.items()})
    span = _tracer.start_span('control.http', context=parent, kind=trace.SpanKind.SERVER)
    span.set_attribute('http.request.method', method)
    span.set_attribute('url.path', path)
    return trace.use_span(span, end_on_exit=True)


def response_status(status):
    if _tracer is None:
        return
    from opentelemetry import trace
    trace.get_current_span().set_attribute('http.response.status_code', status)


def correlation(**fields):
    """Attach immutable references to the active span and return its IDs for Jobs."""
    if _tracer is None:
        return {}
    from opentelemetry import trace
    span = trace.get_current_span()
    for key, value in fields.items():
        if key in SAFE_RESULT_FIELDS and isinstance(value, (str, int, float, bool)):
            span.set_attribute('lab.' + key, value)
    context = span.get_span_context()
    if not context.is_valid:
        return {}
    return {'trace_id': format(context.trace_id, '032x'),
            'span_id': format(context.span_id, '016x')}


def operation(name, deadline_seconds=None):
    """Trace one synchronous boundary, preserving the wrapped function's result."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            started = time.monotonic()
            state = 'failed'
            result = None
            error_kind = None
            with _tracer.start_as_current_span(name) if _tracer else nullcontext() as span:
                try:
                    result = function(*args, **kwargs)
                    state = result.get('state', 'complete') if isinstance(result, dict) else 'complete'
                    return result
                except Exception as error:
                    error_kind = type(error).__name__
                    raise
                finally:
                    duration_ms = (time.monotonic() - started) * 1000
                    # A returned pending, incomplete or unknown state still spends budget.
                    good = state in GOOD_TERMINAL_STATES
                    deadline_met = good and (deadline_seconds is None or duration_ms <= deadline_seconds * 1000)
                    fields = {key: value for key in SAFE_RESULT_FIELDS
                              if isinstance(result, dict) and (value := result.get(key)) is not None
                              and isinstance(value, (str, int, float, bool))}
                    if span is not None:
                        span.set_attribute('lab.operation.kind', name)
                        span.set_attribute('lab.operation.state', state)
                        for key, value in fields.items():
                            span.set_attribute('lab.' + key, value)
                        if error_kind:
                            span.set_attribute('error.type', error_kind)
                    try:
                        if _eligible is not None:
                            attributes = {'lab.operation.kind': name}
                            _eligible.add(1, attributes)
                            _good.add(int(good), attributes)
                            if deadline_seconds is not None:
                                _deadline_good.add(int(deadline_met), attributes)
                            _duration.record(duration_ms, attributes)
                        event = {'event': 'lab.operation.completed', 'service': _service_name,
                                 'operation': name, 'state': state,
                                 'service_version': os.environ.get('LAB_RELEASE_SHA', 'local')[:200],
                                 'deployment_tier': os.environ.get('LAB_DEPLOYMENT_TIER', 'lab')[:80],
                                 'duration_ms': round(duration_ms, 3),
                                 'observed_at': datetime.now(timezone.utc).isoformat(), **fields}
                        if error_kind:
                            event['error_kind'] = error_kind
                        if span is not None:
                            context = span.get_span_context()
                            if context.is_valid:
                                event['trace_id'] = format(context.trace_id, '032x')
                                event['span_id'] = format(context.span_id, '016x')
                        print(json.dumps(event, sort_keys=True), flush=True)
                    except Exception:
                        pass
        return wrapped
    return decorate
