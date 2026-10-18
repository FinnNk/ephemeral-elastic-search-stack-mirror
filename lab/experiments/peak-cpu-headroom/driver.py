"""Replay frozen peak queries as diagnostic probe traffic, never as gate evidence."""
import concurrent.futures
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

from delivery_operations import Operations


def replay(config):
    rows = list(csv.DictReader(Path(config['fixture']).open(encoding='utf-8')))
    count = config['seconds'] * config['rate']
    if len(rows) < count:
        raise ValueError('The frozen fixture is shorter than the diagnostic window.')
    results, futures, drift = [], [], []
    start = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()

    def fetch(index, row):
        began = time.monotonic()
        params = {key: row[key] for key in ('country', 'currency', 'filters')}
        params['q'] = row['query']
        try:
            request = urllib.request.Request(config['url'] + '/search?' + urllib.parse.urlencode(params),
                                             headers={'X-Lab-Traffic-Class': 'probe'})
            with urllib.request.urlopen(request, timeout=10) as response:
                body = json.load(response)
                status = response.status
            return {'index': index, 'query_id': row['query_id'], 'status': status,
                    'client_ms': (time.monotonic() - began) * 1000,
                    'api_ms': body.get('elapsed_ms'),
                    'ids_sha256': hashlib.sha256(json.dumps(body['ids']).encode()).hexdigest()}
        except Exception as error:
            return {'index': index, 'query_id': row['query_id'], 'status': type(error).__name__,
                    'client_ms': (time.monotonic() - began) * 1000}

    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        for index, row in enumerate(rows[:count]):
            if index % (config['rate'] * 5) == 0 and Operations().active():
                raise RuntimeError('Delivery work started; diagnostic load stopped.')
            due = start + index / config['rate']
            time.sleep(max(0, due - time.monotonic()))
            drift.append((time.monotonic() - due) * 1000)
            futures.append(pool.submit(fetch, index, row))
            if index and index % (config['rate'] * 60) == 0:
                print(json.dumps({'progress_seconds': index // config['rate'],
                                  'planned_seconds': config['seconds']}), flush=True)
        results = [future.result() for future in futures]
    directory = Path(config['directory'])
    directory.mkdir(parents=True, exist_ok=True)
    payload = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in results)
    (directory / (config['label'] + '-requests.jsonl')).write_text(payload, encoding='utf-8')
    values = sorted(row['client_ms'] for row in results)
    quantile = lambda fraction: values[math.ceil(len(values) * fraction) - 1]
    summary = {'kind': 'diagnostic-replay', 'label': config['label'],
               'started_at': started_at, 'ended_at': datetime.now(timezone.utc).isoformat(),
               'count': len(results), 'failed': sum(row['status'] != 200 for row in results),
               'p50_ms': quantile(.5), 'p95_ms': quantile(.95), 'p99_ms': quantile(.99),
               'over800': sum(v > 800 for v in values), 'over1200': sum(v > 1200 for v in values),
               'arrival_drift_p95_ms': sorted(drift)[math.ceil(len(drift) * .95) - 1],
               'responses_sha256': hashlib.sha256(payload.encode()).hexdigest(),
               'result_order_sha256': hashlib.sha256(json.dumps(
                   [r.get('ids_sha256') for r in results]).encode()).hexdigest(),
               'request_file': str(directory / (config['label'] + '-requests.jsonl'))}
    (directory / (config['label'] + '-summary.json')).write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'summary': summary}), flush=True)
    return summary


if __name__ == '__main__':
    replay(json.loads(sys.argv[1]))
