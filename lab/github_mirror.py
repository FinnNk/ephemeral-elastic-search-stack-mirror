"""Install GitHub App authentication and configure native Gitea push mirrors."""
import argparse
import json
from pathlib import Path
import re

import yaml

from common import HELM, STATE, guard, k, run
from gitea import api
from keyvault import external_secret, floci_forward, seed, source_name

NAMESPACE = 'platform'
SECRET = 'gitea-github-app'
BIN = '/opt/github-mirror/git-credential-github-app'
KEY = '/etc/github-mirror/private-key.pem'
REPOS = '/data/git/gitea-repositories/elastic-agent/'


def destination(value):
    """Accept a single HTTPS GitHub repository without embedded credentials."""
    if not re.fullmatch(r'https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+\.git', value):
        raise ValueError('Use https://github.com/OWNER/REPOSITORY.git without credentials.')
    return value


def repository(name):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name):
        raise ValueError('Use a lab repository name, without an owner or path.')
    return REPOS + name + '.git'


def helper(app, installation):
    if int(app) <= 0 or int(installation) <= 0:
        raise ValueError('App and installation IDs must be positive.')
    return f'{BIN} -username x-access-token -appId {int(app)} -installationId {int(installation)} -privateKeyFile {KEY}'


def git(name, *args):
    return k('exec', 'deployment/gitea', '-n', NAMESPACE, '-c', 'gitea', '--',
             'git', '-C', repository(name), *args)


def install(image, private_key):
    """Mount an ESO-managed App key and a pinned helper; preserve chart settings."""
    guard()
    if not re.fullmatch(r'nexus\.localhost:18185/github-app-credential@sha256:[a-f0-9]{64}', image):
        raise ValueError('Use the immutable helper image published to local Nexus.')
    key = Path(private_key).read_text(encoding='ascii')
    if 'PRIVATE KEY-----' not in key:
        raise ValueError('Expected a PEM private key.')
    with floci_forward() as base:
        seed(base, source_name(NAMESPACE, SECRET, 'private-key.pem'), key)
    external_secret(NAMESPACE, SECRET, ['private-key.pem'])
    external_secret(NAMESPACE, 'nexus-read', ['.dockerconfigjson'], 'kubernetes.io/dockerconfigjson')
    # Only selected mount/init definitions enter the override file. Full Helm
    # values can contain credentials and must not be saved as inspection output.
    values = json.loads(run([HELM, 'get', 'values', 'gitea', '-n', NAMESPACE,
                            '--kubeconfig', str(STATE / 'kubeconfig.yaml'), '-o', 'json']).stdout)
    extra = {name: values.get(name, []) for name in
             ('extraVolumes', 'extraContainerVolumeMounts', 'postExtraInitContainers')}
    extra['imagePullSecrets'] = values.get('imagePullSecrets', [])
    if not any(row == 'nexus-read' or isinstance(row, dict) and row.get('name') == 'nexus-read'
               for row in extra['imagePullSecrets']):
        extra['imagePullSecrets'].append({'name': 'nexus-read'})
    existing = [row for row in extra['postExtraInitContainers'] if row['name'] != 'github-mirror-helper']
    if existing:
        raise ValueError('Review existing extra init containers before extending this lab installer.')
    def upsert(name, item):
        extra[name] = [row for row in extra[name] if row['name'] != item['name']] + [item]
    upsert('extraVolumes', {'name': 'github-mirror-helper', 'emptyDir': {}})
    upsert('extraVolumes', {'name': 'github-mirror-key', 'secret': {'secretName': SECRET, 'defaultMode': 0o440}})
    upsert('extraContainerVolumeMounts', {'name': 'github-mirror-helper', 'mountPath': '/opt/github-mirror', 'readOnly': True})
    upsert('extraContainerVolumeMounts', {'name': 'github-mirror-key', 'mountPath': '/etc/github-mirror', 'readOnly': True})
    extra['postExtraInitContainers'] = [{'name': 'github-mirror-helper', 'image': image,
        'command': ['cp', '/git-credential-github-app', '/opt/github-mirror/git-credential-github-app'],
        'volumeMounts': [{'name': 'github-mirror-helper', 'mountPath': '/opt/github-mirror'}],
        'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'allowPrivilegeEscalation': False,
                            'capabilities': {'drop': ['ALL']}}}]
    folder = STATE / 'github-mirror'
    folder.mkdir(exist_ok=True)
    overrides = folder / 'mounts.yaml'
    overrides.write_text(yaml.safe_dump(extra), encoding='utf-8')
    run([HELM, 'upgrade', 'gitea', 'gitea', '--repo', 'https://dl.gitea.com/charts/',
         '--version', '12.7.0', '--reuse-values', '-n', NAMESPACE, '-f', str(overrides),
         '--wait', '--timeout', '5m', '--kubeconfig', str(STATE / 'kubeconfig.yaml')])
    print('GitHub App helper installed; no mirror has been enabled.')


def add(name, target, app, installation):
    """Mirror to an empty destination; repeat setup without creating another mirror."""
    guard()
    target = destination(target)
    repository(name)
    command = helper(app, installation)
    endpoint = '/repos/elastic-agent/' + name
    mirrors = api(endpoint + '/push_mirrors')
    found = [mirror for mirror in mirrors if mirror['remote_address'] == target]
    if found:
        if len(found) != 1:
            raise ValueError('Multiple mirrors use this destination; inspect repository settings.')
        return found[0]
    context = 'credential.' + target
    # Probe using temporary settings first. Never initialise a populated remote:
    # Gitea's native mirror force-pushes and can remove destination-only refs.
    refs = git(name, '-c', context + '.helper=', '-c', context + '.helper=' + command,
               '-c', context + '.useHttpPath=true', 'ls-remote', '--heads', '--tags', target).stdout
    if refs.strip():
        raise ValueError('Destination is not empty. Use a new private repository.')
    git(name, 'config', '--local', '--replace-all', context + '.helper', command)
    git(name, 'config', '--local', context + '.useHttpPath', 'true')
    mirror = api(endpoint + '/push_mirrors', 'POST', {'remote_address': target,
        'interval': '1h0m0s', 'sync_on_commit': True})
    api(endpoint + '/push_mirrors-sync', 'POST')
    return mirror


def status(name):
    repository(name)
    return [{'remote_name': row['remote_name'], 'destination': row['remote_address'],
             'sync_on_commit': row['sync_on_commit'], 'interval': row['interval'],
             'last_update': row['last_update'], 'failed': bool(row['last_error'])}
            for row in api('/repos/elastic-agent/' + name + '/push_mirrors')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    setup = commands.add_parser('install')
    setup.add_argument('--image', required=True)
    setup.add_argument('--private-key', required=True)
    create = commands.add_parser('add')
    create.add_argument('--source', required=True)
    create.add_argument('--target', required=True)
    create.add_argument('--app', type=int, required=True)
    create.add_argument('--installation', type=int, required=True)
    check = commands.add_parser('status')
    check.add_argument('--source', required=True)
    args = parser.parse_args()
    if args.command == 'install':
        install(args.image, args.private_key)
    elif args.command == 'add':
        result = add(args.source, args.target, args.app, args.installation)
        print('Native mirror configured: ' + result['remote_name'])
    else:
        print(json.dumps(status(args.source), indent=2))


if __name__ == '__main__':
    main()
