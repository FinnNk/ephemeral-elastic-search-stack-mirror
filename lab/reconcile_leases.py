"""Run the lease and partial-deletion reconciler independently of the UI."""
import argparse
import json
import time

from lifecycle import local_lifecycle


def reconcile_once():
    rows = local_lifecycle().expire()
    summary = [{'id': row['id'], 'name': row['name'], 'state': row['state']} for row in rows]
    print(json.dumps(summary), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--interval-seconds', type=int, default=60)
    args = parser.parse_args()
    if args.once:
        reconcile_once()
        return
    if not 10 <= args.interval_seconds <= 600:
        raise ValueError('Reconciliation interval must be 10–600 seconds.')
    while True:
        try:
            reconcile_once()
        except Exception as error:
            print(json.dumps({'error_kind': type(error).__name__}), flush=True)
        time.sleep(args.interval_seconds)


if __name__ == '__main__':
    main()
