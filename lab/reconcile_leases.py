"""Run the lease and partial-deletion reconciler independently of the UI."""
import argparse
import json
import socket
import time

from lifecycle import local_lifecycle
from common import IN_CLUSTER, STATE
from operation_telemetry import configure as configure_telemetry


def reconcile_once():
    rows = local_lifecycle().expire()
    if IN_CLUSTER:
        from run_gatling_job import cleanup_orphans
        cleanup_orphans()
    summary = [{'id': row['id'], 'name': row['name'], 'state': row['state']} for row in rows]
    print(json.dumps(summary), flush=True)
    return summary


def main():
    configure_telemetry('lab-lease-worker')
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--interval-seconds', type=int, default=60)
    args = parser.parse_args()
    if args.once:
        reconcile_once()
        return
    if not 10 <= args.interval_seconds <= 600:
        raise ValueError('Reconciliation interval must be 10–600 seconds.')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as singleton:
        singleton.bind(('127.0.0.1', 18083))
        while True:
            if (STATE / 'control-drain').exists():
                return
            try:
                reconcile_once()
            except Exception as error:
                print(json.dumps({'error_kind': type(error).__name__}), flush=True)
            time.sleep(args.interval_seconds)


if __name__ == '__main__':
    main()
