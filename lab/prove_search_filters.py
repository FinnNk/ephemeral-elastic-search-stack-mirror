"""Verify public HTTP filtering and capture against a disposable Elasticsearch index."""
import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'search-app'))
from app import Handler
from demo import PRODUCTS
from variants import BASE, select
from common import guard
from data_contract import elastic
from load_release import BASELINE_MAPPING
import evaluation_worker
import variant_capture_worker


def prove():
    guard()
    index = 'lab-filter-proof-' + uuid.uuid4().hex[:12]
    # Fixed synthetic fixture; add excluded availability/market records.
    products = [dict(product_id=pid, title=title, brand=brand, category=category,
        product_type=kind, price_minor=price, country='GB', currency='GBP',
        available=True, colour='black', material='cotton', description=title)
        for pid, title, brand, category, kind, price in PRODUCTS]
    products += [{**products[0], 'product_id': 'excluded-stock', 'available': False},
                 {**products[0], 'product_id': 'excluded-market', 'country': 'US', 'currency': 'USD'}]
    config = {'default_variant': 'ranker-a', 'variants': {
        name: {'field_boosts': {**BASE, 'brand': boost}}
        for name, boost in (('ranker-a', 2), ('ranker-b', 3), ('ranker-c', 4))}}

    class LiveHandler(Handler):
        def search_index(self, body):
            started = time.monotonic()
            return elastic('/' + index + '/_search', body=body, method='POST'), (time.monotonic() - started) * 1000

        def log_message(self, *_args):
            pass

    server = None
    created = False
    checks = []
    try:
        elastic('/' + index, method='PUT', body=BASELINE_MAPPING)
        created = True
        payload = ''.join(json.dumps({'index': {'_id': row['product_id']}}) + '\n' +
                          json.dumps(row) + '\n' for row in products)
        result = elastic('/' + index + '/_bulk?refresh=true', method='POST', body=payload, raw=True)
        if result['errors']:
            raise RuntimeError('Synthetic fixture indexing failed.')
        elastic('/' + index + '/_settings', method='PUT', body={'index.blocks.write': True})
        server = ThreadingHTTPServer(('127.0.0.1', 0), LiveHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        urlopen = urllib.request.urlopen

        def transport(request, **kwargs):
            parsed = urllib.parse.urlparse(request.full_url)
            if parsed.hostname and parsed.hostname.startswith('search.lab-') and parsed.hostname.endswith('.svc.cluster.local'):
                request = urllib.request.Request(base + parsed.path + '?' + parsed.query, headers=dict(request.header_items()))
            return urlopen(request, **kwargs)

        with patch.dict(os.environ, {'SEARCH_VARIANTS_JSON': json.dumps(config)}):
            variants = {name: {'environment': 'lab-filter-api', 'selection': 'default' if name == 'ranker-a' else 'explicit',
                'configuration_sha256': select({} if name == 'ranker-a' else {'X-Lab-Variant': name})[2]}
                for name in config['variants']}
            cases = [({}, ['demo-01', 'demo-02']),
                ({'category': ['footwear'], 'price_minor': {'lte': 6500}}, ['demo-01']),
                ({'price_minor': {'gte': 7900, 'lte': 7900}}, ['demo-02']),
                ({'category': ['home']}, []),
                ({'category': ['home', 'footwear'], 'colour': ['blue', 'black'],
                  'material': ['cotton'], 'price_minor': {'gte': 6500, 'lte': 7900}}, ['demo-01', 'demo-02'])]
            with patch.object(urllib.request, 'urlopen', side_effect=transport), redirect_stdout(io.StringIO()):
                for number, (filters, expected) in enumerate(cases):
                    row = {'query_id': 'filter-' + str(number), 'query': 'running shoes',
                           'country': 'GB', 'currency': 'GBP', 'filters': filters}
                    pair = evaluation_worker.run([row], 'lab-filter-api', 'lab-filter-api')[0]
                    multi = variant_capture_worker.run([row], variants)[0]
                    if 'error' in pair or 'error' in multi:
                        raise AssertionError({'paired': pair.get('error'), 'variants': multi.get('error')})
                    answers = [pair['baseline'], pair['candidate'], *multi['results'].values()]
                    if any(answer['ids'] != expected or answer['total'] != len(expected) for answer in answers):
                        raise AssertionError('Filter membership or total differs from the synthetic fixture.')
                    checks.append({'filters': filters, 'expected_ids': expected,
                                   'paired': 'passed', 'three_variants': 'passed'})
        return {'kind': 'search-filter-verification', 'backend': 'real local Elasticsearch',
                'api': 'current HTTP Handler; host-side TLS transport to the disposable index',
                'fixture_products': len(products), 'checks': checks,
                'limits': 'Host-run workers; no Argo deployment, relevance gate approval or capacity claim.'}
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
            thread.join()
        if created:
            elastic('/' + index, method='DELETE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Choose a new verification output path.')
    result = prove()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode())
    print(json.dumps({'checks': len(result['checks']), 'state': 'passed', 'output': str(args.output)}))


if __name__ == '__main__':
    main()
