"""Ordered application setup for an installer-owned CPU lab, with fresh identities."""
import argparse
import base64
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time

import yaml

from common import ROOT, STATE, KUBE, apply, guard, k
from fresh_install import APPLICATIONS, NODES, execute, private_json
sys.path.insert(0, str(ROOT))

STORES = ('relevance-nexus-db', 'relevance-nexus', 'relevance-snapshot-store')
SERVICES_RECORD = STATE / 'fresh-services.json'


def run_script(name, *arguments):
    """Stream safe stage output while retaining the installer's trust settings."""
    env = os.environ.copy()
    # Direct script execution puts lab/, rather than the repository root, on
    # sys.path. Child scripts also import shared packages such as evaluation/.
    paths = [str(ROOT)]
    if env.get('PYTHONPATH'):
        paths.append(env['PYTHONPATH'])
    env['PYTHONPATH'] = os.pathsep.join(paths)
    return execute([sys.executable, '-u', str(ROOT / name), *map(str, arguments)],
                   env=env, live=True)


def assert_fresh():
    """Refuse application bootstrap against a retained or foreign installation."""
    path = STATE / 'fresh-install.json'
    if STATE.resolve() != (ROOT / '.lab').resolve() or STATE.is_symlink() or not path.exists():
        raise ValueError('Run applications through this checkout\'s fresh installer.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('root') != str(ROOT.resolve()) or 'access' not in record.get('completed', []):
        raise ValueError('Complete the owned foundation before installing applications.')
    from fresh_install import inspect_nodes
    if record.get('nodes') != inspect_nodes():
        raise ValueError('Fresh node identities changed; application setup refused.')
    guard()


@contextmanager
def forwards():
    """Own short-lived operator forwards; stop them even when a stage fails."""
    processes = []
    logs = []
    try:
        for name, port, destination in (('floci', 14577, 4577), ('shared-es-http', 19200, 9200)):
            require_free_port(port)
            log = (STATE / ('fresh-' + name + '-forward.log')).open('a', encoding='utf-8')
            logs.append(log)
            process = subprocess.Popen(KUBE + ['-n', 'platform', 'port-forward', 'svc/' + name,
                f'{port}:{destination}', '--address', '127.0.0.1'], stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            processes.append(process)
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError('Operator forward exited; inspect ' + str(log.name))
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=1):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise TimeoutError('Operator forward did not open: ' + name)
        yield
    finally:
        for process in processes:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()


def require_free_port(port):
    """Reject active listeners while allowing a closed Unix forward's TIME_WAIT sockets."""
    with socket.socket() as probe:
        # kubectl's Unix listener permits address reuse. Match that behaviour so
        # the next stage does not mistake a recently closed socket for a listener.
        # Windows reuse semantics differ and can permit overlapping listeners.
        if sys.platform != 'win32':
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            raise RuntimeError(f'Operator port {port} is occupied; inspect its listener before resuming.') from None


def store_ids():
    """Read only the IDs of the three dedicated external lab stores."""
    return {name: value for name in STORES if (value := execute(
        ['docker', 'inspect', '--format', '{{.Id}}', name], check=False).strip())}


def owned_services(action):
    """Record newly created stores even after failure; refuse existing foreign stores."""
    value = json.loads(SERVICES_RECORD.read_text(encoding='utf-8')) if SERVICES_RECORD.exists() else {
        'format': 1, 'root': str(ROOT.resolve()), 'containers': {}, 'volumes': list(STORES)}
    if value.get('root') != str(ROOT.resolve()) or value.get('format') != 1:
        raise ValueError('External store ownership record is invalid.')
    existing = store_ids()
    if any(value['containers'].get(name) != identity for name, identity in existing.items()):
        raise ValueError('External lab stores already exist without matching installer ownership.')
    volumes = execute(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines()
    if not SERVICES_RECORD.exists() and any(name in volumes for name in STORES):
        raise ValueError('External store volumes already exist; inspect before starting a fresh installation.')
    private_json(SERVICES_RECORD, value)
    try:
        action()
    finally:
        value['containers'] = store_ids()
        private_json(SERVICES_RECORD, value)
        for name in ('nexus.json', 'nexus.env', 'nexus-postgres.env', 'snapshot-s3.json'):
            path = STATE / name
            if path.exists() and os.name != 'nt':
                path.chmod(0o600)


def services():
    """Install dedicated Nexus, snapshot storage and the local secret operator."""
    # Catalogue publication has a measured Floci peak above a 4 GiB node limit.
    print('Allocating 16 GiB to the owned application agent; allow at least 32 GiB for Docker Desktop.', flush=True)
    execute(['docker', 'update', '--memory', '16g', '--memory-swap', '16g', NODES[1]])
    if k('get', 'configmap/coredns-custom', '-n', 'kube-system', check=False).returncode:
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
            'name': 'coredns-custom', 'namespace': 'kube-system'}, 'data': {}})
    registry_dns()
    def create():
        import setup_nexus as nexus
        import setup_snapshot_store as snapshot
        value = nexus.ensure_services()
        nexus.configure(value)
        nexus.configure_network()
        snapshot.ensure_store(snapshot.credentials())
        snapshot.configure_eck(snapshot.credentials())
        snapshot.wait_eck()
        snapshot.register_repository()
    owned_services(create)
    import keyvault
    keyvault.install()
    from setup_nexus import image_secret
    image_secret('platform')
    with keyvault.floci_forward() as base:
        secret = keyvault.read_secret('platform', 'nexus-read')
        keyvault.seed(base, keyvault.NEXUS_SOURCE, keyvault.value_of(secret, '.dockerconfigjson'))


def create_account(name, password, email, admin=False):
    """Create a reserved bootstrap identity without replacing an existing password."""
    from gitea import api
    accounts = api('/admin/users?limit=100', identity='admin')
    if not any(row['login'] == name for row in accounts):
        api('/admin/users', 'POST', {'username': name, 'password': password, 'email': email,
            'must_change_password': False, 'send_notify': False}, identity='admin')
    if admin:
        api('/admin/users/' + name, 'PATCH', {'admin': True, 'active': True}, identity='admin')


def token(value, key, scopes):
    """Retain a scoped token, recovering only this installer's reserved token name."""
    from gitea import api
    if key not in value:
        name = 'fresh-lab-' + key.replace('_', '-')
        for existing in api('/users/elastic-agent/tokens'):
            if existing['name'] == name:
                api('/users/elastic-agent/tokens/' + str(existing['id']), 'DELETE')
        value[key] = api('/users/elastic-agent/tokens', 'POST', {'name': name, 'scopes': scopes})['sha1']
        private_json(STATE / 'credentials.json', value)


def has_commit(path):
    """Recognise a saved seed commit after an interrupted first push."""
    return (path / '.git').exists() and subprocess.run(
        ['git', '-C', str(path), 'rev-parse', '--verify', 'HEAD'], capture_output=True).returncode == 0


def repositories():
    """Seed private source/state repositories, credentials and scoped Actions runners."""
    from gitea import api
    credentials_path = STATE / 'credentials.json'
    value = json.loads(credentials_path.read_text(encoding='utf-8'))
    if 'agent' not in value:
        value['agent'] = {'username': 'elastic-agent', 'password': secrets.token_urlsafe(32)}
        private_json(credentials_path, value)
    create_account('elastic-agent', value['agent']['password'], 'elastic-agent@lab.invalid')
    user_path = STATE / 'user-credentials.json'
    if not user_path.exists():
        private_json(user_path, {'username': 'finnnk', 'email': 'finnnk@lab.invalid',
            'gitea_password': secrets.token_urlsafe(32), 'argocd_password': secrets.token_urlsafe(32)})
    user = json.loads(user_path.read_text(encoding='utf-8'))
    create_account(user['username'], user['gitea_password'], user['email'], admin=True)
    for key, scopes in [('build_token', ['write:repository', 'write:package']),
                        ('read_token', ['read:package']), ('delivery_read_token', ['read:repository'])]:
        token(value, key, scopes)
    for name in ('search-spike', 'environment-state'):
        if not any(row['name'] == name for row in api('/user/repos?limit=100')):
            api('/user/repos', 'POST', {'name': name, 'private': True, 'default_branch': 'main'})
        api('/repos/elastic-agent/' + name, 'PATCH', {'has_actions': name == 'search-spike'})
        api('/repos/elastic-agent/' + name + '/collaborators/finnnk', 'PUT', {'permission': 'admin'})
    api('/repos/elastic-agent/search-spike/actions/secrets/BUILD_TOKEN', 'PUT', {'data': value['build_token']})
    registration = api('/repos/elastic-agent/search-spike/actions/runners/registration-token', 'POST')['token']
    apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'runner-registration',
        'namespace': 'platform'}, 'stringData': {'token': registration}})
    from https_ingress import certificate
    _, _, ca = certificate()
    bundle = (STATE / 'host-ca-bundle.pem').read_text(encoding='utf-8') + '\n' + ca.read_text(encoding='utf-8')
    for name in ('runner-ca', 'delivery-runner-ca'):
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': name,
            'namespace': 'platform'}, 'data': {'root.pem': bundle}})
    k('apply', '-f', str(ROOT / 'research/platform-spike/runner.yaml'))
    k('rollout', 'status', 'deployment/build-runner', '-n', 'platform', '--timeout=300s')
    from setup_delivery import configure_ci, seed_source
    from delivery_provider import ensure_repo
    source = ensure_repo('delivery-source', actions=True)
    ensure_repo('delivery-state')
    configure_ci()
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'fresh-runner-ca',
        'namespace': 'platform'}, 'data': {'root.pem': bundle}})
    for name in ('build-runner', 'delivery-runner'):
        k('patch', 'deployment/' + name, '-n', 'platform', '--type=strategic', '-p',
          json.dumps({'spec': {'template': {'spec': {'volumes': [{'name': 'lab-internal-ca',
             'configMap': {'name': 'fresh-runner-ca'}}]}}}}))
        k('rollout', 'status', 'deployment/' + name, '-n', 'platform', '--timeout=300s')
    from delivery_provider import git as source_git
    if api('/repos/elastic-agent/delivery-source')['empty'] and has_commit(source):
        if source_git('delivery-source', 'status', '--porcelain'):
            raise ValueError('Interrupted source seed contains edits; inspect before resuming.')
        source_git('delivery-source', 'push', '-u', 'origin', 'main')
    else:
        seed_source(source)
    from setup_relevance_gate import install
    install()
    # Supply the shared package credential before the first experimental preview.
    from keyvault import floci_forward, seed, REGISTRY_SOURCE
    docker_auth = base64.b64encode(('elastic-agent:' + value['read_token']).encode()).decode()
    with floci_forward() as base:
        seed(base, REGISTRY_SOURCE, json.dumps({'auths': {'gitea.localhost:31800': {'auth': docker_auth}}}))


def identity():
    """Create the local OIDC provider and named application sign-in."""
    run_script('lab/install_oidc.py', 'install')
    run_script('lab/install_gitea_oidc.py')


def snapshot_payloads(root):
    """Verify the exact frozen labels; never regenerate predictions or treat them as ground truth."""
    lock = json.loads((root / 'lock.json').read_text(encoding='utf-8'))
    defaults = json.loads((ROOT / 'lab/default_inputs.json').read_text(encoding='utf-8'))
    result = []
    for release, pin in lock.items():
        raw = (root / (release + '.manifest.json')).read_bytes()
        content = gzip.decompress((root / (release + '.rows.jsonl.gz')).read_bytes())
        manifest = json.loads(raw)
        if (hashlib.sha256(raw).hexdigest() != defaults[release]['judgement-set'] or
                hashlib.sha256(raw).hexdigest() != pin['manifest_sha256'] or
                hashlib.sha256(content).hexdigest() != manifest['content']['sha256'] or
                manifest['content']['object'] != pin['object'] or
                len(content.splitlines()) != manifest['record_count']):
            raise ValueError('Frozen judgement snapshot differs: ' + release)
        result.extend([(f"manifests/judgement-set/{pin['manifest_sha256']}.json", raw),
                       (pin['object'], content)])
    return result


def catalogue():
    """Download/import both pinned catalogues and restore selected judgement data only."""
    from blob_config import service, settings
    sys.path.insert(0, str(ROOT / 'data'))
    from data.publish import upload
    account = service()
    try:
        account.create_container(settings()[1])
    except Exception as error:
        from azure.core.exceptions import ResourceExistsError
        if not isinstance(error, ResourceExistsError):
            raise
    for name, payload in snapshot_payloads(ROOT / 'data/fresh-judgements'):
        upload(account, settings()[1], name, payload, hashlib.sha256(payload).hexdigest(), len(payload))
    for release in ('esci-gb-v1', 'esci-gb-demo-v1'):
        print('Importing ' + release + ' from the retained ESCI source release.', flush=True)
        run_script('lab/import_catalogue.py', '--download', '--release', release)
    run_script('lab/publish_default_inputs.py')
    run_script('lab/prepare_data_versions.py', '--publish')
    run_script('lab/prepare_seasonal_queries.py', '--publish')
    run_script('lab/install_redis.py')
    for release in ('esci-gb-v1', 'esci-gb-demo-v1'):
        run_script('lab/load_release.py', '--release', release)


def images():
    """Publish native CPU images; fresh image receipts replace source-host digests."""
    run_script('lab/fresh_images.py')


def replace_runtime(value, image):
    """Adapt bootstrap manifests to the new image and the owned CPU agent."""
    if isinstance(value, list):
        return [replace_runtime(item, image) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: replace_runtime(item, image) for key, item in value.items()}
    if 'nodeSelector' in result:
        result['nodeSelector'] = {'kubernetes.io/hostname': NODES[1]}
    if isinstance(result.get('image'), str) and result['image'].startswith('nexus.localhost:18185/relevance-judge:'):
        result['image'] = image
    return result


def judgements():
    """Register a new CPU abstaining model and derive its actual model hash before serving."""
    from setup_judgement_stack import chart
    from setup_judgement_secrets import configure
    from setup_kserve import install
    image = json.loads((STATE / 'judgement-image.json').read_text(encoding='utf-8'))['image']
    chart('cert-manager', 'oci://quay.io/jetstack/charts/cert-manager', 'v1.17.0',
          'cert-manager', '--set', 'crds.enabled=true')
    install()
    configure()
    sources = ROOT / 'judgements/kubernetes'
    target = STATE / 'fresh-judgements'
    target.mkdir(exist_ok=True)
    def manifest(name, transform=None):
        docs = [replace_runtime(doc, image) for doc in yaml.safe_load_all((sources / name).read_text(encoding='utf-8'))]
        if transform:
            docs = transform(docs)
        path = target / name
        path.write_text(yaml.safe_dump_all(docs), encoding='utf-8')
        k('apply', '-f', str(path))
    manifest('postgres.yaml')
    k('rollout', 'status', 'statefulset/mlflow-postgres', '-n', 'lab-models', '--timeout=300s')
    values = replace_runtime(yaml.safe_load((sources / 'mlflow-values.yaml').read_text(encoding='utf-8')), image)
    values['image'] = {'repository': 'nexus.localhost:18185/relevance-judge',
                       'tag': image.split('relevance-judge:', 1)[1]}
    path = target / 'mlflow-values.yaml'
    path.write_text(yaml.safe_dump(values), encoding='utf-8')
    chart('mlflow', 'oci://ghcr.io/mlflow/charts/mlflow', '0.1.0', 'lab-models', '-f', str(path))
    k('rollout', 'status', 'deployment/mlflow-mlflow', '-n', 'lab-models', '--timeout=300s')
    existing = k('get', 'job/register-synthetic-esci-judge', '-n', 'lab-models', '--ignore-not-found')
    if not existing.stdout.strip():
        manifest('register-model.yaml')
    k('wait', '--for=condition=Complete', 'job/register-synthetic-esci-judge', '-n', 'lab-models', '--timeout=300s')
    logs = k('logs', 'job/register-synthetic-esci-judge', '-n', 'lab-models').stdout
    receipt = next((json.loads(line) for line in reversed(logs.splitlines())
                    if line.startswith('{') and 'artifact_sha256' in line), None)
    if not receipt or receipt.get('registered_name') != 'synthetic-esci-judge' or \
            receipt.get('source_sha256') != hashlib.sha256((ROOT / 'judgements/noop_model.py').read_bytes()).hexdigest() or \
            not re.fullmatch('[0-9a-f]{64}', receipt.get('artifact_sha256', '')):
        raise ValueError('Model registration has no verified artefact receipt.')
    private_json(STATE / 'fresh-model.json', receipt)
    def model(docs):
        for doc in docs:
            if doc['kind'] == 'InferenceService':
                doc['spec']['predictor']['model']['storageUri'] = (
                    'mlflow-registry://synthetic-esci-judge/' + str(receipt['version']) +
                    '?sha256=' + receipt['artifact_sha256'])
        return docs
    expected_uri = 'mlflow-registry://synthetic-esci-judge/' + str(receipt['version']) + '?sha256=' + receipt['artifact_sha256']
    current = k('get', 'inferenceservice/synthetic-esci-judge', '-n', 'lab-models', '-o', 'json', check=False)
    if current.returncode == 0 and json.loads(current.stdout)['spec']['predictor']['model'].get('storageUri') != expected_uri:
        raise ValueError('A different model was activated during installation; refusing to replace it.')
    manifest('kserve-model.yaml', model)
    k('wait', '--for=condition=Ready', 'inferenceservice/synthetic-esci-judge', '-n', 'lab-models', '--timeout=300s')
    def pins(docs):
        for doc in docs:
            if doc['kind'] == 'ConfigMap' and doc['metadata']['name'] == 'judgement-model-pin':
                doc['data']['model.json'] = json.dumps({'name': 'synthetic-esci-judge',
                    'version': str(receipt['version']), 'artifact_sha256': receipt['artifact_sha256']})
                inference = json.loads(doc['data']['inference.json'])
                inference['runtime_image'] = image
                doc['data']['inference.json'] = json.dumps(inference)
        return docs
    # Both services use independent published labels; the retained demo snapshot remains separate.
    manifest('judgement-service.yaml', pins)
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'judgement-demo-policy',
        'namespace': 'lab-models'}, 'data': {'policy.json': (ROOT / 'judgements/policies/esci-lab-demo.json').read_text(encoding='utf-8')}})
    manifest('judgement-service-million.yaml', pins)
    for name in ('judgement-service', 'judgement-service-million'):
        k('rollout', 'status', 'deployment/' + name, '-n', 'lab-models', '--timeout=600s')
        k('exec', 'deployment/' + name, '-n', 'lab-models', '-c', name, '--',
          'python', '/app/smoke.py')


def registry_dns():
    """Route the frozen Gitea registry hostname to its service; preserve other DNS rules."""
    rule = 'rewrite name exact gitea.localhost gitea-http.platform.svc.cluster.local\n'
    current = json.loads(k('get', 'configmap/coredns-custom', '-n', 'kube-system', '-o', 'json').stdout)
    if current.get('data', {}).get('gitea.override') == rule:
        return False
    print('Repairing in-cluster Gitea registry DNS; preserving existing DNS rules.', flush=True)
    k('patch', 'configmap/coredns-custom', '-n', 'kube-system', '--type=merge', '-p',
      json.dumps({'data': {'gitea.override': rule}}))
    k('rollout', 'restart', 'deployment/coredns', '-n', 'kube-system')
    k('rollout', 'status', 'deployment/coredns', '-n', 'kube-system', '--timeout=180s')
    return True


def wait_build(repo, sha, retry_failed=False):
    """Wait for the exact source commit, never substitute an old source-host run ID."""
    from gitea import api
    deadline = time.monotonic() + 1800
    previous = None
    retried = None
    while time.monotonic() < deadline:
        runs = api('/repos/elastic-agent/' + repo + '/actions/runs?limit=50')['workflow_runs']
        matching = [row for row in runs if row['head_sha'] == sha and row['event'] == 'push']
        if matching:
            current = max(matching, key=lambda row: row['id'])
            state = (current['id'], current.get('run_attempt', 1), current['status'], current.get('conclusion'))
            if state != previous:
                print(repo + ' build: ' + str(state), flush=True)
                previous = state
            if retried == (current['id'], current.get('run_attempt', 1)):
                # The API may briefly return the old failure after accepting a rerun.
                time.sleep(5)
                continue
            if current['status'] == 'completed':
                if current.get('conclusion') != 'success':
                    if retry_failed and retried is None and current.get('conclusion') == 'failure':
                        print(f"Retrying exact {repo} build {current['id']} once after registry DNS repair.", flush=True)
                        api('/repos/elastic-agent/' + repo + f"/actions/runs/{current['id']}/rerun", 'POST')
                        retried = (current['id'], current.get('run_attempt', 1))
                        time.sleep(5)
                        continue
                    raise RuntimeError(f"{repo} build {current['id']} failed; inspect its Actions log.")
                return current['id']
        time.sleep(5)
    raise TimeoutError('Exact baseline build did not complete within 30 minutes: ' + repo)


def search_probe():
    """Provide host bootstrap checks with a native, unprivileged in-cluster client."""
    image = json.loads((STATE / 'control-image.json').read_text(encoding='utf-8'))['image']
    current = k('get', 'pod/search-probe', '-n', 'platform', '-o', 'json', check=False)
    if current.returncode == 0:
        pod = json.loads(current.stdout)
        if (pod['metadata'].get('labels', {}).get('lab/fresh-install') != 'search-probe' or
                pod['spec']['containers'][0]['image'] != image):
            raise ValueError('Existing search-probe differs from this fresh installer; inspect it before resuming.')
    else:
        print('Creating the in-cluster search verification probe from the retained native image.', flush=True)
        apply({'apiVersion': 'v1', 'kind': 'Pod',
            'metadata': {'name': 'search-probe', 'namespace': 'platform',
                         'labels': {'lab/fresh-install': 'search-probe'}},
            'spec': {'automountServiceAccountToken': False,
                'imagePullSecrets': [{'name': 'nexus-read'}],
                'containers': [{'name': 'probe', 'image': image,
                    'command': ['python', '-c', 'import time; time.sleep(86400)'],
                    'resources': {'requests': {'cpu': '10m', 'memory': '24Mi'},
                                  'limits': {'cpu': '250m', 'memory': '96Mi'}}}]}})
    k('wait', '--for=condition=Ready', 'pod/search-probe', '-n', 'platform', '--timeout=180s')
    print('Search verification probe is ready.', flush=True)


def baseline():
    """Seed the search baseline and identify the native delivery build created by Gitea."""
    from environments import git
    from gitea import api
    dns_repaired = registry_dns()
    search_probe()
    source = STATE / 'search-source'
    if not api('/repos/elastic-agent/search-spike')['empty']:
        if not (source / '.git').exists():
            raise ValueError('Search source was already seeded without its local checkout.')
    elif has_commit(source):
        if git('status', '--porcelain', cwd=source):
            raise ValueError('Interrupted search seed contains edits; inspect before resuming.')
        git('push', '-u', 'origin', 'main', cwd=source)
    else:
        source.mkdir(exist_ok=True)
        shutil.copytree(ROOT / 'lab/search-app', source, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__'))
        git('init', '-b', 'main', cwd=source)
        if not git('remote', cwd=source):
            git('remote', 'add', 'origin', 'http://127.0.0.1:31800/elastic-agent/search-spike.git', cwd=source)
        git('add', '.', cwd=source)
        git('commit', '-m', 'Seed fresh lab search baseline', cwd=source)
        git('push', '-u', 'origin', 'main', cwd=source)
    run = wait_build('search-spike', git('rev-parse', 'HEAD', cwd=source), retry_failed=dns_repaired)
    from delivery_provider import git as delivery_git
    delivery_run = wait_build('delivery-source', delivery_git('delivery-source', 'rev-parse', 'HEAD'))
    private_json(STATE / 'fresh-baselines.json', {'search_run': run, 'delivery_run': delivery_run})
    state = STATE / 'state-source'
    if not has_commit(state):
        state.mkdir(exist_ok=True)
        shutil.copytree(ROOT / 'research/platform-spike/chart', state / 'chart', dirs_exist_ok=True)
        (state / 'environments').mkdir(exist_ok=True)
        (state / 'definitions').mkdir(exist_ok=True)
        git('init', '-b', 'main')
        if not git('remote'):
            git('remote', 'add', 'origin', 'http://127.0.0.1:31800/elastic-agent/environment-state.git')
        git('add', '.')
        git('commit', '-m', 'Seed empty environment definitions')
    if api('/repos/elastic-agent/environment-state')['empty']:
        if git('status', '--porcelain'):
            raise ValueError('Interrupted environment seed contains edits; inspect before resuming.')
        git('push', '-u', 'origin', 'main')
    value = json.loads((STATE / 'credentials.json').read_text(encoding='utf-8'))
    apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'gitea-state-repo',
        'namespace': 'argocd', 'labels': {'argocd.argoproj.io/secret-type': 'repository'}},
        'stringData': {'type': 'git', 'url': 'https://gitea-internal.lab-ingress.svc.cluster.local/elastic-agent/environment-state.git',
                       'username': 'elastic-agent', 'password': value['build_token']}})
    k('apply', '-f', str(ROOT / 'research/platform-spike/applicationset.yaml'))
    from delivery_provider import git as desired_git
    if api('/repos/elastic-agent/delivery-state')['empty'] and has_commit(STATE / 'delivery-state'):
        if desired_git('delivery-state', 'status', '--porcelain'):
            raise ValueError('Interrupted delivery seed contains edits; inspect before resuming.')
        desired_git('delivery-state', 'push', '-u', 'origin', 'main')
    run_script('lab/delivery_cli.py', 'bootstrap', '--run', delivery_run, '--dataset', 'esci-gb-v1')


def control():
    """Transfer freshly created state once; never re-import over an active runtime."""
    image = json.loads((STATE / 'control-image.json').read_text(encoding='utf-8'))['image']
    run = json.loads((STATE / 'fresh-baselines.json').read_text(encoding='utf-8'))['search_run']
    for folder in ('evidence', 'delivery', 'workloads'):
        (STATE / folder).mkdir(exist_ok=True)
    from lifecycle import Store
    Store(STATE / 'lifecycle.sqlite3')
    run_script('lab/control-runtime/install.py', 'stage', '--image', image, '--baseline-run', run)
    from https_ingress import certificate, route
    route(*certificate()[:2])
    existing = k('get', 'deployment/lab-control', '-n', 'lab-control', '--ignore-not-found')
    if not existing.stdout.strip():
        run_script('lab/control-runtime/install.py', 'activate', '--fresh', '--image', image, '--baseline-run', run)
    run_script('lab/install_control_oidc.py', '--image', image)
    # ESO adopts only the specific runtime Secrets created by this fresh bootstrap.
    from keyvault import read_secret, floci_forward, seed, source_name, value_of, external_secret
    for namespace, name in [('lab-control', 'lab-control-gitea'), ('lab-control', 'lab-control-nexus'),
                            ('argocd', 'delivery-state-repo'), ('argocd', 'gitea-state-repo'),
                            ('platform', 'lab-s3-snapshot-client')]:
        secret = read_secret(namespace, name)
        if not secret:
            raise ValueError('Fresh bootstrap Secret is missing: ' + name)
        with floci_forward() as base:
            for key in secret['data']:
                seed(base, source_name(namespace, name, key), value_of(secret, key))
        external_secret(namespace, name, list(secret['data']), secret.get('type', 'Opaque'),
                        {'argocd.argoproj.io/secret-type': 'repository'} if namespace == 'argocd' else None)
    # The preview role extension is required once the control service exists.
    from install_preview_urls import configure_control_role
    configure_control_role()


def delivery():
    """Configure remote Actions and reviewed promotions through the control UI."""
    run_script('lab/setup_delivery_actions.py')
    from https_ingress import certificate, route
    route(*certificate()[:2])
    k('exec', 'deployment/lab-control', '-n', 'lab-control', '-c', 'api', '--',
      'python', 'lab/control-runtime/smoke.py')


def verify():
    """Require healthy control, source CI, judgement services and delivery targets."""
    (STATE / 'fresh-ready.json').unlink(missing_ok=True)
    for namespace, deployments in [('platform', ('gitea', 'delivery-runner', 'build-runner')),
                                   ('lab-control', ('lab-control', 'lab-control-oidc')),
                                   ('lab-models', ('judgement-service', 'judgement-service-million'))]:
        for name in deployments:
            k('rollout', 'status', 'deployment/' + name, '-n', namespace, '--timeout=180s')
    k('exec', 'deployment/lab-control', '-n', 'lab-control', '-c', 'api', '--',
      'python', 'lab/control-runtime/smoke.py')
    for target in ('integration', 'staging', 'production'):
        k('exec', 'deployment/lab-control', '-n', 'lab-control', '-c', 'api', '--',
          'python', 'lab/delivery_cli.py', 'verify', target)
    private_json(STATE / 'fresh-ready.json', {'ready': True, 'verified_at': time.time(),
        'catalogue': 'esci-gb-v1', 'judge': 'CPU abstaining', 'research_models': False})
    print('Verified CPU lab. Browser DNS and certificate trust remain workstation setup steps.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=APPLICATIONS)
    args = parser.parse_args()
    assert_fresh()
    with forwards():
        globals()[args.stage]()


if __name__ == '__main__':
    main()
