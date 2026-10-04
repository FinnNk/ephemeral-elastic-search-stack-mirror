"""Capture every named variant through the public Search API in a finite Job."""

import concurrent.futures
import json
import os
import re
import time
import urllib.parse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'search-app'))
from search_filters import encode_filters, validate_filters
from adaptive_pacing import Pacer


def request(variant, target, row, pacer=None):
    filters = validate_filters(row.get('filters', {}))
    query = urllib.parse.urlencode({'q': row['query'], 'country': row['country'],
                                    'currency': row['currency'], 'filters': encode_filters(filters)})
    url = f"http://search.{target['environment']}.svc.cluster.local:8080/search?{query}"
    headers = {'X-Lab-Traffic-Class': 'probe'}
    trace_id, span_id = os.environ.get('LAB_TRACE_ID', ''), os.environ.get('LAB_SPAN_ID', '')
    if re.fullmatch('[0-9a-f]{32}', trace_id) and re.fullmatch('[0-9a-f]{16}', span_id) and \
            int(trace_id, 16) and int(span_id, 16):
        headers['traceparent'] = f'00-{trace_id}-{span_id}-01'
    if target['selection'] == 'explicit':
        headers['X-Lab-Variant'] = variant
    value = (pacer or Pacer()).fetch(url, headers)
    if (value.get('query'), value.get('country'), value.get('currency')) != (
            row['query'], row['country'], row['currency']):
        raise ValueError('Search API did not echo the frozen request.')
    if value.get('filters') != filters:
        raise ValueError('Search API did not echo the frozen filters.')
    ids = value.get('ids')
    if value.get('variant_id') != variant or \
            value.get('configuration_sha256') != target['configuration_sha256']:
        raise ValueError('Search API served another variant or configuration.')
    if not isinstance(ids, list) or len(ids) > 20 or len(ids) != len(set(ids)) or \
            type(value.get('total')) is not int or value['total'] < len(ids):
        raise ValueError('Search API returned an invalid result list.')
    return {'variant_id': variant, 'configuration_sha256': target['configuration_sha256'],
            'ids': ids[:10], 'total': value['total']}


def run(rows, variants, worker_count=8, diagnostics=None):
    if not 1 <= worker_count <= 16:
        raise ValueError('Capture concurrency must be between 1 and 16.')

    pacers = {target['environment']: Pacer() for target in variants.values()}

    def one(row):
        try:
            return {'query_id': row['query_id'], 'results': {
                variant: request(variant, target, row, pacers[target['environment']])
                for variant, target in variants.items()}}
        except Exception as error:
            return {'query_id': row['query_id'], 'error': {
                'kind': type(error).__name__, 'detail': str(error)[:120]}}

    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as workers:
        result = list(workers.map(one, rows))
    if diagnostics is not None:
        diagnostics.update({name: pacer.summary() for name, pacer in pacers.items()})
    return result


if __name__ == '__main__':
    rows = [json.loads(line) for line in Path('/input/queries.jsonl').read_text(encoding='utf-8').splitlines()]
    variants = json.loads(Path('/input/variants.json').read_text(encoding='utf-8'))
    started = time.monotonic()
    pacing = {}
    result = run(rows, variants, diagnostics=pacing)
    print(json.dumps({'event': 'lab.job.completed', 'service': 'lab-variant-capture-worker',
                      'state': 'complete' if all('error' not in row for row in result) else 'incomplete',
                      'query_count': len(rows), 'variant_count': len(variants),
                      'pacing': pacing,
                      'duration_ms': round((time.monotonic() - started) * 1000, 3)},
                     sort_keys=True), flush=True)
    print(json.dumps(result, separators=(',', ':')), flush=True)
