"""One bounded, order-stable public API query run inside the cluster."""
import concurrent.futures
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def traceparent():
    """Continue the control operation trace without exporting from the finite Job."""
    trace_id = os.environ.get('LAB_TRACE_ID', '')
    span_id = os.environ.get('LAB_SPAN_ID', '')
    if re.fullmatch('[0-9a-f]{32}', trace_id) and re.fullmatch('[0-9a-f]{16}', span_id) and \
            int(trace_id, 16) and int(span_id, 16):
        return '00-' + trace_id + '-' + span_id + '-01'
    return None


def request(name, row):
    query = urllib.parse.urlencode({'q': row['query'], 'country': row['country'],
                                    'currency': row['currency']})
    url = f'http://search.{name}.svc.cluster.local:8080/search?' + query
    for attempt in range(3):
        try:
            headers = {'traceparent': parent} if (parent := traceparent()) else {}
            call = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(call, timeout=10) as reply:
                value = json.load(reply)
            break
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == 2:
                raise
            time.sleep(0.2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(0.2 * (attempt + 1))
    if (value.get('query'), value.get('country'), value.get('currency')) != (row['query'], row['country'], row['currency']):
        raise ValueError('Search API did not echo the frozen request.')
    ids = value['ids'][:10]
    if len(ids) != len(set(ids)) or len(ids) != min(value['total'], 10):
        raise ValueError('Search API returned an invalid ordered result list.')
    return {'ids': ids, 'total': value['total']}


def run(rows, baseline, candidate, worker_count=8):
    if not 1 <= worker_count <= 16:
        raise ValueError('Evaluator concurrency must be between 1 and 16.')
    def one(row):
        try:
            return {'query_id': row['query_id'], 'baseline': request(baseline, row),
                    'candidate': request(candidate, row)}
        except Exception as error:
            return {'query_id': row['query_id'], 'error': {'kind': type(error).__name__,
                    'detail': str(error)[:120]}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
        return list(pool.map(one, rows))


if __name__ == '__main__':
    rows = [json.loads(line) for line in Path('/input/queries.jsonl').read_text(encoding='utf-8').splitlines()]
    started = time.monotonic()
    result = run(rows, os.environ['BASELINE'], os.environ['CANDIDATE'])
    event = {'event': 'lab.job.completed', 'service': 'lab-comparison-worker',
             'operation': 'comparison.capture', 'job_name': os.environ.get('LAB_JOB_NAME'),
             'state': 'complete' if all('error' not in item for item in result) else 'incomplete',
             'query_count': len(rows), 'error_count': sum('error' in item for item in result),
             'duration_ms': round((time.monotonic() - started) * 1000, 3)}
    for field in ('trace_id', 'span_id'):
        if os.environ.get('LAB_' + field.upper()):
            event[field] = os.environ['LAB_' + field.upper()]
    print(json.dumps(event, sort_keys=True), flush=True)
    print(json.dumps(result, separators=(',', ':')), flush=True)
