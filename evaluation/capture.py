"""Capture an explicitly selected synthetic query suite across frozen variants."""

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
from evaluation_job import run_variants


def capture(variant_set_path, query_path, query_manifest_path, catalogue_manifest_path):
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
    variant_set_bytes = Path(variant_set_path).read_bytes()
    variant_set = json.loads(variant_set_bytes)
    variants = variant_set.get('variants')
    if variant_set.get('kind') != 'search-variant-set' or \
            variant_set.get('schema_version') != 1 or not isinstance(variants, dict) or \
            len(variants) < 2 or variant_set.get('default_variant') not in variants or \
            variant_set.get('baseline_variant') not in variants:
        raise ValueError('Select at least two frozen variants and one default and baseline.')
    engines = set()
    for name, target in variants.items():
        if target.get('selection') not in ('default', 'explicit') or \
                not isinstance(target.get('configuration_sha256'), str) or \
                len(target['configuration_sha256']) != 64:
            raise ValueError('Variant selection and configuration hash are required.')
        environment = definition(target['environment'])
        if environment['fingerprint'] != target.get('environment_fingerprint'):
            raise ValueError('Variant environment differs from its frozen definition.')
        if environment['dataset_sha256'] != catalogue_manifest['content']['sha256']:
            raise ValueError('Selected catalogue differs from a frozen environment.')
        engines.add(environment['engine'])
    if len(engines) != 1:
        raise ValueError('Frozen environments use different Elasticsearch versions.')
    observations, execution = run_variants(query_bytes, variants)
    if len(observations) != len(queries):
        raise ValueError('Observation Job returned an incomplete query suite.')
    retained = []
    for query, response in zip(queries, observations):
        if response.get('query_id') != query['query_id'] or 'error' in response or \
                set(response.get('results', {})) != set(variants):
            raise ValueError('Observation Job returned an error or changed query order.')
        retained.append({'query_id': query['query_id'],
                         'request': {'query': query['query'], 'country': query['country'],
                                     'currency': query['currency'], 'filters': query.get('filters', {})},
                         'results': response['results']})
    output = {'kind': 'search-variant-observation-set', 'schema_version': 1,
              'default_variant': variant_set['default_variant'],
              'baseline_variant': variant_set['baseline_variant'],
              'variants': {name: {key: target[key] for key in
                            ('environment_fingerprint', 'configuration_sha256')}
                           for name, target in variants.items()},
              'variant_set_sha256': hashlib.sha256(variant_set_bytes).hexdigest(),
              'catalogue_sha256': catalogue_manifest['content']['sha256'],
              'query_suite_sha256': query_manifest['content']['sha256'],
              'captured_at': datetime.now(timezone.utc).isoformat(),
              'request_adapter': 'search-api-variant-v1', 'execution': execution,
              'errors': [], 'captured_depth': 10, 'observations': retained}
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from offline import validate_observations
    validate_observations(output)
    payload = (json.dumps(output, sort_keys=True, separators=(',', ':')) + '\n').encode()
    sha = hashlib.sha256(payload).hexdigest()
    blob = immutable_blob(settings()[1], sha + '/observations.json', payload)
    return payload, {'sha256': sha, 'blob': blob, 'query_count': len(queries),
                     'default_variant': output['default_variant'],
                     'baseline_variant': output['baseline_variant'],
                     'variants': output['variants']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant-set', required=True, type=Path)
    parser.add_argument('--queries', required=True, type=Path)
    parser.add_argument('--query-manifest', required=True, type=Path)
    parser.add_argument('--catalogue-manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    payload, reference = capture(args.variant_set, args.queries,
                                 args.query_manifest, args.catalogue_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(json.dumps(reference, sort_keys=True))


if __name__ == '__main__':
    main()
