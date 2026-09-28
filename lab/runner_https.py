"""Update retained Gitea runner registrations and the delivery Git source URL."""

import argparse
import json

from common import guard, k
from delivery_provider import SOURCE, endpoint
from gitea import api
from https_git import NEW


OLD_RUNNER = 'http://gitea.localhost:31800'
RUNNERS = ('build-runner', 'delivery-runner')


def address(name):
    result = k('exec', '-n', 'platform', 'deployment/' + name, '-c', 'runner',
               '--', 'cat', '/data/.runner')
    return json.loads(result.stdout)['address']


def migrate():
    guard()
    for name in RUNNERS:
        current = address(name)
        if current not in (OLD_RUNNER, NEW):
            raise ValueError('Unexpected retained runner address: ' + name)
        if current == OLD_RUNNER:
            k('exec', '-n', 'platform', 'deployment/' + name, '-c', 'runner',
              '--', 'sed', '-i', 's#http://gitea[.]localhost:31800#' + NEW + '#',
              '/data/.runner')
        if address(name) != NEW:
            raise RuntimeError('Runner registration address did not change: ' + name)
        k('rollout', 'restart', 'deployment/' + name, '-n', 'platform')
        k('rollout', 'status', 'deployment/' + name, '-n', 'platform', '--timeout=180s')
    api(endpoint(SOURCE, '/actions/variables/SOURCE_BASE_URL'), 'PUT', {'value': NEW})
    return {name: address(name) for name in RUNNERS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('migrate', 'verify'))
    args = parser.parse_args()
    result = migrate() if args.action == 'migrate' else {name: address(name) for name in RUNNERS}
    if any(value != NEW for value in result.values()):
        raise RuntimeError('A Gitea runner still uses the old HTTP address.')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
