"""Install optional CPU-only controllers for Headlamp KServe plugin development."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen

import yaml

from common import HELM, ROOT, STATE, apply, guard, k, run

CONFIG = ROOT / 'lab/headlamp-testbed'
CACHE = STATE / 'headlamp-testbed'
NODE = 'k3d-headlamp-testbed-0'


def download(name, source):
    """Check upstream bytes before applying local resource settings."""
    path = CACHE / (name + '.yaml')
    if not path.exists():
        with urlopen(source['url'], timeout=30) as response:
            path.write_bytes(response.read())
    if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError('Source checksum differs: ' + name)
    return path


def helm(*args):
    return run([HELM, '--kubeconfig', str(STATE / 'kubeconfig.yaml'), *args])


def patch_config(namespace, name, data):
    k('-n', namespace, 'patch', 'configmap/' + name, '--type=merge',
      '-p', json.dumps({'data': data}))


def verify():
    """Require ready controllers; model serving is checked separately."""
    guard()
    controllers = {'lws-system': ['lws-controller-manager'],
        'kserve': ['kserve-controller-manager', 'llmisvc-controller-manager'],
        'knative-serving': ['controller', 'webhook', 'autoscaler', 'activator', 'net-kourier-controller'],
        'kourier-system': ['3scale-kourier-gateway'],
        'keda': ['keda-operator', 'keda-operator-metrics-apiserver', 'keda-admission-webhooks'],
        'monitoring': ['kube-prometheus-stack-operator', 'kube-prometheus-stack-kube-state-metrics']}
    for namespace, names in controllers.items():
        for name in names:
            k('-n', namespace, 'rollout', 'status', 'deployment/' + name, '--timeout=60s')
    k('-n', 'monitoring', 'rollout', 'status',
      'statefulset/prometheus-kube-prometheus-stack-prometheus', '--timeout=60s')
    config = json.loads(k('-n', 'kserve', 'get', 'configmap/inferenceservice-config', '-o', 'json').stdout)
    if json.loads(config['data']['deploy'])['defaultDeploymentMode'] != 'Standard':
        raise ValueError('KServe must retain Standard as its default.')
    presets = json.loads(k('-n', 'kserve', 'get', 'llminferenceserviceconfigs', '-o', 'json').stdout)
    if len(presets['items']) < 13:
        raise ValueError('The upstream LLM configuration presets are incomplete.')
    gateway = json.loads(k('-n', 'kourier-system', 'get', 'service/kourier', '-o', 'json').stdout)
    if gateway['spec']['type'] != 'ClusterIP':
        raise ValueError('Kourier must remain internal.')
    return {'controllers': 'ready', 'llm_presets': len(presets['items']),
            'prometheus': 'monitoring/kube-prometheus-stack-prometheus', 'worker': NODE}


def install():
    """Add optional testbed dependencies without replacing shared model pins."""
    guard()
    CACHE.mkdir(parents=True, exist_ok=True)
    before = {}
    for kind in ('inferenceservices', 'servingruntimes', 'clusterstoragecontainers'):
        snapshot = json.loads(k('get', kind, '-A', '-o', 'json').stdout)
        before[kind] = {row['metadata']['uid']: row['spec'] for row in snapshot['items']}
        (CACHE / (kind + '-install-before.json')).write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
    if k('get', 'node', NODE, check=False).returncode:
        executable = STATE / 'tools' / ('k3d.exe' if os.name == 'nt' else 'k3d')
        run([str(executable), 'node', 'create', 'headlamp-testbed', '-c', 'relevance-lab',
             '--role', 'agent', '--memory', '8g', '--k3s-node-label', 'lab.relevance/testbed=true'])
    sources = json.loads((CONFIG / 'sources.json').read_bytes())
    presets = []
    for name, source in sources.items():
        path = download(name, source)
        if name.startswith('preset-'):
            obj = yaml.safe_load(path.read_text(encoding='utf-8'))
            obj['metadata']['namespace'] = 'kserve'
            presets.append(obj)
            continue
        if name in ('lws', 'knative-core', 'kourier'):
            docs = [d for d in yaml.safe_load_all(path.read_text(encoding='utf-8')) if d]
            for doc in docs:
                if doc['kind'] == 'Deployment':
                    doc['spec']['replicas'] = 1
                    spec = doc['spec']['template']['spec']
                    spec['nodeSelector'] = {**spec.get('nodeSelector', {}), 'lab.relevance/testbed': 'true'}
                    for container in spec['containers']:
                        container['resources'] = {'requests': {'cpu': '100m', 'memory': '128Mi'},
                                                  'limits': {'cpu': '2', 'memory': '512Mi'}}
                if name == 'kourier' and doc['kind'] == 'Service' and doc['metadata']['name'] == 'kourier':
                    doc['spec']['type'] = 'ClusterIP'
            path = CACHE / (name + '-lab.yaml')
            path.write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding='utf-8')
        # Knative's webhook owns fields it normalises after installation.
        # Retain its upstream client-side apply workflow rather than forcing
        # server-side ownership of those controller-managed fields.
        flags = ['--server-side'] if name in ('gateway', 'gie', 'lws') else []
        k('apply', *flags, '-f', str(path))
    for namespace, deployment in [('lws-system', 'lws-controller-manager'), ('knative-serving', 'webhook')]:
        k('-n', namespace, 'rollout', 'status', 'deployment/' + deployment, '--timeout=180s')
    charts = json.loads((CONFIG / 'charts.json').read_bytes())
    for component, pin in charts.items():
        name = 'kserve-llmisvc-' + component
        path = CACHE / pin['file']
        if not path.exists():
            helm('pull', 'oci://ghcr.io/kserve/charts/' + name, '--version', 'v0.21.0-rc1', '--destination', str(CACHE))
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('Chart checksum differs: ' + name)
        values = ['-f', str(CONFIG / 'llm-values.json')] if component == 'resources' else []
        helm('upgrade', '--install', name, str(path), '-n', 'kserve', *values, '--wait', '--timeout', '3m')
    for preset in presets:
        apply(preset)
    for repository, url in [('kedacore', 'https://kedacore.github.io/charts'),
                            ('prometheus-community', 'https://prometheus-community.github.io/helm-charts')]:
        helm('repo', 'add', repository, url)
    helm('repo', 'update')
    for release, chart, version, namespace, values in [
            ('keda', 'kedacore/keda', '2.20.2', 'keda', 'keda-values.json'),
            ('kube-prometheus-stack', 'prometheus-community/kube-prometheus-stack', '83.4.0', 'monitoring', 'prometheus-values.json')]:
        helm('upgrade', '--install', release, chart, '--version', version, '-n', namespace,
             '--create-namespace', '-f', str(CONFIG / values), '--wait', '--timeout', '4m')
    patch_config('knative-serving', 'config-network', {'ingress-class': 'kourier.ingress.networking.knative.dev'})
    patch_config('knative-serving', 'config-domain', {'example.com': ''})
    patch_config('knative-serving', 'config-features', {'kubernetes.podspec-nodeselector': 'enabled'})
    config = json.loads(k('-n', 'kserve', 'get', 'configmap/inferenceservice-config', '-o', 'json').stdout)
    ingress = json.loads(config['data']['ingress'])
    ingress.update(disableIstioVirtualHost=True,
                   knativeLocalGatewayService='kourier-internal.kourier-system.svc.cluster.local')
    patch_config('kserve', 'inferenceservice-config', {'ingress': json.dumps(ingress)})
    k('-n', 'kserve', 'rollout', 'restart', 'deployment/kserve-controller-manager')
    result = verify()
    for kind, specs in before.items():
        current = json.loads(k('get', kind, '-A', '-o', 'json').stdout)
        if specs != {row['metadata']['uid']: row['spec'] for row in current['items']}:
            raise ValueError('Existing KServe definitions changed: ' + kind)
    return {**result, 'existing_model_definitions': 'unchanged'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify() if args.verify_only else install(), indent=2))
