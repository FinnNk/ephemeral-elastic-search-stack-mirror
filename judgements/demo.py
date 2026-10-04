"""Replay saved probabilities under an explicit, scoped lab demo policy."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from core import canonical, digest
from esci.contract import outcome, validate_policy as validate_acceptance


def validate_policy(policy):
    if policy.get('kind') != 'lab-demo-judgement-policy' or policy.get('schema_version') != 1:
        raise ValueError('Unsupported lab demo policy.')
    context, model = policy['context'], policy['model']
    if set(context) != {'catalogue_sha256', 'query_suite_sha256', 'rubric'} or \
            context['rubric'] != 'esci-v1' or any(not re.fullmatch('[0-9a-f]{64}', context[k])
            for k in ('catalogue_sha256', 'query_suite_sha256')):
        raise ValueError('Demo policy needs an exact ESCI source scope.')
    if set(model) != {'name', 'version', 'artifact_sha256'} or not all(model.values()) or \
            not re.fullmatch('[0-9a-f]{64}', model['artifact_sha256']):
        raise ValueError('Demo policy needs an exact model identity.')
    approval = policy.get('authorisation', {})
    if not approval.get('reviewer') or approval.get('purpose') != 'local ESCI demos' or \
            not approval.get('decided_at') or len(approval.get('reason', '').strip()) < 20:
        raise ValueError('Demo policy requires recorded human authorisation.')
    validate_acceptance(policy['acceptance'])


def policy_sha(policy):
    return digest(canonical(policy))


def validate_record(record, policy):
    validate_policy(policy)
    source = record.get('provenance', {})
    if record.get('gate_eligible') is not False or \
            source.get('qualification') != 'lab-demo-authorised' or \
            source.get('model') != policy['model'] or \
            source.get('policy_sha256') != policy_sha(policy) or \
            source.get('authorisation') != policy['authorisation']:
        raise ValueError('Model evidence is outside the authorised demo policy.')
    decision = outcome(record['probabilities'], policy['acceptance'])
    if any(record.get(key) != value for key, value in decision.items()):
        raise ValueError('Demo label differs from its saved probability decision.')


def replay(saved, policy, saved_sha):
    validate_policy(policy)
    if saved.get('kind') != 'judgement-pass' or saved.get('complete') is not True or \
            saved.get('model') != policy['model'] or saved.get('context') != policy['context']:
        raise ValueError('Saved pass is incomplete or belongs to another model/source.')
    identity = policy_sha(policy)
    seen, records = set(), []
    for row in saved['records']:
        key = row['query_id'], row['product_id']
        if key in seen or row.get('gate_eligible') is not False or \
                row.get('provenance', {}).get('model') != policy['model']:
            raise ValueError('Saved prediction is duplicated, eligible or from another model.')
        seen.add(key)
        source = {**row['provenance'], 'qualification': 'lab-demo-authorised',
                  'policy_sha256': identity, 'pass_id': 'lab-demo-' + identity[:16],
                  'saved_prediction_pass_sha256': saved_sha,
                  'authorisation': policy['authorisation']}
        source['source_id'] = digest(canonical(source))
        record = {**row, **outcome(row['probabilities'], policy['acceptance']),
                  'gate_eligible': False, 'provenance': source}
        validate_record(record, policy)
        records.append(record)
    return {**saved, 'records': records, 'selection': 'demo',
            'saved_prediction_pass_sha256': saved_sha, 'demo_policy_sha256': identity,
            'counts': dict(Counter(row['outcome'] for row in records)),
            'accepted_by_label': dict(Counter(row['label'] for row in records
                                             if row['outcome'] == 'labelled')),
            # Coverage must be recomputed against actual frozen observations.
            'coverage': None, 'seconds': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved-pass', required=True, type=Path)
    parser.add_argument('--policy', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw = args.saved_pass.read_bytes()
    result = replay(json.loads(raw), json.loads(args.policy.read_bytes()), digest(raw))
    payload = canonical(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and args.output.read_bytes() != payload:
        raise ValueError('Preserve previous passes; use a new output path.')
    args.output.write_bytes(payload)
    print(json.dumps({k: result[k] for k in ('counts', 'accepted_by_label', 'demo_policy_sha256')}))


if __name__ == '__main__':
    main()
