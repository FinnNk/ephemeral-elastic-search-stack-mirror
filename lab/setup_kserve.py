"""Install the pinned KServe controller and CRDs without changing model pins."""
import hashlib
import json
from common import HELM, IN_CLUSTER, ROOT, STATE, guard, k, run

VENDOR = ROOT / 'lab/vendor/kserve-0.21.0'


def retained_specs(value):
    return {row['metadata']['uid']: row['spec'] for row in value['items']
            if row['metadata'].get('annotations', {}).get('meta.helm.sh/release-name') != 'kserve-resources'}


def install():
    guard()
    pins = json.loads((VENDOR / 'release.json').read_text(encoding='utf-8'))
    for component, chart in pins['charts'].items():
        if hashlib.sha256((VENDOR / chart['file']).read_bytes()).hexdigest() != chart['sha256']:
            raise ValueError('KServe chart checksum mismatch: ' + component)
    # Retain recovery evidence, and never reapply the bootstrap model definition.
    snapshot = STATE / 'kserve-upgrade'
    snapshot.mkdir(parents=True, exist_ok=True)
    before = {}
    for kind in ('inferenceservices', 'servingruntimes', 'clusterstoragecontainers'):
        result = k('get', kind, '-A', '-o', 'json', check=False)
        if result.returncode:
            if "doesn't have a resource type" not in result.stderr:
                raise RuntimeError('Cannot read KServe resource definitions: ' + kind)
            value = {'items': []}
        else:
            value = json.loads(result.stdout)
        before[kind] = retained_specs(value)
        (snapshot / (kind + '-before.json')).write_text(json.dumps(value, indent=2), encoding='utf-8')
    for component in ('crd', 'resources'):
        release = 'kserve-' + component
        args = [HELM]
        if not IN_CLUSTER:
            args += ['--kubeconfig', str(STATE / 'kubeconfig.yaml')]
        # Preserve explicit values while replacing the upstream version defaults.
        existing = run(args + ['get', 'values', release, '-n', 'kserve', '-o', 'json'], check=False)
        values = json.loads(existing.stdout) if existing.returncode == 0 else {}
        values = values or {}
        (snapshot / (component + '-previous-values.json')).write_text(json.dumps(values, indent=2), encoding='utf-8')
        if component == 'resources':
            values.setdefault('kserve', {})['version'] = pins['release']
            controller = values['kserve'].setdefault('controller', {})
            controller.update(deploymentMode='Standard', image=pins['controller'].split(':v')[0],
                              tag=pins['controller'].split(':', 1)[1])
            gateway = controller.setdefault('gateway', {})
            gateway['disableIstioVirtualHost'] = True
            gateway.setdefault('ingressGateway', {})['className'] = 'traefik'
        path = snapshot / (component + '-values.json')
        path.write_text(json.dumps(values), encoding='utf-8')
        run(args + ['upgrade', '--install', release, str(VENDOR / pins['charts'][component]['file']),
            '-n', 'kserve', '--create-namespace', '-f', str(path), '--wait', '--timeout', '5m'])
    k('rollout', 'status', 'deployment/kserve-controller-manager', '-n', 'kserve', '--timeout=180s')
    for kind, specs in before.items():
        current = json.loads(k('get', kind, '-A', '-o', 'json').stdout)
        if specs != retained_specs(current):
            raise ValueError('KServe upgrade changed model/runtime definitions: ' + kind)
    print('KServe v0.21.0 controller and CRDs installed; model and runtime definitions preserved.')


if __name__ == '__main__':
    install()
