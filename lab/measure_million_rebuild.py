"""Measure a clean local rebuild of the frozen synthetic release."""
import json
import time

from common import STATE, record
from release_million import RELEASE, build


def main():
    output = STATE / 'million-rebuild-check'
    if output.exists():
        raise ValueError('Clean rebuild directory already exists; retain its evidence and use a new path.')
    start = time.monotonic()
    rebuilt = build(output)
    seconds = round(time.monotonic() - start, 3)
    original = json.loads((STATE / 'releases' / RELEASE / 'manifest.json').read_text(encoding='utf-8'))
    if rebuilt != original:
        raise ValueError('Clean rebuild manifest differs from the frozen release.')
    evidence = {'release': RELEASE, 'clean_rebuild_seconds': seconds,
                'sha256': rebuilt['sha256'], 'byte_counts': rebuilt['bytes'],
                'identical_manifest': True}
    record('million-rebuild', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
