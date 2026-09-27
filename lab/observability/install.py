"""Install the pinned local SigNoz backend and vendor-neutral OTLP agents."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

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


def preflight():
    nodes = subprocess.run(KUBE + ['get', 'nodes', '-l', 'lab.relevance/role=observability',
                                    '-o', 'jsonpath={.items[*].metadata.name}'],
                           capture_output=True, text=True, check=True)
    if not nodes.stdout.strip():
        raise RuntimeError('Label a worker lab.relevance/role=observability with >=8 GiB headroom.')


def install(root_account=False):
    preflight()
    chart = chart_archive()
    namespace = subprocess.run(KUBE + ['get', 'namespace', NAMESPACE],
                               capture_output=True, text=True)
    if namespace.returncode:
        run(KUBE + ['create', 'namespace', NAMESPACE])
    values = [str(HERE / 'signoz-values.yaml')]
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
    run(command)
    for name in ('gateway.yaml', 'log-agent.yaml'):
        run(KUBE + ['apply', '-f', str(HERE / name)])
    run(KUBE + ['rollout', 'status', f'deployment/{GATEWAY}', '-n', NAMESPACE, '--timeout=3m'])
    run(KUBE + ['rollout', 'status', 'daemonset/lab-log-agent', '-n', NAMESPACE, '--timeout=3m'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--agent-root', action='store_true',
                        help='Enable the separately approved agent admin bootstrap overlay')
    args = parser.parse_args()
    install(args.agent_root)
