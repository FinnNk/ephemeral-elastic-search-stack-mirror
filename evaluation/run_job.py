"""Run a digest-pinned evaluator Job with Blob-only egress and no API token."""

import argparse
import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get('LAB_STATE_DIR', ROOT / '.lab'))
NAMESPACE = 'lab-offline-evaluation'
KUBE = ['kubectl', '--kubeconfig', str(STATE / 'kubeconfig.yaml')]


def kubectl(*args, payload=None, check=True):
    result = subprocess.run(KUBE + list(args), cwd=ROOT,
                            input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, encoding='utf-8')
    if check and result.returncode:
        raise RuntimeError('kubectl failed: ' + result.stderr[-1000:])
    return result


def apply(value):
    kubectl('apply', '-f', '-', payload=value)


def reference(path, kind=None):
    value = json.loads(Path(path).read_bytes())
    if kind and value.get('kind') != kind:
        raise ValueError('Selected reference has the wrong artifact kind.')
    return value


def manifest_reference(path):
    path = Path(path)
    payload = path.read_bytes()
    value = json.loads(payload)
    kind = value['kind']
    if kind not in ('catalogue', 'query-suite', 'judgement-set'):
        raise ValueError('Unsupported evaluator input manifest.')
    digest = hashlib.sha256(payload).hexdigest()
    return {'sha256': digest, 'bytes': len(payload),
            'blob': f'datasets/manifests/{kind}/{digest}.json'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observation-reference', required=True, type=Path)
    parser.add_argument('--specification-reference', required=True, type=Path)
    parser.add_argument('--catalogue-manifest', required=True, type=Path)
    parser.add_argument('--query-manifest', required=True, type=Path)
    parser.add_argument('--judgement-manifest', required=True, type=Path)
    parser.add_argument('--evaluated-at')
    args = parser.parse_args()
    if args.evaluated_at and datetime.fromisoformat(args.evaluated_at.replace('Z', '+00:00')).utcoffset() is None:
        raise ValueError('Evaluation time must include a UTC offset.')
    if kubectl('config', 'current-context').stdout.strip() != 'k3d-relevance-lab':
        raise ValueError('Evaluator requires the named local lab cluster.')
    connection = os.environ.get('DATA_BLOB_CONNECTION_STRING', '')
    if 'AccountName=devstoreaccount1;' not in connection or \
            'BlobEndpoint=http://127.0.0.1:14577/devstoreaccount1;' not in connection:
        raise ValueError('Supply the explicit local Floci connection.')
    connection = connection.replace('BlobEndpoint=http://127.0.0.1:14577/devstoreaccount1;',
        'BlobEndpoint=http://floci.platform.svc.cluster.local:4577/devstoreaccount1;')
    image = reference(STATE / 'tool-images-7j.json')['lab-evaluator']['image']
    if not image.startswith('nexus.localhost:18185/lab-evaluator@sha256:'):
        raise ValueError('Evaluator image must be pinned to its Nexus digest.')
    catalogue = json.loads(args.catalogue_manifest.read_bytes())
    query = json.loads(args.query_manifest.read_bytes())
    judgement = json.loads(args.judgement_manifest.read_bytes())
    if judgement['dependencies'] != {'catalogue': catalogue['content']['sha256'],
                                      'query-suite': query['content']['sha256']}:
        raise ValueError('Judgement dependencies differ from selected inputs.')
    content = judgement['content']
    inputs = {'observations': reference(args.observation_reference, 'observation-set'),
              'specification': reference(args.specification_reference, 'evaluation-specification'),
              'catalogue_manifest': manifest_reference(args.catalogue_manifest),
              'query_manifest': manifest_reference(args.query_manifest),
              'judgement_manifest': manifest_reference(args.judgement_manifest),
              'judgements': {'sha256': content['sha256'], 'bytes': content['bytes'],
                             'blob': 'datasets/' + content['object']}}
    reader = reference(STATE / 'nexus.json')['reader']
    auth = base64.b64encode((reader['username'] + ':' + reader['password']).encode()).decode()
    suffix = uuid.uuid4().hex[:8]
    name = 'offline-evaluate-' + suffix
    secret_name = 'blob-reader-' + suffix
    apply({'apiVersion': 'v1', 'kind': 'Namespace',
           'metadata': {'name': NAMESPACE, 'labels': {'lab/owner': 'offline-evaluation'}}})
    apply({'apiVersion': 'v1', 'kind': 'Secret',
           'metadata': {'name': 'nexus-read', 'namespace': NAMESPACE},
           'type': 'kubernetes.io/dockerconfigjson',
           'stringData': {'.dockerconfigjson': json.dumps({'auths': {'nexus.localhost:18185': {
               'username': reader['username'], 'password': reader['password'], 'auth': auth}}})}})
    apply({'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
           'metadata': {'name': 'blob-only-egress', 'namespace': NAMESPACE},
           'spec': {'podSelector': {'matchLabels': {'app': 'lab-offline-evaluator'}},
                    'policyTypes': ['Ingress', 'Egress'], 'ingress': [],
                    'egress': [
                        {'to': [{'namespaceSelector': {'matchLabels': {
                            'kubernetes.io/metadata.name': 'kube-system'}}}],
                         'ports': [{'port': 53, 'protocol': 'UDP'},
                                   {'port': 53, 'protocol': 'TCP'}]},
                        {'to': [{'namespaceSelector': {'matchLabels': {
                            'kubernetes.io/metadata.name': 'platform'}},
                                 'podSelector': {'matchLabels': {'app': 'floci'}}}],
                         'ports': [{'port': 4577, 'protocol': 'TCP'}]}]}})
    apply({'apiVersion': 'v1', 'kind': 'Secret',
           'metadata': {'name': secret_name, 'namespace': NAMESPACE},
           'stringData': {'connection': connection}})
    environment = [{'name': 'DATA_BLOB_CONNECTION_STRING',
                    'valueFrom': {'secretKeyRef': {'name': secret_name, 'key': 'connection'}}},
                   {'name': 'EVALUATION_INPUTS_JSON', 'value': json.dumps(inputs, sort_keys=True)},
                   {'name': 'LAB_JOB_NAME', 'value': name}]
    if args.evaluated_at:
        environment.append({'name': 'EVALUATED_AT', 'value': args.evaluated_at})
    job = {'apiVersion': 'batch/v1', 'kind': 'Job',
           'metadata': {'name': name, 'namespace': NAMESPACE,
                        'labels': {'lab/owner': 'offline-evaluation'}},
           'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300,
                    'template': {'metadata': {'labels': {'app': 'lab-offline-evaluator'}},
                                 'spec': {'restartPolicy': 'Never',
                                          'affinity': {'nodeAffinity': {
                                              'requiredDuringSchedulingIgnoredDuringExecution': {
                                                  'nodeSelectorTerms': [{'matchExpressions': [{
                                                      'key': 'lab.relevance/role',
                                                      'operator': 'DoesNotExist'}]}]}}},
                                          'automountServiceAccountToken': False,
                                          'securityContext': {'runAsUser': 10001,
                                                              'runAsGroup': 10001},
                                          'imagePullSecrets': [{'name': 'nexus-read'}],
                                          'containers': [{'name': 'evaluator', 'image': image,
                                              'command': ['python', '/app/job_entry.py'],
                                              'env': environment,
                                              'resources': {'requests': {'cpu': '100m', 'memory': '128Mi'},
                                                            'limits': {'cpu': '1', 'memory': '768Mi'}}}]}}}}
    try:
        kubectl('create', '-f', '-', payload=job)
        deadline = time.monotonic() + 300
        while True:
            status = json.loads(kubectl('get', 'job/' + name, '-n', NAMESPACE, '-o', 'json').stdout)['status']
            if status.get('succeeded'):
                break
            if status.get('failed') or time.monotonic() >= deadline:
                logs = kubectl('logs', 'job/' + name, '-n', NAMESPACE, check=False)
                raise RuntimeError('Offline evaluator Job failed: ' + logs.stdout[-800:])
            time.sleep(2)
        logs = kubectl('logs', 'job/' + name, '-n', NAMESPACE, check=False)
        if logs.returncode:
            raise RuntimeError('Offline evaluator Job logs unavailable: ' + logs.stderr[-800:])
        print(json.dumps({'job': name, **json.loads(logs.stdout.splitlines()[-1])}, sort_keys=True))
    finally:
        kubectl('delete', 'job/' + name, '-n', NAMESPACE,
                '--ignore-not-found', '--wait=true', check=False)
        kubectl('delete', 'secret/' + secret_name, '-n', NAMESPACE,
                '--ignore-not-found', check=False)


if __name__ == '__main__':
    main()
