"""Capture an explicitly selected synthetic query suite through two frozen APIs."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, 'data')
sys.path.insert(0, 'lab')
sys.path.insert(0, 'research/platform-spike')
from contracts import validate_envelope
from blob_config import settings
from compare_search import definition, immutable_blob
from evaluation_job import run as run_job


def capture(baseline_name, candidate_name, query_path, query_manifest_path,
            catalogue_manifest_path):
    query_bytes = Path(query_path).read_bytes()
    query_manifest = validate_envelope(json.loads(Path(query_manifest_path).read_bytes()))
    catalogue_manifest = validate_envelope(json.loads(Path(catalogue_manifest_path).read_bytes()))
    if query_manifest['kind'] != 'query-suite' or catalogue_manifest['kind'] != 'catalogue':
        raise ValueError('Select a query-suite and catalogue manifest.')
    if hashlib.sha256(query_bytes).hexdigest() != query_manifest['content']['sha256']:
        raise ValueError('Query bytes differ from the selected manifest.')
    queries = [json.loads(line) for line in query_bytes.splitlines()]
    if not queries or len(queries) != query_manifest['record_count'] or \
            len({row['query_id'] for row in queries}) != len(queries):
        raise ValueError('Query suite is empty, duplicated or incomplete.')
    first, second = definition(baseline_name), definition(candidate_name)
    for environment in (first, second):
        if environment['dataset_sha256'] != catalogue_manifest['content']['sha256']:
            raise ValueError('Selected catalogue differs from a frozen environment.')
    if first['engine'] != second['engine']:
        raise ValueError('Frozen environments use different Elasticsearch versions.')
    observations, execution = run_job(query_bytes, baseline_name, candidate_name)
    if len(observations) != len(queries):
        raise ValueError('Observation Job returned an incomplete query suite.')
    retained = []
    for query, response in zip(queries, observations):
        if response.get('query_id') != query['query_id'] or 'error' in response:
            raise ValueError('Observation Job returned an error or changed query order.')
        retained.append({'query_id': query['query_id'],
                         'request': {'query': query['query'], 'country': query['country'],
                                     'currency': query['currency'], 'filters': query.get('filters', {})},
                         'baseline': response['baseline'], 'candidate': response['candidate']})
    output = {'kind': 'search-observation-set', 'schema_version': 1,
              'baseline_fingerprint': first['fingerprint'],
              'candidate_fingerprint': second['fingerprint'],
              'catalogue_sha256': catalogue_manifest['content']['sha256'],
              'query_suite_sha256': query_manifest['content']['sha256'],
              'captured_at': datetime.now(timezone.utc).isoformat(),
              'request_adapter': 'search-api-v1', 'execution': execution,
              'errors': [], 'captured_depth': 10, 'observations': retained}
    payload = (json.dumps(output, sort_keys=True, separators=(',', ':')) + '\n').encode()
    sha = hashlib.sha256(payload).hexdigest()
    blob = immutable_blob(settings()[1], sha + '/observations.json', payload)
    return payload, {'sha256': sha, 'blob': blob, 'query_count': len(queries),
                     'baseline_fingerprint': first['fingerprint'],
                     'candidate_fingerprint': second['fingerprint']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-name', required=True)
    parser.add_argument('--candidate-name', required=True)
    parser.add_argument('--queries', required=True, type=Path)
    parser.add_argument('--query-manifest', required=True, type=Path)
    parser.add_argument('--catalogue-manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    payload, reference = capture(args.baseline_name, args.candidate_name, args.queries,
                                 args.query_manifest, args.catalogue_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(json.dumps(reference, sort_keys=True))


if __name__ == '__main__':
    main()
