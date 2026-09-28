"""Run the finite synthetic producer in its own Kubernetes namespace."""

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get('LAB_STATE_DIR', ROOT / '.lab'))
NAMESPACE = 'lab-data'
KUBE = ['kubectl', '--kubeconfig', str(STATE / 'kubeconfig.yaml')]
sys.path.insert(0, str(ROOT / 'lab'))
from keyvault import image_secret as vault_image_secret


def kubectl(*args, payload=None, check=True):
    result = subprocess.run(KUBE + list(args), cwd=ROOT,
                            input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, encoding='utf-8')
    if check and result.returncode:
        raise RuntimeError('kubectl failed: ' + result.stderr[-1000:])
    return result


def apply(value):
    kubectl('apply', '-f', '-', payload=value)


def main():
    if kubectl('config', 'current-context').stdout.strip() != 'k3d-relevance-lab':
        raise ValueError('The data producer requires the named local lab cluster.')
    connection = os.environ.get('DATA_BLOB_CONNECTION_STRING')
    if not connection:
        raise ValueError('Supply DATA_BLOB_CONNECTION_STRING to the finite producer job.')
    if 'AccountName=devstoreaccount1;' not in connection or \
            'BlobEndpoint=http://127.0.0.1:14577/devstoreaccount1;' not in connection:
        raise ValueError('Use the explicit local Floci connection for this lab Job.')
    connection = connection.replace(
        'BlobEndpoint=http://127.0.0.1:14577/devstoreaccount1;',
        'BlobEndpoint=http://floci.platform.svc.cluster.local:4577/devstoreaccount1;')
    image = json.loads((STATE / 'tool-images-7j.json').read_text())['lab-data-producer']['image']
    if not image.startswith('nexus.localhost:18185/lab-data-producer@sha256:'):
        raise ValueError('Use a digest-pinned data producer image.')
    suffix = uuid.uuid4().hex[:8]
    name = 'lab-data-example-' + suffix
    credential_name = 'blob-publisher-' + suffix
    apply({'apiVersion': 'v1', 'kind': 'Namespace',
           'metadata': {'name': NAMESPACE, 'labels': {'lab/owner': 'synthetic-data'}}})
    if not vault_image_secret(NAMESPACE, 'nexus-read'):
        reader = json.loads((STATE / 'nexus.json').read_text())['reader']
        auth = base64.b64encode((reader['username'] + ':' + reader['password']).encode()).decode()
        apply({'apiVersion': 'v1', 'kind': 'Secret',
               'metadata': {'name': 'nexus-read', 'namespace': NAMESPACE},
               'type': 'kubernetes.io/dockerconfigjson',
               'stringData': {'.dockerconfigjson': json.dumps({'auths': {'nexus.localhost:18185': {
                   'username': reader['username'], 'password': reader['password'], 'auth': auth}}})}})
    apply({'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
           'metadata': {'name': 'producer-egress', 'namespace': NAMESPACE},
           'spec': {'podSelector': {'matchLabels': {'app': 'lab-data-producer'}},
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
           'metadata': {'name': credential_name, 'namespace': NAMESPACE},
           'stringData': {'connection': connection}})
    job = {'apiVersion': 'batch/v1', 'kind': 'Job',
           'metadata': {'name': name, 'namespace': NAMESPACE,
                        'labels': {'lab/owner': 'synthetic-data'}},
           'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 180,
                    'template': {'metadata': {'labels': {'app': 'lab-data-producer'}},
                                 'spec': {'restartPolicy': 'Never',
                                          'affinity': {'nodeAffinity': {
                                              'requiredDuringSchedulingIgnoredDuringExecution': {
                                                  'nodeSelectorTerms': [{'matchExpressions': [{
                                                      'key': 'lab.relevance/role',
                                                      'operator': 'DoesNotExist'}]}]}}},
                                          'automountServiceAccountToken': False,
                                          'securityContext': {'runAsUser': 10001,
                                                              'runAsGroup': 10001,
                                                              'fsGroup': 10001},
                                          'imagePullSecrets': [{'name': 'nexus-read'}],
                                          'containers': [{'name': 'producer', 'image': image,
                                              'env': [
                                                  {'name': 'DATA_BLOB_URL', 'value':
                                                   'http://floci.platform.svc.cluster.local:4577/devstoreaccount1'},
                                                  {'name': 'DATA_BLOB_CONNECTION_STRING',
                                                   'valueFrom': {'secretKeyRef': {
                                                       'name': credential_name, 'key': 'connection'}}},
                                                  {'name': 'LAB_JOB_NAME', 'value': name}],
                                              'volumeMounts': [{'name': 'output', 'mountPath': '/output'}],
                                              'resources': {'requests': {'cpu': '50m', 'memory': '64Mi'},
                                                            'limits': {'cpu': '500m', 'memory': '256Mi'}}}],
                                          'volumes': [{'name': 'output', 'emptyDir': {}}]}}}}
    try:
        kubectl('create', '-f', '-', payload=job)
        waited = kubectl('wait', '--for=condition=complete', 'job/' + name,
                         '-n', NAMESPACE, '--timeout=180s', check=False)
        logs = kubectl('logs', 'job/' + name, '-n', NAMESPACE, check=False)
        if waited.returncode or logs.returncode:
            raise RuntimeError('Producer Job failed: ' + (logs.stdout or waited.stderr)[-800:])
        value = json.loads(logs.stdout.splitlines()[-1])
        print(json.dumps({'job': name, **value}, indent=2))
    finally:
        kubectl('delete', 'job/' + name, '-n', NAMESPACE,
                '--ignore-not-found', '--wait=true', check=False)
        kubectl('delete', 'secret/' + credential_name, '-n', NAMESPACE,
                '--ignore-not-found', check=False)


if __name__ == '__main__':
    main()
