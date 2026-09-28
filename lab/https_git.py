"""Move retained Argo CD Git sources to the lab's verified HTTPS ingress."""

import argparse
import base64
import json
import time

from common import KUBE, ROOT, guard, k, run
from https_ingress import INTERNAL_GITEA
from keyvault import floci_forward, source_name, vault_request


OLD = 'http://gitea-http.platform.svc.cluster.local:31800'
NEW = 'https://' + INTERNAL_GITEA
REPOSITORIES = {
    'gitea-state-repo': 'environment-state',
    'delivery-state-repo': 'delivery-state',
}


def repository_url(repo):
    return NEW + '/elastic-agent/' + repo + '.git'


def sync_repository_secrets():
    with floci_forward() as base:
        for secret, repo in REPOSITORIES.items():
            key = source_name('argocd', secret, 'url')
            vault_request(base, key, 'PUT', repository_url(repo))
    deadline = time.monotonic() + 120
    for secret, repo in REPOSITORIES.items():
        external = 'vault-' + secret
        k('annotate', 'externalsecret/' + external, '-n', 'argocd',
          'force-sync=' + str(int(time.time())), '--overwrite')
        while time.monotonic() < deadline:
            item = json.loads(k('get', 'secret/' + secret, '-n', 'argocd', '-o', 'json').stdout)
            current = base64.b64decode(item['data']['url']).decode('utf-8')
            if current == repository_url(repo):
                break
            time.sleep(2)
        else:
            raise TimeoutError('Vault-backed Argo CD repository URL did not reconcile: ' + secret)


def patch_live_sources():
    source = ROOT / 'research/platform-spike/applicationset.yaml'
    run(KUBE + ['apply', '-f', str(source)])
    k('patch', 'applicationset/spike-plugin', '-n', 'argocd', '--type=merge',
      '-p', json.dumps({'spec': {'template': {'spec': {'source': {
          'repoURL': repository_url('environment-state')}}}}}))
    applications = json.loads(k('get', 'applications', '-n', 'argocd', '-o', 'json').stdout)['items']
    updated = []
    for item in applications:
        name = item['metadata']['name']
        current = item['spec']['source']['repoURL']
        if not current.startswith(OLD + '/elastic-agent/'):
            if not current.startswith(NEW + '/elastic-agent/'):
                raise ValueError('Unexpected Argo CD Git source: ' + name)
            continue
        target = NEW + current[len(OLD):]
        k('patch', 'application/' + name, '-n', 'argocd', '--type=merge',
          '-p', json.dumps({'spec': {'source': {'repoURL': target}}}))
        updated.append(name)
    return updated


def verify():
    applications = json.loads(k('get', 'applications', '-n', 'argocd', '-o', 'json').stdout)['items']
    status = {}
    for item in applications:
        name = item['metadata']['name']
        url = item['spec']['source']['repoURL']
        if not url.startswith(NEW + '/elastic-agent/'):
            raise ValueError('Argo CD still uses a non-HTTPS Git source: ' + name)
        status[name] = (item.get('status', {}).get('sync', {}).get('status'),
                        item.get('status', {}).get('health', {}).get('status'))
    return status


def wait_healthy(timeout=180):
    k('annotate', 'applications', '-n', 'argocd', '--all',
      'argocd.argoproj.io/refresh=hard', '--overwrite')
    for name in ('search-environments', 'spike-plugin'):
        k('annotate', 'applicationset/' + name, '-n', 'argocd',
          'argocd.argoproj.io/application-set-refresh=true', '--overwrite')
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = verify()
        if status and all(value == ('Synced', 'Healthy') for value in status.values()):
            return status
        time.sleep(3)
    raise TimeoutError('Argo CD applications did not all become Synced and Healthy.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('migrate', 'verify'))
    args = parser.parse_args()
    guard()
    if args.action == 'migrate':
        k('rollout', 'restart', 'deployment/argocd-repo-server', '-n', 'argocd')
        k('rollout', 'status', 'deployment/argocd-repo-server', '-n', 'argocd',
          '--timeout=180s')
        sync_repository_secrets()
        print('Patched applications:', len(patch_live_sources()))
    status = wait_healthy() if args.action == 'migrate' else verify()
    healthy = sum(sync == 'Synced' and health == 'Healthy' for sync, health in status.values())
    print(json.dumps({'applications': len(status), 'synced_and_healthy': healthy}))


if __name__ == '__main__':
    main()
