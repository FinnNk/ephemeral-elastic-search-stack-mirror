"""Bounded OTel signals for judgement lookup and model inference.

Only a numbered model version, outcome and fixed feature buckets are metric
dimensions. Query text, product data and pair IDs never leave the service.
"""

from contextlib import nullcontext
import os
from urllib.parse import urlparse


class Telemetry:
    def __init__(self):
        self.tracer = None
        self.results = None
        self.predictions = None
        self.requests = None
        self.duration = None
        self.input_shift = None
        self.coverage = None

    def configure(self, service_name):
        endpoint = os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', '').rstrip('/')
        if not endpoint or self.tracer is not None:
            return
        parsed = urlparse(endpoint)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError('OTEL_EXPORTER_OTLP_ENDPOINT must be an HTTP(S) collector URL.')
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
            'lab.source_profile': os.environ.get('LAB_SOURCE_PROFILE', 'shared'),
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
        self.tracer = trace.get_tracer('relevance-lab.judgements', '1')
        meter = metrics.get_meter('relevance-lab.judgements', '1')
        self.results = meter.create_counter('lab.judgement.results', unit='{pair}')
        self.predictions = meter.create_counter('lab.model.predictions', unit='{pair}')
        self.requests = meter.create_counter('lab.model.requests', unit='{request}')
        self.duration = meter.create_histogram('lab.model.inference_duration', unit='ms')
        self.input_shift = meter.create_gauge('lab.model.input_shift_jsd', unit='1')
        self.coverage = meter.create_gauge('lab.judgement.pool_coverage_percent', unit='%')

    def span(self, name, headers=None, kind='internal'):
        if self.tracer is None:
            return nullcontext()
        from opentelemetry import propagate, trace
        parent = propagate.extract({key.lower(): value for key, value in headers.items()}) if headers else None
        kinds = {'server': trace.SpanKind.SERVER, 'client': trace.SpanKind.CLIENT,
                 'internal': trace.SpanKind.INTERNAL}
        return self.tracer.start_as_current_span(name, context=parent, kind=kinds[kind])

    def inject(self, headers):
        if self.tracer is not None:
            from opentelemetry import propagate
            propagate.inject(headers)

    def attributes(self, **values):
        if self.tracer is None:
            return
        from opentelemetry import trace
        span = trace.get_current_span()
        for key, value in values.items():
            if value is not None:
                name = {'http_response_status_code': 'http.response.status_code',
                        'error_type': 'error.type'}.get(key, key.replace('_', '.'))
                span.set_attribute(name, value)

    def count_results(self, model_version, rows):
        if self.results is None:
            return
        for row in rows:
            outcome = row['outcome']
            source = row.get('source', 'none') if outcome == 'labelled' else 'none'
            try:
                version = row.get('provenance', {}).get('model', {}).get('version', model_version)
                self.results.add(1, {'lab.model.version': str(version),
                                     'lab.judgement.outcome': outcome,
                                     'lab.judgement.source': source})
            except Exception:
                pass

    def count_predictions(self, model_version, rows, duration_ms):
        try:
            if self.predictions is not None:
                for row in rows:
                    self.predictions.add(1, {
                        'lab.model.version': str(model_version),
                        'lab.model.outcome': row['outcome'],
                        'lab.model.label': row.get('label') or 'none'})
            if self.duration is not None:
                self.duration.record(duration_ms, {'lab.model.version': str(model_version)})
        except Exception:
            pass

    def count_request(self, model_version, outcome):
        if self.requests is not None:
            try:
                self.requests.add(1, {'lab.model.version': str(model_version),
                                      'lab.model.request_outcome': outcome})
            except Exception:
                pass

    def record_shift(self, model_version, score):
        if self.input_shift is not None and score is not None:
            try:
                self.input_shift.set(score, {'lab.model.version': str(model_version),
                                             'lab.model.feature': 'query_length'})
            except Exception:
                pass

    def record_coverage(self, model_version, counts):
        if self.coverage is not None and counts['required']:
            try:
                percent = 100 * (counts['stored'] + counts['newly_labelled']) / counts['required']
                self.coverage.set(percent, {'lab.model.version': str(model_version)})
            except Exception:
                pass


telemetry = Telemetry()
