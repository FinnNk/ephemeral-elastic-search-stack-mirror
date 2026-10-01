"""Compare two ready control-plane instances through their public search APIs."""
import hashlib
import json
from datetime import datetime, timezone

from compare_search import definition, immutable_blob, jaccard, rbo, response
from blob_config import settings
from evaluate_relevance import query_ndcg, score
from search_probe import search
from input_selection import select

MODES = ('result-regression', 'relevance')
SCOPES = ('quick', 'full')


def evaluate_pair(baseline, candidate, mode, scope='full', query_manifest_sha=None,
                  judgement_manifest_sha=None):
    if mode not in MODES:
        raise ValueError('Comparison mode must be result-regression or relevance.')
    if scope not in SCOPES:
        raise ValueError('Comparison scope must be quick or full.')
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
    release_id = baseline['release_id']
    selected = select(release_id, first['dataset_sha256'], query_manifest_sha,
                      judgement_manifest_sha, relevance=mode == 'relevance')
    suite = selected['queries']
    judgements = selected.get('judgements')
    if scope == 'quick':
        suite = suite[:50]
    if judgements is not None:
        selected_ids = {row['query_id'] for row in suite}
        judgements = [row for row in judgements if row['query_id'] in selected_ids]
    suite_bytes = b''.join((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode()
                           for row in suite)
    suite_sha = hashlib.sha256(suite_bytes).hexdigest()
    suite_blob = immutable_blob(settings()[1], suite_sha + '/query-suite.jsonl', suite_bytes)
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
    if not errors:
        from evaluation_job import run as run_job
        try:
            observations, execution = run_job(suite_bytes, baseline['name'], candidate['name'])
        except (AssertionError, KeyError, RuntimeError, TimeoutError, TypeError, ValueError) as error:
            observations, execution = [], {'execution': 'in-cluster evaluator Job', 'error': type(error).__name__}
            errors.append({'kind': type(error).__name__, 'detail': str(error)[:120], 'stage': 'evaluation job'})
    else:
        observations, execution = [], {'execution': 'preflight only'}
    request_by_id = {row['query_id']: row for row in suite}
    retained_observations = []
    for item in observations:
        request = request_by_id[item['query_id']]
        entry = {'query_id': item['query_id'],
                 'request': {'query': request['query'], 'country': request['country'],
                             'currency': request['currency'], 'filters': request.get('filters', {})}}
        if 'error' in item:
            entry['error'] = item['error']
        else:
            entry['baseline'] = item.get('baseline')
            entry['candidate'] = item.get('candidate')
        retained_observations.append(entry)
    by_query = {row['query_id']: row for row in observations}
    for query in suite if not errors else ():
        try:
            observation = by_query[query['query_id']]
            if 'error' in observation:
                errors.append({'query_id': query['query_id'], **observation['error']})
                continue
            left, right = observation['baseline'], observation['candidate']
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
        graded = {}
        for judgement in judgements:
            graded.setdefault(judgement['query_id'], set()).add(judgement['product_id'])
        per_query = {side: query_ndcg(judgements, {row['query_id']: row[side]['ids'] for row in results})
                     for side in ('baseline', 'candidate')}
        for row in results:
            qid = row['query_id']
            for side in ('baseline', 'candidate'):
                ids = row[side]['ids']
                row[side]['unjudged_top_10_ids'] = [pid for pid in ids if pid not in graded.get(qid, set())]
                row[side]['judged_top_10_count'] = len(ids) - len(row[side]['unjudged_top_10_ids'])
                row[side]['ndcg_at_10'] = per_query[side].get(qid, 0.0)
            row['ndcg_delta_at_10'] = round(row['candidate']['ndcg_at_10'] - row['baseline']['ndcg_at_10'], 6)
    coverage = None
    if mode == 'relevance' and complete:
        coverage = {side: {'judged': sum(row[side]['judged_top_10_count'] for row in results),
                           'returned': sum(len(row[side]['ids']) for row in results)}
                    for side in ('baseline', 'candidate')}
        for value in coverage.values():
            value['fraction'] = round(value['judged'] / value['returned'], 6) if value['returned'] else None
    coverage_status = ('insufficient' if coverage and any(
        value['fraction'] is None or value['fraction'] < 0.8 for value in coverage.values())
        else 'reported' if coverage else None)
    # A small selected diagnostic replay explains differences without changing the
    # black-box verdict or being counted as a latency measurement.
    if complete:
        changed_rows = [row for row in results if not row['equal_top_10']]
        if mode == 'relevance':
            changed_rows.sort(key=lambda row: row['ndcg_delta_at_10'])
        for row in changed_rows[:10]:
            for side, environment in (('baseline', baseline), ('candidate', candidate)):
                try:
                    answer = search(environment['name'], row['query'],
                                    request_id=row['query_id'] + '-' + side,
                                    filters=request_by_id[row['query_id']].get('filters', {}),
                                    country=request_by_id[row['query_id']]['country'],
                                    currency=request_by_id[row['query_id']]['currency'])
                    if answer and answer.get('ids', [])[:10] == row[side]['ids'] and \
                            answer.get('filters') == request_by_id[row['query_id']].get('filters', {}):
                        detail = answer.get('diagnostics')
                        if detail:
                            row[side]['diagnostics'] = {key: value for key, value in detail.items()
                                                        if key != 'stage_ms'}
                except (RuntimeError, TimeoutError, ValueError):
                    pass
    stable_execution = {key: value for key, value in execution.items() if key not in ('seconds', 'job_name')}
    observation_set = {'kind': 'search-observation-set', 'schema_version': 1,
                       'baseline_fingerprint': first['fingerprint'],
                       'candidate_fingerprint': second['fingerprint'],
                       'catalogue_sha256': first['dataset_sha256'],
                       'query_suite_sha256': selected['query_manifest']['content']['sha256'],
                       'captured_depth': 10,
                       'captured_at': datetime.now(timezone.utc).isoformat(),
                       'request_adapter': 'search-api-v1', 'execution': stable_execution,
                       'errors': errors, 'observations': retained_observations}
    observation_payload = (json.dumps(observation_set, sort_keys=True, separators=(',', ':')) + '\n').encode()
    observation_sha = hashlib.sha256(observation_payload).hexdigest()
    observation_blob = immutable_blob('runs',
        'observation-set/' + observation_sha + '/observations.json', observation_payload)
    report = {'kind': 'controlled-api-comparison', 'mode': mode, 'scope': scope,
              'complete': complete, 'verdict': verdict, 'execution': stable_execution,
              'baseline': {'runtime_id': baseline['id'], 'source_sha': baseline['source_sha'], **first},
              'candidate': {'runtime_id': candidate['id'], 'source_sha': candidate['source_sha'], **second},
              'suite_sha256': suite_sha, 'suite_blob': suite_blob,
              'query_manifest_sha256': selected['query_manifest_sha256'],
              'observation_sha256': observation_sha, 'observation_blob': observation_blob,
              'judgement_sha256': selected['judgement_manifest']['content']['sha256']
              if mode == 'relevance' else None,
              'judgement_manifest_sha256': selected['judgement_manifest_sha256']
              if mode == 'relevance' else None,
              'judgement_provenance': selected['judgement_manifest']['producer']
              if mode == 'relevance' else None,
              'judgement_coverage': coverage,
              'judgement_coverage_status': coverage_status,
              'judgement_usage': ('Selected synthetic labels; unjudged products remain unknown.'
                                  if mode == 'relevance' else 'Not used for result preservation.'),
              'query_count': len(suite), 'completed_query_count': len(results), 'zero_result_counts': zero_counts,
              'changed_query_ids': changed, 'metrics': metrics, 'errors': errors, 'queries': results}
    payload = (json.dumps(report, sort_keys=True, indent=2) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    location = immutable_blob('runs', digest + '/controlled-comparison.json', payload)
    return {'report_sha256': digest, 'report_blob': location, 'mode': mode, 'complete': complete,
            'observation_sha256': observation_sha, 'observation_blob': observation_blob,
            'verdict': verdict, 'scope': scope, 'execution': execution,
            'query_count': len(suite), 'completed_query_count': len(results),
            'changed_query_ids': changed, 'zero_result_counts': zero_counts,
            'query_manifest_sha256': selected['query_manifest_sha256'],
            'judgement_manifest_sha256': selected.get('judgement_manifest_sha256'),
            'metrics': metrics, 'judgement_coverage': coverage,
            'judgement_coverage_status': coverage_status, 'errors': errors}
