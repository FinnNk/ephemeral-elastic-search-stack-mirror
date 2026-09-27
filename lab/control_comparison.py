"""Compare two ready control-plane instances through their public search APIs."""
import hashlib
import json
import sys

sys.path.insert(0, 'research/platform-spike')
from compare_search import definition, frozen_suite, immutable_blob, jaccard, rbo, response
from evaluate_relevance import frozen_judgements, score

MODES = ('result-regression', 'relevance')


def evaluate_pair(baseline, candidate, mode):
    if mode not in MODES:
        raise ValueError('Comparison mode must be result-regression or relevance.')
    if baseline['state'] != 'ready' or candidate['state'] != 'ready':
        raise ValueError('Both environments must be ready.')
    first = definition(baseline['name'])
    second = definition(candidate['name'])
    if first['fingerprint'] != baseline['fingerprint'] or second['fingerprint'] != candidate['fingerprint']:
        raise ValueError('A deployed environment no longer matches its runtime record.')
    if first['dataset_sha256'] != second['dataset_sha256']:
        raise ValueError('Environments use different product releases.')
    if first['engine'] != second['engine']:
        raise ValueError('Environments use different Elasticsearch versions.')
    release_id = baseline.get('release_id') or 'retail-gb-10k-v1'
    if release_id != (candidate.get('release_id') or 'retail-gb-10k-v1'):
        raise ValueError('Environments use different frozen releases.')
    full_suite, suite_bytes, full_suite_sha, manifest = frozen_suite(release_id)
    if mode == 'relevance':
        pooled = release_id == 'retail-gb-1m-v1'
        suite, judgements, pool_manifest = frozen_judgements(release_id, pooled=pooled)
        suite_sha = manifest['sha256']['queries.jsonl']
        suite_blob = 'datasets/' + release_id + '/queries.jsonl'
    else:
        suite = full_suite
        judgements = None
        suite_sha = full_suite_sha
        suite_blob = immutable_blob('datasets', suite_sha + '/query-suite.jsonl', suite_bytes)
    results = []
    errors = []
    zero_counts = {'baseline': 0, 'candidate': 0}
    if suite:
        for side, environment in (('baseline', baseline), ('candidate', candidate)):
            try:
                response(environment['name'], suite[0])
            except (AssertionError, KeyError, RuntimeError, TimeoutError, TypeError, ValueError) as error:
                errors.append({'query_id': suite[0]['query_id'], 'side': side,
                               'kind': type(error).__name__, 'detail': str(error)[:120],
                               'stage': 'response preflight'})
    for query in suite if not errors else ():
        try:
            left = response(baseline['name'], query)
            right = response(candidate['name'], query)
            zero_counts['baseline'] += left['total'] == 0
            zero_counts['candidate'] += right['total'] == 0
            ids_a, ids_b = left['ids'], right['ids']
            results.append({'query_id': query['query_id'], 'query': query['query'],
                            'baseline': left, 'candidate': right,
                            'equal_top_10': ids_a == ids_b,
                            'jaccard_at_10': round(jaccard(ids_a, ids_b), 6),
                            'rbo_at_10_p_0_9': round(rbo(ids_a, ids_b), 6)
                            if len(ids_a) == len(ids_b) == 10 else None})
        except (AssertionError, KeyError, RuntimeError, TimeoutError, TypeError, ValueError) as error:
            errors.append({'query_id': query['query_id'], 'kind': type(error).__name__,
                           'detail': str(error)[:120]})
    complete = not errors and len(results) == len(suite)
    changed = [row['query_id'] for row in results if not row['equal_top_10']]
    if not complete:
        verdict = 'incomplete'
    elif mode == 'result-regression':
        verdict = 'unchanged' if not changed else 'changed'
    else:
        verdict = 'measured'
    metrics = None
    if mode == 'relevance' and complete:
        metrics = {side: score(judgements, {row['query_id']: row[side]['ids'] for row in results})
                   for side in ('baseline', 'candidate')}
    report = {'kind': 'controlled-api-comparison', 'mode': mode, 'complete': complete, 'verdict': verdict,
              'baseline': {'runtime_id': baseline['id'], 'source_sha': baseline['source_sha'], **first},
              'candidate': {'runtime_id': candidate['id'], 'source_sha': candidate['source_sha'], **second},
              'suite_sha256': suite_sha, 'suite_blob': suite_blob,
              'judgement_sha256': pool_manifest['sha256']['judgements.jsonl'] if mode == 'relevance' else None,
              'judgement_pool': pool_manifest.get('judgement_pool') if mode == 'relevance' else None,
              'judgement_usage': ('Symmetric frozen synthetic E/S/C/I pool from baseline and both candidates; '
                                  'future results may be unjudged.'
                                  if release_id != 'retail-gb-10k-v1' else
                                  'Incomplete positive-only synthetic labels; unjudged products are unknown.')
              if mode == 'relevance' else 'Not used for result preservation.',
              'query_count': len(suite), 'completed_query_count': len(results), 'zero_result_counts': zero_counts,
              'changed_query_ids': changed, 'metrics': metrics, 'errors': errors, 'queries': results}
    payload = (json.dumps(report, sort_keys=True, indent=2) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    location = immutable_blob('runs', digest + '/controlled-comparison.json', payload)
    return {'report_sha256': digest, 'report_blob': location, 'mode': mode, 'complete': complete,
            'verdict': verdict, 'query_count': len(suite), 'completed_query_count': len(results),
            'changed_query_ids': changed, 'zero_result_counts': zero_counts, 'metrics': metrics, 'errors': errors}
