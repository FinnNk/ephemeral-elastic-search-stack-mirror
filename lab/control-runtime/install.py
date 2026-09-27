"""Stage and cut over the local control runtime without copying host credentials."""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lab'))
from common import KUBE, STATE, guard, k

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from identity import digest as identity_digest
NAMESPACE = 'lab-control'
TRANSFER = 'control-state-transfer'
GITEA_INTERNAL = 'http://gitea-http.platform.svc.cluster.local:31800'
COPIED = ('releases', 'state-source', 'delivery-state', 'delivery-source',
          'delivery', 'evidence', 'workloads')


def apply(payload):
    result = subprocess.run(KUBE + ['apply', '-f', '-'], input=json.dumps(payload),
                            text=True, capture_output=True, encoding='utf-8', cwd=ROOT)
    if result.returncode:
        raise RuntimeError(result.stderr[-1200:])
    return result.stdout.strip()


def set_secret(name, filename, value):
    return apply({'apiVersion': 'v1', 'kind': 'Secret',
                  'metadata': {'name': name, 'namespace': NAMESPACE},
                  'type': 'Opaque', 'stringData': {filename: json.dumps(value)}})


def prepare_config(image, baseline_run):
    if not image.startswith('nexus.localhost:18185/lab-control@sha256:'):
        raise ValueError('Use a digest-pinned lab-control image from Nexus.')
    if type(baseline_run) is not int or baseline_run <= 0:
        raise ValueError('A successful baseline run ID is required.')
    cluster_uid = json.loads(k('get', 'namespace', 'kube-system', '-o', 'json').stdout)['metadata']['uid']
    data = {
        'LAB_CLUSTER_UID': cluster_uid,
        'LAB_PR_BASELINE_RUN': str(baseline_run),
        'LAB_CONTROL_BIND': '0.0.0.0',
        'LAB_CONTROL_PUBLIC_URL': 'http://localhost:18082',
        'LAB_GITEA_API_URL': GITEA_INTERNAL + '/api/v1',
        'LAB_GITEA_GIT_URL': GITEA_INTERNAL,
        'LAB_ELASTICSEARCH_URL': 'https://shared-es-http.platform.svc.cluster.local:9200',
        'LAB_BLOB_ACCOUNT_URL': 'http://floci.platform.svc.cluster.local:4577/devstoreaccount1',
        'LAB_BLOB_POD_URL': 'http://floci.platform.svc.cluster.local:4577/devstoreaccount1',
        'LAB_BLOB_EMULATOR': '1',
        'LAB_NEXUS_API_URL': 'http://nexus.platform.svc.cluster.local:8081',
        'LAB_SNAPSHOT_REPOSITORY': 'lab-s3',
        'HELM_CACHE_HOME': '/state/helm-cache',
        'HELM_CONFIG_HOME': '/state/helm-config',
        'HELM_DATA_HOME': '/state/helm-data',
    }
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap',
           'metadata': {'name': 'lab-control-config', 'namespace': NAMESPACE}, 'data': data})
    source = json.loads((STATE / 'credentials.json').read_text(encoding='utf-8'))
    runtime = {key: source[key] for key in ('agent', 'build_token', 'read_token', 'delivery_read_token')}
    set_secret('lab-control-gitea', 'credentials.json', runtime)
    nexus = json.loads((STATE / 'nexus.json').read_text(encoding='utf-8'))
    set_secret('lab-control-nexus', 'nexus.json', {'reader': nexus['reader']})
    from setup_nexus import image_secret
    image_secret(NAMESPACE)
    return cluster_uid


def base():
    guard()
    result = subprocess.run(KUBE + ['apply', '-f', str(HERE / 'base.yaml')],
                            capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    if result.returncode:
        raise RuntimeError(result.stderr[-1200:])


def transfer_pod(image):
    payload = {'apiVersion': 'v1', 'kind': 'Pod',
               'metadata': {'name': TRANSFER, 'namespace': NAMESPACE},
               'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                        'imagePullSecrets': [{'name': 'nexus-read'}],
                        'securityContext': {'runAsUser': 10001, 'runAsGroup': 10001,
                                            'fsGroup': 10001},
                        'containers': [{'name': 'copy',
                                        'image': image,
                                        'command': ['sleep', '3600'],
                                        'volumeMounts': [{'name': 'state', 'mountPath': '/state'}]}],
                        'volumes': [{'name': 'state', 'persistentVolumeClaim':
                                    {'claimName': 'lab-control-state'}}]}}
    result = subprocess.run(KUBE + ['create', '-f', '-'], input=json.dumps(payload),
                            text=True, capture_output=True, encoding='utf-8', cwd=ROOT)
    if result.returncode and 'AlreadyExists' not in result.stderr:
        raise RuntimeError(result.stderr[-1200:])
    k('wait', '--for=condition=ready', 'pod/' + TRANSFER, '-n', NAMESPACE, '--timeout=120s')


def write_bundle(path):
    mandatory = ('releases', 'state-source', 'delivery-state', 'delivery', 'evidence')
    if any(not (STATE / name).exists() for name in mandatory):
        raise ValueError('Control state is incomplete; supply the retained state bundle first.')
    with tarfile.open(path, 'w:gz') as archive:
        for name in COPIED:
            source = STATE / name
            if not source.exists():
                continue
            for member in source.rglob('*'):
                if member.is_file() and '__pycache__' not in member.parts:
                    archive.add(member, arcname=member.relative_to(STATE).as_posix(), recursive=False)
        source = STATE / 'lifecycle.sqlite3'
        if source.exists():
            with tempfile.TemporaryDirectory(prefix='lab-control-db-') as temp:
                target = Path(temp) / source.name
                with closing(sqlite3.connect(source)) as live, closing(sqlite3.connect(target)) as backup:
                    live.backup(backup)
                archive.add(target, arcname=source.name, recursive=False)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_bundle(path):
    """Seed a fresh checkout from an operator-supplied state archive."""
    if any((STATE / name).exists() for name in COPIED + ('lifecycle.sqlite3',)):
        raise ValueError('State already exists; import only into a fresh checkout.')
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        for member in members:
            parts = Path(member.name).parts
            if not parts or any(part in ('.', '..') for part in parts) or \
                    parts[0] not in COPIED + ('lifecycle.sqlite3',) or \
                    member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise ValueError('State archive contains an unexpected entry.')
        archive.extractall(STATE, members=members, filter='data')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transfer(image):
    transfer_pod(image)
    expected_identity = identity_digest(STATE / 'lifecycle.sqlite3')
    with tempfile.TemporaryDirectory(prefix='lab-control-state-') as temporary:
        archive = Path(temporary) / 'state.tar.gz'
        checksum = write_bundle(archive)
        with archive.open('rb') as source:
            result = subprocess.run(KUBE + ['exec', '-i', '-n', NAMESPACE, TRANSFER,
                                            '--', 'tar', '-xz', '-C', '/state'],
                                    stdin=source, capture_output=True, cwd=ROOT)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace')[-1200:])
    observed_identity = k('exec', '-n', NAMESPACE, TRANSFER, '--', 'python',
        'lab/control-runtime/identity.py', '/state/lifecycle.sqlite3').stdout.strip()
    if observed_identity != expected_identity:
        raise ValueError('Migrated control identities differ from the retained host backup.')
    for repo in ('state-source', 'delivery-state', 'delivery-source'):
        if (STATE / repo / '.git').exists():
            k('exec', '-n', NAMESPACE, TRANSFER, '--', 'git', '-C', '/state/' + repo,
              'remote', 'set-url', 'origin', GITEA_INTERNAL + '/elastic-agent/' +
              ('environment-state' if repo == 'state-source' else repo) + '.git')
            # Windows checkouts retain CRLF files; Linux must clean them as input.
            k('exec', '-n', NAMESPACE, TRANSFER, '--', 'git', '-C', '/state/' + repo,
              'config', '--local', 'core.autocrlf', 'input')
    return checksum


def release_transfer_pod():
    k('delete', 'pod/' + TRANSFER, '-n', NAMESPACE, '--ignore-not-found', '--wait=true')


def bind_existing_namespaces():
    names = [item['metadata']['name'] for item in json.loads(k('get', 'namespaces', '-o', 'json').stdout)['items']]
    for name in names:
        if name.startswith(('lab-', 'retail-', 'spike-')) and name != NAMESPACE:
            apply({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding',
                   'metadata': {'name': 'lab-control-runtime', 'namespace': name},
                   'roleRef': {'apiGroup': 'rbac.authorization.k8s.io',
                               'kind': 'ClusterRole', 'name': 'lab-control-environment'},
                   'subjects': [{'kind': 'ServiceAccount', 'name': 'lab-control',
                                 'namespace': NAMESPACE}]})
        if name in ('lab-delivery-integration', 'lab-delivery-staging',
                    'lab-delivery-production'):
            # Historical frozen release bundles retain their older chart. An
            # installer-owned policy admits the relocated verifier without
            # changing the release or the protected desired-state branch.
            apply({'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
                   'metadata': {'name': 'control-search-ingress', 'namespace': name},
                   'spec': {'podSelector': {}, 'policyTypes': ['Ingress'],
                            'ingress': [{'from': [{'namespaceSelector': {'matchLabels': {
                                'kubernetes.io/metadata.name': NAMESPACE}},
                                'podSelector': {'matchLabels': {'app': 'lab-control'}}}],
                                'ports': [{'port': 8080, 'protocol': 'TCP'}]}]}})


def staged(image, baseline_run):
    base()
    prepare_config(image, baseline_run)
    bind_existing_namespaces()
    active = k('get', 'deployment/lab-control', '-n', NAMESPACE, check=False).returncode == 0
    return {'image': image, 'baseline_run': baseline_run, 'active': active}


def operation_idle():
    with sqlite3.connect(STATE / 'lifecycle.sqlite3') as database:
        environments = database.execute("SELECT count(*) FROM environments WHERE state IN ('requested','provisioning','deleting')").fetchone()[0]
        comparisons = database.execute("SELECT count(*) FROM comparisons WHERE state='running'").fetchone()[0]
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', 18086))
            delivery = False
        except OSError:
            delivery = True
    return environments == 0 and comparisons == 0 and not delivery


def host_controls():
    import psutil
    scripts = {'control_api.py', 'reconcile_leases.py', 'pr_workflow.py', 'delivery_cli.py'}
    found = []
    for process in psutil.process_iter(['pid', 'cmdline']):
        try:
            command = process.info['cmdline'] or []
            if process.cwd().lower() != str(ROOT).lower():
                continue
            if any(Path(part).name in scripts and ('lab/' in part.replace('\\', '/') or
                    part in ('lab/control_api.py', 'lab/reconcile_leases.py',
                             'lab/pr_workflow.py', 'lab/delivery_cli.py')) for part in command):
                found.append(process)
        except (psutil.Error, OSError):
            continue
    return found


def pause_host():
    drain = STATE / 'control-drain'
    drain.write_text('Kubernetes control cutover in progress.\n', encoding='utf-8')
    deadline = time.monotonic() + 120
    while not operation_idle():
        if time.monotonic() >= deadline:
            drain.unlink(missing_ok=True)
            raise TimeoutError('Host controls have not become idle; cutover cancelled.')
        time.sleep(2)
    processes = host_controls()
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=20)
        except Exception:
            raise RuntimeError('A host control process did not stop; inspect before activating.')
    if host_controls():
        raise RuntimeError('A host control process is still running.')


def resume_host(baseline_run):
    (STATE / 'control-drain').unlink(missing_ok=True)
    for args in ([sys.executable, 'lab/start_control.py'],
                 [sys.executable, 'lab/start_pr_watch.py', '--baseline-run', str(baseline_run)],
                 [sys.executable, 'lab/start_delivery_watch.py']):
        subprocess.run(args, cwd=ROOT, check=True, capture_output=True)


def browser_forward():
    stop_browser_forward()
    output = (STATE / 'control-forward.log').open('ab')
    kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else \
        {'start_new_session': True}
    process = subprocess.Popen([sys.executable, str(HERE / 'forward.py')],
        stdin=subprocess.DEVNULL, stdout=output, stderr=output, cwd=ROOT, **kwargs)
    output.close()
    (STATE / 'control-forward.pid').write_text(str(process.pid), encoding='utf-8')
    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError('Control browser port forward stopped.')
        try:
            with socket.create_connection(('127.0.0.1', 18082), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError('Control browser port forward did not open.')


def stop_browser_forward():
    pid_file = STATE / 'control-forward.pid'
    if not pid_file.exists():
        return
    import psutil
    try:
        process = psutil.Process(int(pid_file.read_text(encoding='utf-8')))
        command = ' '.join(process.cmdline())
        if 'forward.py' in command and 'control-runtime' in command:
            for child in process.children(recursive=True):
                child.terminate()
            process.terminate()
            process.wait(timeout=15)
    except (psutil.Error, ValueError):
        pass
    pid_file.unlink(missing_ok=True)


def export_bundle(path, image):
    """Export a quiescent control PVC and resume the same deployment."""
    if k('get', 'deployment/lab-control', '-n', NAMESPACE, check=False).returncode:
        raise ValueError('The Kubernetes control deployment is not active.')
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    k('exec', 'deployment/lab-control', '-n', NAMESPACE, '-c', 'api', '--',
      'touch', '/state/control-drain')
    scaled = False
    try:
        idle_script = ("import sqlite3,socket; c=sqlite3.connect('/state/lifecycle.sqlite3'); "
            "a=c.execute(\"select count(*) from environments where state in "
            "('requested','provisioning','deleting')\").fetchone()[0]; "
            "b=c.execute(\"select count(*) from comparisons where state='running'\").fetchone()[0]; "
            "s=socket.socket(); s.bind(('127.0.0.1',18086)); print(a,b)")
        deadline = time.monotonic() + 120
        while True:
            probe = k('exec', 'deployment/lab-control', '-n', NAMESPACE,
                '-c', 'api', '--', 'python', '-c', idle_script, check=False)
            if probe.returncode == 0 and probe.stdout.strip() == '0 0':
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Control work did not become idle; backup cancelled.')
            time.sleep(2)
        k('scale', 'deployment/lab-control', '-n', NAMESPACE, '--replicas=0')
        scaled = True
        deadline = time.monotonic() + 120
        while json.loads(k('get', 'pods', '-n', NAMESPACE, '-l', 'app=lab-control',
                           '-o', 'json').stdout)['items']:
            if time.monotonic() >= deadline:
                raise TimeoutError('Old control Pod did not release the state volume.')
            time.sleep(2)
        transfer_pod(image)
        entries = [name for name in COPIED if
                   k('exec', '-n', NAMESPACE, TRANSFER, '--', 'test', '-e',
                     '/state/' + name, check=False).returncode == 0]
        entries.append('lifecycle.sqlite3')
        with path.open('wb') as output:
            result = subprocess.run(KUBE + ['exec', '-n', NAMESPACE, TRANSFER,
                '--', 'tar', '-cz', '-C', '/state', *entries], stdout=output,
                stderr=subprocess.PIPE, cwd=ROOT)
        if result.returncode:
            path.unlink(missing_ok=True)
            raise RuntimeError(result.stderr.decode(errors='replace')[-800:])
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        (path.parent / (path.name + '.sha256')).write_text(checksum + '\n', encoding='ascii')
        return {'path': str(path), 'sha256': checksum}
    finally:
        if scaled:
            try:
                if k('get', 'pod/' + TRANSFER, '-n', NAMESPACE, check=False).returncode == 0:
                    k('exec', '-n', NAMESPACE, TRANSFER, '--', 'rm', '-f',
                      '/state/control-drain', check=False)
                release_transfer_pod()
            finally:
                k('scale', 'deployment/lab-control', '-n', NAMESPACE, '--replicas=1')
                k('rollout', 'status', 'deployment/lab-control', '-n', NAMESPACE,
                  '--timeout=180s')
        else:
            k('exec', 'deployment/lab-control', '-n', NAMESPACE, '-c', 'api',
              '--', 'rm', '-f', '/state/control-drain', check=False)
            k('rollout', 'restart', 'deployment/lab-control', '-n', NAMESPACE,
              check=False)


def activate(image, baseline_run):
    if k('get', 'deployment/lab-control', '-n', NAMESPACE, check=False).returncode == 0:
        raise ValueError('Control deployment already exists; inspect it before cutover.')
    result = staged(image, baseline_run)
    pause_host()
    try:
        result['state_bundle_sha256'] = transfer(image)
        release_transfer_pod()
        manifest = (HERE / 'deployment.yaml').read_text(encoding='utf-8').replace('__CONTROL_IMAGE__', image)
        response = subprocess.run(KUBE + ['apply', '-f', '-'], input=manifest, text=True,
                                  capture_output=True, encoding='utf-8', cwd=ROOT)
        if response.returncode:
            raise RuntimeError(response.stderr[-1200:])
        k('rollout', 'status', 'deployment/lab-control', '-n', NAMESPACE, '--timeout=180s')
        k('exec', 'deployment/lab-control', '-n', NAMESPACE, '-c', 'api', '--',
          'python', 'lab/control-runtime/smoke.py')
        browser_forward()
    except Exception:
        stop_browser_forward()
        k('delete', 'deployment/lab-control', '-n', NAMESPACE,
          '--ignore-not-found', '--wait=true', check=False)
        release_transfer_pod()
        resume_host(baseline_run)
        raise
    result['active'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('stage', 'activate', 'export', 'import'))
    parser.add_argument('--image')
    parser.add_argument('--baseline-run', type=int)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    if args.command == 'import':
        if not args.bundle:
            parser.error('import requires --bundle')
        result = {'state_bundle_sha256': import_bundle(args.bundle)}
    elif args.command == 'export':
        if not args.image or not args.bundle:
            parser.error('export requires --image and --bundle')
        result = export_bundle(args.bundle, args.image)
    else:
        if not args.image or not args.baseline_run:
            parser.error(args.command + ' requires --image and --baseline-run')
        if args.bundle:
            import_bundle(args.bundle)
        result = staged(args.image, args.baseline_run) if args.command == 'stage' else \
            activate(args.image, args.baseline_run)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
