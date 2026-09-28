"""Sync retained lab credentials from Floci Key Vault into Kubernetes with ESO."""

import argparse
import base64
from contextlib import contextmanager
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request

from common import HELM, IN_CLUSTER, KUBE, ROOT, STATE, apply, guard, k, record, run


ESO_VERSION = '2.11.0'
ESO_NAMESPACE = 'lab-secrets'
STORE = 'lab-keyvault'
VAULT_URL = 'http://floci.platform.svc.cluster.local:4577/devstoreaccount1-keyvault'
REGISTRY_SOURCE = 'lab-registry-image-pull'
NEXUS_SOURCE = 'lab-nexus-image-pull'
STATIC = {
    ('argocd', 'delivery-state-repo'),
    ('argocd', 'gitea-state-repo'),
    ('argocd', 'spike-plugin-token'),
    ('lab-control', 'lab-control-gitea'),
    ('lab-control', 'lab-control-nexus'),
    ('platform', 'lab-s3-snapshot-client'),
    ('platform', 'spike-plugin-token'),
    ('platform', 'webhook-secret'),
}


def available():
    if IN_CLUSTER:
        return True
    return k('get', 'crd/externalsecrets.external-secrets.io', check=False).returncode == 0


def managed(namespace, name):
    if not available():
        return False
    if IN_CLUSTER:
        secret = read_secret(namespace, name)
        return bool(secret and any(owner.get('kind') == 'ExternalSecret'
                   for owner in secret['metadata'].get('ownerReferences', [])))
    return k('get', 'externalsecret/vault-' + name, '-n', namespace,
             check=False).returncode == 0


def source_name(namespace, name, key):
    if name == 'registry-read':
        return REGISTRY_SOURCE
    if name == 'nexus-read':
        return NEXUS_SOURCE
    result = re.sub('[^a-z0-9]+', '-', f'lab-{namespace}-{name}-{key}'.lower()).strip('-')
    if len(result) > 127:
        raise ValueError('Key Vault secret name is too long: ' + result)
    return result


def secret_store(namespace):
    apply({'apiVersion': 'external-secrets.io/v1', 'kind': 'SecretStore',
           'metadata': {'name': STORE, 'namespace': namespace},
           'spec': {'provider': {'webhook': {
               'url': VAULT_URL + '/secrets/{{ .remoteRef.key }}?api-version=7.4',
               'method': 'GET',
               'headers': {'Authorization': 'Bearer synthetic-local-lab'},
               'result': {'jsonPath': '$.value'},
           }}}})


def external_secret(namespace, name, keys, secret_type='Opaque', labels=None):
    secret_store(namespace)
    target = {'name': name, 'creationPolicy': 'Owner', 'deletionPolicy': 'Retain',
              'template': {'type': secret_type}}
    if labels:
        target['template']['metadata'] = {'labels': labels}
    apply({'apiVersion': 'external-secrets.io/v1', 'kind': 'ExternalSecret',
           'metadata': {'name': 'vault-' + name, 'namespace': namespace},
           'spec': {'refreshInterval': '1m', 'secretStoreRef': {'name': STORE,
               'kind': 'SecretStore'}, 'target': target,
               'data': [{'secretKey': key, 'remoteRef': {
                   'key': source_name(namespace, name, key)}} for key in keys]}})
    k('wait', '--for=condition=Ready', 'externalsecret/vault-' + name,
      '-n', namespace, '--timeout=90s')


def image_secret(namespace, name):
    """Report whether ESO already owns an image-pull Secret in this namespace."""
    if name not in ('registry-read', 'nexus-read'):
        raise ValueError('Unknown image-pull credential: ' + name)
    return managed(namespace, name)


def install():
    guard()
    result = run([HELM, 'upgrade', '--install', 'external-secrets', 'external-secrets',
                  '--repo', 'https://charts.external-secrets.io', '--version', ESO_VERSION,
                  '--namespace', ESO_NAMESPACE, '--create-namespace', '--wait',
                  '--timeout', '5m', '--kubeconfig', str(STATE / 'kubeconfig.yaml')])
    if not available():
        raise RuntimeError('External Secrets Operator CRDs are not available.')
    return result.stdout.strip()


@contextmanager
def floci_forward():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    log_path = STATE / 'keyvault-port-forward.log'
    with log_path.open('a', encoding='utf-8') as log:
        process = subprocess.Popen(KUBE + ['-n', 'platform', 'port-forward', 'svc/floci',
            f'{port}:4577', '--address', '127.0.0.1'], cwd=ROOT, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            for _ in range(50):
                if process.poll() is not None:
                    raise RuntimeError('Floci port forward stopped unexpectedly.')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=1):
                        yield f'http://127.0.0.1:{port}/devstoreaccount1-keyvault'
                        return
                except OSError:
                    time.sleep(0.1)
            raise TimeoutError('Floci port forward did not open.')
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def vault_request(base, name, method='GET', value=None):
    body = None if value is None else json.dumps({'value': value}).encode('utf-8')
    request = urllib.request.Request(base + '/secrets/' + name + '?api-version=7.4',
        data=body, method=method, headers={'Authorization': 'Bearer synthetic-local-lab',
                                            'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404 and method == 'GET':
            return None
        raise RuntimeError(f'Floci Key Vault {method} {name}: HTTP {error.code}') from None


def value_of(secret, key):
    return base64.b64decode(secret['data'][key], validate=True).decode('utf-8')


def read_secret(namespace, name):
    result = k('get', 'secret/' + name, '-n', namespace, '-o', 'json', check=False)
    return json.loads(result.stdout) if result.returncode == 0 else None


def source_secret(items, namespace, name):
    value = next((item for item in items if item['metadata']['namespace'] == namespace
                  and item['metadata']['name'] == name), None)
    if value is None:
        raise ValueError(f'Expected bootstrap Secret {namespace}/{name} is missing.')
    return value


def candidates(items):
    selected = []
    for secret in items:
        namespace = secret['metadata']['namespace']
        name = secret['metadata']['name']
        if ((namespace, name) in STATIC or
                (name == 'registry-read' and namespace == 'platform') or
                (name == 'registry-read' and namespace.startswith(('lab-', 'retail-', 'spike-'))) or
                (name == 'nexus-read' and namespace.startswith('lab-'))):
            selected.append(secret)
    return selected


def seed(base, name, value):
    existing = vault_request(base, name)
    if existing is None:
        vault_request(base, name, 'PUT', value)
        existing = vault_request(base, name)
    if existing['value'] != value:
        raise ValueError('Vault source differs from the bootstrap Secret: ' + name)


def migrate():
    """Adopt only named lab credentials; never copy generated ECK or user credentials."""
    guard()
    install()
    items = json.loads(k('get', 'secrets', '-A', '-o', 'json').stdout)['items']
    selected = candidates(items)
    # A single source feeds every namespace's image-pull Secret of each type.
    canonical = {
        REGISTRY_SOURCE: value_of(source_secret(items, 'platform', 'registry-read'),
                                  '.dockerconfigjson'),
        NEXUS_SOURCE: value_of(source_secret(items, 'lab-control', 'nexus-read'),
                               '.dockerconfigjson'),
    }
    sources = dict(canonical)
    for secret in selected:
        namespace = secret['metadata']['namespace']
        name = secret['metadata']['name']
        for key in secret['data']:
            remote = source_name(namespace, name, key)
            if remote not in sources:
                sources[remote] = value_of(secret, key)
    with floci_forward() as base:
        for name, value in sorted(sources.items()):
            seed(base, name, value)
    synced = []
    for secret in selected:
        namespace = secret['metadata']['namespace']
        name = secret['metadata']['name']
        labels = {key: value for key, value in secret['metadata'].get('labels', {}).items()
                  if key == 'argocd.argoproj.io/secret-type'}
        external_secret(namespace, name, sorted(secret['data']), secret['type'], labels)
        observed = read_secret(namespace, name)
        for key in secret['data']:
            expected = sources[source_name(namespace, name, key)]
            if value_of(observed, key) != expected:
                raise RuntimeError('Synced Secret differs from Key Vault: ' + namespace + '/' + name)
        synced.append(namespace + '/' + name)
    result = {'eso_chart': ESO_VERSION, 'vault_sources': len(sources),
              'synced_secrets': sorted(synced),
              'excluded': ['bootstrap accounts and runner registration',
                           'ECK and Argo CD generated material',
                           'per-environment Elasticsearch users',
                           'finite Job credentials']}
    record('keyvault-migration', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('migrate',))
    args = parser.parse_args()
    if args.command == 'migrate':
        print(json.dumps(migrate(), indent=2))


if __name__ == '__main__':
    main()
