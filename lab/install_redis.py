"""Install one small shared, read-only Redis service seeded from paired releases."""
import argparse
import base64
import hashlib
import json
import secrets

from common import apply, k
from data_versions import PAIRS, canonical, verified_binding
from input_selection import DEFAULTS, fetch_manifest

IMAGE = ('redis:7.4.7-alpine@sha256:'
         '02f2cc4882f8bf87c79a220ac958f58c700bdec0dfb9b9ea61b62fb0e8f1bfcf')


def command(*values):
    """Encode a seed command for Redis's binary-safe pipe protocol."""
    parts = [str(value).encode() for value in values]
    return b'*' + str(len(parts)).encode() + b'\r\n' + b''.join(
        b'$' + str(len(value)).encode() + b'\r\n' + value + b'\r\n' for value in parts)


def seed():
    """Publish all small rewrite hashes; each value carries its catalogue identity."""
    result = b''
    for release, refs in DEFAULTS.items():
        product_sha = fetch_manifest('catalogue', refs['catalogue'])['content']['sha256']
        data = PAIRS[release]['rewrite']
        key = verified_binding(release, product_sha)['rewrite_redis_key']
        result += command('HSET', key, '__manifest', canonical(data).decode())
        for query, (target, decision) in data['rules'].items():
            result += command('HSET', key, query, canonical({'catalogue_sha256': product_sha,
                              'query': target, 'decision': decision}).decode())
    return result


def install():
    """Reconcile the owned Redis server; no PVC or per-environment process is needed."""
    payload = seed()
    existing = k('get', 'secret/lab-redis-loader', '-n', 'platform', '-o', 'json', '--ignore-not-found')
    password = (base64.b64decode(json.loads(existing.stdout)['data']['password']).decode()
                if existing.stdout.strip() else secrets.token_hex(24))
    # API clients can read only rewrite hashes. Only the seed loader can write them.
    acl = ('user default on nopass ~rewrite:* -@all +hget +ping +client|setinfo\n'
           'user loader on #' + hashlib.sha256(password.encode()).hexdigest() +
           ' ~rewrite:* -@all +hset +ping +echo\n')
    apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'lab-redis-loader',
        'namespace': 'platform'}, 'stringData': {'password': password, 'users.acl': acl}})
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'lab-redis-seed',
        'namespace': 'platform'}, 'binaryData': {'data.resp': base64.b64encode(payload).decode()}})
    spec = {'automountServiceAccountToken': False, 'securityContext': {'runAsUser': 999,
        'runAsGroup': 999, 'fsGroup': 999}, 'containers': [{'name': 'redis', 'image': IMAGE,
        'command': ['sh', '-ec', 'redis-server --aclfile /auth/users.acl --save "" --appendonly no '
            '--maxmemory 16mb --maxmemory-policy noeviction & pid=$!; '
            'trap "kill $pid" TERM INT; until redis-cli ping; do sleep 1; done; '
            'redis-cli --user loader --pipe < /seed/data.resp; touch /tmp/seed-ready; wait "$pid"'],
        'env': [{'name': 'REDISCLI_AUTH', 'valueFrom': {'secretKeyRef': {
                    'name': 'lab-redis-loader', 'key': 'password'}}}],
        'ports': [{'containerPort': 6379}], 'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'},
                    'limits': {'cpu': '250m', 'memory': '96Mi'}},
        'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
        'readinessProbe': {'exec': {'command': ['sh', '-ec',
            'test -f /tmp/seed-ready && REDISCLI_AUTH= redis-cli ping | grep PONG']}, 'periodSeconds': 2},
        'volumeMounts': [{'name': 'seed', 'mountPath': '/seed', 'readOnly': True},
                         {'name': 'auth', 'mountPath': '/auth', 'readOnly': True}]}],
        'volumes': [{'name': 'seed', 'configMap': {'name': 'lab-redis-seed'}},
                    {'name': 'auth', 'secret': {'secretName': 'lab-redis-loader', 'defaultMode': 292}}]}
    # The loader's authentication applies only to seed commands, not readiness.
    spec['containers'][0]['command'][2] = spec['containers'][0]['command'][2].replace(
        'until redis-cli ping', 'until REDISCLI_AUTH= redis-cli ping')
    apply({'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'lab-redis',
        'namespace': 'platform'}, 'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'},
        'selector': {'matchLabels': {'app': 'lab-redis'}}, 'template': {'metadata': {
            'labels': {'app': 'lab-redis'}, 'annotations': {'lab/seed-sha256': hashlib.sha256(payload).hexdigest()}},
            'spec': spec}}})
    apply({'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'lab-redis',
        'namespace': 'platform'}, 'spec': {'selector': {'app': 'lab-redis'}, 'ports': [{'port': 6379}]}})
    apply({'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': {
        'name': 'lab-redis', 'namespace': 'platform'}, 'spec': {'podSelector': {'matchLabels': {
            'app': 'lab-redis'}}, 'policyTypes': ['Ingress'], 'ingress': [{'from': [
                {'namespaceSelector': {'matchLabels': {'lab': 'search-spike'}}},
                {'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': 'lab-control'}}}],
                'ports': [{'port': 6379}]}]}})
    k('rollout', 'status', 'deployment/lab-redis', '-n', 'platform', '--timeout=180s')
    print('Shared Redis rewrite datasets ready; 32 MiB request, 96 MiB limit, no PVC.', flush=True)


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    install()
