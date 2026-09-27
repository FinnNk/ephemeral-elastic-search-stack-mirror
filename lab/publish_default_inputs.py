"""Recreate pinned independent manifests from frozen synthetic source bytes."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/platform-spike'))
from publish import publish
from blob_config import settings
from common import STATE
from input_selection import DEFAULTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=STATE / 'releases')
    parser.add_argument('--output-root', type=Path, default=STATE / 'artifacts-reference')
    args = parser.parse_args()
    result = {}
    for release, expected in DEFAULTS.items():
        published = publish(args.source_root / release, args.output_root / release,
                            'synthetic-retail-v2', release, blob_url=settings()[0])
        actual = {kind: entry['manifest_sha256'] for kind, entry in published.items()}
        if actual != expected:
            raise ValueError('Published independent manifests differ from pinned defaults: ' + release)
        result[release] = actual
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
