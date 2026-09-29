"""Measured gate result and human exception stay distinct."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from variant_gate import approve, attest, canonical, check, sha
from variant_gate_issue import issue_approval


NOW = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
STAMP = NOW.isoformat()
SOURCE = 'a' * 40
EVIDENCE_KEY = b'synthetic-evaluator-key'
APPROVAL_KEY = b'synthetic-reviewer-key'
POLICY = Path(__file__).resolve().parent / 'delivery/policies/variant-merge-v1.json'


class VariantGateTests(unittest.TestCase):
    def setUp(self):
        self.policy = POLICY.read_bytes()
        self.report = {'kind': 'variant-evaluation-report', 'schema_version': 1,
            'complete': True, 'query_count': 100, 'default_variant': 'ranker-a',
            'baseline_variant': 'ranker-b', 'variants': {name: {
                'configuration_sha256': 'c' * 64,
                'environment_fingerprint': 'd' * 64} for name in
                ('ranker-a', 'ranker-b', 'ranker-c')},
            'observation_sha256': 'b' * 64,
            'observation_captured_at': STAMP, 'evaluated_at': STAMP,
            'metrics': {'ranker-a': {'nDCG@10': 0.68},
                        'ranker-b': {'nDCG@10': 0.7},
                        'ranker-c': {'nDCG@10': 0.72}},
            'delta_from_baseline': {'ranker-a': {'nDCG@10': -0.02},
                                    'ranker-c': {'nDCG@10': 0.02}},
            'coverage': {name: {'fraction': 0.8} for name in
                         ('ranker-a', 'ranker-b', 'ranker-c')},
            'result_changes': {name: {'changed_queries': 1, 'fraction': 0.01}
                               for name in ('ranker-a', 'ranker-c')}}
        for name in ('variant_set_sha256', 'catalogue_sha256', 'query_suite_sha256',
                     'judgement_sha256', 'judgement_manifest_sha256',
                     'specification_sha256', 'evaluator_sha256'):
            self.report[name] = 'e' * 64
        self.report['result_changes']['ranker-b'] = {'changed_queries': 0, 'fraction': 0.0}
        self.selection = {'kind': 'variant-gate-selection', 'schema_version': 1,
            'selected': [
                {'variant': 'ranker-a', 'intent': 'ranking-change'}]}

    def check(self, approvals=()):
        report, selection = canonical(self.report), canonical(self.selection)
        receipt = attest(report, SOURCE, EVIDENCE_KEY, STAMP)
        return check(report, self.policy, selection, receipt, list(approvals),
                     EVIDENCE_KEY, APPROVAL_KEY, sha(self.policy), SOURCE, NOW)

    def test_negative_within_bounds_requires_human_decision(self):
        self.assertEqual(self.check()['state'], 'decision_required')
        self.assertEqual(self.check()['variants'][0]['delta'], -0.02)

    def test_authenticated_exception_retains_measured_loss(self):
        report, selection = canonical(self.report), canonical(self.selection)
        evidence = attest(report, SOURCE, EVIDENCE_KEY, STAMP)
        with patch('variant_gate_issue.GiteaIdentity') as identity:
            identity.return_value.verify.return_value = {'username': 'finn', 'is_admin': True}
            approval = issue_approval(report, self.policy, selection, evidence,
                'ranker-a', 'Security fix accepted with bounded relevance loss.',
                SOURCE, 'finn', 'test-password', EVIDENCE_KEY, APPROVAL_KEY,
                sha(self.policy), STAMP)
        verdict = self.check([approval])
        self.assertEqual(verdict['state'], 'approved_exception')
        self.assertEqual(verdict['variants'][0]['delta'], -0.02)
        self.assertEqual(approval['reviewer'], 'finn')

    def test_forged_or_retargeted_approval_is_invalid(self):
        report, selection = canonical(self.report), canonical(self.selection)
        approval = approve(report, self.policy, selection, SOURCE, 'ranker-a',
            'finn', 'A sufficiently detailed reason for review.', APPROVAL_KEY, STAMP)
        approval['reason'] = 'Forged reason after approval.'
        with self.assertRaisesRegex(ValueError, 'signature differs'):
            self.check([approval])

    def test_outside_exception_band_stays_blocked(self):
        self.report['metrics']['ranker-a']['nDCG@10'] = 0.6
        self.report['delta_from_baseline']['ranker-a']['nDCG@10'] = -0.1
        self.assertEqual(self.check()['state'], 'blocked')

    def test_preservation_gate_and_multiple_selected_variants(self):
        self.selection['selected'] = [
            {'variant': 'ranker-a', 'intent': 'preserve-results'},
            {'variant': 'ranker-c', 'intent': 'ranking-change'}]
        self.assertEqual(self.check()['state'], 'decision_required')
        self.assertEqual(self.check()['variants'][1]['state'], 'pass')

    def test_untrusted_report_or_wrong_policy_is_invalid(self):
        report, selection = canonical(self.report), canonical(self.selection)
        evidence = attest(report, SOURCE, EVIDENCE_KEY, STAMP)
        with self.assertRaisesRegex(ValueError, 'attestation belongs'):
            check(report + b' ', self.policy, selection, evidence, [], EVIDENCE_KEY,
                  APPROVAL_KEY, sha(self.policy), SOURCE, NOW)
        with self.assertRaisesRegex(ValueError, 'trusted policy pin'):
            check(report, self.policy, selection, evidence, [], EVIDENCE_KEY,
                  APPROVAL_KEY, '0' * 64, SOURCE, NOW)
        with self.assertRaisesRegex(ValueError, 'another report or source'):
            check(report, self.policy, selection, evidence, [], EVIDENCE_KEY,
                  APPROVAL_KEY, sha(self.policy), 'f' * 40, NOW)

    def test_missing_frozen_evaluator_pin_is_invalid(self):
        del self.report['evaluator_sha256']
        with self.assertRaisesRegex(ValueError, 'frozen evaluator_sha256'):
            self.check()

    def test_low_baseline_coverage_cannot_be_overridden(self):
        self.report['coverage']['ranker-b']['fraction'] = 0.79
        self.assertEqual(self.check()['state'], 'blocked')


if __name__ == '__main__':
    unittest.main()
