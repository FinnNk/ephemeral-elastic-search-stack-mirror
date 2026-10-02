"""Time real abstaining-model resolution batches; no synthetic latency model."""
import concurrent.futures
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.request


def run(spec):
    started = time.monotonic()
    with urllib.request.urlopen(spec['pack_url'], timeout=30) as reply:
        payload = reply.read()
    if hashlib.sha256(payload).hexdigest() != spec['pack_sha256']:
        raise ValueError('Judgement experiment pack differs.')
    pack = json.loads(gzip.decompress(payload))
    setup_seconds = time.monotonic() - started
    items = pack['pairs']
    batches = [items[i:i + 64] for i in range(0, len(items), 64)]

    def resolve(batch):
        data = json.dumps({'context': pack['context'], 'pairs': batch}).encode()
        request = urllib.request.Request(spec['url'] + '/v1/judgements:resolve', data=data,
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=10) as reply:
            value = json.load(reply)
        if value['model'] != pack['model'] or len(value['results']) != len(batch):
            raise ValueError('Judgement model/count differs.')
        return value['results']

    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=spec['concurrency']) as workers:
        outcomes = [value for batch in workers.map(resolve, batches) for value in batch]
    duration = time.monotonic() - started
    return {'kind': 'judgement-throughput-experiment', 'model': pack['model'],
        'pairs': len(items), 'batches': len(batches), 'concurrency': spec['concurrency'],
        'setup_seconds': setup_seconds, 'resolution_seconds': duration,
        'outcomes_sha256': hashlib.sha256(json.dumps(outcomes, sort_keys=True).encode()).hexdigest(),
        'labelled': sum(value['outcome'] == 'labelled' for value in outcomes),
        'unjudged': sum(value['outcome'] == 'unjudged' for value in outcomes),
        'errors': sum(value['outcome'] == 'inference_error' for value in outcomes)}


if __name__ == '__main__':
    print(json.dumps(run(json.loads(Path('/input/specification.json').read_bytes()))), flush=True)
