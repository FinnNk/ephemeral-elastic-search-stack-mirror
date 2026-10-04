"""One bounded, order-stable public API query run inside the cluster."""
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


def traceparent():
    """Continue the control operation trace without exporting from the finite Job."""
    trace_id = os.environ.get('LAB_TRACE_ID', '')
    span_id = os.environ.get('LAB_SPAN_ID', '')
    if re.fullmatch('[0-9a-f]{32}', trace_id) and re.fullmatch('[0-9a-f]{16}', span_id) and \
            int(trace_id, 16) and int(span_id, 16):
        return '00-' + trace_id + '-' + span_id + '-01'
    return None


def request(name, row, pacer=None):
    filters = validate_filters(row.get('filters', {}))
    query = urllib.parse.urlencode({'q': row['query'], 'country': row['country'],
                                    'currency': row['currency'], 'filters': encode_filters(filters)})
    url = f'http://search.{name}.svc.cluster.local:8080/search?' + query
    headers = {'traceparent': parent} if (parent := traceparent()) else {}
    value = (pacer or Pacer()).fetch(url, headers)
    if (value.get('query'), value.get('country'), value.get('currency')) != (row['query'], row['country'], row['currency']):
        raise ValueError('Search API did not echo the frozen request.')
    if value.get('filters') != filters:
        raise ValueError('Search API did not echo the frozen filters.')
    ids = value['ids'][:10]
    if len(ids) != len(set(ids)) or len(ids) != min(value['total'], 10):
        raise ValueError('Search API returned an invalid ordered result list.')
    return {'ids': ids, 'total': value['total']}


def run(rows, baseline, candidate, worker_count=8, diagnostics=None):
    if not 1 <= worker_count <= 16:
        raise ValueError('Evaluator concurrency must be between 1 and 16.')
    pacers = {name: Pacer() for name in (baseline, candidate)}

    def one(row):
        try:
            return {'query_id': row['query_id'], 'baseline': request(baseline, row, pacers[baseline]),
                    'candidate': request(candidate, row, pacers[candidate])}
        except Exception as error:
            return {'query_id': row['query_id'], 'error': {'kind': type(error).__name__,
                    'detail': str(error)[:120]}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
        result = list(pool.map(one, rows))
    if diagnostics is not None:
        diagnostics.update({name: pacer.summary() for name, pacer in pacers.items()})
    return result


if __name__ == '__main__':
    rows = [json.loads(line) for line in Path('/input/queries.jsonl').read_text(encoding='utf-8').splitlines()]
    started = time.monotonic()
    pacing = {}
    result = run(rows, os.environ['BASELINE'], os.environ['CANDIDATE'], diagnostics=pacing)
    event = {'event': 'lab.job.completed', 'service': 'lab-comparison-worker',
             'operation': 'comparison.capture', 'job_name': os.environ.get('LAB_JOB_NAME'),
             'state': 'complete' if all('error' not in item for item in result) else 'incomplete',
             'query_count': len(rows), 'error_count': sum('error' in item for item in result),
             'pacing': pacing,
             'duration_ms': round((time.monotonic() - started) * 1000, 3)}
    for field in ('trace_id', 'span_id'):
        if os.environ.get('LAB_' + field.upper()):
            event[field] = os.environ['LAB_' + field.upper()]
    print(json.dumps(event, sort_keys=True), flush=True)
    print(json.dumps(result, separators=(',', ':')), flush=True)
