"""Run a finite Gatling Job in the lab cluster with no Kubernetes API credential."""
from catalogue import DEFAULT_RELEASE, RELEASES
import hashlib
import base64
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid

from common import IN_CLUSTER, ROOT, STATE, apply, guard, k, record
from compare_search import definition, immutable_blob
from gatling_report import summarise
from run_gatling import IMAGE, SIMULATION, archive, retain_workload
from traffic import compile_profile
from input_selection import DEFAULTS, fetch_manifest

NAMESPACE = 'lab-evaluation'
OWNED_LABEL = {'app.kubernetes.io/managed-by': 'lab-control-gatling'}
DELIVERY_LABEL = {'app.kubernetes.io/managed-by': 'lab-delivery-gatling'}
TARGETS = {'baseline': 'retail-baseline', 'candidate': 'retail-candidate'}


def workload_parts(files, prefix):
    """Transport large CSVs in bounded ConfigMaps and reconstruct their exact bytes."""
    configs, commands = [], []
    for filename, payload in sorted(files.items()):
        if not filename.endswith('.csv') or not all(c.isalnum() or c in '-.' for c in filename):
            raise ValueError('Unsafe workload filename.')
        keys = []
        for offset in range(0, len(payload), 512 * 1024):
            key = 'part-' + str(len(configs)).zfill(5)
            keys.append('/workload-parts/' + key)
            configs.append({'name': prefix + '-' + str(len(configs)),
                            'binaryData': {key: base64.b64encode(payload[offset:offset + 512 * 1024]).decode()}})
        if not keys:
            raise ValueError('Empty workload file.')
        commands.append('cat ' + ' '.join(keys) + ' > /workload/' + filename)
    return configs, ' && '.join(commands)


def local_copy_target(path, root=ROOT, in_cluster=IN_CLUSTER):
    """kubectl cp needs a drive-free path on Windows, including an external state directory."""
    return str(path) if in_cluster else os.path.relpath(path, root).replace('\\', '/')


def cleanup_orphans():
    """Remove only resources owned by interrupted control comparisons."""
    if not IN_CLUSTER:
        return False
    from lifecycle import Store
    store = Store(STATE / 'lifecycle.sqlite3')
    if any(row['mode'] == 'performance' and row['state'] == 'running'
           for row in store.all_comparisons()):
        return False
    selector = 'app.kubernetes.io/managed-by=lab-control-gatling'
    for resource in ('jobs', 'pods', 'configmaps', 'pvc'):
        k('delete', resource, '-l', selector, '-n', NAMESPACE,
          '--ignore-not-found', '--wait=true')
    return True


def run(profile, target, environment=None, release_id=DEFAULT_RELEASE, owner='control'):
    guard()
    if owner not in ('control', 'delivery'):
        raise ValueError('Unknown Gatling Job owner.')
    owned_label = OWNED_LABEL if owner == 'control' else DELIVERY_LABEL
    environment = environment or TARGETS[target]
    pinned = definition(environment)
    catalogue = fetch_manifest('catalogue', DEFAULTS[release_id]['catalogue'])
    if pinned['dataset_sha256'] != catalogue['content']['sha256']:
        raise ValueError('Gatling workload and environment must use the same frozen catalogue.')
    workload = compile_profile(profile, release_id)
    short = uuid.uuid4().hex[:8]
    name = 'gatling-' + short
    run_dir = STATE / 'gatling-jobs' / short
    run_dir.mkdir(parents=True, exist_ok=False)
    apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE}})
    project = ROOT / 'lab/gatling'
    data = {'pom.xml': (project / 'pom.xml').read_text(encoding='utf-8'),
            'Simulation.java': (project / 'src/test/java/lab/relevance/SyntheticSearchSimulation.java').read_text(encoding='utf-8'),
            'run-job.sh': (project / 'run-job.sh').read_text(encoding='utf-8')}
    source_name, workload_name = name + '-source', name + '-workload'
    claim = name + '-results'
    source = STATE / 'workloads' / workload['workload_sha256']
    workload_files = {path.name: path.read_bytes() for path in source.glob('*.csv')}
    parts, restore = workload_parts(workload_files, workload_name)
    job = {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': name, 'namespace': NAMESPACE,
        'labels': {**owned_label, 'lab': 'gatling', 'profile': profile, 'target': target}},
        'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': workload['duration_seconds'] + 480,
            'template': {'metadata': {'labels': {'lab': 'gatling'}},
                'spec': {'automountServiceAccountToken': False, 'restartPolicy': 'Never',
                'initContainers': [{'name': 'prepare', 'image': IMAGE,
                    'command': ['sh', '-ec', 'mkdir -p /workspace/src/test/java/lab/relevance && cp /source/pom.xml /workspace/pom.xml && cp /source/Simulation.java /workspace/src/test/java/lab/relevance/SyntheticSearchSimulation.java && ' + restore],
                    'volumeMounts': [{'name': 'project', 'mountPath': '/workspace'},
                                     {'name': 'source', 'mountPath': '/source'},
                                     {'name': 'workload-parts', 'mountPath': '/workload-parts'},
                                     {'name': 'workload', 'mountPath': '/workload'}]}],
                'containers': [{'name': 'gatling', 'image': IMAGE, 'workingDir': '/workspace',
                    'command': ['sh', '/source/run-job.sh'],
                    'env': [{'name': 'LAB_BASE_URL',
                             'value': 'http://search.' + environment + '.svc.cluster.local:8080'},
                            {'name': 'LAB_TRAFFIC_PROFILE', 'value': profile}],
                    'resources': {'requests': {'cpu': '500m', 'memory': '512Mi'},
                                  'limits': {'cpu': '2', 'memory': '2Gi'}},
                    'volumeMounts': [{'name': 'project', 'mountPath': '/workspace'},
                                     {'name': 'source', 'mountPath': '/source'},
                                     {'name': 'workload', 'mountPath': '/workload'},
                                     {'name': 'results', 'mountPath': '/results'}]}],
                'volumes': [{'name': 'project', 'emptyDir': {}},
                            {'name': 'results', 'persistentVolumeClaim': {'claimName': claim}},
                            {'name': 'source', 'configMap': {'name': source_name}},
                            {'name': 'workload', 'emptyDir': {}},
                            {'name': 'workload-parts', 'projected': {'sources': [
                                {'configMap': {'name': part['name']}} for part in parts]}}]}}}}
    started = time.monotonic()
    try:
        apply({'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim',
               'metadata': {'name': claim, 'namespace': NAMESPACE, 'labels': owned_label},
               'spec': {'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': '1Gi'}}}})
        k('create', '-f', '-', body={'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'name': source_name, 'namespace': NAMESPACE,
                         'labels': owned_label}, 'data': data})
        for part in parts:
            k('create', '-f', '-', body={'apiVersion': 'v1', 'kind': 'ConfigMap',
                'metadata': {'name': part['name'], 'namespace': NAMESPACE,
                             'labels': owned_label}, 'binaryData': part['binaryData']})
        apply(job)
        k('wait', '--for=condition=complete', 'job/' + name, '-n', NAMESPACE,
          '--timeout=' + str(workload['duration_seconds'] + 480) + 's')
        pods = json.loads(k('get', 'pods', '-n', NAMESPACE, '-l', 'job-name=' + name, '-o', 'json').stdout)['items']
        if len(pods) != 1:
            raise RuntimeError('Expected one Gatling Job pod.')
        pod = pods[0]['metadata']['name']
        logs = k('logs', 'pod/' + pod, '-n', NAMESPACE).stdout
        (run_dir / 'runner.log').write_text(logs, encoding='utf-8')
        reader = name + '-reader'
        apply({'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': reader, 'namespace': NAMESPACE,
               'labels': owned_label},
               'spec': {'automountServiceAccountToken': False, 'restartPolicy': 'Never',
                   'containers': [{'name': 'reader', 'image': IMAGE, 'command': ['sleep', '600'],
                                   'volumeMounts': [{'name': 'results', 'mountPath': '/results'}]}],
                   'volumes': [{'name': 'results', 'persistentVolumeClaim': {'claimName': claim}}]}})
        k('wait', '--for=condition=ready', 'pod/' + reader, '-n', NAMESPACE, '--timeout=120s')
        # kubectl cp treats a Windows drive-letter colon as a remote separator.
        if IN_CLUSTER:
            k('cp', '-n', NAMESPACE, reader + ':/results/report', str(run_dir / 'report'))
            k('cp', '-n', NAMESPACE, reader + ':/results/arrivals.csv', str(run_dir / 'arrivals.csv'))
        else:
            # Stage beside this checkout when retained state is on another drive.
            with tempfile.TemporaryDirectory(prefix='gatling-copy-', dir=ROOT) as temporary:
                staging = Path(temporary)
                k('cp', '-n', NAMESPACE, reader + ':/results/report', local_copy_target(staging / 'report'))
                k('cp', '-n', NAMESPACE, reader + ':/results/arrivals.csv', local_copy_target(staging / 'arrivals.csv'))
                shutil.copytree(staging / 'report', run_dir / 'report')
                shutil.copy2(staging / 'arrivals.csv', run_dir / 'arrivals.csv')
        reports = list((run_dir / 'report').glob('syntheticsearchsimulation-*'))
        if len(reports) != 1:
            raise RuntimeError('Expected one copied Gatling native report.')
        summary = summarise(reports[0], source, run_dir / 'arrivals.csv')
        summary.update({'run_id': short, 'target': target, 'environment': environment,
            'release_id': release_id,
            'fingerprint': pinned['fingerprint'], 'index': pinned['index'], 'image': pinned['image'],
            'runner_image': IMAGE, 'gatling_version': '3.15.1', 'maven_plugin': '4.21.12',
            'simulation_sha256': hashlib.sha256(SIMULATION.read_bytes()).hexdigest(),
            'duration_wall_seconds': round(time.monotonic() - started, 3), 'runner_exit_code': 0,
            'runner_limits': {'cpu': 2, 'memory': '2Gi'},
            'host': 'Kubernetes control Pod / local k3d' if IN_CLUSTER else 'Windows 11 / local k3d',
            'execution': 'finite Kubernetes Job', 'job_name': name})
        summary.update(retain_workload(workload))
        files = {str(path.relative_to(reports[0])).replace('\\', '/'): path.read_bytes()
                 for path in reports[0].rglob('*') if path.is_file()}
        files['arrivals.csv'] = (run_dir / 'arrivals.csv').read_bytes()
        files['runner.log'] = logs.encode()
        files['simulation.java'] = SIMULATION.read_bytes()
        files['pom.xml'] = (ROOT / 'lab/gatling/pom.xml').read_bytes()
        files['run-job.sh'] = (ROOT / 'lab/gatling/run-job.sh').read_bytes()
        payload = archive(files)
        digest = hashlib.sha256(payload).hexdigest()
        summary['native_report_sha256'] = digest
        summary['native_report_blob'] = immutable_blob('runs', digest + '/gatling-report.zip', payload)
        record('gatling-job-' + profile + '-' + target + '-' + short, summary)
        return summary
    except Exception as error:
        pods_result = k('get', 'pods', '-n', NAMESPACE, '-l', 'job-name=' + name, '-o', 'json', check=False)
        if pods_result.returncode == 0:
            for pod in json.loads(pods_result.stdout)['items']:
                logs_result = k('logs', 'pod/' + pod['metadata']['name'], '-n', NAMESPACE, check=False)
                (run_dir / 'failure.log').write_text(logs_result.stdout + logs_result.stderr, encoding='utf-8')
        record('gatling-job-failure-' + short, {'profile': profile, 'target': target,
            'environment': environment, 'job_name': name,
            'error_kind': type(error).__name__, 'error': str(error)[:500]})
        raise
    finally:
        k('delete', 'pod/' + name + '-reader', '-n', NAMESPACE, '--ignore-not-found', '--wait=true', check=False)
        k('delete', 'job/' + name, '-n', NAMESPACE, '--ignore-not-found', '--wait=true', check=False)
        for config in [source_name, *(part['name'] for part in parts)]:
            k('delete', 'configmap/' + config, '-n', NAMESPACE, '--ignore-not-found', check=False)
        k('delete', 'pvc/' + claim, '-n', NAMESPACE, '--ignore-not-found', '--wait=true', check=False)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', choices=('probe', 'smoke', 'normal', 'peak', 'stress',
                                            'normal-full', 'sustained-peak', 'stress-full', 'production-load'))
    parser.add_argument('target', choices=TARGETS)
    parser.add_argument('--release', choices=RELEASES, default=DEFAULT_RELEASE)
    parser.add_argument('--environment', help='Ready namespace to test; baseline/candidate identifies the report side')
    args = parser.parse_args()
    print(json.dumps(run(args.profile, args.target, release_id=args.release, environment=args.environment), indent=2))
