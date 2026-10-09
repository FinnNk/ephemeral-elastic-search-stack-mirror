"""Deterministic dated subsets of the frozen demo; dates are simulation metadata."""
import gzip
import hashlib
import io
import json
from pathlib import Path

from contracts import canonical, rows, sha_file

DATES = ('2026-01-01', '2026-02-01', '2026-03-01')


def build(source, output, month):
    """Retain unchanged ESCI records and labels, simulating additions and removals."""
    source, output = Path(source), Path(output)
    if month not in (1, 2, 3):
        raise ValueError('Choose timeline month 1, 2 or 3.')
    products = sorted(rows(source / 'products.jsonl.gz'),
                      key=lambda row: hashlib.sha256(row['product_id'].encode()).hexdigest())
    # January: first 80%; February: first 90%; March: remove 10%, add final 5%.
    size = len(products)
    selected = (products[:size * 8 // 10] if month == 1 else products[:size * 9 // 10]
                if month == 2 else products[size // 10:size * 9 // 10] + products[size * 95 // 100:])
    ids = {row['product_id'] for row in selected}
    queries = list(rows(source / 'queries.jsonl'))
    labels = [row for row in rows(source / 'judgements.jsonl') if row['product_id'] in ids]
    release = f'esci-gb-demo-2026-{month:02}'
    compressed = io.BytesIO()
    # GzipFile fixes filename, timestamp and OS header across Python 3.12/3.13.
    with gzip.GzipFile(filename='', mode='wb', fileobj=compressed, mtime=0) as stream:
        stream.write(b''.join(canonical(row) for row in selected))
    payloads = {'products.jsonl.gz': compressed.getvalue(),
                'queries.jsonl': b''.join(canonical(row) for row in queries),
                'judgements.jsonl': b''.join(canonical(row) for row in labels)}
    manifest = {'release': release, 'count': len(selected), 'query_count': len(queries),
                'judgement_count': len(labels), 'country': 'GB', 'currency': 'GBP',
                'compression': 'gzip', 'effective_date': DATES[month-1],
                'producer': {'synthetic': True, 'name': 'esci-demo-timeline-v1',
                    'source_manifest_sha256': sha_file(source / 'manifest.json'),
                    'date_policy': 'simulated-months-v1', 'labels': 'unchanged-source-subset'},
                'sha256': {name: hashlib.sha256(content).hexdigest() for name, content in payloads.items()},
                'bytes': {name: len(content) for name, content in payloads.items()}}
    payloads['manifest.json'] = canonical(manifest)
    output.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        path = output / name
        if path.exists() and path.read_bytes() != payload:
            raise ValueError('Existing simulated data differs; use a new named release.')
        if not path.exists():
            path.write_bytes(payload)
    return manifest
