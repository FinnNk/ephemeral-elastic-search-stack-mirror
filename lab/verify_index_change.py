"""Exercise a dedicated mapping change beside a shared-index baseline."""
import base64
import json
import sys
import time
import urllib.error

sys.path.insert(0, 'research/platform-spike')
from common import STATE, k, record
from data_contract import elastic
from index_candidate import _existing, index_name, mapping_contract
from lifecycle import INDEX, INDEX_KIND, local_lifecycle

BASELINE = 'lab-index-baseline'
CANDIDATE = 'lab-index-candidate'


def check_access(name, candidate_index):
    secret = json.loads(k('get', 'secret/search-access', '-n', name, '-o', 'json').stdout)['data']
    password = base64.b64decode(secret['ES_PASSWORD']).decode()
    def denied(path, method='GET', body=None):
        try:
            elastic(path, method, body, user=name, password=password)
            return False
        except urllib.error.HTTPError as error:
            return error.code == 403
    return {'baseline_read_denied': denied('/' + INDEX + '/_search', 'POST', {'query': {'match_all': {}}}),
            'candidate_write_denied': denied('/' + candidate_index + '/_doc/forbidden', 'PUT', {'title': 'x'})}


def main():
    build_run = json.loads((STATE / 'evidence/retail-deployment.json').read_text())['build_run']
    service = local_lifecycle()
    evidence = {'build_run': build_run, 'baseline': BASELINE, 'candidate': CANDIDATE,
                'dataset': 'retail-gb-10k-v1', 'index_kind': INDEX_KIND}
    rows = []
    baseline_count = elastic('/' + INDEX + '/_count')['count']
    try:
        for name, kind in ((BASELINE, 'shared'), (CANDIDATE, INDEX_KIND)):
            started = time.monotonic()
            row = service.create(name, build_run, owner='elastic-agent', index_kind=kind)
            rows.append(row)
            evidence[name + '_create_seconds'] = round(time.monotonic() - started, 3)
            evidence[name + '_state'] = row['state']
            if row['state'] != 'ready':
                raise RuntimeError(name + ' failed: ' + str(row['error']))
        candidate_index = index_name(CANDIDATE)
        mapping, digest = mapping_contract()
        actual = elastic('/' + candidate_index)[candidate_index]
        frozen = elastic('/' + candidate_index + '/_settings')[candidate_index]['settings']['index']['blocks']['write']
        count = elastic('/' + candidate_index + '/_count')['count']
        evidence['candidate_index'] = candidate_index
        evidence['mapping_sha256'] = digest
        evidence['mapping_matches'] = actual['mappings'] == mapping['mappings']
        evidence['count'] = count
        evidence['write_blocked'] = frozen == 'true'
        evidence['access'] = check_access(CANDIDATE, candidate_index)
        evidence['result_comparison'] = service.compare(rows[0]['id'], rows[1]['id'], 'result-regression')
        evidence['relevance_comparison'] = service.compare(rows[0]['id'], rows[1]['id'], 'relevance')
        for mode in ('result_comparison', 'relevance_comparison'):
            row = evidence[mode]
            evidence[mode] = {'state': row['state'], 'verdict': row['verdict'],
                              'report_sha256': row['report_sha256'], 'report_blob': row['report_blob'],
                              'summary': row['summary']}
        assert evidence['mapping_matches'] and evidence['write_blocked'] and count == baseline_count == 10000
        assert all(evidence['access'].values())
        assert all(evidence[mode]['state'] == 'complete' for mode in ('result_comparison', 'relevance_comparison'))
    finally:
        for row in reversed(rows):
            started = time.monotonic()
            deleted = service.delete(row['id'])
            evidence[row['name'] + '_delete_seconds'] = round(time.monotonic() - started, 3)
            evidence[row['name'] + '_final_state'] = deleted['state']
        evidence['candidate_index_removed'] = _existing(index_name(CANDIDATE)) is None
        evidence['baseline_count_unchanged'] = elastic('/' + INDEX + '/_count')['count'] == baseline_count
        evidence['baseline_write_blocked'] = elastic('/' + INDEX + '/_settings')[INDEX]['settings']['index']['blocks']['write'] == 'true'
        record('index-change-live', evidence)
        print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
