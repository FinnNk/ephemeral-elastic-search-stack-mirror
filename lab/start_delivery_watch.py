"""Start the local promotion validator, deployment verifier and preview expiry loop."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def main():
    try:
        with socket.create_connection(('127.0.0.1', 18087), timeout=1):
            print('Delivery watcher is already running.')
            return
    except OSError:
        pass
    state = Path('.lab')
    with (state / 'delivery-watch.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-u', 'lab/delivery_cli.py', 'watch'],
            stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    (state / 'delivery-watch.pid').write_text(str(process.pid), encoding='utf-8')
    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError('Delivery watcher stopped; inspect .lab/delivery-watch.log.')
        try:
            with socket.create_connection(('127.0.0.1', 18087), timeout=1):
                print('Delivery watcher ready; log: .lab/delivery-watch.log')
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError('Delivery watcher did not start.')


if __name__ == '__main__':
    main()
