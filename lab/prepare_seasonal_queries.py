"""Prepare additional exploratory query suites without changing frozen defaults."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from common import ROOT, STATE
sys.path.insert(0, str(ROOT / 'data'))
from contracts import sha_file
from publish import publish

SETS = ('halloween', 'christmas', 'seasonal-controls')
RELEASES = ('esci-gb-demo-halloween-2026', 'esci-gb-demo-christmas-2026')


def retain(path, payload):
    """Create immutable demo inputs, refusing a different retained version."""
    if path.exists() and path.read_bytes() != payload:
        raise ValueError('Retained seasonal query input differs: ' + str(path))
    if not path.exists():
        path.write_bytes(payload)


def prepare(source, output, query_root, **options):
    """Combine frozen queries and demo sets, preserving original labels and products."""
    source, output, query_root = map(Path, (source, output, query_root))
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    product = 'products.jsonl.gz' if manifest.get('compression') == 'gzip' else 'products.jsonl'
    for name in (product, 'queries.jsonl', 'judgements.jsonl'):
        if sha_file(source / name) != manifest['sha256'][name]:
            raise ValueError('Frozen seasonal input differs: ' + name)
    payload = (source / 'queries.jsonl').read_bytes()
    if not payload.endswith(b'\n'):
        raise ValueError('Frozen query file must end with a newline.')
    original_count = len(payload.splitlines())
    sets = {}
    for name in SETS:
        extra = (query_root / (name + '.jsonl')).read_bytes()
        if not extra.endswith(b'\n'):
            raise ValueError('Demo query file must end with a newline.')
        sets[name] = {'queries': len(extra.splitlines()),
                      'sha256': hashlib.sha256(extra).hexdigest()}
        payload += extra
    output.mkdir(parents=True, exist_ok=True)
    retain(output / product, (source / product).read_bytes())
    retain(output / 'queries.jsonl', payload)
    retain(output / 'judgements.jsonl', (source / 'judgements.jsonl').read_bytes())
    refs = publish(output, output / 'manifests', 'seasonal-demo-queries-v1',
                   manifest['release'], provenance={
                       'synthetic': True, 'selection': 'gate',
                       'source_manifest_sha256': sha_file(source / 'manifest.json'),
                       'labels': 'unchanged-source-subset',
                       'extra_queries': 'curated-unlabelled-demo-queries',
                       'additional_query_sets': sets}, **options)
    return {'release': manifest['release'], 'base_queries': original_count,
            'query_count': original_count + sum(v['queries'] for v in sets.values()),
            'additional_query_sets': sets,
            'query_manifest_sha256': refs['query-suite']['manifest_sha256'],
            'judgement_manifest_sha256': refs['judgement-set']['manifest_sha256']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='Upload immutable inputs to the configured lab Blob store')
    args = parser.parse_args()
    options = {}
    if args.publish:
        from blob_config import settings, service
        options = {'blob_url': settings()[0], 'container': settings()[1], 'blob_service': service()}
    results = []
    for release in RELEASES:
        print('Preparing exploratory queries for ' + release, flush=True)
        results.append(prepare(STATE / 'releases' / release,
            STATE / 'seasonal-queries' / release,
            ROOT / 'lab/delivery/bootstrap/evaluation/queries', **options))
    path = STATE / 'seasonal-queries' / 'references.json'
    retain(path, (json.dumps(results, indent=2) + '\n').encode())
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
