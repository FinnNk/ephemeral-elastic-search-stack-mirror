"""Run the Search API and browser page with synthetic in-memory search results."""
import argparse
import re
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app import Handler

PRODUCTS = [
    ('demo-01', 'Stride running shoes', 'Stride', 'footwear', 'running shoes', 6500),
    ('demo-02', 'Alder trail running shoes', 'Alder', 'footwear', 'running shoes', 7900),
    ('demo-03', 'Alder wireless headphones', 'Alder', 'electronics', 'headphones', 4900),
    ('demo-04', 'Echo wireless headphones', 'Echo', 'electronics', 'headphones', 8500),
    ('demo-05', 'Lumen black desk lamp', 'Lumen', 'home', 'desk lamp', 3200),
    ('demo-06', 'Hearth ceramic mug', 'Hearth', 'home', 'mug', 1200),
    ('demo-07', 'Alder cotton shirt', 'Alder', 'clothing', 'shirt', 2500),
    ('demo-08', 'Stride sports socks', 'Stride', 'clothing', 'socks', 900),
]


def mock_search(body):
    """Approximate weighted token matches, not Elasticsearch scoring semantics."""
    request = body['query']['bool']['must'][0]['multi_match']
    terms = set(re.findall(r'\w+', request['query'].casefold()))
    hits = []
    for product_id, title, brand, category, product_type, price in PRODUCTS:
        product = dict(product_id=product_id, title=title, brand=brand, category=category,
                       product_type=product_type, price_minor=price, country='GB',
                       currency='GBP', available=True, description=f'{title} for everyday use')
        score = 0
        for field in request['fields']:
            name, _, boost = field.partition('^')
            score += len(terms & set(re.findall(r'\w+', product[name].casefold()))) * float(boost or 1)
        if score:
            hits.append({'_source': product, '_score': score})
    hits.sort(key=lambda hit: (-hit['_score'], hit['_source']['product_id']))
    return {'hits': {'total': {'value': len(hits)}, 'hits': hits[:body['size']]}}


class DemoHandler(Handler):
    def search_index(self, body):
        started = time.monotonic()
        return mock_search(body), (time.monotonic() - started) * 1000

    def do_GET(self):
        if urlparse(self.path).path == '/':
            page = Path(__file__).with_name('index.html').read_text(encoding='utf-8')
            page = re.sub(r'(<div class="eyebrow">).*?(</div>)', r'\1Standalone demo - 8 mock products\2', page)
            page = page.replace('Explore the baseline search.', 'Explore the mock search.')
            page = page.replace('Search a reproducible retail catalogue.',
                                'Offline demo with in-memory search. Elasticsearch and the lab are not connected.')
            return self.send_body(200, page.encode(), 'text/html; charset=utf-8')
        return super().do_GET()

    def send_json(self, status, value):
        return super().send_json(status, {**value, 'data_source': 'standalone-mock'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1', help='Use 0.0.0.0 inside Docker.')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f'Standalone mock demo: http://127.0.0.1:{server.server_port}/', flush=True)
    print('8 synthetic products; no lab, Elasticsearch, credentials or telemetry exporter. Stop with Ctrl+C.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
