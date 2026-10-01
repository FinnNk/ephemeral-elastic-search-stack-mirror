"""Run from the protected target revision; never execute candidate source code."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from relevance_scope import classify
from variant_gate import canonical, check


def decide(changes, base_sha, source_sha, evaluate):
    if not all(re.fullmatch('[0-9a-f]{40}', sha) for sha in (base_sha, source_sha)):
        raise ValueError('The target and candidate must be exact commit SHAs.')
    scope = {'base_sha': base_sha, 'source_sha': source_sha,
             'diff_sha256': hashlib.sha256(changes).hexdigest(), **classify(changes)}
    if scope['documentation_only']:
        return {'kind': 'relevance-gate-verdict', 'state': 'evaluation_not_required', 'scope': scope}
    try:
        result = evaluate()
    except (ValueError, KeyError, subprocess.CalledProcessError) as error:
        result = {'kind': 'relevance-gate-verdict', 'state': 'invalid',
                  'reason': str(error)[:160] if not isinstance(error, subprocess.CalledProcessError)
                  else 'Frozen evaluation evidence could not be retrieved.'}
    return {**result, 'scope': scope}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--changes', required=True, type=Path)
    parser.add_argument('--base-sha', required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--source-repository', required=True)
    parser.add_argument('--selection', required=True, type=Path)
    parser.add_argument('--policy', required=True, type=Path)
    args = parser.parse_args()

    def evaluate():
        if not args.selection.exists():
            raise ValueError('A behaviour change needs gate/selection.json and frozen evaluation evidence.')
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            subprocess.run([sys.executable, str(Path(__file__).with_name('variant_gate_store.py')),
                            'fetch', '--source-sha', args.source_sha, '--directory', directory], check=True)
            return check((evidence / 'report.json').read_bytes(), args.policy.read_bytes(),
                         args.selection.read_bytes(), json.loads((evidence / 'attestation.json').read_bytes()),
                         json.loads((evidence / 'approvals.json').read_bytes()),
                         os.environ['LAB_VARIANT_EVIDENCE_KEY'].encode(),
                         os.environ['LAB_VARIANT_APPROVAL_KEY'].encode(),
                         os.environ['LAB_VARIANT_POLICY_SHA256'], args.source_sha,
                         (evidence / 'build-receipt.json').read_bytes(), args.source_repository)
    try:
        result = decide(args.changes.read_bytes(), args.base_sha, args.source_sha, evaluate)
    except (ValueError, KeyError, subprocess.CalledProcessError) as error:
        result = {'kind': 'relevance-gate-verdict', 'state': 'invalid',
                  'reason': str(error)[:160] if not isinstance(error, subprocess.CalledProcessError)
                  else 'Frozen evaluation evidence could not be retrieved.'}
    print(canonical(result).decode().strip())
    return 0 if result['state'] in ('evaluation_not_required', 'pass', 'approved_exception') else 2


if __name__ == '__main__':
    raise SystemExit(main())
