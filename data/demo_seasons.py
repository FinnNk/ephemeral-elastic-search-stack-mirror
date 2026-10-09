"""Small Halloween/Christmas catalogues; event dates and membership are simulated."""
import gzip
import hashlib
import heapq
import io
import json
from pathlib import Path
import re

from contracts import canonical, rows, sha_file

SEASONS = {'halloween': ('2026-10-01', re.compile(r'\bhalloween\b', re.I)),
           'christmas': ('2026-12-01', re.compile(r'\b(christmas|xmas)\b', re.I))}
DEMO_QUERIES = ('seasonal decorations', 'party decorations', 'halloween decorations', 'christmas decorations')


def build_pair(full, base, output, themed_count=250, common_count=1000):
    """Select unchanged event products from full ESCI and share ordinary controls."""
    full, base, output = Path(full), Path(base), Path(output)
    provenance = {'synthetic': True, 'name': 'esci-demo-seasons-v1',
        'source_manifest_sha256': sha_file(full/'manifest.json'),
        'base_manifest_sha256': sha_file(base/'manifest.json'),
        'selection': 'title-event-terms-b-prefixed-product-ids-sha256-v1',
        'date_policy': 'simulated-events-v1', 'labels': 'unchanged-source-subset',
        'extra_queries': 'curated-unlabelled-demo-queries',
        'themed_count': themed_count, 'common_count': common_count}
    # Resume without scanning the full catalogue again. Verify every retained file.
    retained = {}
    for theme in SEASONS:
        folder = output/f'esci-gb-demo-{theme}-2026'
        if not (folder/'manifest.json').exists(): break
        manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if manifest['producer'] != {**provenance, 'theme': theme}:
            raise ValueError('Existing seasonal selection differs; use a new named release.')
        for name, digest in manifest['sha256'].items():
            if sha_file(folder/name) != digest:
                raise ValueError('Retained seasonal file differs: '+name)
        retained[theme] = manifest
    if len(retained) == len(SEASONS): return retained

    ordinary = [row for row in rows(base/'products.jsonl.gz')
                if not any(pattern.search(row['title']) for _date, pattern in SEASONS.values())]
    labels = list(rows(base/'judgements.jsonl'))
    labelled_ids = {row['product_id'] for row in labels}
    rank = lambda row: hashlib.sha256(row['product_id'].encode()).hexdigest()
    ordinary.sort(key=lambda row: (row['product_id'] not in labelled_ids, rank(row)))
    controls = ordinary[:common_count]
    if len(controls) != common_count: raise ValueError('Insufficient ordinary control products.')
    selected = {theme: [] for theme in SEASONS}
    matched = {theme: 0 for theme in SEASONS}
    # Keep only the bounded selection in memory. The byte prefilter avoids decoding
    # unrelated products; eligibility is determined from the decoded title only.
    with gzip.open(full/'products.jsonl.gz', 'rb') as stream:
        for line in stream:
            lower = line.lower()
            if not any(term in lower for term in (b'halloween', b'christmas', b'xmas')): continue
            row = json.loads(line)
            if not row['product_id'].startswith('B'): continue
            themes = [theme for theme, (_date, pattern) in SEASONS.items() if pattern.search(row['title'])]
            if len(themes) != 1: continue  # Keep the contrast unambiguous.
            theme = themes[0]; matched[theme] += 1
            item = (-int(rank(row), 16), row['product_id'], row)
            heapq.heappush(selected[theme], item)
            if len(selected[theme]) > themed_count: heapq.heappop(selected[theme])

    queries = list(rows(base/'queries.jsonl')) + [
        {'query_id': 'seasonal-demo-'+str(i), 'query': query, 'country': 'GB',
         'currency': 'GBP', 'filters': {}} for i, query in enumerate(DEMO_QUERIES)]
    result = {}
    for theme, (effective_date, _pattern) in SEASONS.items():
        if len(selected[theme]) != themed_count: raise ValueError('Insufficient '+theme+' products.')
        products = sorted(controls + [item[2] for item in selected[theme]], key=rank)
        ids = {row['product_id'] for row in products}
        retained_labels = [row for row in labels if row['product_id'] in ids]
        compressed = io.BytesIO()
        with gzip.GzipFile(filename='', mode='wb', fileobj=compressed, mtime=0) as stream:
            stream.write(b''.join(canonical(row) for row in products))
        payloads = {'products.jsonl.gz': compressed.getvalue(),
                    'queries.jsonl': b''.join(canonical(row) for row in queries),
                    'judgements.jsonl': b''.join(canonical(row) for row in retained_labels)}
        release = f'esci-gb-demo-{theme}-2026'
        manifest = {'release': release, 'count': len(products), 'query_count': len(queries),
            'judgement_count': len(retained_labels), 'country': 'GB', 'currency': 'GBP',
            'compression': 'gzip', 'effective_date': effective_date,
            'seasonal_match_count': matched[theme], 'producer': {**provenance, 'theme': theme},
            'sha256': {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()},
            'bytes': {name: len(payload) for name, payload in payloads.items()}}
        payloads['manifest.json'] = canonical(manifest)
        folder = output/release; folder.mkdir(parents=True, exist_ok=True)
        for name, payload in payloads.items():
            path = folder/name
            if path.exists() and path.read_bytes() != payload:
                raise ValueError('Existing seasonal bytes differ; use a new named release.')
            if not path.exists(): path.write_bytes(payload)
        result[theme] = manifest
    return result
