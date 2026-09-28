"""Optional vendor-neutral OTLP signals for the public Search API."""

from contextlib import nullcontext
from datetime import datetime, timezone
import json
import os
from urllib.parse import urlparse

TRAFFIC_CLASSES = frozenset({'normal', 'warmup', 'peak', 'stress', 'recovery', 'probe'})
RESPONSIVE_MS = 250


def traffic_class(value):
    return value if value in TRAFFIC_CLASSES else 'unspecified'


def classify(status, duration_ms):
    """Classify one accepted search. Slow HTTP 200s consume the latency budget."""
    if not isinstance(duration_ms, (int, float)) or duration_ms < 0:
        raise ValueError('Search duration must be non-negative.')
    success = status == 200
    return {'eligible': 1, 'success_good': int(success),
            'responsive_good': int(success and duration_ms <= RESPONSIVE_MS)}


class Telemetry:
    def __init__(self):
        self.tracer = None
        self.eligible = None
        self.success = None
        self.responsive = None
        self.duration = None

    def configure(self):
        endpoint = os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', '').rstrip('/')
        if not endpoint:
            return
        parsed = urlparse(endpoint)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError('OTEL_EXPORTER_OTLP_ENDPOINT must be an HTTP(S) collector URL.')
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({'service.name': 'search-api',
                                    'service.namespace': 'relevance-lab',
                                    'service.version': os.environ.get('LAB_RELEASE_SHA', 'local'),
                                    'deployment.environment.name': os.environ.get('LAB_DEPLOYMENT_TIER', 'preview')})
        traces = TracerProvider(resource=resource)
        traces.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint + '/v1/traces', timeout=2),
            max_queue_size=256, max_export_batch_size=64, schedule_delay_millis=1000))
        trace.set_tracer_provider(traces)
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint + '/v1/metrics', timeout=2),
            export_interval_millis=5000)
        meters = MeterProvider(resource=resource, metric_readers=[reader], views=[
            View(instrument_name='lab.search.server_duration',
                 aggregation=ExplicitBucketHistogramAggregation((50, 100, 250, 500, 1000, 5000)))])
        metrics.set_meter_provider(meters)
        self.tracer = trace.get_tracer('relevance-lab.search-api', '1')
        meter = metrics.get_meter('relevance-lab.search-api', '1')
        self.eligible = meter.create_counter('lab.search.eligible', unit='{request}')
        self.success = meter.create_counter('lab.search.success_good', unit='{request}')
        self.responsive = meter.create_counter('lab.search.responsive_good', unit='{request}')
        self.duration = meter.create_histogram('lab.search.server_duration', unit='ms')

    def span(self, name, headers=None):
        if self.tracer is None:
            return nullcontext()
        from opentelemetry import propagate, trace
        context = propagate.extract({key.lower(): value for key, value in headers.items()}) if headers is not None else None
        return self.tracer.start_as_current_span(
            name, context=context,
            kind=trace.SpanKind.SERVER if headers is not None else trace.SpanKind.INTERNAL)

    def inject(self, headers):
        if self.tracer is not None:
            from opentelemetry import propagate
            propagate.inject(headers)

    def record(self, status, duration_ms, cohort, error_kind=None, request_id=None):
        counts = classify(status, duration_ms)
        cohort = traffic_class(cohort)
        attributes = {'lab.traffic_class': cohort}
        if self.eligible is not None:
            try:
                self.eligible.add(counts['eligible'], attributes)
                self.success.add(counts['success_good'], attributes)
                self.responsive.add(counts['responsive_good'], attributes)
                self.duration.record(duration_ms, attributes)
            except Exception:
                pass  # Telemetry must not turn a valid search into an HTTP failure.
        trace_id = span_id = None
        if self.tracer is not None:
            from opentelemetry import trace
            span = trace.get_current_span()
            span.set_attribute('http.response.status_code', status)
            span.set_attribute('lab.traffic_class', cohort)
            span.set_attribute('lab.search.responsive_good', bool(counts['responsive_good']))
            if error_kind:
                span.set_attribute('error.type', error_kind)
            context = span.get_span_context()
            if context.is_valid:
                trace_id, span_id = format(context.trace_id, '032x'), format(context.span_id, '016x')
        event = {'event': 'search.completed', 'observed_at': datetime.now(timezone.utc).isoformat(),
                 'service': 'search-api', 'status': status,
                 'service_version': os.environ.get('LAB_RELEASE_SHA', 'local')[:200],
                 'deployment_tier': os.environ.get('LAB_DEPLOYMENT_TIER', 'preview')[:80],
                 'duration_ms': round(duration_ms, 3), 'traffic_class': cohort,
                 'success_good': bool(counts['success_good']),
                 'responsive_good': bool(counts['responsive_good'])}
        if error_kind:
            event['error_kind'] = error_kind
        if request_id:
            event['request_id'] = request_id
        if trace_id:
            event.update(trace_id=trace_id, span_id=span_id)
        try:
            print(json.dumps(event, sort_keys=True), flush=True)
        except OSError:
            pass


telemetry = Telemetry()
