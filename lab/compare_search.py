"""Compare two pinned environments through their public search APIs."""
from catalogue import DEFAULT_RELEASE, RELEASES
import hashlib
import json
from pathlib import Path

from common import ROOT, STATE, guard, k, record
from azure.core.exceptions import ResourceExistsError
from blob_config import service, settings
from environments import REPO
from search_probe import search

BASELINE = 'retail-baseline'
CANDIDATE = 'retail-candidate'
DEPTH = 10
RBO_P = .9


def jaccard(first, second):
    left, right = set(first), set(second)
    return len(left & right) / len(left | right) if left or right else 1.0


def rbo(first, second, persistence=RBO_P, depth=DEPTH):
    """Finite, extrapolated RBO at depth 10 for complete result lists."""
    if first == second:
        return 1.0
    assert len(first) in (0, depth) and len(second) in (0, depth)
    weighted = 0.0
    overlap_at_depth = 0.0
    for rank in range(1, depth + 1):
        overlap_at_depth = len(set(first[:rank]) & set(second[:rank])) / rank
        weighted += (1 - persistence) * overlap_at_depth * persistence ** (rank - 1)
    return weighted + overlap_at_depth * persistence ** depth


def definition(name):
    if name.startswith('lab-delivery-'):
        resource = json.loads(k('get', 'configmap/frozen-definition', '-n', name, '-o', 'json').stdout)
        entry = json.loads(resource['data']['definition.json'])
    else:
        entry = json.loads((REPO / 'environments' / (name + '.json')).read_text())
    fields = {key: value for key, value in entry.items() if key not in ('fingerprint', 'environment')}
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    assert entry['fingerprint'] == digest and entry['environment'] == name
    app = json.loads(k('get', 'application/' + name, '-n', 'argocd', '-o', 'json').stdout)
    assert app['status']['sync']['status'] == 'Synced'
    assert app['status']['health']['status'] == 'Healthy'
    deployment = json.loads(k('get', 'deployment/search', '-n', name, '-o', 'json').stdout)
    container = deployment['spec']['template']['spec']['containers'][0]
    assert container['image'] == entry['image']
    assert next(env['value'] for env in container['env'] if env['name'] == 'ES_INDEX') == entry['index']
    return entry


def frozen_suite(release_id=DEFAULT_RELEASE):
    release = STATE / 'releases' / release_id
    original = (release / 'queries.jsonl').read_bytes()
    manifest = json.loads((release / 'manifest.json').read_text())
    assert hashlib.sha256(original).hexdigest() == manifest['sha256']['queries.jsonl']
    payload = original
    rows = [json.loads(line) for line in payload.splitlines()]
    assert len(rows) == manifest['query_count']
    assert len({row['query_id'] for row in rows}) == len(rows)
    return rows, payload, hashlib.sha256(payload).hexdigest(), manifest


def immutable_blob(container, name, payload):
    account = service()
    try:
        account.create_container(container)
    except ResourceExistsError:
        pass
    blob = account.get_blob_client(container, name)
    try:
        blob.upload_blob(payload, overwrite=False)
    except ResourceExistsError:
        pass
    assert blob.download_blob().readall() == payload
    return container + '/' + name


def response(name, row):
    result = search(name, row['query'], filters=row.get('filters', {}),
                    country=row['country'], currency=row['currency'])
    assert result is not None, f'{name} did not return {row["query_id"]}'
    assert result['query'] == row['query']
    assert result['filters'] == row.get('filters', {}), 'Search API did not echo the frozen filters.'
    assert (result['country'], result['currency']) == (row['country'], row['currency'])
    ids = result['ids'][:DEPTH]
    assert len(ids) == len(set(ids))
    assert len(ids) == min(result['total'], DEPTH)
    return {'ids': ids, 'total': result['total']}


def compare():
    guard()
    baseline = definition(BASELINE)
    candidate = definition(CANDIDATE)
    assert baseline['dataset_sha256'] == candidate['dataset_sha256']
    assert baseline['index'] == candidate['index']
    assert baseline['engine'] == candidate['engine']
    assert baseline['image'] != candidate['image']
    rows, suite_bytes, suite_sha, manifest = frozen_suite()
    suite_blob = immutable_blob(settings()[1], suite_sha + '/query-suite.jsonl', suite_bytes)
    results = []
    for row in rows:
        left = response(BASELINE, row)
        right = response(CANDIDATE, row)
        results.append({'query_id': row['query_id'], 'query': row['query'],
            'baseline': left, 'candidate': right,
            'equal_top_10': left['ids'] == right['ids'],
            'jaccard_at_10': round(jaccard(left['ids'], right['ids']), 6),
            'rbo_at_10_p_0_9': round(rbo(left['ids'], right['ids']), 6)})
    changed = [row['query_id'] for row in results if not row['equal_top_10']]
    report = {
        'kind': 'black-box-result-comparison', 'complete': True,
        'baseline': baseline, 'candidate': candidate,
        'suite_sha256': suite_sha, 'suite_blob': suite_blob,
        'query_count': len(rows), 'original_query_sha256': manifest['sha256']['queries.jsonl'],
        'judgement_sha256': manifest['sha256']['judgements.jsonl'],
        'judgement_usage': 'Not used for this result-preservation check.',
        'metrics': {'depth': DEPTH, 'rbo_persistence': RBO_P,
                    'changed_query_ids': changed, 'unchanged_count': len(rows) - len(changed)},
        'queries': results,
    }
    payload = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    location = immutable_blob('runs', digest + '/retail-blackbox-comparison.json', payload)
    summary = {'report_sha256': digest, 'report_blob': location,
        'suite_sha256': suite_sha, 'suite_blob': suite_blob,
        'query_count': len(rows), 'changed_query_ids': changed,
        'unchanged_count': len(rows) - len(changed),
        'baseline_fingerprint': baseline['fingerprint'],
        'candidate_fingerprint': candidate['fingerprint']}
    record('retail-comparison', summary)
    return summary


if __name__ == '__main__':
    print(json.dumps(compare(), indent=2))
