"""Fresh bounded captures for transport/scheduling experiments, not load tests."""
import asyncio
import concurrent.futures
import hashlib
import json
import math
import random
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import httpx
from search_filters import encode_filters


def validate(value, row, variant, target):
    if any(value.get(key) != row[key] for key in ('query', 'country', 'currency')) or \
            value.get('filters') != row.get('filters', {}) or value.get('variant_id') != variant or \
            value.get('configuration_sha256') != target['configuration_sha256']:
        raise ValueError('Response does not echo the frozen request/configuration.')
    ids, total = value.get('ids'), value.get('total')
    if not isinstance(ids, list) or len(ids) > 20 or len(ids) != len(set(ids)) or \
            type(total) is not int or total < len(ids) or len(ids) != min(20, total):
        raise ValueError('Invalid ordered result list.')
    return {'variant_id': variant, 'configuration_sha256': target['configuration_sha256'],
            'ids': ids[:10], 'total': total}


def parameters(row, variant, target):
    params = {'q': row['query'], 'country': row['country'], 'currency': row['currency'],
              'filters': encode_filters(row.get('filters', {}))}
    headers = {'X-Lab-Traffic-Class': 'probe'}
    if target['selection'] == 'explicit':
        headers['X-Lab-Variant'] = variant
    return target['url'] + '/search?' + urllib.parse.urlencode(params), headers


def percentile(values, fraction):
    return sorted(values)[min(len(values) - 1, math.ceil(len(values) * fraction) - 1)] if values else None


class Recorder:
    def __init__(self):
        self.started = time.monotonic()
        self.events = []
        self.values = {}

    def retain(self, row, variant, value, started, attempts, error):
        self.events.append({'query_id': row['query_id'], 'variant': variant,
            'ms': round((time.monotonic() - started) * 1000, 3), 'attempts': attempts,
            'completed_ms': round((time.monotonic() - self.started) * 1000, 3), 'error': error})
        if value is not None:
            self.values[(row['query_id'], variant)] = value


def synchronous(rows, specification, recorder):
    variants = specification['variants']
    client = httpx.Client(timeout=10, trust_env=False,
        limits=httpx.Limits(max_connections=specification['limit'],
                           max_keepalive_connections=specification['limit']))

    def request(row, variant, target):
        url, headers = parameters(row, variant, target)
        started = time.monotonic()
        value, error = None, None
        for attempt in range(3):
            try:
                if specification['client'] == 'urllib':
                    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10) as response:
                        value = validate(json.load(response), row, variant, target)
                else:
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    value = validate(response.json(), row, variant, target)
                error = None
                break
            except Exception as failure:
                error = type(failure).__name__
                code = getattr(failure, 'code', getattr(getattr(failure, 'response', None), 'status_code', 0))
                transient = isinstance(failure, (urllib.error.URLError, TimeoutError, httpx.TransportError)) or code >= 500
                if not transient or (code and code < 500) or attempt == 2:
                    break
                time.sleep(.2 * (attempt + 1))
        recorder.retain(row, variant, value, started, attempt + 1, error)

    def query(row):
        for variant, target in variants.items():
            request(row, variant, target)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=specification['limit']) as workers:
            if specification['strategy'] == 'thread-query':
                list(workers.map(query, rows))
            else:
                work = [(row, variant, target) for row in rows for variant, target in variants.items()]
                list(workers.map(lambda item: request(*item), work))
    finally:
        client.close()


async def asynchronous(rows, specification, recorder):
    variants = specification['variants']
    ceiling = specification['limit']
    limit = min(8, ceiling) if specification['strategy'] == 'adaptive' else ceiling
    history = [{'completed': 0, 'limit': limit}]
    window = []
    references = {}
    async with httpx.AsyncClient(timeout=10, trust_env=False,
            limits=httpx.Limits(max_connections=ceiling, max_keepalive_connections=ceiling)) as client:
        async def request(row, variant, target):
            url, headers = parameters(row, variant, target)
            started = time.monotonic()
            value, error = None, None
            for attempt in range(3):
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    value = validate(response.json(), row, variant, target)
                    error = None
                    break
                except Exception as failure:
                    error = type(failure).__name__
                    code = getattr(getattr(failure, 'response', None), 'status_code', 0)
                    if not (isinstance(failure, httpx.TransportError) or code >= 500) or attempt == 2:
                        break
                    await asyncio.sleep(.2 * (attempt + 1))
            recorder.retain(row, variant, value, started, attempt + 1, error)
            return recorder.events[-1]

        if specification['strategy'] == 'async-query':
            semaphore = asyncio.Semaphore(ceiling)
            async def query(row):
                async with semaphore:
                    for variant, target in variants.items():
                        await request(row, variant, target)
            await asyncio.gather(*(query(row) for row in rows))
        else:
            iterator = iter((row, variant, target) for row in rows for variant, target in variants.items())
            pending = set()
            exhausted = False
            while pending or not exhausted:
                while not exhausted and len(pending) < limit:
                    item = next(iterator, None)
                    if item is None:
                        exhausted = True
                    else:
                        pending.add(asyncio.create_task(request(*item)))
                if not pending:
                    break
                completed, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                window.extend(task.result() for task in completed)
                if specification['strategy'] == 'adaptive' and len(window) >= 32:
                    inflation = False
                    for variant in variants:
                        samples = [event['ms'] for event in window if event['variant'] == variant and not event['error']]
                        if samples:
                            observed = statistics.median(samples)
                            reference = references.setdefault(variant, observed)
                            inflation |= observed > 1.5 * reference
                    failed = any(event['error'] or event['attempts'] > 1 for event in window)
                    limit = max(2, limit // 2) if failed or inflation else min(ceiling, limit + 2)
                    history.append({'completed': len(recorder.events), 'limit': limit,
                                    'reason': 'backoff' if failed or inflation else 'healthy'})
                    window = []
    return history


def capture(rows, specification):
    original_order = rows
    rows = list(rows)
    random.Random(specification.get('seed', 20261002)).shuffle(rows)
    recorder = Recorder()
    if specification['strategy'].startswith('thread-'):
        synchronous(rows, specification, recorder)
        history = [{'completed': 0, 'limit': specification['limit']}]
    else:
        history = asyncio.run(asynchronous(rows, specification, recorder))
    duration = time.monotonic() - recorder.started
    observations = []
    for row in original_order:
        results = {variant: recorder.values.get((row['query_id'], variant)) for variant in specification['variants']}
        observations.append({'query_id': row['query_id'], 'request': {key: row.get(key, {}) if key == 'filters' else row[key]
            for key in ('query', 'country', 'currency', 'filters')}, 'results': results})
    payload = json.dumps(observations, sort_keys=True, separators=(',', ':')).encode()
    return {'kind': 'evaluation-throughput-experiment', 'capture_seconds': round(duration, 6),
            'query_count': len(rows), 'request_count': len(recorder.events),
            'expected_requests': len(rows) * len(specification['variants']),
            'errors': sum(event['error'] is not None for event in recorder.events),
            'retries': sum(event['attempts'] - 1 for event in recorder.events),
            'latency_median_ms': statistics.median(event['ms'] for event in recorder.events),
            'request_p95_ms': percentile([event['ms'] for event in recorder.events], .95),
            'semantic_sha256': hashlib.sha256(payload).hexdigest(),
            'concurrency_history': history, 'events': recorder.events, 'observations': observations}


if __name__ == '__main__':
    started = datetime.now(timezone.utc).isoformat()
    rows = [json.loads(line) for line in Path('/input/queries.jsonl').read_bytes().splitlines()]
    spec = json.loads(Path('/input/specification.json').read_bytes())
    value = capture(rows, spec)
    value['worker_started_at'] = started
    print(json.dumps(value, separators=(',', ':')), flush=True)
