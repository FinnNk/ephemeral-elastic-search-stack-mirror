"""Read-only verification of the migrated control Pod's service contracts."""

import json
import sys

sys.path[:0] = ['lab']

from common import STATE, guard
from data_contract import elastic
from gitea import api
from nexus import request
from lifecycle import Store


def main():
    guard()
    identity = api('/user')
    if identity['login'] != 'elastic-agent':
        raise ValueError('Unexpected Gitea runtime identity.')
    engine = elastic('/')['version']['number']
    if not engine:
        raise ValueError('Elasticsearch version is missing.')
    request('/service/rest/v1/status', identity='reader')
    store = Store(STATE / 'lifecycle.sqlite3')
    result = {'cluster': 'matched', 'gitea_identity': identity['login'],
              'elasticsearch_version': engine,
              'environment_records': len(store.all()),
              'comparison_records': len(store.all_comparisons()),
              'nexus': 'reachable'}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
