"""Small black-box search API and browser page for the frozen UK retail release."""
import hashlib
import json
import os
import re
import ssl
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from telemetry import telemetry
from variants import BASE, select
from search_filters import clauses, parse_filters

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
    params = urllib.parse.parse_qs(urllib.parse.urlparse(path).query, keep_blank_values=True)
    selected = params.get('filters', ['{}'])
    if len(selected) != 1:
        raise ValueError('Supply filters once.')
    return query, country, currency, parse_filters(selected[0])


def understand(query):
    """Return the Elasticsearch query and a named rewrite decision."""
    return query, 'none'


def query_body(query, country, currency, variant=None, filters=None):
    understood_query, _decision = understand(query)
    boosts = (variant or {'field_boosts': BASE})['field_boosts']
    return {
        'size': 20,
        'track_total_hits': True,
        'query': {'bool': {
            'must': [{'multi_match': {'query': understood_query,
                                     'fields': [field if boosts[field] == 1 else
                                                f'{field}^{boosts[field]}' for field in BASE]}}],
            'filter': [{'term': {'country': country}}, {'term': {'currency': currency}}, {'term': {'available': True}}] + clauses(filters if filters is not None else {}),
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


def api_response(query, country, currency, elastic_response, elapsed_ms, filters=None):
    hits = elastic_response['hits']
    products = []
    for hit in hits['hits']:
        source = hit['_source']
        products.append({key: source[key] for key in (
            'product_id', 'title', 'brand', 'category', 'price_minor', 'currency', 'available'
        )})
    return {
        'query': query, 'country': country, 'currency': currency,
        'filters': filters if filters is not None else {},
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
        if route == '/catalogue':
            return self.handle_catalogue()
        if route != '/search':
            return self.send_json(404, {'error': 'Not found'})
        return self.handle_search(start)

    def handle_catalogue(self):
        with telemetry.span('catalogue.request', self.headers):
            try:
                return self.send_json(200, self.catalogue())
            except Exception as error:
                self.log_error('Catalogue request failed: %s', type(error).__name__)
                return self.send_json(502, {'error': 'Catalogue information is temporarily unavailable.'})

    def catalogue(self):
        """Count all UK products, including those unavailable for search."""
        headers = {}
        with telemetry.span('catalogue.elasticsearch'):
            telemetry.inject(headers)
            response = self.server.elasticsearch.post('/' + os.environ['ES_INDEX'] + '/_count',
                json={'query': {'bool': {'filter': [
                    {'term': {'country': 'GB'}}, {'term': {'currency': 'GBP'}}]}}}, headers=headers)
            response.raise_for_status()
            result = response.json()
            if result.get('_shards', {}).get('failed', 0):
                raise ValueError('Incomplete catalogue count')
            return {'products': result['count'], 'country': 'GB', 'currency': 'GBP', 'mode': 'lab'}

    def handle_search(self, start):
        try:
            query, country, currency, filters = validated_query(self.path)
            correlation_id = diagnostic_options(self.path)
            variant_id, variant, configuration_sha256 = select(self.headers)
        except ValueError as error:
            return self.send_json(400, {'error': str(error)})
        with telemetry.span('search.request', self.headers) as request_span:
            if request_span is not None:
                request_span.set_attribute('http.request.method', 'GET')
                request_span.set_attribute('http.route', '/search')
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            raw_query = params.get('q', [''])[0]
            with telemetry.span('search.query_understanding'):
                body = query_body(query, country, currency, variant, filters)
            try:
                result, es_ms = self.search_index(body)
            except Exception as error:
                self.log_error('Elasticsearch request failed: %s', type(error).__name__)
                telemetry.record(502, (time.monotonic() - start) * 1000,
                                 self.headers.get('X-Lab-Traffic-Class'), type(error).__name__, correlation_id)
                return self.send_json(502, {'error': 'Search is temporarily unavailable.'})
            api_ms = (time.monotonic() - start) * 1000
            try:
                payload = api_response(query, country, currency, result, api_ms, filters)
                payload['variant_id'] = variant_id
                payload['configuration_sha256'] = configuration_sha256
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

    def search_index(self, body):
        """Elasticsearch dependency; the standalone demo supplies an in-memory substitute."""
        headers = {}
        with telemetry.span('search.elasticsearch') as dependency_span:
            if dependency_span is not None:
                dependency_span.set_attribute('db.collection.name', os.environ['ES_INDEX'])
            telemetry.inject(headers)
            started = time.monotonic()
            response = self.server.elasticsearch.post('/' + os.environ['ES_INDEX'] + '/_search',
                                                       json=body, headers=headers)
            response.raise_for_status()
            return response.json(), (time.monotonic() - started) * 1000

    def send_json(self, status, value):
        self.send_body(status, json.dumps(value).encode(), 'application/json; charset=utf-8')

    def send_body(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


class SearchServer(ThreadingHTTPServer):
    """Own one verified Elasticsearch connection pool for this API process."""
    def __init__(self, address):
        # The disconnected demo replaces search_index and needs only Python.
        import httpx
        self.elasticsearch = httpx.Client(
            base_url=os.environ['ES_URL'],
            auth=(os.environ['ES_USER'], os.environ['ES_PASSWORD']),
            verify=ssl.create_default_context(cafile='/es-ca/tls.crt'),
            timeout=10, trust_env=False,
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=64))
        try:
            super().__init__(address, Handler)
        except Exception:
            self.elasticsearch.close()
            raise

    def server_close(self):
        try:
            super().server_close()
        finally:
            self.elasticsearch.close()


if __name__ == '__main__':
    telemetry.configure()
    server = SearchServer(('0.0.0.0', 8080))
    print('Search API listening on port 8080. Browser: http://127.0.0.1:8080/ (local process).', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
