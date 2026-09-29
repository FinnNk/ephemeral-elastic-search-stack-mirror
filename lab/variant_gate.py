"""Portable merge gate for attested offline variant evidence and human exceptions."""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def utc(value):
    moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if moment.utcoffset() is None:
        raise ValueError('Evidence time needs a UTC offset.')
    return moment.astimezone(timezone.utc)


def sign(value, key):
    if not key:
        raise ValueError('A trusted signing key is required.')
    payload = dict(value)
    payload['signature'] = hmac.new(key, canonical(value), hashlib.sha256).hexdigest()
    return payload


def verify(value, key, kind):
    if not isinstance(value, dict) or value.get('kind') != kind or \
            value.get('schema_version') != 1 or not re.fullmatch(
                '[0-9a-f]{64}', str(value.get('signature', ''))):
        raise ValueError('Trusted ' + kind + ' receipt is missing.')
    unsigned = {name: field for name, field in value.items() if name != 'signature'}
    if not hmac.compare_digest(sign(unsigned, key)['signature'], value['signature']):
        raise ValueError('Trusted ' + kind + ' signature differs.')


def attest(report_bytes, source_sha, key, issued_at):
    if not re.fullmatch('[0-9a-f]{40}', source_sha):
        raise ValueError('Attestation needs an exact source commit.')
    return sign({'kind': 'variant-evidence-attestation', 'schema_version': 1,
                 'report_sha256': sha(report_bytes), 'source_sha': source_sha,
                 'issued_at': issued_at}, key)


def approve(report_bytes, policy_bytes, selection_bytes, source_sha, variant,
            reviewer, reason, key, decided_at):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', variant) or \
            not reviewer or len(reason.strip()) < 20:
        raise ValueError('Approval needs a variant, reviewer and substantive reason.')
    return sign({'kind': 'variant-exception-approval', 'schema_version': 1,
                 'report_sha256': sha(report_bytes), 'policy_sha256': sha(policy_bytes),
                 'selection_sha256': sha(selection_bytes), 'source_sha': source_sha,
                 'variant': variant, 'reviewer': reviewer,
                 'reason': reason.strip(), 'decided_at': decided_at}, key)


def number(value, name, low=0, high=1):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(name + ' is outside its allowed range.')
    return value


def check(report_bytes, policy_bytes, selection_bytes, attestation, approvals,
          evidence_key, approval_key, trusted_policy_sha, source_sha, now=None):
    """Return a review state; malformed or untrusted evidence raises ValueError."""
    now = now or datetime.now(timezone.utc)
    if not re.fullmatch('[0-9a-f]{40}', source_sha) or \
            sha(policy_bytes) != trusted_policy_sha:
        raise ValueError('Source revision or trusted policy pin differs.')
    report, policy, selection = (json.loads(value) for value in
                                 (report_bytes, policy_bytes, selection_bytes))
    if policy.get('kind') != 'variant-merge-policy' or policy.get('schema_version') != 1:
        raise ValueError('Unsupported variant merge policy.')
    if selection.get('kind') != 'variant-gate-selection' or \
            selection.get('schema_version') != 1 or set(selection) != {
                'kind', 'schema_version', 'selected'}:
        raise ValueError('Selection contract is invalid.')
    if report.get('kind') != 'variant-evaluation-report' or \
            report.get('schema_version') != 1 or report.get('complete') is not True:
        raise ValueError('A complete current variant report is required.')
    variants = report.get('variants')
    baseline = report.get('baseline_variant')
    if not isinstance(variants, dict) or len(variants) < 2 or \
            baseline not in variants or report.get('default_variant') not in variants or \
            set(report.get('metrics', {})) != set(variants) or \
            set(report.get('coverage', {})) != set(variants) or \
            set(report.get('result_changes', {})) != set(variants) or \
            type(report.get('query_count')) is not int or report['query_count'] < 1 or \
            not re.fullmatch('[0-9a-f]{64}', str(report.get('observation_sha256', ''))):
        raise ValueError('Report variant identity or coverage is incomplete.')
    for name in ('variant_set_sha256', 'catalogue_sha256', 'query_suite_sha256',
                 'judgement_sha256', 'judgement_manifest_sha256',
                 'specification_sha256', 'evaluator_sha256'):
        if not re.fullmatch('[0-9a-f]{64}', str(report.get(name, ''))):
            raise ValueError('Report has no frozen ' + name + ' pin.')
    if any(not isinstance(pin, dict) or not re.fullmatch(
            '[0-9a-f]{64}', str(pin.get('configuration_sha256', ''))) or
            not re.fullmatch('[0-9a-f]{64}', str(pin.get('environment_fingerprint', '')))
            for pin in variants.values()):
        raise ValueError('Variant configuration or environment pin is missing.')
    choices = selection.get('selected')
    if not isinstance(choices, list) or not choices or len(choices) != len({
            item.get('variant') for item in choices if isinstance(item, dict)}):
        raise ValueError('Select one or more distinct variants before evaluation.')
    verify(attestation, evidence_key, 'variant-evidence-attestation')
    if attestation.get('report_sha256') != sha(report_bytes) or \
            attestation.get('source_sha') != source_sha:
        raise ValueError('Evidence attestation belongs to another report or source.')
    hours = policy.get('max_age_hours')
    if type(hours) is not int or not 0 < hours <= 720:
        raise ValueError('Evidence age policy is invalid.')
    for field in (report.get('observation_captured_at'), report.get('evaluated_at'),
                  attestation.get('issued_at')):
        if not field or utc(field) > now or now - utc(field) > timedelta(hours=hours):
            raise ValueError('Evidence is outside the allowed time window.')
    metric = policy.get('metric')
    if not isinstance(metric, str) or not metric:
        raise ValueError('Decision metric is missing.')
    minimum_coverage = number(policy.get('minimum_judged_fraction'), 'Coverage policy')
    pass_delta = number(policy.get('pass_min_delta'), 'Pass delta', -1, 1)
    exception_delta = number(policy.get('exception_min_delta'), 'Exception delta', -1, 1)
    if exception_delta > pass_delta:
        raise ValueError('Exception floor exceeds the normal threshold.')
    change_policy = policy.get('changed_query_fraction')
    if not isinstance(change_policy, dict) or set(change_policy) != {
            'preserve-results', 'ranking-change'}:
        raise ValueError('Both release intents need changed-result policy.')
    for limits in change_policy.values():
        if not isinstance(limits, dict) or set(limits) != {'pass', 'exception'} or \
                number(limits['pass'], 'Result threshold') > \
                number(limits['exception'], 'Result exception threshold'):
            raise ValueError('Result-change thresholds are invalid.')
    baseline_score = number(report['metrics'][baseline].get(metric), 'Baseline metric')
    baseline_coverage = number(report['coverage'][baseline].get('fraction'),
                               'Baseline judged coverage')
    receipts = []
    for choice in choices:
        if not isinstance(choice, dict) or set(choice) != {'variant', 'intent'}:
            raise ValueError('Selected variant and intent must be explicit.')
        variant, intent = choice['variant'], choice['intent']
        if variant not in variants or variant == baseline or intent not in change_policy:
            raise ValueError('Selection names an unknown variant, baseline or intent.')
        score = number(report['metrics'][variant].get(metric), 'Selected metric')
        coverage = number(report['coverage'][variant].get('fraction'), 'Judged coverage')
        changed = report['result_changes'][variant]
        fraction = number(changed.get('fraction'), 'Changed-query fraction')
        if type(changed.get('changed_queries')) is not int or \
                changed['changed_queries'] < 0 or changed['changed_queries'] > report['query_count'] or \
                abs(fraction - round(changed['changed_queries'] / report['query_count'], 6)) > 1e-6:
            raise ValueError('Changed-query count and fraction differ.')
        delta = round(score - baseline_score, 6)
        if report.get('delta_from_baseline', {}).get(variant, {}).get(metric) != delta:
            raise ValueError('Reported metric delta differs from its scores.')
        limits = change_policy[intent]
        if baseline_coverage < minimum_coverage or coverage < minimum_coverage or \
                delta < exception_delta or \
                fraction > limits['exception']:
            state = 'blocked'
        elif delta >= pass_delta and fraction <= limits['pass']:
            state = 'pass'
        else:
            state = 'decision_required'
        matching_approvals = [item for item in approvals if isinstance(item, dict) and
                              item.get('variant') == variant]
        if len(matching_approvals) > 1:
            raise ValueError('Multiple approvals target the same selected variant.')
        approval = matching_approvals[0] if matching_approvals else None
        if approval is not None:
            verify(approval, approval_key, 'variant-exception-approval')
            if any(approval.get(key) != expected for key, expected in {
                    'report_sha256': sha(report_bytes), 'policy_sha256': sha(policy_bytes),
                    'selection_sha256': sha(selection_bytes), 'source_sha': source_sha,
                    'variant': variant}.items()) or not approval.get('reviewer') or \
                    len(str(approval.get('reason', '')).strip()) < 20 or \
                    utc(approval['decided_at']) > now:
                raise ValueError('Approval belongs to another decision or lacks provenance.')
            if state == 'decision_required':
                state = 'approved_exception'
        receipts.append({'variant': variant, 'intent': intent, 'state': state,
                         'baseline': baseline, 'metric': metric, 'value': score,
                         'delta': delta, 'judged_fraction': coverage,
                         'changed_query_fraction': fraction,
                         'approval_sha256': sha(canonical(approval)) if
                         state == 'approved_exception' else None})
    states = {item['state'] for item in receipts}
    overall = ('blocked' if 'blocked' in states else
               'decision_required' if 'decision_required' in states else
               'approved_exception' if 'approved_exception' in states else 'pass')
    return {'kind': 'variant-gate-verdict', 'schema_version': 1,
            'state': overall, 'report_sha256': sha(report_bytes),
            'policy_sha256': sha(policy_bytes), 'selection_sha256': sha(selection_bytes),
            'source_sha': source_sha, 'variants': receipts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--policy', required=True, type=Path)
    parser.add_argument('--selection', required=True, type=Path)
    parser.add_argument('--attestation', required=True, type=Path)
    parser.add_argument('--approval', type=Path, action='append', default=[])
    parser.add_argument('--approvals-file', type=Path)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        approvals = [json.loads(path.read_bytes()) for path in args.approval]
        if args.approvals_file:
            approvals.extend(json.loads(args.approvals_file.read_bytes()))
        verdict = check(args.report.read_bytes(), args.policy.read_bytes(),
                        args.selection.read_bytes(), json.loads(args.attestation.read_bytes()),
                        approvals,
                        os.environ['LAB_VARIANT_EVIDENCE_KEY'].encode(),
                        os.environ['LAB_VARIANT_APPROVAL_KEY'].encode(),
                        os.environ['LAB_VARIANT_POLICY_SHA256'], args.source_sha)
    except (ValueError, KeyError) as error:
        verdict = {'kind': 'variant-gate-verdict', 'state': 'invalid',
                   'reason': str(error)[:160]}
    payload = canonical(verdict)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
    print(payload.decode().strip())
    return {'pass': 0, 'approved_exception': 0, 'invalid': 2,
            'decision_required': 3, 'blocked': 4}[verdict['state']]


if __name__ == '__main__':
    raise SystemExit(main())
