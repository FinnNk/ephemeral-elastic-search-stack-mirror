"""Install the pinned local SigNoz backend and vendor-neutral OTLP agents."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import json

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'lab'))
from common import HELM, KUBE, STATE  # noqa: E402

HERE = Path(__file__).resolve().parent
CHART_VERSION = '0.143.0'
CHART_SHA256 = 'e3ec7144de45404b10837ef80e86c6cec4960cde41e914f4782d9205c739adad'
NAMESPACE = 'lab-observability'
GATEWAY = 'lab-otel-gateway'


def run(args):
    print('Running', args[0], args[1] if len(args) > 1 else '', flush=True)
    environment = os.environ.copy()
    environment['KUBECONFIG'] = str(STATE / 'kubeconfig.yaml')
    bundle = STATE / 'host-ca-bundle.pem'
    if bundle.exists():
        environment.update(SSL_CERT_FILE=str(bundle), REQUESTS_CA_BUNDLE=str(bundle))
    subprocess.run(args, cwd=ROOT, env=environment, check=True)


def chart_archive():
    folder = STATE / 'artifacts' / 'signoz'
    folder.mkdir(parents=True, exist_ok=True)
    chart = folder / f'signoz-{CHART_VERSION}.tgz'
    if not chart.exists():
        cache = STATE / 'helm-cache'
        config = STATE / 'helm-repositories.yaml'
        run([HELM, 'repo', 'add', 'signoz', 'https://charts.signoz.io', '--force-update',
             '--repository-cache', str(cache), '--repository-config', str(config)])
        run([HELM, 'repo', 'update', 'signoz',
             '--repository-cache', str(cache), '--repository-config', str(config)])
        run([HELM, 'pull', 'signoz/signoz', '--version', CHART_VERSION,
             '--destination', str(folder), '--repository-cache', str(cache),
             '--repository-config', str(config)])
    actual = hashlib.sha256(chart.read_bytes()).hexdigest()
    if actual != CHART_SHA256:
        raise RuntimeError('SigNoz chart SHA-256 differs from the reviewed release.')
    return chart


def preflight(profile='standard'):
    if profile == 'demo':
        from fresh_application import assert_fresh
        assert_fresh()
        if not (STATE / 'control-image.json').exists() or not (STATE / 'host-ca-bundle.pem').exists():
            raise RuntimeError('Complete fresh CPU image setup before installing demo SigNoz.')
        print('Demo profile uses existing CPU nodes. Allow approximately 4 GiB extra memory headroom.', flush=True)
        # PVC shrinking is not a supported upgrade path for a retained backend.
        existing = subprocess.run(KUBE + ['get', 'pvc', '-n', NAMESPACE, '-o', 'json'],
                                  capture_output=True, text=True)
        if existing.returncode == 0:
            from demo_profile import storage_bytes
            for claim in json.loads(existing.stdout)['items']:
                size = claim['spec']['resources']['requests']['storage']
                maximum = '10Gi' if 'clickhouse' in claim['metadata']['name'] else '1Gi'
                if storage_bytes(size) > storage_bytes(maximum):
                    raise RuntimeError('Demo profile refuses to shrink existing observability PVCs; retain the standard profile.')
        return
    nodes = subprocess.run(KUBE + ['get', 'nodes', '-l', 'lab.relevance/role=observability',
                                    '-o', 'jsonpath={.items[*].metadata.name}'],
                           capture_output=True, text=True, check=True)
    if not nodes.stdout.strip():
        raise RuntimeError('Label a worker lab.relevance/role=observability with >=8 GiB headroom.')


def reset_demo_migrator(folder):
    """Retain diagnostics and recreate only this release's immutable migration Job."""
    name = 'signoz-telemetrystore-migrator'
    expected = {'app.kubernetes.io/name': 'signoz',
                'app.kubernetes.io/instance': 'signoz',
                'app.kubernetes.io/component': name}
    retained = []
    for kind in ('job', 'serviceaccount'):
        previous = subprocess.run(KUBE + ['get', kind, name, '-n', NAMESPACE,
                                         '--ignore-not-found', '-o', 'json'],
                                  capture_output=True, text=True, check=True)
        if not previous.stdout.strip():
            continue
        resource = json.loads(previous.stdout)
        metadata = resource['metadata']
        if any(metadata.get('labels', {}).get(key) != value for key, value in expected.items()):
            raise RuntimeError('Refusing to recreate ' + kind + '/' + name +
                               ' with unexpected ownership labels: ' +
                               json.dumps(metadata.get('labels', {}), sort_keys=True))
        # The old hook account may lack normal Helm ownership annotations.
        # Keep an ordinary account; recreate only the abandoned hook account.
        if kind == 'job' or (metadata.get('annotations') or {}).get('helm.sh/hook') == 'pre-upgrade':
            retained.append(kind)
    for kind in retained:
        if kind == 'job':
            logs = subprocess.run(KUBE + ['logs', 'job/' + name, '-n', NAMESPACE,
                                          '--all-containers=true', '--tail=100', '--pod-running-timeout=5s'],
                                  capture_output=True, text=True)
            (folder / 'previous-migrator.log').write_text(logs.stdout + logs.stderr, encoding='utf-8')
            print('Recreating the retained SigNoz migration Job; previous logs saved in ' + str(folder), flush=True)
        run(KUBE + ['delete', kind, name, '-n', NAMESPACE, '--wait=true', '--timeout=60s'])


def install(root_account=False, profile='standard'):
    preflight(profile)
    chart = chart_archive()
    namespace = subprocess.run(KUBE + ['get', 'namespace', NAMESPACE],
                               capture_output=True, text=True)
    if namespace.returncode:
        run(KUBE + ['create', 'namespace', NAMESPACE])
    values = [str(HERE / 'signoz-values.yaml')]
    if profile == 'demo':
        from demo_profile import values as demo_values, agents
        from setup_nexus import image_secret
        image_secret(NAMESPACE)
        folder = STATE / 'observability-demo'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'values.yaml'
        path.write_text(yaml.safe_dump(demo_values(HERE, STATE), sort_keys=False), encoding='utf-8')
        values = [str(path)]
    if root_account:
        secret = subprocess.run(KUBE + ['get', 'secret', 'lab-signoz-root', '-n', NAMESPACE],
                                capture_output=True, text=True)
        if secret.returncode:
            raise RuntimeError('Create lab-signoz-root Secret from an ignored local password file first.')
        values.append(str(HERE / 'signoz-agent-root-values.yaml'))
    command = [HELM, 'upgrade', '--install', 'signoz', str(chart),
               '--namespace', NAMESPACE, '--wait', '--timeout', '10m']
    for path in values:
        command += ['-f', path]
    if profile == 'demo':
        reset_demo_migrator(folder)
        command.append('--wait-for-jobs')
        print('Applying backend resources, then waiting for ClickHouse and completed migrations.', flush=True)
    run(command)
    if profile == 'demo':
        from demo_profile import operator_patch
        run(KUBE + ['patch', 'deployment/signoz-clickhouse-operator', '-n', NAMESPACE,
                    '--type=strategic', '-p', json.dumps(operator_patch())])
        run(KUBE + ['rollout', 'status', 'deployment/signoz-clickhouse-operator',
                    '-n', NAMESPACE, '--timeout=3m'])
        path = folder / 'agents.yaml'
        path.write_text(yaml.safe_dump_all(agents(HERE), sort_keys=False), encoding='utf-8')
        run(KUBE + ['apply', '-f', str(path)])
    else:
        for name in ('gateway.yaml', 'log-agent.yaml'):
            run(KUBE + ['apply', '-f', str(HERE / name)])
    run(KUBE + ['rollout', 'status', f'deployment/{GATEWAY}', '-n', NAMESPACE, '--timeout=3m'])
    run(KUBE + ['rollout', 'status', 'daemonset/lab-log-agent', '-n', NAMESPACE, '--timeout=3m'])
    if profile == 'demo':
        from https_ingress import certificate, route
        route(*certificate()[:2], browser_names=('signoz',))
        print('Open https://signoz.localhost:34443 and create your first administrator account.', flush=True)
        print('Set retention in Settings: logs 7 days, traces 7 days, metrics 30 days. '
              'Organisation setup and retention confirmation are required before measuring ingestion.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--agent-root', action='store_true',
                        help='Enable the separately approved agent admin bootstrap overlay')
    parser.add_argument('--profile', choices=('standard', 'demo'), default='standard',
                        help='Demo: smaller resources on existing fresh-lab CPU nodes')
    args = parser.parse_args()
    install(args.agent_root, args.profile)
