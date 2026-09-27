"""Keep the browser-only control port forward attached after Pod replacement."""

import signal
import subprocess
import time

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KUBE = ['kubectl', '--kubeconfig', str(ROOT / '.lab/kubeconfig.yaml')]
running = True
child = None


def stop(_signal, _frame):
    global running
    running = False
    if child and child.poll() is None:
        child.terminate()


def main():
    global child
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        child = subprocess.Popen(KUBE + ['-n', 'lab-control', 'port-forward',
            'svc/lab-control', '18082:18082', '--address', '127.0.0.1'], cwd=ROOT)
        child.wait()
        child = None
        if running:
            time.sleep(2)


if __name__ == '__main__':
    main()
