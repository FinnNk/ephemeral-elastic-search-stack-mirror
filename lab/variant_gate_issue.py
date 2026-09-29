"""Issue trusted evidence and authenticated human exception receipts."""

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path

from control_identity import GiteaIdentity
from keyvault import floci_forward, vault_request
from variant_gate import approve, attest, canonical, check, sha


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


def issue_approval(report, policy, selection, attestation, build_receipt,
                   source_repository, variant, reason,
                   source_sha, username, password, evidence_key, approval_key,
                   policy_sha, decided_at):
    identity = GiteaIdentity().verify(username, password)
    if not identity['is_admin']:
        raise ValueError('A Gitea administrator must approve an exception.')
    verdict = check(report, policy, selection, attestation, [], evidence_key,
                    approval_key, policy_sha, source_sha,
                    build_receipt, source_repository,
                    datetime.fromisoformat(decided_at.replace('Z', '+00:00')))
    matching = [item for item in verdict['variants'] if item['variant'] == variant]
    if len(matching) != 1 or matching[0]['state'] != 'decision_required':
        raise ValueError('The named variant has no approvable exception.')
    return approve(report, policy, selection, source_sha, variant,
                   identity['username'], reason, approval_key, decided_at)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    evidence = sub.add_parser('attest')
    evidence.add_argument('--report', required=True, type=Path)
    evidence.add_argument('--source-sha', required=True)
    evidence.add_argument('--build-receipt', required=True, type=Path)
    evidence.add_argument('--output', required=True, type=Path)
    approval = sub.add_parser('approve')
    for name in ('report', 'policy', 'selection', 'attestation', 'build-receipt', 'output'):
        approval.add_argument('--' + name, required=True, type=Path)
    for name in ('source-sha', 'source-repository', 'variant', 'reason', 'username'):
        approval.add_argument('--' + name, required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    if args.action == 'attest':
        receipt = attest(args.report.read_bytes(), args.source_sha,
                         args.build_receipt.read_bytes(),
                         operator_key('LAB_VARIANT_EVIDENCE_KEY'), now)
    else:
        receipt = issue_approval(args.report.read_bytes(), args.policy.read_bytes(),
            args.selection.read_bytes(), json.loads(args.attestation.read_bytes()),
            args.build_receipt.read_bytes(), args.source_repository,
            args.variant, args.reason, args.source_sha, args.username,
            getpass.getpass('Gitea password: '),
            operator_key('LAB_VARIANT_EVIDENCE_KEY'),
            operator_key('LAB_VARIANT_APPROVAL_KEY'),
            sha((Path(__file__).resolve().parent /
                'delivery/policies/variant-merge-v1.json').read_bytes()), now)
    print(json.dumps({'receipt_sha256': write_immutable(args.output, receipt),
                      'output': str(args.output)}, sort_keys=True))


if __name__ == '__main__':
    main()
