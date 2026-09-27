"""Probe live API namespace, RBAC and Elasticsearch index boundaries."""
import json

from common import k, record
from data_contract import elastic
from verify_million_access import denied, password

BASELINE = 'lab-concurrency-baseline'
API = 'lab-concurrency-api'
INDEX = 'lab-concurrency-index'
SHARED = 'retail-gb-1m-v1'
DEDICATED = INDEX + '-idx'


def probe(namespace, target):
    address = 'http://search.' + target + '.svc.cluster.local:8080/health'
    code = ('import urllib.request; '
            'urllib.request.urlopen(' + repr(address) + ', timeout=3).read()')
    return k('exec', 'deployment/search' if namespace != 'platform' else 'pod/search-probe',
             '-n', namespace, '--', 'python', '-c', code, check=False).returncode == 0


def main():
    evidence = {
        'release': SHARED,
        'baseline_and_api_share_index': elastic('/' + SHARED + '/_count')['count'] == 1_000_000,
        'dedicated_count': elastic('/' + DEDICATED + '/_count')['count'],
        'baseline_cannot_read_dedicated': denied(BASELINE, '/' + DEDICATED + '/_search', 'POST',
                                                  {'query': {'match_all': {}}}),
        'dedicated_cannot_read_shared': denied(INDEX, '/' + SHARED + '/_search', 'POST',
                                                {'query': {'match_all': {}}}),
        'dedicated_cannot_write': denied(INDEX, '/' + DEDICATED + '/_doc/forbidden', 'PUT',
                                          {'title': 'forbidden'}),
        'baseline_can_read_shared': elastic('/' + SHARED + '/_count', user=BASELINE,
                                             password=password(BASELINE))['count'] == 1_000_000,
        'dedicated_can_read_own': elastic('/' + DEDICATED + '/_count', user=INDEX,
                                          password=password(INDEX))['count'] == 1_000_000,
        'baseline_cannot_reach_dedicated_api': not probe(BASELINE, INDEX),
        'platform_can_reach_dedicated_api': probe('platform', INDEX),
        'api_pod_has_no_service_account_token': k('exec', 'deployment/search', '-n', API, '--',
            'test', '-e', '/var/run/secrets/kubernetes.io/serviceaccount/token', check=False).returncode != 0,
        'default_sa_cannot_get_peer_secrets': k('auth', 'can-i', 'get', 'secrets', '-n', INDEX,
            '--as=system:serviceaccount:' + BASELINE + ':default', check=False).stdout.strip() == 'no',
    }
    record('concurrency-isolation', evidence)
    print(json.dumps(evidence, indent=2))
    assert evidence['dedicated_count'] == 1_000_000 and all(value for key, value in evidence.items()
        if key not in ('release', 'dedicated_count')), evidence


if __name__ == '__main__':
    main()
