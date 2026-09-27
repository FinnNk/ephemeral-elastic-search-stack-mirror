"""Generate a second, small synthetic retail input pack independently."""

import argparse
import hashlib
import json
from pathlib import Path

from contracts import canonical

RELEASE = 'retail-gb-independent-example-v1'


def build(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    products = []
    for category, kind, price in (('home', 'desk lamp', 2400),
                                  ('sports', 'water bottle', 1200),
                                  ('garden', 'plant pot', 900)):
        for variant in range(4):
            products.append({'product_id': f'example-{len(products):03d}',
                             'title': f'North {kind} {variant + 1}',
                             'description': f'Synthetic {category} product.',
                             'category': category, 'price_minor': price + variant * 100,
                             'available': True, 'country': 'GB', 'currency': 'GBP'})
    queries = [{'query_id': f'example-q{index + 1}', 'query': phrase,
                'country': 'GB', 'currency': 'GBP'}
               for index, phrase in enumerate(('desk lamp', 'water bottle', 'plant pot'))]
    judgements = [{'query_id': query['query_id'],
                   'product_id': products[index * 4 + variant]['product_id'],
                   'grade': 3 if variant == 0 else 2}
                  for index, query in enumerate(queries) for variant in range(4)]
    payloads = {'products.jsonl': b''.join(canonical(row) for row in products),
                'queries.jsonl': b''.join(canonical(row) for row in queries),
                'judgements.jsonl': b''.join(canonical(row) for row in judgements)}
    manifest = {'release': RELEASE, 'count': len(products),
                'query_count': len(queries), 'judgement_count': len(judgements),
                'country': 'GB', 'currency': 'GBP', 'fixed_time': '2026-01-01T00:00:00Z',
                'sha256': {name: hashlib.sha256(value).hexdigest()
                           for name, value in payloads.items()},
                'assumptions': ['All inputs are synthetic.',
                                'Three departments have four variants each.',
                                'Rules-based positive grades are not exhaustive judgements.']}
    payloads['manifest.json'] = json.dumps(manifest, sort_keys=True, indent=2).encode() + b'\n'
    for name, payload in payloads.items():
        path = directory / name
        if path.exists() and path.read_bytes() != payload:
            raise ValueError('Existing frozen example differs: ' + str(path))
        if not path.exists():
            path.write_bytes(payload)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.lab/releases') / RELEASE)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
