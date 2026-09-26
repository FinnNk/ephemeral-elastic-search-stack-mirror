"""Start the loopback UI and independent lease worker without visible consoles."""
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.lab'


def ui_running():
    try:
        with urllib.request.urlopen('http://localhost:18082/api/health', timeout=2) as response:
            return json.load(response).get('ready') is True
    except (OSError, ValueError):
        return False


def reconciler_running():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 18083))
        return False
    except OSError:
        return True


def launch(script, label):
    STATE.mkdir(exist_ok=True)
    stdout = open(STATE / (label + '.stdout.log'), 'ab')
    stderr = open(STATE / (label + '.stderr.log'), 'ab')
    options = {'cwd': ROOT, 'stdin': subprocess.DEVNULL, 'stdout': stdout, 'stderr': stderr,
               'creationflags': subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
               'start_new_session': os.name != 'nt'}
    process = subprocess.Popen([sys.executable, str(ROOT / 'lab' / script)], **options)
    stdout.close()
    stderr.close()
    return process.pid


def main():
    result = {'ui': 'already running' if ui_running() else launch('control_api.py', 'control-api'),
              'reconciler': 'already running' if reconciler_running() else
              launch('reconcile_leases.py', 'reconciler'),
              'url': 'http://localhost:18082/'}
    (STATE / 'control-processes.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
