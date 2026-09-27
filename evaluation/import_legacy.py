"""Adapt one retained complete comparison report into an observation set."""

import argparse
import json
from pathlib import Path

from offline import canonical, import_legacy, sha, validate_observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--captured-at', help='Original comparison completion time, if retained')
    args = parser.parse_args()
    source = args.report.read_bytes()
    value = validate_observations(import_legacy(json.loads(source), sha(source), args.captured_at))
    payload = canonical(value)
    if args.output.exists() and args.output.read_bytes() != payload:
        raise ValueError('Existing observation bytes differ.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists():
        args.output.write_bytes(payload)
    print(json.dumps({'observation_sha256': sha(payload),
                      'query_count': len(value['observations']),
                      'baseline_fingerprint': value['baseline_fingerprint'],
                      'candidate_fingerprint': value['candidate_fingerprint']}))


if __name__ == '__main__':
    main()
