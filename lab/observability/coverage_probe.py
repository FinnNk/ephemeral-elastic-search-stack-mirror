"""Retain independent gateway/backend readiness samples during a load run."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get('LAB_STATE_DIR', ROOT / '.lab'))
KUBE = ['kubectl', '--kubeconfig', str(STATE / 'kubeconfig.yaml')]


def ready(kind, name):
    result = subprocess.run(KUBE + ['get', kind + '/' + name, '-n', 'lab-observability',
                                     '-o', 'json'], capture_output=True, text=True)
    if result.returncode:
        return False
    value = json.loads(result.stdout)
    desired = value['spec'].get('replicas', 1)
    return desired > 0 and value.get('status', {}).get('readyReplicas', 0) == desired


def sample(url):
    gateway = ready('deployment', 'lab-otel-gateway')
    backend = ready('statefulset', 'signoz')
    try:
        with urlopen(url.rstrip('/') + '/api/v1/health', timeout=3) as response:
            http = response.status == 200
    except (OSError, URLError):
        http = False
    return {'observed_at': datetime.now(timezone.utc).isoformat(),
            'gateway_ready': gateway, 'backend_ready': backend,
            'backend_http_ok': http,
            'collector_ok': gateway and backend and http}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--duration-seconds', type=int, required=True)
    parser.add_argument('--every-seconds', type=int, default=10)
    parser.add_argument('--signoz-url', default='http://127.0.0.1:18090')
    args = parser.parse_args()
    if args.duration_seconds <= 0 or args.every_seconds <= 0:
        raise ValueError('Probe intervals and duration must be positive.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stop = time.monotonic() + args.duration_seconds
    with args.output.open('x', encoding='utf-8') as output:
        while time.monotonic() < stop:
            started = time.monotonic()
            output.write(json.dumps(sample(args.signoz_url), sort_keys=True) + '\n')
            output.flush()
            remaining = stop - time.monotonic()
            if remaining > 0:
                time.sleep(min(max(0, args.every_seconds - (time.monotonic() - started)),
                               remaining))


if __name__ == '__main__':
    main()
