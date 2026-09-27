"""Attach an independently retained offline report to immutable delivery evidence."""

import argparse
import json
from pathlib import Path

from delivery_gates import attach_offline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--report-reference', required=True, type=Path)
    parser.add_argument('--policy-reference', required=True, type=Path)
    parser.add_argument('--expected', required=True, type=Path)
    args = parser.parse_args()
    result = attach_offline(json.loads(args.evidence.read_bytes()),
                            json.loads(args.report_reference.read_bytes()),
                            json.loads(args.policy_reference.read_bytes()),
                            json.loads(args.expected.read_bytes()))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
