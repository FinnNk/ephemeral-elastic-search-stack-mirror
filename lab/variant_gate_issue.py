"""Issue trusted evaluation attestations. Relevance decisions are reviewed in Git."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from keyvault import floci_forward, vault_request
from variant_gate import attest, canonical, sha


def operator_key(name):
    if value := os.environ.get(name):
        return value.encode()
    remote = 'lab-variant-gate-' + name.lower().replace('_', '-')
    with floci_forward() as base:
        record = vault_request(base, remote)
    if record is None:
        raise ValueError('Run the variant-gate secret setup before issuing receipts.')
    return record['value'].encode()


def write_immutable(path, value):
    payload = canonical(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != payload:
        raise ValueError('Existing signed receipt differs.')
    if not path.exists():
        path.write_bytes(payload)
    return sha(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    evidence = sub.add_parser('attest')
    evidence.add_argument('--report', required=True, type=Path)
    evidence.add_argument('--source-sha', required=True)
    evidence.add_argument('--build-receipt', required=True, type=Path)
    evidence.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    receipt = attest(args.report.read_bytes(), args.source_sha,
                     args.build_receipt.read_bytes(),
                     operator_key('LAB_VARIANT_EVIDENCE_KEY'), now,
                     json.loads((Path(__file__).resolve().parent /
                         'delivery/policies/variant-merge-v1.json').read_bytes()))
    print(json.dumps({'receipt_sha256': write_immutable(args.output, receipt),
                      'output': str(args.output)}, sort_keys=True))


if __name__ == '__main__':
    main()
