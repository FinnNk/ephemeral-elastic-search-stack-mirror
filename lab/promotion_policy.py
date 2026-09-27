"""Evaluate exact offline report inputs against a separate delivery policy."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def utc(value):
    moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if moment.utcoffset() is None:
        raise ValueError('Evidence time must include a UTC offset.')
    return moment.astimezone(timezone.utc)


def validate(report_bytes, policy_bytes, expected, now=None):
    now = now or datetime.now(timezone.utc)
    report = json.loads(report_bytes)
    policy = json.loads(policy_bytes)
    if policy.get('kind') != 'promotion-policy' or policy.get('schema_version') != 1 or \
            policy.get('review') != 'human approval required':
        raise ValueError('Unsupported promotion policy or review rule.')
    if report.get('kind') != 'offline-evaluation-report' or \
            report.get('schema_version') != 1 or report.get('complete') is not True:
        raise ValueError('An incomplete evaluation cannot pass delivery policy.')
    fields = ('baseline_fingerprint', 'candidate_fingerprint', 'catalogue_sha256',
              'query_suite_sha256', 'observation_sha256', 'judgement_sha256',
              'judgement_manifest_sha256', 'specification_sha256', 'evaluator_sha256')
    if set(expected) != set(fields) or any(report.get(key) != expected[key] for key in fields):
        raise ValueError('Evaluation report belongs to another exact input set.')
    if not isinstance(report.get('query_count'), int) or report['query_count'] <= 0:
        raise ValueError('Evaluation has no complete query set.')
    for name, timestamp, hours in (
            ('capture', report.get('observation_captured_at'), policy['max_capture_age_hours']),
            ('evaluation', report.get('evaluated_at'), policy['max_evaluation_age_hours'])):
        if not timestamp or not 0 < hours <= 24 * 30:
            raise ValueError(name + ' time or policy window is missing.')
        moment = utc(timestamp)
        if moment > now or now - moment > timedelta(hours=hours):
            raise ValueError(name + ' evidence is outside the policy window.')
    minimum = policy['minimum_judged_fraction']
    if not 0 <= minimum <= 1:
        raise ValueError('Judgement coverage policy is invalid.')
    for side in ('baseline', 'candidate'):
        metrics = report.get('metrics', {}).get(side, {})
        if any(name not in metrics for name in policy['required_metrics']):
            raise ValueError('Required evaluation metric is missing.')
        coverage = report.get('coverage', {}).get(side, {})
        if coverage.get('fraction') is None or coverage['fraction'] < minimum:
            raise ValueError('Judgement coverage is below the policy threshold.')
    if set(policy['required_other_checks']) != {'result-regression', 'performance'}:
        raise ValueError('The other black-box delivery gates must remain explicit.')
    return {'passed': True, 'report_sha256': sha(report_bytes),
            'policy_sha256': sha(policy_bytes), 'review_required': True,
            'baseline_fingerprint': expected['baseline_fingerprint'],
            'candidate_fingerprint': expected['candidate_fingerprint']}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--policy', required=True, type=Path)
    parser.add_argument('--expected', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.report.read_bytes(), args.policy.read_bytes(),
                              json.loads(args.expected.read_bytes())), indent=2))


if __name__ == '__main__':
    main()
