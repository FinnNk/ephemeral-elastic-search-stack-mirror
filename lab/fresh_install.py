"""Create and resume a fresh CPU search lab without importing old identities."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[1]
CLUSTER = 'relevance-lab'
NODES = ('k3d-relevance-lab-server-0', 'k3d-relevance-lab-agent-0')
FOUNDATION = ('cluster', 'platform', 'storage', 'access')
APPLICATIONS = ('services', 'repositories', 'identity', 'catalogue', 'images',
                'judgements', 'baseline', 'control', 'delivery', 'verify')
PHASES = FOUNDATION + APPLICATIONS
GITEA_DIGEST = 'sha256:c168e7ccb767164793a67e1e874639488260795567337452b06292d1515bea12'
ECK_IMAGE = 'docker.io/elastic/eck-operator:3.5.0@sha256:b6f261372d9d9af7b00aab03efea25263314d16063c4d440ac322e52c2fdf314'
ELASTICSEARCH_IMAGE = 'docker.io/elastic/elasticsearch:9.5.4@sha256:82ac14f43fe701992e601f4cc81e1c0d7dbc5a2576d8cd736006452925df4026'
DOWNLOADS = {
    'argocd': 'https://api.github.com/repos/argoproj/argo-cd/contents/manifests/install.yaml?ref=v3.5.3',
    'eck-crds': 'https://download.elastic.co/downloads/eck/3.5.0/crds.yaml',
    'eck-operator': 'https://download.elastic.co/downloads/eck/3.5.0/operator.yaml',
}


def private_json(path, value):
    """Atomically retain installer state, with owner-only permissions on Unix."""
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    if os.name != 'nt':
        temporary.chmod(0o600)
    temporary.replace(path)


def ca_bundle(destination, corporate):
    """Preserve public trust roots and add the supplied corporate CA bundle."""
    stale = os.environ.get('SSL_CERT_FILE')
    if stale == str(destination) and not destination.exists():
        os.environ.pop('SSL_CERT_FILE')
    try:
        context = ssl.create_default_context()
    finally:
        if stale is not None:
            os.environ['SSL_CERT_FILE'] = stale
    # uv-managed Python may have no OpenSSL default CA file on macOS.
    # certifi is locked in the operator environment and supplies public roots.
    import certifi
    context.load_verify_locations(cafile=certifi.where())
    roots = context.get_ca_certs(binary_form=True)
    if not roots:
        raise RuntimeError('Python has no public CA roots; repair Python certificate trust first.')
    extra = corporate.read_text(encoding='utf-8') if corporate else ''
    if corporate:
        # Parse the entire supplied PEM before any cluster changes.
        context.load_verify_locations(cadata=extra)
    destination.write_text(''.join(ssl.DER_cert_to_PEM_cert(root) for root in roots)
                           + '\n' + extra, encoding='utf-8')
    return context


def execute(command, *, env=None, body=None, live=False, check=True):
    """Run a scoped command; stream safe installer output and report quiet waits."""
    if not live:
        result = subprocess.run(command, input=body, text=True, encoding='utf-8',
                                capture_output=True, cwd=ROOT, env=env)
        if check and result.returncode:
            raise RuntimeError(result.stderr[-3000:] or 'Command failed: ' + command[0])
        return result.stdout
    process = subprocess.Popen(command, stdin=subprocess.PIPE if body is not None else None,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding='utf-8', cwd=ROOT, env=env, bufsize=1)
    lines = queue.Queue()
    def read_output():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    if body is not None:
        process.stdin.write(body)
        process.stdin.close()
    start = time.monotonic()
    try:
        while True:
            try:
                line = lines.get(timeout=20)
            except queue.Empty:
                print(f'  Still running ({time.monotonic() - start:.0f}s elapsed)', flush=True)
                continue
            if line is None:
                break
            print('  ' + line.rstrip(), flush=True)
        if process.wait():
            raise RuntimeError('Command failed: ' + command[0] + '; review the output above.')
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        reader.join()
        process.stdout.close()
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
    return ''


def inspect_nodes():
    """Return Docker identities without reading container environment variables."""
    nodes = {}
    for name in NODES:
        raw = execute(['docker', 'inspect', '--format', '{{.Id}}', name], check=False).strip()
        if raw:
            nodes[name] = raw
    return nodes


def node_volumes():
    """Record anonymous as well as named volumes mounted into these fresh nodes."""
    volumes = set()
    for name in NODES:
        mounts = execute(['docker', 'inspect', '--format', '{{json .Mounts}}', name], check=False).strip()
        if mounts:
            volumes.update(mount['Name'] for mount in json.loads(mounts) if mount['Type'] == 'volume')
    return sorted(volumes)


def operator_manifest(content):
    """Use the official Docker Hub image without changing the upstream operator configuration."""
    documents = list(yaml.safe_load_all(content))
    changed = 0
    for document in documents:
        if document.get('kind') == 'StatefulSet' and document['metadata']['name'] == 'elastic-operator':
            for container in document['spec']['template']['spec']['containers']:
                if container['name'] == 'manager':
                    if container['image'] != 'docker.elastic.co/eck/eck-operator:3.5.0':
                        raise ValueError('Unexpected upstream ECK operator image; review the pinned manifest.')
                    container['image'] = ECK_IMAGE
                    changed += 1
    if changed != 1:
        raise ValueError('Expected exactly one ECK operator manager in the downloaded manifest.')
    return yaml.safe_dump_all(documents)


def elasticsearch_manifest(content):
    """Select the pinned official Elasticsearch image while preserving its data configuration."""
    document = yaml.safe_load(content)
    if document.get('kind') != 'Elasticsearch' or document['spec']['version'] != '9.5.4':
        raise ValueError('Expected the retained Elasticsearch 9.5.4 foundation resource.')
    document['spec']['image'] = ELASTICSEARCH_IMAGE
    return yaml.safe_dump(document)


class Installer:
    def __init__(self, args):
        self.args = args
        self.state = Path(args.state_dir).expanduser().absolute()
        if self.state.is_symlink() or self.state.resolve() != (ROOT / '.lab').resolve():
            raise ValueError('Fresh setup uses this checkout\'s .lab directory only.')
        self.path = self.state / 'fresh-install.json'
        self.env = dict(os.environ, LAB_STATE_DIR=str(self.state), PYTHONUNBUFFERED='1')
        self.kube = ['kubectl', '--kubeconfig', str(self.state / 'kubeconfig.yaml')]
        self.record = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else None

    def command(self, command, **options):
        return execute(command, env=self.env, **options)

    def kubectl(self, *arguments, **options):
        return self.command(self.kube + list(arguments), **options)

    def save(self):
        private_json(self.path, self.record)

    def preflight(self):
        """Reject foreign state and verify host/download prerequisites before creating nodes."""
        if sys.version_info < (3, 12):
            raise RuntimeError('Use Python 3.12 or later.')
        for tool in ('docker', 'k3d', 'kubectl', 'helm', 'git'):
            if not shutil.which(tool):
                raise RuntimeError('Missing host tool: ' + tool)
        if self.command(['docker', 'info', '--format', '{{.OSType}}']).strip() != 'linux':
            raise RuntimeError('Docker must be running Linux containers.')
        current = inspect_nodes()
        if self.record is None:
            if current or (self.state.exists() and any(path.name != 'fresh-install.lock'
                                                     for path in self.state.iterdir())):
                raise RuntimeError('Existing lab state found. Fresh setup will not adopt it. '
                                   'Use the cleanup guide or a separate clean checkout.')
        elif (self.record.get('root') != str(ROOT.resolve())
              or self.record.get('nodes', {}) != current):
            raise RuntimeError('Installer ownership differs from Docker. Inspect cleanup status first.')
        self.state.mkdir(parents=True, exist_ok=True)
        if os.name != 'nt':
            self.state.chmod(0o700)
        corporate = Path(self.args.corporate_ca).expanduser().resolve() if self.args.corporate_ca else None
        context = ca_bundle(self.state / 'host-ca-bundle.pem', corporate)
        self.env.update(SSL_CERT_FILE=str(self.state / 'host-ca-bundle.pem'),
                        REQUESTS_CA_BUNDLE=str(self.state / 'host-ca-bundle.pem'))
        configuration = {'corporate_ca_sha256': hashlib.sha256(corporate.read_bytes()).hexdigest()
                         if corporate else None, 'gitea_registry': self.args.gitea_registry,
                         'server_memory': self.args.server_memory, 'agent_memory': self.args.agent_memory}
        if self.record and self.record['configuration'] != configuration:
            raise RuntimeError('Setup options changed. Resume with the original options; '
                               'use a separate installation for configuration changes.')
        if self.record is None:
            self.record = {'format': 1, 'root': str(ROOT.resolve()), 'cluster': CLUSTER,
                           'configuration': configuration, 'nodes': {}, 'completed': []}
            self.save()
        downloads = self.state / 'installer-downloads'
        downloads.mkdir(exist_ok=True)
        for name, url in DOWNLOADS.items():
            print('Checking and downloading ' + name + ': ' + url, flush=True)
            request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github.raw+json',
                                                          'User-Agent': 'relevance-lab-installer'})
            with urllib.request.urlopen(request, context=context, timeout=60) as response:
                content = response.read()
            documents = list(yaml.safe_load_all(content))
            if not documents or any(not isinstance(doc, dict) or not doc.get('apiVersion')
                                    or not doc.get('kind') for doc in documents):
                raise RuntimeError('Download is not a Kubernetes manifest: ' + url)
            checksum = hashlib.sha256(content).hexdigest()
            pinned = self.record.setdefault('manifest_sha256', {}).get(name)
            if pinned is not None and pinned != checksum:
                raise RuntimeError('Previously downloaded manifest changed: ' + name)
            self.record['manifest_sha256'][name] = checksum
            self.save()
            (downloads / (name + '.yaml')).write_bytes(content)
            print(f'  Downloaded {len(content):,} bytes; SHA-256 {checksum}')
        print('Host and manifest preflight passed.', flush=True)

    def cluster(self):
        """Create nodes once and export the dedicated kubeconfig after each restart."""
        if not self.record['nodes']:
            config = yaml.safe_load((ROOT / 'research/platform-spike/k3d.yaml').read_text(encoding='utf-8'))
            corporate = self.args.corporate_ca
            if corporate:
                # This mount persists across restarts and subsequent node recreation.
                config['volumes'] = [{'volume': str(Path(corporate).expanduser().resolve())
                                      + ':/etc/ssl/certs/lab-corporate.pem:ro',
                                      'nodeFilters': ['server:*', 'agent:*']}]
            target = self.state / 'fresh-k3d.yaml'
            target.write_text(yaml.safe_dump(config), encoding='utf-8')
            try:
                self.command(['k3d', 'cluster', 'create', '--config', str(target),
                              '--servers-memory', self.args.server_memory,
                              '--agents-memory', self.args.agent_memory], live=True)
            finally:
                self.record['nodes'] = inspect_nodes()
                self.record['volumes'] = node_volumes()
                self.save()
            if len(self.record['nodes']) != len(NODES):
                raise RuntimeError('Cluster creation is incomplete; inspect cleanup status before retrying.')
        for name in NODES:
            self.command(['docker', 'start', name])
        config = self.command(['k3d', 'kubeconfig', 'get', CLUSTER])
        (self.state / 'kubeconfig.yaml').write_text(config, encoding='utf-8')
        if os.name != 'nt':
            (self.state / 'kubeconfig.yaml').chmod(0o600)
        self.kubectl('wait', '--for=condition=Ready', 'nodes', '--all', '--timeout=180s', live=True)
        uid = json.loads(self.kubectl('get', 'namespace/kube-system', '-o', 'json'))['metadata']['uid']
        if self.record.get('cluster_uid') and self.record['cluster_uid'] != uid:
            raise RuntimeError('Cluster identity changed; refusing to reuse completed stages.')
        self.record['cluster_uid'] = uid
        self.save()

    def namespace(self, name):
        self.kubectl('apply', '-f', '-', body=json.dumps({'apiVersion': 'v1', 'kind': 'Namespace',
                     'metadata': {'name': name}}))

    def platform(self):
        """Install pinned platform services using fresh, locally retained credentials."""
        import secrets
        self.namespace('platform')
        path = self.state / 'credentials.json'
        if not path.exists():
            private_json(path, {'username': 'lab-admin', 'password': secrets.token_urlsafe(32)})
        credentials = json.loads(path.read_text(encoding='utf-8'))
        self.kubectl('apply', '-f', '-', body=json.dumps({'apiVersion': 'v1', 'kind': 'Secret',
                     'metadata': {'name': 'gitea-admin', 'namespace': 'platform'},
                     'stringData': {key: credentials[key] for key in ('username', 'password')}}))
        values = yaml.safe_load((ROOT / 'research/platform-spike/gitea-values.yaml').read_text(encoding='utf-8'))
        values['image']['fullOverride'] = self.args.gitea_registry + '@' + GITEA_DIGEST
        target = self.state / 'fresh-gitea-values.yaml'
        target.write_text(yaml.safe_dump(values), encoding='utf-8')
        print('Installing Gitea 28.0.0; initial image pulls may take several minutes.', flush=True)
        self.command(['helm', 'upgrade', '--install', 'gitea', 'gitea', '--repo',
                      'https://dl.gitea.com/charts/', '--version', '12.7.0', '--namespace', 'platform',
                      '--kubeconfig', str(self.state / 'kubeconfig.yaml'), '-f', str(target),
                      '--wait', '--timeout', '10m'], live=True)
        for name, namespace in (('argocd', 'argocd'), ('eck-crds', 'elastic-system'),
                                ('eck-operator', 'elastic-system')):
            self.namespace(namespace)
            print('Installing ' + name, flush=True)
            source = self.state / 'installer-downloads' / (name + '.yaml')
            if name == 'eck-operator':
                source = self.state / 'eck-operator-configured.yaml'
                source.write_text(operator_manifest((self.state / 'installer-downloads/eck-operator.yaml')
                                                    .read_text(encoding='utf-8')), encoding='utf-8')
            self.kubectl('apply', '--server-side', '-n', namespace, '-f', str(source), live=True)
        self.repair_failed_operator_pod()
        self.kubectl('rollout', 'status', 'statefulset/elastic-operator', '-n', 'elastic-system',
                     '--timeout=180s', live=True)
        for name in ('argocd-server', 'argocd-repo-server', 'argocd-redis'):
            self.kubectl('rollout', 'status', 'deployment/' + name, '-n', 'argocd',
                         '--timeout=300s', live=True)
        self.kubectl('rollout', 'status', 'statefulset/argocd-application-controller', '-n', 'argocd',
                     '--timeout=300s', live=True)

    def storage(self):
        """Create empty Elasticsearch and Floci stores; do not import catalogue data."""
        for name in ('elasticsearch', 'floci'):
            source = ROOT / 'research/platform-spike' / (name + '.yaml')
            if name == 'elasticsearch':
                configured = self.state / 'elasticsearch-configured.yaml'
                configured.write_text(elasticsearch_manifest(source.read_text(encoding='utf-8')),
                                      encoding='utf-8')
                source = configured
            self.kubectl('apply', '-f', str(source), live=True)
        self.kubectl('rollout', 'status', 'deployment/floci', '-n', 'platform',
                     '--timeout=300s', live=True)
        self.wait_for_elasticsearch()

    def wait_for_elasticsearch(self):
        """Wait for the operator to process the current specification and finish its rollout."""
        current = json.loads(self.kubectl('get', 'elasticsearch/shared', '-n', 'platform', '-o', 'json'))
        generation = current['metadata']['generation']
        for condition in (f'jsonpath={{.status.observedGeneration}}={generation}',
                          'jsonpath={.status.phase}=Ready', 'jsonpath={.status.health}=green'):
            self.kubectl('wait', '--for=' + condition, 'elasticsearch/shared',
                         '-n', 'platform', '--timeout=600s', live=True)

    def reconcile_operator_image(self):
        """Repair an earlier completed platform stage without reinstalling its services."""
        print('Checking the retained ECK image source.', flush=True)
        self.kubectl('set', 'image', 'statefulset/elastic-operator', '-n', 'elastic-system',
                     'manager=' + ECK_IMAGE, live=True)
        self.repair_failed_operator_pod()
        self.kubectl('rollout', 'status', 'statefulset/elastic-operator', '-n', 'elastic-system',
                     '--timeout=300s', live=True)

    def repair_failed_operator_pod(self):
        """Replace only an old failed-pull pod after its controller has the new image."""
        raw = self.kubectl('get', 'pod/elastic-operator-0', '-n', 'elastic-system',
                           '-o', 'json', '--ignore-not-found')
        if not raw.strip():
            return
        pod = json.loads(raw)
        old = next((item['image'] for item in pod['spec']['containers'] if item['name'] == 'manager'), None)
        failed = any(item.get('state', {}).get('waiting', {}).get('reason') in
                     ('ErrImagePull', 'ImagePullBackOff') for item in pod.get('status', {}).get('containerStatuses', []))
        if old and old != ECK_IMAGE and failed:
            desired = json.loads(self.kubectl('get', 'statefulset/elastic-operator', '-n',
                                  'elastic-system', '-o', 'json'))
            if any(item['name'] == 'manager' and item['image'] == ECK_IMAGE
                   for item in desired['spec']['template']['spec']['containers']):
                print('Replacing the old ECK pod whose registry pull failed.', flush=True)
                self.kubectl('delete', 'pod/elastic-operator-0', '-n', 'elastic-system', live=True)

    def reconcile_elasticsearch_image(self):
        """Repair a retained Elasticsearch source without changing version, indices or PVCs."""
        current = json.loads(self.kubectl('get', 'elasticsearch/shared', '-n', 'platform', '-o', 'json'))
        if current['spec']['version'] != '9.5.4':
            raise ValueError('Retained Elasticsearch version changed; image reconciliation refused.')
        if current['spec'].get('image') != ELASTICSEARCH_IMAGE:
            self.kubectl('patch', 'elasticsearch/shared', '-n', 'platform', '--type=merge',
                         '-p', json.dumps({'spec': {'image': ELASTICSEARCH_IMAGE}}), live=True)
        self.wait_for_elasticsearch()

    def access(self):
        """Install HTTPS, wildcard DNS and Headlamp after their backend prerequisites."""
        # Traefik terminates browser TLS; Argo's internal HTTP backend must not redirect to itself.
        self.kubectl('patch', 'configmap/argocd-cmd-params-cm', '-n', 'argocd', '--type=merge',
                     '-p', json.dumps({'data': {'server.insecure': 'true'}}))
        self.kubectl('rollout', 'restart', 'deployment/argocd-server', '-n', 'argocd')
        self.kubectl('rollout', 'status', 'deployment/argocd-server', '-n', 'argocd',
                     '--timeout=300s', live=True)
        for script, arguments in (('https_ingress.py', ['bootstrap-gitea']),
                                  ('install_preview_urls.py', []),
                                  ('install_headlamp.py', ['install'])):
            print('Running ' + script, flush=True)
            self.command([sys.executable, '-u', str(ROOT / 'lab' / script), *arguments], live=True)

    def diagnostics(self):
        """Print pod status and event reasons, without dumping credentials or Secret data."""
        for arguments in (('get', 'pods', '-A'), ('get', 'events', '-A', '--sort-by=.lastTimestamp')):
            try:
                print(self.kubectl(*arguments, check=False)[-10000:], flush=True)
            except OSError:
                pass

    def install(self):
        """Prevent simultaneous installers from creating conflicting local identities."""
        self.state.mkdir(parents=True, exist_ok=True)
        lock = self.state / 'fresh-install.lock'
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise RuntimeError('Another installer may be running. Inspect .lab/fresh-install.lock; '
                               'remove it only after confirming that process has stopped.') from None
        try:
            os.write(descriptor, str(os.getpid()).encode('ascii'))
            os.close(descriptor)
            self._install()
        finally:
            lock.unlink(missing_ok=True)

    def _install(self):
        self.preflight()
        for phase in PHASES[:PHASES.index(self.args.through) + 1]:
            # Cluster identity/readiness is always checked. Other completed phases are retained.
            if phase in self.record['completed'] and phase not in ('cluster', 'verify'):
                print('Retained completed stage: ' + phase, flush=True)
                try:
                    if phase == 'platform':
                        self.reconcile_operator_image()
                    elif phase == 'storage':
                        self.reconcile_elasticsearch_image()
                except Exception:
                    self.diagnostics()
                    raise
                continue
            print('\nStarting stage: ' + phase, flush=True)
            start = time.monotonic()
            try:
                if phase in APPLICATIONS:
                    self.command([sys.executable, '-u', str(ROOT / 'lab/fresh_application.py'),
                                  phase], live=True)
                else:
                    getattr(self, phase)()
            except Exception:
                self.diagnostics()
                raise
            if phase not in self.record['completed']:
                self.record['completed'].append(phase)
            self.save()
            print(f'Completed {phase} in {time.monotonic() - start:.1f}s', flush=True)
        print('\nFresh installation ready through: ' + self.args.through)
        if self.args.through in FOUNDATION:
            print('Catalogue, CI repositories, judgement stack, OIDC and delivery runtime are not installed.')
        elif self.args.through == 'verify':
            print('CPU search lab installed. Open https://control.localhost:34443/.')
            print('Retrieve your initial sign-in: uv run --locked python lab/install_oidc.py credentials --user finnnk')
        print('Next: docs/fresh-install.md. Completed stages are retained when you rerun this command.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', default=str(ROOT / '.lab'))
    parser.add_argument('--corporate-ca', help='PEM bundle; kept outside Git and mounted into k3d nodes')
    parser.add_argument('--gitea-registry', choices=('docker.io/gitea/gitea', 'docker.gitea.com/gitea'),
                        default='docker.io/gitea/gitea')
    parser.add_argument('--server-memory', default='6g')
    parser.add_argument('--agent-memory', default='4g')
    parser.add_argument('--through', choices=PHASES, default='verify')
    args = parser.parse_args()
    if not all(re.fullmatch(r'[1-9][0-9]*[gm]', value) for value in (args.server_memory, args.agent_memory)):
        parser.error('Memory limits must be positive whole values such as 6g.')
    try:
        Installer(args).install()
    except Exception as error:
        print('\nSetup stopped: ' + str(error), file=sys.stderr)
        print('Fix the named failure and rerun with the same options. Completed stages are retained.',
              file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
