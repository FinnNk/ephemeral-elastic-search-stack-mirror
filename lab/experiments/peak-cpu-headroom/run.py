"""Compare CPU quotas in disposable instrumented copies of one frozen API."""
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

import common
from common import ROOT, STATE, apply, guard, k

HERE = Path(__file__).resolve().parent
SOURCE = 'lab-delivery-run-204-611a583c'
WORKLOAD = '15e39a2502c5ceb99baab11b2ff5d1ada1f9ba011dbba92227d2f45760c6a566'
LABEL = 'lab-peak-cpu-headroom'


def timing_method():
    tree = ast.parse((ROOT / 'lab/search-app/app.py').read_text(encoding='utf-8'))
    handler = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Handler')
    method = next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == 'search_index')
    return ast.unparse(method) + '\n'


def resource_refs(spec):
    refs = {'secrets': set(), 'configmaps': set()}
    refs['secrets'].update(r['name'] for r in spec.get('imagePullSecrets', []))
    for volume in spec.get('volumes', []):
        if 'secret' in volume:
            refs['secrets'].add(volume['secret']['secretName'])
        if 'configMap' in volume:
            refs['configmaps'].add(volume['configMap']['name'])
    for container in spec.get('containers', []) + spec.get('initContainers', []):
        for env in container.get('env', []):
            value = env.get('valueFrom', {})
            for key, resource in (('secretKeyRef', 'secrets'), ('configMapKeyRef', 'configmaps')):
                if key in value:
                    refs[resource].add(value[key]['name'])
        for env in container.get('envFrom', []):
            for key, resource in (('secretRef', 'secrets'), ('configMapRef', 'configmaps')):
                if key in env:
                    refs[resource].add(env[key]['name'])
    return refs


def idle():
    script = ("import sqlite3; from delivery_operations import Operations; "
              "c=sqlite3.connect('/state/lifecycle.sqlite3'); "
              "assert not Operations().active(); "
              "assert c.execute(\"select count(*) from comparisons where state='running'\").fetchone()[0]==0; "
              "assert c.execute(\"select count(*) from environments where state in ('requested','provisioning','deleting')\").fetchone()[0]==0")
    k('exec', 'deployment/lab-control', '-n', 'lab-control', '-c', 'api', '--', 'python', '-c', script)


def clean_metadata(obj, namespace, identifier):
    obj = deepcopy(obj)
    obj['metadata'] = {'name': obj['metadata']['name'], 'namespace': namespace,
                       'labels': {'app.kubernetes.io/managed-by': LABEL, 'diagnostic-id': identifier}}
    obj.pop('status', None)
    return obj


def preview(namespace, quota, identifier, original, node):
    labels = {'app.kubernetes.io/managed-by': LABEL, 'diagnostic-id': identifier}
    apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': namespace, 'labels': labels}})
    deployment = clean_metadata(original, namespace, identifier)
    template = deployment['spec']['template']
    template['metadata'] = {'labels': {'app': 'search', **labels}}
    deployment['spec']['selector'] = {'matchLabels': {'app': 'search'}}
    deployment['spec']['replicas'] = 1
    spec = template['spec']
    spec['nodeName'] = node
    spec['automountServiceAccountToken'] = False
    optional_maps = {v['configMap']['name'] for v in spec.get('volumes', [])
                     if v.get('configMap', {}).get('optional')}
    for resource, names in resource_refs(spec).items():
        for name in sorted(names):
            raw = k('get', resource + '/' + name, '-n', SOURCE, '-o', 'json', '--ignore-not-found').stdout
            if not raw and resource == 'configmaps' and name in optional_maps:
                continue
            if not raw:
                raise ValueError('Missing required diagnostic dependency: ' + resource + '/' + name)
            source = json.loads(raw)
            apply(clean_metadata(source, namespace, identifier))
    app = spec['containers'][0]
    app['command'] = ['python', '/diagnostic/server.py']
    app.pop('args', None)
    app['resources']['limits']['cpu'] = quota
    app['env'] = [e for e in app.get('env', []) if e['name'] != 'LAB_DEPLOYMENT_TIER'] + [
        {'name': 'LAB_DEPLOYMENT_TIER', 'value': namespace}]
    app.setdefault('volumeMounts', []).append({'name': 'diagnostic', 'mountPath': '/diagnostic', 'readOnly': True})
    spec.setdefault('volumes', []).append({'name': 'diagnostic', 'configMap': {'name': 'diagnostic'}})
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'diagnostic', 'namespace': namespace},
           'data': {'server.py': (HERE / 'server.py').read_text(), 'search_index.py': timing_method()}})
    policies = json.loads(k('get', 'networkpolicies', '-n', SOURCE, '-o', 'json').stdout)['items']
    for policy in policies:
        apply(clean_metadata(policy, namespace, identifier))
    apply({'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'search', 'namespace': namespace},
           'spec': {'selector': {'app': 'search'}, 'ports': [{'port': 8080}]}})
    apply(deployment)
    k('rollout', 'status', 'deployment/search', '-n', namespace, '--timeout=180s')


def counters(namespace, target='deployment/search', container=None):
    args = ['exec', target, '-n', namespace]
    if container:
        args += ['-c', container]
    data = k(*args, '--', 'cat', '/sys/fs/cgroup/cpu.stat').stdout
    cpu = {line.split()[0]: int(line.split()[1]) for line in data.splitlines()}
    return cpu


def redis_access(identifier):
    """Allow only these owned previews to use the shared rewrite dependency."""
    return {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
            'metadata': {'name': 'redis-diagnostic-' + identifier, 'namespace': 'platform',
                         'labels': {'app.kubernetes.io/managed-by': LABEL, 'diagnostic-id': identifier}},
            'spec': {'podSelector': {'matchLabels': {'app': 'lab-redis'}},
                     'policyTypes': ['Ingress'], 'ingress': [{'from': [{'namespaceSelector': {
                         'matchLabels': {'app.kubernetes.io/managed-by': LABEL, 'diagnostic-id': identifier}}}],
                         'ports': [{'protocol': 'TCP', 'port': 6379}]}]}}


def check_redis(namespace):
    script = ("import os; from rewrite_lookup import client; "
              "c=client(os.environ['REWRITE_REDIS_HOST']); "
              "c.hget(os.environ['REWRITE_REDIS_KEY'], 'sneakers'); "
              "print('Redis HGET completed without fallback')")
    k('exec', 'deployment/search', '-n', namespace, '--', 'python', '-c', script)


def replay(config):
    script = (HERE / 'driver.py').read_text(encoding='utf-8')
    command = common.KUBE + ['exec', '-i', 'deployment/lab-control', '-n', 'lab-control',
                             '-c', 'api', '--', 'python', '-', json.dumps(config)]
    started = time.monotonic()
    summary = None
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, encoding='utf-8') as process:
        process.stdin.write(script)
        process.stdin.close()
        for line in process.stdout:
            event = json.loads(line)
            print(json.dumps({'label': config['label'], **event}), flush=True)
            summary = event.get('summary', summary)
        error = process.stderr.read()
        code = process.wait(timeout=30)
        if code or summary is None:
            raise RuntimeError('Diagnostic driver failed: ' + error[-1000:])
    if time.monotonic() - started > config['seconds'] + 90:
        raise RuntimeError('Diagnostic driver exceeded its expected window.')
    return summary


def run(server, seconds):
    common.KUBE += ['--server=' + server]
    guard()
    idle()
    identifier = uuid.uuid4().hex[:8]
    names = [(f'lab-peak-cpu-{identifier}-250m', '250m'), (f'lab-peak-cpu-{identifier}-1000m', '1')]
    directory = STATE / 'experiments/peak-cpu-headroom' / identifier
    directory.mkdir(parents=True)
    original = json.loads(k('get', 'deployment/search', '-n', SOURCE, '-o', 'json').stdout)
    pods = json.loads(k('get', 'pods', '-n', SOURCE, '-l', 'app=search', '-o', 'json').stdout)['items']
    node = pods[0]['spec']['nodeName']
    parent = json.loads(json.loads(k('get', 'configmap/frozen-definition', '-n', SOURCE,
                                    '-o', 'json').stdout)['data']['definition.json'])
    result = {'kind': 'isolated-cpu-headroom-diagnostic', 'id': identifier,
              'started_at': datetime.now(timezone.utc).isoformat(), 'parent': parent,
              'source_namespace': SOURCE, 'image': original['spec']['template']['spec']['containers'][0]['image'],
              'node': node, 'workload_sha256': WORKLOAD, 'rate': 20, 'seconds': seconds,
              'method_sha256': hashlib.sha256(timing_method().encode()).hexdigest(), 'runs': []}
    remote_dir = '/state/experiments/peak-cpu-headroom/' + identifier
    print(json.dumps({'experiment': identifier, 'directory': str(directory), 'namespaces': names}), flush=True)
    try:
        apply(redis_access(identifier))
        for namespace, quota in names:
            preview(namespace, quota, identifier, original, node)
            check_redis(namespace)
        for namespace, quota in names:
            idle()
            config = {'url': 'http://search.' + namespace + '.svc.cluster.local:8080',
                      'fixture': '/state/workloads/' + WORKLOAD + '/warmup.csv',
                      'seconds': 60, 'rate': 10, 'directory': remote_dir, 'label': namespace + '-warmup'}
            replay(config)
            before = {'api': counters(namespace), 'elasticsearch': counters('platform', 'shared-es-lab-0', 'elasticsearch')}
            began = time.monotonic()
            config.update(fixture='/state/workloads/' + WORKLOAD + '/peak.csv', seconds=seconds,
                          rate=20, label=namespace)
            summary = replay(config)
            elapsed = time.monotonic() - began
            after = {'api': counters(namespace), 'elasticsearch': counters('platform', 'shared-es-lab-0', 'elasticsearch')}
            delta = {name: {key: after[name][key] - value for key, value in data.items()}
                     for name, data in before.items()}
            for row in delta.values():
                row['average_cores'] = round(row['usage_usec'] / 1e6 / elapsed, 4)
                row['throttled_period_fraction'] = round(row['nr_throttled'] / max(1, row['nr_periods']), 4)
            result['runs'].append({'namespace': namespace, 'quota': quota, 'summary': summary, 'cpu_delta': delta})
            (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        result['complete'] = True
    finally:
        result['ended_at'] = datetime.now(timezone.utc).isoformat()
        result['cleanup'] = []
        policy = 'networkpolicy/redis-diagnostic-' + identifier
        raw = k('get', policy, '-n', 'platform', '-o', 'json', '--ignore-not-found').stdout
        if raw:
            if json.loads(raw)['metadata'].get('labels', {}).get('diagnostic-id') != identifier:
                raise RuntimeError('Refusing to remove a policy with different diagnostic ownership.')
            k('delete', policy, '-n', 'platform')
        for namespace, _ in names:
            resource = k('get', 'namespace/' + namespace, '-o', 'json', '--ignore-not-found').stdout
            if resource:
                metadata = json.loads(resource)['metadata']
                if metadata.get('labels', {}).get('diagnostic-id') != identifier:
                    raise RuntimeError('Refusing to remove a namespace with different diagnostic ownership.')
                k('delete', 'namespace/' + namespace, '--wait=false')
            result['cleanup'].append(namespace)
        (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'result': result, 'file': str(directory / 'result.json')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--seconds', type=int, default=900)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 900:
        parser.error('Use between 30 and 900 measured seconds per arm.')
    run(args.server, args.seconds)
