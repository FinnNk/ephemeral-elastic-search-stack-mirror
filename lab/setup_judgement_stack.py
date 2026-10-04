"""Install or verify the lab's pinned MLflow/KServe judgement stack."""

import argparse
import json
import re

from common import HELM, IN_CLUSTER, ROOT, STATE, apply, guard, k, run
from setup_judgement_secrets import configure as configure_secrets
from setup_nexus import configure_network
from publish_judgement_image import source_sha256

SOURCES = ROOT / 'judgements' / 'kubernetes'


def chart(name, source, version, namespace, *values):
    command = [HELM]
    if not IN_CLUSTER:
        command += ['--kubeconfig', str(STATE / 'kubeconfig.yaml')]
    command += ['upgrade', '--install', name, source, '--version', version,
               '--namespace', namespace, '--create-namespace', '--wait',
               '--timeout', '5m', *values]
    run(command)


def manifest(name):
    k('apply', '-f', str(SOURCES / name))


def guard_bootstrap_model():
    """The bootstrap includes a v1-only smoke test and must not reset a later model."""
    existing = k('get', 'inferenceservice/synthetic-esci-judge', '-n', 'lab-models',
                 '-o', 'json', check=False)
    if existing.returncode:
        return
    model = json.loads(existing.stdout)['spec']['predictor']['model']
    expected = re.search(r'storageUri: (\S+)',
                         (SOURCES / 'kserve-model.yaml').read_text(encoding='utf-8')).group(1)
    if model.get('storageUri') != expected or model.get('runtime') != 'synthetic-judge-runtime':
        raise ValueError('A replacement judgement model is installed. This bootstrap would '
                         'reset it to v1. Use docs/esci-model-installation.md for model '
                         'verification, promotion and rollback.')


def wait_ready(million=False):
    guard()
    guard_bootstrap_model()
    k('wait', '--for=condition=Ready', 'externalsecret', '--all', '-n', 'lab-models',
      '--timeout=180s')
    k('rollout', 'status', 'statefulset/mlflow-postgres', '-n', 'lab-models',
      '--timeout=180s')
    k('rollout', 'status', 'deployment/mlflow-mlflow', '-n', 'lab-models',
      '--timeout=180s')
    k('wait', '--for=condition=Ready', 'inferenceservice/synthetic-esci-judge',
      '-n', 'lab-models', '--timeout=180s')
    k('rollout', 'status', 'deployment/synthetic-esci-judge-predictor',
      '-n', 'lab-models', '--timeout=180s')
    k('rollout', 'status', 'deployment/judgement-service', '-n', 'lab-models',
      '--timeout=180s')
    expected = 'j1-' + source_sha256()[:16]
    deployments = ['mlflow-mlflow', 'synthetic-esci-judge-predictor',
                   'judgement-service']
    if million:
        k('rollout', 'status', 'deployment/judgement-service-million', '-n', 'lab-models',
          '--timeout=600s')
        deployments.append('judgement-service-million')
    for deployment in deployments:
        value = json.loads(k('get', 'deployment/' + deployment, '-n', 'lab-models',
                             '-o', 'json').stdout)
        pod = value['spec']['template']['spec']
        images = [item['image'] for item in pod.get('initContainers', []) +
                  pod.get('containers', [])]
        if not images or any(expected not in image for image in images):
            raise ValueError(deployment + ' does not run the pinned source image.')
    result = k('exec', '-n', 'lab-models', 'deployment/judgement-service', '-c',
               'judgement-service', '--', 'python', '/app/smoke.py')
    checks = {'demo': json.loads(result.stdout)}
    if million:
        result = k('exec', '-n', 'lab-models', 'deployment/judgement-service-million',
                   '-c', 'judgement-service-million', '--', 'python', '/app/smoke.py')
        checks['full'] = json.loads(result.stdout)
    return checks


def install(million=False):
    guard()
    guard_bootstrap_model()
    expected = 'j1-' + source_sha256()[:16]
    for name in ('mlflow-values.yaml', 'register-model.yaml', 'kserve-model.yaml',
                 'judgement-service.yaml', 'judgement-service-million.yaml'):
        if expected not in (SOURCES / name).read_text(encoding='utf-8'):
            raise ValueError(name + ' does not pin the current judgement source image.')
    configure_network()
    chart('cert-manager', 'oci://quay.io/jetstack/charts/cert-manager', 'v1.17.0',
          'cert-manager', '--set', 'crds.enabled=true')
    from setup_kserve import install as install_kserve
    install_kserve()
    configure_secrets()
    k('wait', '--for=condition=Ready', 'externalsecret', '--all', '-n', 'lab-models',
      '--timeout=180s')
    manifest('postgres.yaml')
    k('rollout', 'status', 'statefulset/mlflow-postgres', '-n', 'lab-models',
      '--timeout=180s')
    chart('mlflow', 'oci://ghcr.io/mlflow/charts/mlflow', '0.1.0', 'lab-models',
          '-f', str(SOURCES / 'mlflow-values.yaml'))
    existing = k('get', 'job/register-synthetic-esci-judge', '-n', 'lab-models',
                 '-o', 'json', check=False)
    if existing.returncode:
        manifest('register-model.yaml')
    k('wait', '--for=condition=Complete', 'job/register-synthetic-esci-judge',
      '-n', 'lab-models', '--timeout=240s')
    manifest('kserve-model.yaml')
    k('wait', '--for=condition=Ready', 'inferenceservice/synthetic-esci-judge',
      '-n', 'lab-models', '--timeout=180s')
    k('rollout', 'restart', 'deployment/synthetic-esci-judge-predictor',
      '-n', 'lab-models')
    manifest('judgement-service.yaml')
    if million:
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap',
               'metadata': {'name': 'judgement-demo-policy', 'namespace': 'lab-models'},
               'data': {'policy.json': (ROOT / 'judgements/policies/esci-lab-demo.json').read_text(encoding='utf-8')}})
        manifest('judgement-service-million.yaml')
    return wait_ready(million)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--million', action='store_true',
                        help='Also deploy or check the full ESCI source profile')
    args = parser.parse_args()
    print(json.dumps(wait_ready(args.million) if args.verify_only else install(args.million),
                     sort_keys=True))
