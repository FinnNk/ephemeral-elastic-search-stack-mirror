"""Package accepted model assessments with frozen inputs and measured coverage."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def package(folder, destination):
    frozen = json.loads((folder / 'frozen-inputs.json').read_text(encoding='utf-8'))
    inputs = json.loads((folder / 'judge-inputs.json').read_text(encoding='utf-8'))
    indexed = {(i['set'], i['query_id'], i['product']['product_id']): i for i in inputs}
    rows = [json.loads(line) for line in (folder / 'luna-labels.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(indexed) != len(rows) or set(indexed) != {(r['set'], r['query_id'], r['product_id']) for r in rows}:
        raise ValueError('Every selected input pair needs one assessment.')
    acceptance = {'reviewer': 'finnnk', 'decided_at': '2026-10-16',
        'reason': 'The owner explicitly authorises Luna-generated judgements for these additional sets and accepts them as-is; preserve model provenance and use them as advisory reference data.'}
    destination.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name, observations in frozen['sets'].items():
        labels = []
        for row in rows:
            if row['set'] != name:
                continue
            if row.get('model') != 'gpt-6-luna' or {'I': 0, 'C': 1, 'S': 2, 'E': 3}.get(row.get('label')) != row.get('grade'):
                raise ValueError('Invalid assessment model or ESCI grade.')
            item = indexed[name, row['query_id'], row['product_id']]
            labels.append({'query_id': row['query_id'], 'product_id': row['product_id'],
                'label': row['label'], 'grade': row['grade'], 'source': 'model', 'gate_eligible': False,
                'rationale': row['rationale'], 'provenance': {'kind': 'model', 'model': 'gpt-6-luna',
                    'rubric': 'esci-v1', 'catalogue_sha256': observations['catalogue_sha256'],
                    'query_suite_sha256': observations['query_suite_sha256'],
                    'input_sha256': sha(canonical(item)), 'acceptance': acceptance}})
        labels.sort(key=lambda r: (r['query_id'], r['product_id']))
        payload = b''.join(canonical(row) for row in labels)
        (destination / (name + '.jsonl')).write_bytes(payload)
        known = {(r['query_id'], r['product_id']) for r in labels}
        coverage = {}
        for side in ('baseline', 'candidate'):
            pairs = [(r['query_id'], p) for r in observations['observations'] for p in r['results'][side]['ids']]
            count = sum(pair in known for pair in pairs)
            fraction = count / len(pairs)
            if not .85 <= fraction < 1:
                raise ValueError('Coverage needs headroom above 80% and a retained gap.')
            coverage[side] = {'judged': count, 'returned': len(pairs), 'fraction': fraction}
        capture = gzip.compress(canonical(observations), mtime=0)
        (destination / (name + '-observations.json.gz')).write_bytes(capture)
        summary[name] = {'labels': len(labels), 'grades': dict(Counter(r['label'] for r in labels)),
                         'coverage': coverage, 'query_sha256': observations['query_suite_sha256'],
                         'judgement_sha256': sha(payload), 'observations_sha256': sha(capture)}
    compressed = gzip.compress(b''.join(canonical(item) for item in inputs), mtime=0)
    (destination / 'inputs.jsonl.gz').write_bytes(compressed)
    (destination / 'omitted-pairs.json').write_bytes(canonical(json.loads((folder / 'omitted-pairs.json').read_text(encoding='utf-8'))))
    manifest = {'kind': 'accepted-advisory-judgements', 'schema_version': 1, 'model': 'gpt-6-luna',
        'rubric': 'esci-v1', 'acceptance': acceptance, 'catalogue_sha256': observations['catalogue_sha256'],
        'inputs_sha256': sha(compressed), 'sampling': 'Per query, omit the lowest SHA-256(query_id + newline + product_id) in the shared pool, or one per side when pools do not intersect. Selection precedes judging and does not use ranks or relevance scores.',
        'sets': summary}
    (destination / 'manifest.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.inputs, args.destination)['sets'], indent=2))
