"""Expose the fresh lab's built-in Gitea SSH server on loopback only."""
import base64
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import uuid

import yaml

from common import HELM, K3D, KUBE, STATE, k, run

HOST_PORT = 31822
NODE_PORT = 30022
LISTEN_PORT = 2222
LOAD_BALANCER = 'k3d-relevance-lab-serverlb'
HOST_KEY = '/data/gitea/ssh/gitea.ed25519'
SSH_SERVICE = 'gitea-ssh-workstation'
CHART_SHA256 = '5881ef9c59400bee2d5547e77c4cd0efb925143c2f5d93fb4f38446db76b0167'


def chart(folder):
    """Use exact chart bytes and the retained corporate/public CA bundle."""
    path = folder / 'gitea-12.7.0.tgz'
    if not path.exists():
        import certifi
        bundle = STATE / 'host-ca-bundle.pem'
        print('Downloading the pinned Gitea SSH chart with Helm; no server changes yet.', flush=True)
        # Match the working foundation installer download path. Isolate Helm's
        # repository cache so unrelated workstation repositories cannot affect it.
        with tempfile.TemporaryDirectory(prefix='chart-', dir=folder) as temporary:
            staging = Path(temporary)
            run([HELM, 'pull', 'gitea', '--repo', 'https://dl.gitea.com/charts/',
                 '--version', '12.7.0', '--destination', str(staging),
                 '--repository-config', str(staging / 'repositories.yaml'),
                 '--repository-cache', str(staging / 'cache'),
                 '--ca-file', str(bundle) if bundle.exists() else certifi.where()], timeout=120)
            downloaded = staging / path.name
            if (downloaded.stat().st_size > 25_000_000
                    or hashlib.sha256(downloaded.read_bytes()).hexdigest() != CHART_SHA256):
                raise ValueError('Downloaded Gitea chart differs from its pinned checksum.')
            downloaded.replace(path)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != CHART_SHA256:
        raise ValueError('Retained Gitea chart differs from its pinned checksum.')
    return path


def identity():
    from fresh_application import assert_fresh
    assert_fresh()
    uid = json.loads(k('get', 'namespace/kube-system', '-o', 'json').stdout)['metadata']['uid']
    record = json.loads((STATE / 'fresh-install.json').read_text(encoding='utf-8'))
    if uid != record.get('cluster_uid'):
        raise ValueError('The cluster does not match the fresh installation record.')
    return str(uuid.UUID(uid))


def require_idle():
    """Do not restart Gitea while delivery, comparisons or CI are active."""
    script = """import json, sqlite3
from delivery_operations import Operations
c=sqlite3.connect('/state/lifecycle.sqlite3')
print(json.dumps({'operations':len(Operations().active()),
'comparisons':c.execute("select count(*) from comparisons where state='running'").fetchone()[0],
'mutations':c.execute("select count(*) from environments where state in ('requested','provisioning','deleting')").fetchone()[0]}))
"""
    # Pass the program through stdin, never through a shell or a command string.
    value = json.loads(run(KUBE + ['exec', '-i', 'deployment/lab-control', '-n', 'lab-control',
                                  '-c', 'api', '--', 'python', '-'], body=script).stdout)
    if any(value.values()):
        raise ValueError('Delivery or comparison work is active. Retry SSH setup when idle.')
    from gitea import api
    for repo in ('delivery-source', 'search-spike'):
        runs = api('/repos/elastic-agent/' + repo + '/actions/runs?limit=50')['workflow_runs']
        if any(row.get('status') not in ('completed', 'cancelled', 'skipped', 'success', 'failure')
               for row in runs):
            raise ValueError('Gitea Actions is active. Retry SSH setup when its jobs finish.')


def bindings():
    return json.loads(run(['docker', 'inspect', LOAD_BALANCER, '--format',
                           '{{json .HostConfig.PortBindings}}']).stdout) or {}


def exposed(value):
    rows = value.get(str(NODE_PORT) + '/tcp')
    if rows is None:
        return False
    if rows != [{'HostIp': '127.0.0.1', 'HostPort': str(HOST_PORT)}]:
        raise ValueError('Existing SSH port mapping differs; refusing to replace or widen it.')
    return True


def settings():
    # The chart creates a headless SSH service even when SSH is disabled.
    # Preserve it, and clear a NodePort value retained by a failed old upgrade.
    return {'service': {'ssh': {'type': 'ClusterIP', 'clusterIP': 'None', 'port': 22, 'nodePort': None}},
            'gitea': {'config': {'server': {
                'DISABLE_SSH': False, 'START_SSH_SERVER': True,
                'SSH_DOMAIN': 'gitea.localhost', 'SSH_PORT': HOST_PORT,
                'SSH_LISTEN_PORT': LISTEN_PORT, 'SSH_SERVER_HOST_KEYS': HOST_KEY}}}}


def require_available_service(uid):
    services = json.loads(k('get', 'services', '-A', '-o', 'json').stdout)['items']
    original = None
    existing = None
    for service in services:
        name = (service['metadata'].get('namespace'), service['metadata']['name'])
        if name == ('platform', 'gitea-ssh'):
            original = service
        if name == ('platform', SSH_SERVICE):
            existing = service
        if any(port.get('nodePort') == NODE_PORT for port in service['spec'].get('ports', [])):
            if name != ('platform', SSH_SERVICE):
                raise ValueError('NodePort 30022 belongs to another service; nothing was replaced.')
    if (not original or original['metadata'].get('annotations', {}).get('meta.helm.sh/release-name') != 'gitea'
            or original['spec'].get('clusterIP') != 'None' or not original['spec'].get('selector')):
        raise ValueError('Expected the owned headless Gitea SSH service; inspect its configuration before retrying.')
    selector = original['spec']['selector']
    labels = {'app.kubernetes.io/managed-by': 'relevance-lab-ssh', 'lab.relevance.test/cluster-uid': uid}
    if existing and (any(existing['metadata'].get('labels', {}).get(key) != value for key, value in labels.items())
                     or existing['spec'].get('type') != 'NodePort'
                     or existing['spec'].get('selector') != selector):
        raise ValueError('The workstation SSH service has unexpected ownership or settings; nothing was replaced.')
    # Read Helm settings in memory; never print or retain a full values dump.
    values = json.loads(run([HELM, 'get', 'values', 'gitea', '-n', 'platform', '-o', 'json',
                             '--kubeconfig', str(STATE / 'kubeconfig.yaml')]).stdout)
    current = (values or {}).get('gitea', {}).get('config', {}).get('server', {})
    enabled = str(current.get('DISABLE_SSH', True)).lower() == 'false'
    if enabled and current.get('SSH_SERVER_HOST_KEYS') != HOST_KEY:
        raise ValueError('Gitea already has other SSH host-key settings; review them before changing access.')
    return {'apiVersion': 'v1', 'kind': 'Service',
            'metadata': {'name': SSH_SERVICE, 'namespace': 'platform', 'labels': labels},
            'spec': {'type': 'NodePort', 'selector': selector,
                     'ports': [{'name': 'ssh', 'port': 22, 'targetPort': LISTEN_PORT, 'nodePort': NODE_PORT}]}}


def install():
    uid = identity()
    require_idle()
    published = exposed(bindings())
    if not published:
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', HOST_PORT))
            except OSError:
                raise ValueError('Loopback port 31822 is occupied; nothing will be replaced.') from None
    service = require_available_service(uid)
    folder = STATE / 'gitea-ssh'
    folder.mkdir(exist_ok=True)
    values = folder / 'values.yaml'
    values.write_text(yaml.safe_dump(settings()), encoding='utf-8')
    archive = chart(folder)
    print('Enabling loopback Gitea SSH; waiting for its rollout.', flush=True)
    run([HELM, 'upgrade', 'gitea', str(archive), '--reuse-values', '-n', 'platform', '-f', str(values),
         '--wait', '--timeout', '5m', '--kubeconfig', str(STATE / 'kubeconfig.yaml')])
    k('apply', '-f', '-', body=service)
    if not published:
        run([K3D, 'cluster', 'edit', 'relevance-lab', '--port-add',
             f'127.0.0.1:{HOST_PORT}:{NODE_PORT}@server:0'])
    if not exposed(bindings()):
        raise RuntimeError('SSH loopback mapping was not created.')
    return uid


def public_key(output):
    keys = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == 'ssh-ed25519':
            raw = base64.b64decode(parts[2], validate=True)
            if (len(raw) != 51 or raw[:15] != b'\x00\x00\x00\x0bssh-ed25519'
                    or raw[15:19] != b'\x00\x00\x00\x20'):
                raise ValueError('Invalid Ed25519 host key.')
            keys.add('ssh-ed25519 ' + parts[2])
    if len(keys) != 1:
        raise ValueError('Expected exactly one Ed25519 SSH host key.')
    return keys.pop()


def host_key(keyscan):
    """Match the endpoint to the owned Pod's public host key, not blind TOFU."""
    internal = k('exec', 'deployment/gitea', '-n', 'platform', '-c', 'gitea', '--',
                 'cat', HOST_KEY + '.pub').stdout
    external = run([keyscan, '-T', '10', '-t', 'ed25519', '-p', str(HOST_PORT), '127.0.0.1']).stdout
    first, second = public_key('pod ' + internal), public_key(external)
    if first != second:
        raise ValueError('The loopback endpoint does not present this Gitea Pod\'s host key.')
    return first


def fingerprint(key):
    raw = base64.b64decode(key.split()[1], validate=True)
    return 'SHA256:' + base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
