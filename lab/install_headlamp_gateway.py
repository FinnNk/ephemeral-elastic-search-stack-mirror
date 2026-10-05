"""Install the optional Envoy gateway for Headlamp KServe routing tests."""
import argparse
import hashlib
import json
from pathlib import Path
import yaml
from common import ROOT, STATE, HELM, run, k, guard

CONFIG = ROOT / 'lab/headlamp-gateway'
CACHE = STATE / 'headlamp-gateway'


def helm(*args):
    return run([HELM, '--kubeconfig', str(STATE / 'kubeconfig.yaml'), *args])


def protected():
    """Record schemas, serving definitions and existing ingress configuration."""
    crds = json.loads(k('get', 'crd', '-o', 'json').stdout)['items']
    result = {'crds': {o['metadata']['name']: o['spec'] for o in crds
        if o['spec']['group'] in ('gateway.networking.k8s.io', 'gateway.networking.x-k8s.io',
                                 'inference.networking.k8s.io', 'inference.networking.x-k8s.io')}}
    for resource in ('inferenceservices', 'servingruntimes', 'clusterstoragecontainers'):
        objects = json.loads(k('get', resource, '-A', '-o', 'json').stdout)['items']
        result[resource] = {o['metadata']['uid']: o['spec'] for o in objects}
    result['ingress'] = json.loads(k('-n', 'kserve', 'get', 'configmap/inferenceservice-config', '-o', 'json').stdout)['data']['ingress']
    result['traefik'] = json.loads(k('-n', 'lab-ingress', 'get', 'deployment/lab-traefik', '-o', 'json').stdout)['spec']
    return result


def verify():
    guard()
    for namespace, name in [('envoy-gateway-system', 'envoy-gateway'),
                             ('envoy-ai-gateway-system', 'ai-gateway-controller')]:
        k('-n', namespace, 'rollout', 'status', 'deployment/' + name, '--timeout=120s')
    k('wait', 'gatewayclass/envoy', '--for=condition=Accepted', '--timeout=120s')
    k('-n', 'kserve', 'wait', 'gateway/kserve-ingress-gateway',
      '--for=condition=Programmed', '--timeout=120s')
    services = json.loads(k('-n', 'envoy-gateway-system', 'get', 'service',
        '-l', 'gateway.envoyproxy.io/owning-gateway-name=kserve-ingress-gateway', '-o', 'json').stdout)['items']
    if len(services) != 1 or services[0]['spec']['type'] != 'ClusterIP':
        raise ValueError('Expected one internal ClusterIP gateway proxy.')
    deployments = json.loads(k('-n', 'envoy-gateway-system', 'get', 'deployment',
        '-l', 'gateway.envoyproxy.io/owning-gateway-name=kserve-ingress-gateway', '-o', 'json').stdout)['items']
    if len(deployments) != 1:
        raise ValueError('Expected one gateway proxy deployment.')
    k('-n', 'envoy-gateway-system', 'rollout', 'status',
      'deployment/' + deployments[0]['metadata']['name'], '--timeout=120s')
    return {'gateway': 'kserve/kserve-ingress-gateway', 'accepted': True, 'programmed': True,
            'proxy_service': services[0]['metadata']['name'], 'proxy_type': 'ClusterIP'}


def install():
    guard()
    node = k('get', 'nodes', '-l', 'lab.relevance/testbed=true', '-o', 'json')
    if not json.loads(node.stdout)['items']:
        raise ValueError('Install the Headlamp testbed worker first.')
    CACHE.mkdir(parents=True, exist_ok=True)
    before = protected()
    (CACHE / 'protected-before.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    sources = json.loads((CONFIG / 'sources.json').read_text(encoding='utf-8'))
    for name, source in sources['values'].items():
        if hashlib.sha256((CONFIG / name).read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('Upstream values checksum differs: ' + name)
    charts = {}
    for source in sources['charts']:
        path = CACHE / (source['name'] + '-' + source['version'] + '.tgz')
        if not path.exists():
            helm('pull', source['repository'], '--version', source['version'], '--destination', str(CACHE))
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('Chart checksum differs: ' + source['name'])
        charts[source['name']] = path
    raw = helm('show', 'crds', str(charts['gateway-helm'])).stdout
    own = [o for o in yaml.safe_load_all(raw) if o and o['spec']['group'] == 'gateway.envoyproxy.io']
    if not own:
        raise ValueError('Pinned chart has no Envoy CRDs.')
    run(['kubectl', '--kubeconfig', str(STATE / 'kubeconfig.yaml'), 'apply', '--server-side', '-f', '-'],
        body=yaml.safe_dump_all(own))
    k('apply', '-f', str(CONFIG / 'inferencepool-rbac.yaml'))
    helm('upgrade', '--install', 'eg', str(charts['gateway-helm']), '-n', 'envoy-gateway-system',
         '--create-namespace', '--skip-crds', '-f', str(CONFIG / 'envoy-base-values.yaml'),
         '-f', str(CONFIG / 'envoy-inference-values.yaml'), '-f', str(CONFIG / 'envoy-lab-values.yaml'),
         '--wait', '--timeout', '4m')
    helm('upgrade', '--install', 'aieg-crd', str(charts['ai-gateway-crds-helm']),
         '-n', 'envoy-ai-gateway-system', '--create-namespace', '--wait', '--timeout', '3m')
    helm('upgrade', '--install', 'aieg', str(charts['ai-gateway-helm']),
         '-n', 'envoy-ai-gateway-system', '--create-namespace', '-f', str(CONFIG / 'ai-lab-values.yaml'),
         '--wait', '--timeout', '4m')
    k('apply', '-f', str(CONFIG / 'gateway.yaml'))
    result = verify()
    if protected() != before:
        raise ValueError('Existing routing, model definitions or protected schemas changed.')
    result['protected_resources'] = 'unchanged'
    (CACHE / 'installation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify() if args.verify_only else install(), indent=2))
