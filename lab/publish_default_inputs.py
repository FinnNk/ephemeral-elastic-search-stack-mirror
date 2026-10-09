"""Recreate pinned independent manifests from frozen source bytes."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from publish import publish
from blob_config import settings, service
from common import STATE
from catalogue import PROFILES
from input_selection import DEFAULTS, fetch_manifest, fetch_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=STATE / 'releases')
    parser.add_argument('--output-root', type=Path, default=STATE / 'artifacts-reference')
    args = parser.parse_args()
    result = {}
    for release, expected in DEFAULTS.items():
        if PROFILES['releases'][release].get('simulated'):
            continue  # The deterministic timeline producer publishes and verifies these separately.
        published = publish(args.source_root / release, args.output_root / release,
                            'esci-import-v1', release, blob_url=settings()[0],
                            container=settings()[1], blob_service=service(),
                            provenance=json.loads((args.source_root / release / 'manifest.json').read_text(encoding='utf-8'))['producer'])
        actual = {kind: entry['manifest_sha256'] for kind, entry in published.items()}
        if actual.get('judgement-set') != expected['judgement-set']:
            selected = fetch_manifest('judgement-set', expected['judgement-set'])
            if selected['producer'].get('selection') != 'demo':
                raise ValueError('Selected judgement snapshot differs from published sources.')
            fetch_rows(selected)
            actual['judgement-set'] = expected['judgement-set']
        if actual != expected:
            raise ValueError('Published independent manifests differ from pinned defaults: ' + release)
        result[release] = actual
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
