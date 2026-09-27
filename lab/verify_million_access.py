"""Check index-scoped read access and write blocks for million-scale instances."""
import base64
import json
import urllib.error

from common import STATE, k, record
from data_contract import elastic


def password(name):
    secret = json.loads(k('get', 'secret/search-access', '-n', name, '-o', 'json').stdout)
    return base64.b64decode(secret['data']['ES_PASSWORD']).decode()


def denied(user, path, method='GET', body=None):
    try:
        elastic(path, method, body, user=user, password=password(user))
        return False
    except urllib.error.HTTPError as error:
        return error.code == 403


def main():
    baseline = 'lab-million-baseline'
    candidate = 'lab-million-index'
    shared = 'retail-gb-1m-v1'
    dedicated = candidate + '-idx'
    evidence = {'shared_index': shared, 'candidate_index': dedicated,
                'shared_count': elastic('/' + shared + '/_count')['count'],
                'candidate_count': elastic('/' + dedicated + '/_count')['count'],
                'shared_write_block': elastic('/' + shared + '/_settings')[shared]['settings']['index']['blocks']['write'],
                'candidate_write_block': elastic('/' + dedicated + '/_settings')[dedicated]['settings']['index']['blocks']['write'],
                'baseline_cannot_read_candidate': denied(baseline, '/' + dedicated + '/_search', 'POST',
                                                         {'query': {'match_all': {}}}),
                'candidate_cannot_read_baseline': denied(candidate, '/' + shared + '/_search', 'POST',
                                                         {'query': {'match_all': {}}}),
                'candidate_cannot_write': denied(candidate, '/' + dedicated + '/_doc/forbidden', 'PUT',
                                                 {'title': 'forbidden'})}
    record('million-access', evidence)
    if evidence['shared_count'] != 1_000_000 or evidence['candidate_count'] != 1_000_000 or \
            evidence['shared_write_block'] != 'true' or evidence['candidate_write_block'] != 'true' or \
            not all(evidence[key] for key in ('baseline_cannot_read_candidate',
                                               'candidate_cannot_read_baseline', 'candidate_cannot_write')):
        raise ValueError('Million-product isolation check failed: ' + str(evidence))
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
