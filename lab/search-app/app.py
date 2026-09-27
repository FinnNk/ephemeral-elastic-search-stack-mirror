"""Small black-box search API and browser page for the frozen UK retail release."""
import base64
import hashlib
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from telemetry import telemetry

MAX_QUERY_LENGTH = 150
DIAGNOSTIC_SCHEMA = 1


def validated_query(path):
    params = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    query = ' '.join(params.get('q', [''])[0].split())
    country = params.get('country', ['GB'])[0]
    currency = params.get('currency', ['GBP'])[0]
    if not query or len(query) > MAX_QUERY_LENGTH:
        raise ValueError('Enter a search term of 1–150 characters.')
    if (country, currency) != ('GB', 'GBP'):
        raise ValueError('This release supports GB and GBP.')
    return query, country, currency


def understand(query):
    """Return the Elasticsearch query and a named rewrite decision."""
    return query, 'none'


def query_body(query, country, currency):
    understood_query, _decision = understand(query)
    return {
        'size': 20,
        'track_total_hits': True,
        'query': {'bool': {
            'must': [{'multi_match': {'query': understood_query, 'fields': ['title^4', 'product_type^3', 'brand^2', 'description']}}],
            'filter': [{'term': {'country': country}}, {'term': {'currency': currency}}, {'term': {'available': True}}],
        }},
        'sort': [{'_score': 'desc'}, {'product_id': 'asc'}],
    }


def diagnostic_options(path):
    params = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    if params.get('diagnostics', ['0'])[0] != '1':
        return None
    correlation_id = params.get('request_id', [str(uuid.uuid4())])[0]
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', correlation_id):
        raise ValueError('Invalid request ID.')
    return correlation_id


def diagnostic_record(raw_query, query, body, result, correlation_id, api_ms, es_ms):
    understood_query, decision = understand(query)
    canonical_request = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    return {
        'schema_version': DIAGNOSTIC_SCHEMA,
        'correlation_id': correlation_id,
        'original_query': raw_query,
        'normalised_query': query,
        'elasticsearch_query': understood_query,
        'rewrite': decision,
        'elasticsearch_request_sha256': hashlib.sha256(canonical_request).hexdigest(),
        'retrieved_ids': [hit['_source']['product_id'] for hit in result['hits']['hits']],
        'stage_ms': {'elasticsearch': round(es_ms, 3), 'api_total': round(api_ms, 3)},
        'unavailable_stages': ['reranker'],
    }


def api_response(query, country, currency, elastic_response, elapsed_ms):
    hits = elastic_response['hits']
    products = []
    for hit in hits['hits']:
        source = hit['_source']
        products.append({key: source[key] for key in (
            'product_id', 'title', 'brand', 'category', 'price_minor', 'currency', 'available'
        )})
    return {
        'query': query, 'country': country, 'currency': currency,
        'total': hits['total']['value'], 'results': products,
        'ids': [product['product_id'] for product in products],
        'elapsed_ms': round(elapsed_ms, 3),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        start = time.monotonic()
        route = urllib.parse.urlparse(self.path).path
        if route == '/health':
            return self.send_json(200, {'ready': True})
        if route == '/':
            body = Path(__file__).with_name('index.html').read_bytes()
            return self.send_body(200, body, 'text/html; charset=utf-8')
        if route != '/search':
            return self.send_json(404, {'error': 'Not found'})
        return self.handle_search(start)

    def handle_search(self, start):
        try:
            query, country, currency = validated_query(self.path)
            correlation_id = diagnostic_options(self.path)
        except ValueError as error:
            return self.send_json(400, {'error': str(error)})
        with telemetry.span('search.request', self.headers) as request_span:
            if request_span is not None:
                request_span.set_attribute('http.request.method', 'GET')
                request_span.set_attribute('http.route', '/search')
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            raw_query = params.get('q', [''])[0]
            with telemetry.span('search.query_understanding'):
                body = query_body(query, country, currency)
            auth = base64.b64encode((os.environ['ES_USER'] + ':' + os.environ['ES_PASSWORD']).encode()).decode()
            headers = {'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth}
            telemetry.inject(headers)
            request = urllib.request.Request(
                os.environ['ES_URL'] + '/' + os.environ['ES_INDEX'] + '/_search',
                data=json.dumps(body).encode(), headers=headers)
            try:
                with telemetry.span('search.elasticsearch'):
                    context = ssl.create_default_context(cafile='/es-ca/tls.crt')
                    es_start = time.monotonic()
                    with urllib.request.urlopen(request, context=context, timeout=10) as response:
                        result = json.load(response)
                    es_ms = (time.monotonic() - es_start) * 1000
            except Exception as error:
                self.log_error('Elasticsearch request failed: %s', type(error).__name__)
                telemetry.record(502, (time.monotonic() - start) * 1000,
                                 self.headers.get('X-Lab-Traffic-Class'), type(error).__name__, correlation_id)
                return self.send_json(502, {'error': 'Search is temporarily unavailable.'})
            api_ms = (time.monotonic() - start) * 1000
            try:
                payload = api_response(query, country, currency, result, api_ms)
            except (KeyError, TypeError, ValueError) as error:
                telemetry.record(502, api_ms, self.headers.get('X-Lab-Traffic-Class'),
                                 type(error).__name__, correlation_id)
                return self.send_json(502, {'error': 'Search response is temporarily unavailable.'})
            if correlation_id is not None:
                payload['diagnostics'] = diagnostic_record(raw_query, query, body, result,
                                                           correlation_id, api_ms, es_ms)
            telemetry.record(200, api_ms, self.headers.get('X-Lab-Traffic-Class'),
                             request_id=correlation_id)
            return self.send_json(200, payload)

    def send_json(self, status, value):
        self.send_body(status, json.dumps(value).encode(), 'application/json; charset=utf-8')

    def send_body(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    telemetry.configure()
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
