"""Freeze synthetic query/timestamp traffic and compile Gatling arrival schedules."""
import argparse
import csv
import hashlib
import io
import json
import math
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import STATE

ROOT = Path(__file__).with_name('traffic')
TRACE = ROOT / 'source-trace-v1.csv'
RECIPES = ROOT / 'recipes-v2.json'
QUERY_PATH = STATE / 'releases/retail-gb-10k-v1/queries.jsonl'
MILLION_TRACE = ROOT / 'source-trace-million-v1.csv'
MILLION_RECIPES = ROOT / 'recipes-million-v1.json'
MILLION_QUERIES = STATE / 'releases/retail-gb-1m-v1/queries.jsonl'
MILLION_TRACE_EXT = ROOT / 'source-trace-million-v2.csv'
MILLION_RECIPES_EXT = ROOT / 'recipes-million-v2.json'
OUTPUT = STATE / 'workloads'
FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def csv_bytes(fields, rows):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def freeze(path, payload):
    if path.exists() and path.read_bytes() != payload:
        raise ValueError(f'Frozen file differs: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(payload)


def generate_trace():
    queries = [json.loads(line) for line in QUERY_PATH.read_text(encoding='utf-8').splitlines()]
    assert len(queries) == 50 and all(row['country'] == 'GB' and row['currency'] == 'GBP' for row in queries)
    rng = random.Random(20260927)
    rows = []
    for second in range(600):
        intensity = 7 + 3 * math.sin(second * math.pi / 150) + (5 if second % 180 < 10 else 0)
        count = max(2, round(intensity))
        for slot in range(count):
            query = queries[rng.randrange(10) if rng.random() < .7 else rng.randrange(10, 50)]
            timestamp = FIXED_TIME + timedelta(milliseconds=second * 1000 + round((slot + .5) * 1000 / count))
            rows.append({'timestamp': timestamp.isoformat().replace('+00:00', 'Z'),
                         'query_id': query['query_id'], 'query': query['query']})
    payload = csv_bytes(['timestamp', 'query_id', 'query'], rows)
    freeze(TRACE, payload)
    manifest = {'kind': 'wholly synthetic traffic source', 'schema_version': 1,
                'trace_sha256': sha(payload), 'query_sha256': sha(QUERY_PATH.read_bytes()),
                'seed': 20260927, 'start': '2026-01-01T00:00:00Z', 'seconds': 600,
                'events': len(rows), 'country': 'GB', 'currency': 'GBP',
                'assumptions': ['70% of searches use ten head queries; 30% use forty tail queries',
                    'A sinusoidal intensity varies within the ten-minute synthetic window',
                    'Ten-second bursts recur every three minutes',
                    'Requests are evenly spaced within each source second']}
    freeze(ROOT / 'source-manifest-v1.json', (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode())
    return manifest


def generate_million_trace():
    queries = [json.loads(line) for line in MILLION_QUERIES.read_text(encoding='utf-8').splitlines()]
    assert len(queries) == 1000 and all(row['country'] == 'GB' and row['currency'] == 'GBP' for row in queries)
    rng = random.Random(20260928)
    rows = []
    for second in range(600):
        intensity = 7 + 3 * math.sin(second * math.pi / 150) + (5 if second % 180 < 10 else 0)
        count = max(2, round(intensity))
        for slot in range(count):
            query = queries[rng.randrange(50) if rng.random() < .7 else rng.randrange(50, 1000)]
            timestamp = FIXED_TIME + timedelta(milliseconds=second * 1000 + round((slot + .5) * 1000 / count))
            rows.append({'timestamp': timestamp.isoformat().replace('+00:00', 'Z'),
                         'query_id': query['query_id'], 'query': query['query']})
    payload = csv_bytes(['timestamp', 'query_id', 'query'], rows)
    freeze(MILLION_TRACE, payload)
    manifest = {'kind': 'wholly synthetic million-release traffic source', 'schema_version': 1,
                'trace_sha256': sha(payload), 'query_sha256': sha(MILLION_QUERIES.read_bytes()),
                'seed': 20260928, 'start': '2026-01-01T00:00:00Z', 'seconds': 600,
                'events': len(rows), 'country': 'GB', 'currency': 'GBP',
                'assumptions': ['70% of searches use fifty head queries; 30% use 950 tail queries',
                    'A sinusoidal intensity varies within the ten-minute synthetic window',
                    'Ten-second bursts recur every three minutes',
                    'Requests are evenly spaced within each source second']}
    freeze(ROOT / 'source-manifest-million-v1.json', (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode())
    return manifest


def generate_million_trace_extended():
    queries = [json.loads(line) for line in MILLION_QUERIES.read_text(encoding='utf-8').splitlines()]
    assert len(queries) == 1000
    rng = random.Random(20260929)
    rows = []
    for second in range(1800):
        intensity = 7 + 3 * math.sin(second * math.pi / 150) + (5 if second % 180 < 10 else 0)
        count = max(2, round(intensity))
        for slot in range(count):
            query = queries[rng.randrange(50) if rng.random() < .7 else rng.randrange(50, 1000)]
            timestamp = FIXED_TIME + timedelta(milliseconds=second * 1000 + round((slot + .5) * 1000 / count))
            rows.append({'timestamp': timestamp.isoformat().replace('+00:00', 'Z'),
                         'query_id': query['query_id'], 'query': query['query']})
    payload = csv_bytes(['timestamp', 'query_id', 'query'], rows)
    freeze(MILLION_TRACE_EXT, payload)
    manifest = {'kind': 'wholly synthetic extended million-release traffic source', 'schema_version': 2,
                'trace_sha256': sha(payload), 'query_sha256': sha(MILLION_QUERIES.read_bytes()),
                'seed': 20260929, 'start': '2026-01-01T00:00:00Z', 'seconds': 1800,
                'events': len(rows), 'country': 'GB', 'currency': 'GBP',
                'assumptions': ['70% of searches use fifty head queries; 30% use 950 tail queries',
                    'A sinusoidal intensity varies within the thirty-minute synthetic window',
                    'Ten-second bursts recur every three minutes',
                    'Requests are evenly spaced within each source second',
                    'Longer phase windows use distinct source seconds; they do not loop a short query block']}
    freeze(ROOT / 'source-manifest-million-v2.json', (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode())
    return manifest


def source_buckets(trace_path=TRACE):
    buckets = defaultdict(list)
    with trace_path.open(encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            moment = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
            second = int((moment - FIXED_TIME).total_seconds())
            buckets[second].append(row)
    return buckets


def phase_rate(phase, position, source_count):
    if 'rate' in phase:
        return phase['rate']
    if 'rate_start' in phase:
        fraction = position / max(1, phase['seconds'] - 1)
        return round(phase['rate_start'] + fraction * (phase['rate_end'] - phase['rate_start']))
    if 'rate_steps' in phase:
        step = min(len(phase['rate_steps']) - 1,
                   position * len(phase['rate_steps']) // phase['seconds'])
        return phase['rate_steps'][step]
    return max(1, round(source_count * phase['source_multiplier']))


def compile_profile(profile, release_id='retail-gb-10k-v1'):
    if release_id == 'retail-gb-1m-v1':
        trace_path, recipe_path, query_path = MILLION_TRACE_EXT, MILLION_RECIPES_EXT, MILLION_QUERIES
        source_manifest = ROOT / 'source-manifest-million-v2.json'
    elif release_id == 'retail-gb-10k-v1':
        trace_path, recipe_path, query_path = TRACE, RECIPES, QUERY_PATH
        source_manifest = ROOT / 'source-manifest-v1.json'
    else:
        raise ValueError('Unsupported frozen traffic release.')
    recipe_bytes = recipe_path.read_bytes()
    recipes = json.loads(recipe_bytes)
    if profile not in recipes['profiles']:
        raise ValueError('Unknown traffic profile.')
    trace_bytes = trace_path.read_bytes()
    manifest = json.loads(source_manifest.read_text(encoding='utf-8'))
    if sha(trace_bytes) != manifest['trace_sha256'] or sha(query_path.read_bytes()) != manifest['query_sha256']:
        raise ValueError('Source trace or frozen query release hash differs.')
    buckets = source_buckets(trace_path)
    schedule = []
    requests = defaultdict(list)
    offset = 0
    for phase in recipes['profiles'][profile]:
        name = phase['name']
        for position in range(phase['seconds']):
            source = buckets[phase['source_start'] + position]
            if not source:
                raise ValueError('Recipe source window has no synthetic requests.')
            count = phase_rate(phase, position, len(source))
            schedule.append({'phase': name, 'offset_second': offset, 'count': count})
            for slot in range(count):
                query = source[slot * len(source) // count]
                requests[name].append({'planned_ms': offset * 1000 + round((slot + .5) * 1000 / count),
                                       'query_id': query['query_id'], 'query': query['query']})
            offset += 1
    files = {'schedule.csv': csv_bytes(['phase', 'offset_second', 'count'], schedule)}
    for phase, rows in requests.items():
        files[phase + '.csv'] = csv_bytes(['planned_ms', 'query_id', 'query'], rows)
    identity = sha(json.dumps({'profile': profile, 'source_sha256': sha(trace_bytes),
        'recipe_sha256': sha(recipe_bytes), 'files': {name: sha(data) for name, data in files.items()}},
        sort_keys=True, separators=(',', ':')).encode())
    directory = OUTPUT / identity
    for name, payload in files.items():
        freeze(directory / name, payload)
    compiled = {'profile': profile, 'workload_sha256': identity, 'source_sha256': sha(trace_bytes),
                'recipe_sha256': sha(recipe_bytes), 'duration_seconds': offset,
                'phase_counts': {phase: len(rows) for phase, rows in requests.items()},
                'files': {name: sha(data) for name, data in files.items()},
                'directory': str(directory)}
    manifest_path = directory / 'manifest.json'
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding='utf-8'))
        # Older manifests recorded a host-specific absolute directory. The
        # workload identity and every content hash must still agree.
        if {key: value for key, value in previous.items() if key != 'directory'} != \
                {key: value for key, value in compiled.items() if key != 'directory'}:
            raise ValueError(f'Frozen workload manifest differs: {manifest_path}')
    else:
        portable = {**compiled, 'directory': 'workloads/' + identity}
        freeze(manifest_path, (json.dumps(portable, sort_keys=True, indent=2) + '\n').encode())
    return {**compiled, 'source_path': str(trace_path), 'recipe_path': str(recipe_path)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('generate', 'generate-million', 'generate-million-extended', 'compile'))
    parser.add_argument('--profile', default='probe')
    parser.add_argument('--release', default='retail-gb-10k-v1')
    args = parser.parse_args()
    print(json.dumps(generate_trace() if args.command == 'generate' else
                     generate_million_trace() if args.command == 'generate-million' else
                     generate_million_trace_extended() if args.command == 'generate-million-extended' else
                     compile_profile(args.profile, args.release), indent=2))
