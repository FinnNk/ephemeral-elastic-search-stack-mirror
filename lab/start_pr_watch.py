"""Start the opt-in local Gitea PR watcher without a visible console."""
from catalogue import DEFAULT_RELEASE, RELEASES
import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.lab'


def running():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 18084))
        return False
    except OSError:
        return True


def start(baseline_run, release):
    if (STATE / 'control-drain').exists():
        raise RuntimeError('Host controls are drained for Kubernetes cutover.')
    if running():
        return {'watcher': 'already running'}
    STATE.mkdir(exist_ok=True)
    output = (STATE / 'pr-watch.log').open('ab')
    command = [sys.executable, str(ROOT / 'lab/pr_workflow.py'), '--watch',
               '--baseline-run', str(baseline_run), '--release', release]
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                               stdout=output, stderr=output,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                               start_new_session=os.name != 'nt')
    output.close()
    (STATE / 'pr-watch.pid').write_text(str(process.pid), encoding='utf-8')
    return {'watcher': 'started', 'pid': process.pid, 'baseline_run': baseline_run, 'release': release}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-run', type=int, required=True)
    parser.add_argument('--release', choices=RELEASES,
                        default=DEFAULT_RELEASE)
    args = parser.parse_args()
    print(json.dumps(start(args.baseline_run, args.release)))
