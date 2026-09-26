"""Small black-box search API and browser page for the frozen UK retail release."""
import base64
import json
import os
import ssl
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_QUERY_LENGTH = 150


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


def query_body(query, country, currency):
    return {
        'size': 20,
        'track_total_hits': True,
        'query': {'bool': {
            'must': [{'multi_match': {'query': query, 'fields': ['title^4', 'product_type^3', 'brand^2', 'description']}}],
            'filter': [{'term': {'country': country}}, {'term': {'currency': currency}}, {'term': {'available': True}}],
        }},
        'sort': [{'_score': 'desc'}, {'product_id': 'asc'}],
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
        try:
            query, country, currency = validated_query(self.path)
        except ValueError as error:
            return self.send_json(400, {'error': str(error)})
        auth = base64.b64encode((os.environ['ES_USER'] + ':' + os.environ['ES_PASSWORD']).encode()).decode()
        request = urllib.request.Request(
            os.environ['ES_URL'] + '/' + os.environ['ES_INDEX'] + '/_search',
            data=json.dumps(query_body(query, country, currency)).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth},
        )
        try:
            context = ssl.create_default_context(cafile='/es-ca/tls.crt')
            with urllib.request.urlopen(request, context=context, timeout=10) as response:
                result = json.load(response)
        except Exception as error:
            self.log_error('Elasticsearch request failed: %s', type(error).__name__)
            return self.send_json(502, {'error': 'Search is temporarily unavailable.'})
        return self.send_json(200, api_response(query, country, currency, result,
                                                (time.monotonic() - start) * 1000))

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
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
