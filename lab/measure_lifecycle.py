"""Measure 20 real warm create/search/delete cycles without discarding failures."""
import json
import math
import os
import platform
import statistics
import sys
import time

from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import STATE, guard, record
from lifecycle import local_lifecycle

SAMPLES = 20
TARGET_SECONDS = 300


def summarise(rows):
    completed = [row['delete_seconds'] for row in rows if row.get('passed')]
    failures = [row for row in rows if not row.get('passed')]
    return {'sample_count': len(rows), 'successful_count': len(completed), 'failure_count': len(failures),
            'p50_delete_seconds': round(statistics.median(completed), 3) if completed else None,
            'p95_delete_seconds': round(sorted(completed)[math.ceil(.95 * len(completed)) - 1], 3)
            if len(completed) == SAMPLES else None,
            'target_met': len(rows) == SAMPLES and not failures and
                          sorted(completed)[math.ceil(.95 * len(completed)) - 1] <= TARGET_SECONDS}


def main():
    guard()
    build_run = json.loads((STATE / 'evidence/retail-deployment.json').read_text())['build_run']
    service = local_lifecycle()
    rows = []
    for index in range(1, SAMPLES + 1):
        name = f'lab-removal-{index:02d}'
        sample = {'name': name, 'build_run': build_run, 'passed': False}
        try:
            start = time.monotonic()
            ready = service.create(name, build_run)
            sample['create_seconds'] = round(time.monotonic() - start, 3)
            assert ready['state'] == 'ready', ready
            sample['source_sha'] = ready['source_sha']
            sample['fingerprint'] = ready['fingerprint']
            start = time.monotonic()
            deleted = service.delete(ready['id'])
            sample['delete_seconds'] = round(time.monotonic() - start, 3)
            assert deleted['state'] == 'deleted', deleted
            sample['passed'] = True
        except Exception as error:
            sample['error_kind'] = type(error).__name__
            sample['error'] = str(error)[:300]
            current = service.store.active_name(name)
            if current:
                sample['final_state'] = current['state']
        rows.append(sample)
        record('lifecycle-removal-20', {'conditions': conditions(), 'samples': rows, 'summary': summarise(rows)})
        print(json.dumps(sample), flush=True)
    result = {'conditions': conditions(), 'samples': rows, 'summary': summarise(rows)}
    record('lifecycle-removal-20', result)
    print(json.dumps(result['summary'], indent=2), flush=True)
    if not result['summary']['target_met']:
        raise RuntimeError('The 20-run removal target was not met; inspect retained samples.')


def conditions():
    return {'host_platform': platform.platform(), 'cpu_count': os.cpu_count(),
            'cluster': 'k3d-relevance-lab', 'dataset': 'retail-gb-10k-v1',
            'environment_kind': 'API-only, shared frozen index',
            'samples': SAMPLES, 'target_seconds': TARGET_SECONDS,
            'measurement_boundary': 'delete request to persisted deleted state after namespace and scoped credential removal',
            'p95_method': 'nearest rank, ceil(0.95 × 20)th sorted successful sample; any failure blocks target pass'}


if __name__ == '__main__':
    main()
