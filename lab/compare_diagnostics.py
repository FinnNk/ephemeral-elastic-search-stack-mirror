"""Join final API results with opt-in stage and selected Elasticsearch evidence."""
import hashlib
import json
import sys

sys.path.insert(0, 'research/platform-spike')
from common import STATE, guard, record
from data_contract import elastic
from measure import search
from compare_search import definition, frozen_suite, immutable_blob, jaccard, rbo
from blob_config import settings

BASELINE = 'retail-baseline'
DIAGNOSTIC = 'retail-diagnostics'
REWRITE = 'retail-diagnostics-trainers'
DEPTH = 10


def functional_record(result, expected_id=None):
    assert result is not None
    ids = result['ids'][:DEPTH]
    assert len(ids) == len(set(ids)) == min(result['total'], DEPTH)
    record = {'ids': ids, 'total': result['total']}
    if expected_id is not None:
        details = result['diagnostics']
        assert details['schema_version'] == 1 and details['correlation_id'] == expected_id
        assert details['retrieved_ids'][:DEPTH] == ids
        assert set(details['stage_ms']) == {'elasticsearch', 'api_total'}
        record['diagnostics'] = {key: value for key, value in details.items() if key != 'stage_ms'}
    return record


def difference(left, right):
    first, second = left['ids'], right['ids']
    return {'equal_top_10': first == second, 'jaccard_at_10': round(jaccard(first, second), 6),
            'rbo_at_10_p_0_9': round(rbo(first, second), 6) if len(first) == len(second) == DEPTH else None,
            'added_ids': [pid for pid in second if pid not in first],
            'removed_ids': [pid for pid in first if pid not in second]}


def verdict(rows, errors):
    if errors or len(rows) != 51:
        return 'incomplete'
    return 'unchanged' if all(row['preservation']['equal_top_10'] for row in rows) else 'changed'


def whitebox_probe(index):
    # Direct component evidence is separate from the API's final-result verdict.
    body = {'size': 10, 'profile': True, 'query': {'multi_match': {
        'query': 'running shoes', 'fields': ['title^4', 'product_type^3', 'brand^2', 'description']}}}
    response = elastic('/' + index + '/_search', 'POST', body)
    mapping = elastic('/' + index + '/_mapping')
    query_types = sorted({query['type'] for shard in response['profile']['shards']
                          for search_phase in shard['searches'] for query in search_phase['query']})
    return {'scope': 'Selected direct Elasticsearch _profile probe; not an end-to-end relevance score.',
            'index': index, 'query': 'running shoes', 'hit_count': len(response['hits']['hits']),
            'query_types': query_types,
            'request_sha256': hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(),
            'mapping_sha256': hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest()}


def compare():
    guard()
    definitions = {name: definition(name) for name in (BASELINE, DIAGNOSTIC, REWRITE)}
    assert len({entry['dataset_sha256'] for entry in definitions.values()}) == 1
    assert len({entry['index'] for entry in definitions.values()}) == 1
    assert len({entry['engine'] for entry in definitions.values()}) == 1
    assert len({entry['image'] for entry in definitions.values()}) == 3
    suite, suite_bytes, suite_sha, manifest = frozen_suite()
    suite_blob = immutable_blob(settings()[1], suite_sha + '/query-suite.jsonl', suite_bytes)
    rows, timings, errors = [], [], []
    for row in suite:
        qid = row['query_id']
        try:
            baseline = search(BASELINE, row['query'])
            diagnostic = search(DIAGNOSTIC, row['query'], request_id=qid + '-diagnostic')
            rewrite = search(REWRITE, row['query'], request_id=qid + '-rewrite')
            for result in (baseline, diagnostic, rewrite):
                assert result is not None and result['query'] == row['query']
                assert (result['country'], result['currency']) == (row['country'], row['currency'])
            before = functional_record(baseline)
            middle = functional_record(diagnostic, qid + '-diagnostic')
            after = functional_record(rewrite, qid + '-rewrite')
            rows.append({'query_id': qid, 'query': row['query'],
                         'baseline': before, 'diagnostic': middle, 'rewrite': after,
                         'preservation': difference(before, middle),
                         'query_understanding': difference(middle, after)})
            timings.append({'query_id': qid,
                            'baseline_api_ms': baseline['elapsed_ms'],
                            'diagnostic_stage_ms': diagnostic['diagnostics']['stage_ms'],
                            'rewrite_stage_ms': rewrite['diagnostics']['stage_ms']})
        except (AssertionError, KeyError, RuntimeError, TimeoutError, TypeError, ValueError) as error:
            errors.append({'query_id': qid, 'kind': type(error).__name__})
    preservation = verdict(rows, errors)
    changed = [row['query_id'] for row in rows if not row['query_understanding']['equal_top_10']]
    zero_result_counts = {name: sum(row[name]['total'] == 0 for row in rows)
                          for name in ('baseline', 'diagnostic', 'rewrite')}
    complete = not errors and len(rows) == len(suite)
    if complete:
        assert preservation == 'unchanged'
        assert changed == ['q051']
        last = rows[-1]
        assert last['diagnostic']['diagnostics']['rewrite'] == 'none'
        assert last['rewrite']['diagnostics']['rewrite'] == 'trainers-to-running-shoes'
        assert last['diagnostic']['diagnostics']['elasticsearch_request_sha256'] != last['rewrite']['diagnostics']['elasticsearch_request_sha256']
    report = {'kind': 'correlated-search-comparison', 'complete': complete,
              'preservation_verdict': preservation, 'query_understanding_changed_ids': changed,
              'baseline_diagnostics': 'unavailable: deployed baseline predates schema v1',
              'definitions': definitions, 'suite_sha256': suite_sha, 'suite_blob': suite_blob,
              'original_query_sha256': manifest['sha256']['queries.jsonl'],
              'judgement_sha256': manifest['sha256']['judgements.jsonl'],
              'metric_scope': 'Top-ten public API results only; stage records explain changes but do not set the verdict.',
              'zero_result_counts': zero_result_counts, 'errors': errors, 'queries': rows}
    payload = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    location = immutable_blob('runs', digest + '/retail-diagnostic-comparison.json', payload)
    timing_payload = (json.dumps(timings, indent=2, sort_keys=True) + '\n').encode()
    timing_digest = hashlib.sha256(timing_payload).hexdigest()
    timing_blob = immutable_blob('runs', timing_digest + '/retail-diagnostic-timings.json', timing_payload)
    whitebox = whitebox_probe(definitions[BASELINE]['index'])
    whitebox_payload = (json.dumps(whitebox, indent=2, sort_keys=True) + '\n').encode()
    whitebox_digest = hashlib.sha256(whitebox_payload).hexdigest()
    whitebox_blob = immutable_blob('runs', whitebox_digest + '/retail-whitebox-profile.json', whitebox_payload)
    summary = {'report_sha256': digest, 'report_blob': location,
               'timing_blob': timing_blob, 'whitebox_blob': whitebox_blob,
               'suite_sha256': suite_sha, 'query_count': len(rows),
               'preservation_verdict': preservation, 'query_understanding_changed_ids': changed,
               'zero_result_counts': zero_result_counts, 'errors': errors,
               'fingerprints': {name: entry['fingerprint'] for name, entry in definitions.items()}}
    record('retail-diagnostic-comparison', summary)
    assert complete, 'Diagnostic comparison was incomplete'
    return summary


if __name__ == '__main__':
    print(json.dumps(compare(), indent=2))
