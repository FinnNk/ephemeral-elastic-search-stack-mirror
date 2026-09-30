"""Run a packaged exploratory notebook against an already frozen evaluation report."""

import argparse
import hashlib
import json
from pathlib import Path

from notebook_task import run, source
from compare_search import immutable_blob


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--notebook', required=True)
    args = parser.parse_args()
    source(args.notebook)
    payload = args.report.read_bytes()
    report = json.loads(payload)
    kind = report.get('kind')
    if kind not in ('variant-evaluation-report', 'offline-evaluation-report'):
        raise ValueError('Select a frozen offline evaluation report.')
    digest = hashlib.sha256(payload).hexdigest()
    blob = immutable_blob('runs', kind + '/' + digest + '/evaluation.json', payload)
    print(json.dumps(run(args.notebook, digest, blob), sort_keys=True))


if __name__ == '__main__':
    main()
