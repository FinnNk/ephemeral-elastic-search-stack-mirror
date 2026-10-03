"""Measured gate result and human exception stay distinct."""

from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from variant_gate import approve, attest, canonical, check, sha, sign
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
            'complete': True, 'judgement_selection': 'gate', 'unqualified_judgements': 0,
            'query_count': 100, 'default_variant': 'ranker-a',
            'baseline_variant': 'ranker-b', 'variants': {name: {
                'configuration_sha256': 'c' * 64,
                'image': 'nexus.localhost:18185/search-api@sha256:' + '1' * 64,
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
        self.build = canonical({'source_sha': SOURCE,
            'source_repository': 'elastic-agent/delivery-source',
            'event_kind': 'pull_request', 'run_id': '8', 'run_attempt': '1',
            'image': 'nexus.localhost:18185/search-api@sha256:' + '1' * 64})

    def check(self, approvals=()):
        report, selection = canonical(self.report), canonical(self.selection)
        receipt = attest(report, SOURCE, self.build, EVIDENCE_KEY, STAMP)
        return check(report, self.policy, selection, receipt, list(approvals),
                     EVIDENCE_KEY, APPROVAL_KEY, sha(self.policy), SOURCE,
                     self.build, 'elastic-agent/delivery-source', NOW)

    def test_exploratory_labels_cannot_be_overridden(self):
        for field, value in [('judgement_selection', 'exploratory'),
                             ('unqualified_judgements', 1)]:
            old = self.report[field]
            self.report[field] = value
            with self.assertRaisesRegex(ValueError, 'unqualified'):
                self.check()
            self.report[field] = old

    def test_negative_within_bounds_requires_human_decision(self):
        self.assertEqual(self.check()['state'], 'decision_required')
        self.assertEqual(self.check()['variants'][0]['delta'], -0.02)

    def test_authenticated_exception_retains_measured_loss(self):
        report, selection = canonical(self.report), canonical(self.selection)
        evidence = attest(report, SOURCE, self.build, EVIDENCE_KEY, STAMP)
        with patch('variant_gate_issue.GiteaIdentity') as identity:
            identity.return_value.verify.return_value = {'username': 'finn', 'is_admin': True}
            approval = issue_approval(report, self.policy, selection, evidence,
                self.build, 'elastic-agent/delivery-source',
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
        evidence = attest(report, SOURCE, self.build, EVIDENCE_KEY, STAMP)
        with self.assertRaisesRegex(ValueError, 'attestation belongs'):
            check(report + b' ', self.policy, selection, evidence, [], EVIDENCE_KEY,
                  APPROVAL_KEY, sha(self.policy), SOURCE,
                  self.build, 'elastic-agent/delivery-source', NOW)
        with self.assertRaisesRegex(ValueError, 'trusted policy pin'):
            check(report, self.policy, selection, evidence, [], EVIDENCE_KEY,
                  APPROVAL_KEY, '0' * 64, SOURCE,
                  self.build, 'elastic-agent/delivery-source', NOW)
        with self.assertRaisesRegex(ValueError, 'another report or source'):
            check(report, self.policy, selection, evidence, [], EVIDENCE_KEY,
                  APPROVAL_KEY, sha(self.policy), 'f' * 40,
                  self.build, 'elastic-agent/delivery-source', NOW)

    def test_missing_frozen_evaluator_pin_is_invalid(self):
        del self.report['evaluator_sha256']
        with self.assertRaisesRegex(ValueError, 'frozen evaluator_sha256'):
            self.check()

    def test_selected_variant_must_use_the_exact_source_build_image(self):
        report, selection = canonical(self.report), canonical(self.selection)
        self.report['variants']['ranker-a']['image'] = (
            'nexus.localhost:18185/search-api@sha256:' + '2' * 64)
        report = canonical(self.report)
        receipt = attest(report, SOURCE, self.build, EVIDENCE_KEY, STAMP)
        with self.assertRaisesRegex(ValueError, 'this source build image'):
            check(report, self.policy, selection, receipt, [], EVIDENCE_KEY,
                  APPROVAL_KEY, sha(self.policy), SOURCE,
                  self.build, 'elastic-agent/delivery-source', NOW)

    def test_low_baseline_coverage_cannot_be_overridden(self):
        self.report['coverage']['ranker-b']['fraction'] = 0.79
        self.assertEqual(self.check()['state'], 'blocked')


    def unchanged_low_coverage(self):
        self.selection['selected'][0]['intent'] = 'preserve-results'
        self.report['metrics']['ranker-a']['nDCG@10'] = 0.7
        self.report['delta_from_baseline']['ranker-a']['nDCG@10'] = 0.0
        self.report['coverage']['ranker-a']['fraction'] = 0.297
        self.report['coverage']['ranker-b']['fraction'] = 0.297
        self.report['result_changes']['ranker-a'] = {'changed_queries': 0, 'fraction': 0.0}

    def fixture_approval(self):
        return approve(canonical(self.report), self.policy, canonical(self.selection),
                       SOURCE, 'ranker-a', 'finn',
                       'Accept this unchanged-result fixture with disclosed judgement gaps.',
                       APPROVAL_KEY, STAMP)

    def test_low_coverage_unchanged_results_requires_authenticated_decision(self):
        self.unchanged_low_coverage()
        verdict = self.check()
        self.assertEqual(verdict['state'], 'decision_required')
        item = verdict['variants'][0]
        self.assertTrue(item['coverage_exception'])
        self.assertEqual(item['judged_fraction'], 0.297)
        self.assertEqual(item['baseline_judged_fraction'], 0.297)
        self.assertEqual(item['required_judged_fraction'], 0.8)
        self.assertIsNone(item['approval_sha256'])
        report, selection = canonical(self.report), canonical(self.selection)
        evidence = attest(report, SOURCE, self.build, EVIDENCE_KEY, STAMP)
        with patch('variant_gate_issue.GiteaIdentity') as identity:
            identity.return_value.verify.return_value = {'username': 'finn', 'is_admin': True}
            approval = issue_approval(report, self.policy, selection, evidence,
                self.build, 'elastic-agent/delivery-source', 'ranker-a',
                'Accept the unchanged fixture with coverage explicitly below 80 percent.',
                SOURCE, 'finn', 'test-password', EVIDENCE_KEY, APPROVAL_KEY,
                sha(self.policy), STAMP)
        verdict = self.check([approval])
        self.assertEqual(verdict['state'], 'approved_exception')
        self.assertEqual(verdict['variants'][0]['judged_fraction'], 0.297)
        self.assertEqual(verdict['variants'][0]['delta'], 0)
        self.assertIsNotNone(verdict['variants'][0]['approval_sha256'])

    def test_low_coverage_changed_results_and_loss_cannot_be_overridden(self):
        for change in ('query', 'delta', 'coverage', 'intent', 'tiny-delta'):
            with self.subTest(change=change):
                self.setUp()
                self.unchanged_low_coverage()
                if change == 'query':
                    self.report['result_changes']['ranker-a'] = {
                        'changed_queries': 1, 'fraction': 0.01}
                elif change == 'delta':
                    self.report['metrics']['ranker-a']['nDCG@10'] = 0.69
                    self.report['delta_from_baseline']['ranker-a']['nDCG@10'] = -0.01
                elif change == 'tiny-delta':
                    self.report['metrics']['ranker-a']['nDCG@10'] = 0.70000001
                elif change == 'coverage':
                    self.report['coverage']['ranker-a']['fraction'] = 0.298
                else:
                    self.selection['selected'][0]['intent'] = 'ranking-change'
                self.assertEqual(self.check([self.fixture_approval()])['state'], 'blocked')

    def test_low_coverage_exception_requires_explicit_valid_policy(self):
        self.unchanged_low_coverage()
        policy = json.loads(self.policy)
        del policy['low_coverage_exception']
        self.policy = canonical(policy)
        self.assertEqual(self.check([self.fixture_approval()])['state'], 'blocked')
        invalid = [None, {}, {'intent': 'ranking-change', 'maximum_changed_queries': 0,
                             'required_delta': 0},
                   {'intent': 'preserve-results', 'maximum_changed_queries': 1,
                    'required_delta': 0},
                   {'intent': 'preserve-results', 'maximum_changed_queries': False,
                    'required_delta': 0},
                   {'intent': 'preserve-results', 'maximum_changed_queries': 0,
                    'required_delta': -0.01},
                   {'intent': 'preserve-results', 'maximum_changed_queries': 0,
                    'required_delta': False},
                   {'intent': 'preserve-results', 'maximum_changed_queries': 0,
                    'required_delta': 0, 'extra': True}]
        for stanza in invalid:
            with self.subTest(stanza=stanza):
                policy['low_coverage_exception'] = stanza
                self.policy = canonical(policy)
                with self.assertRaisesRegex(ValueError, 'Low-coverage exception'):
                    self.check()

    def test_low_coverage_exception_retains_identity_and_judgement_guards(self):
        for field, value in [('judgement_selection', 'exploratory'),
                             ('unqualified_judgements', 1)]:
            with self.subTest(field=field):
                self.setUp()
                self.unchanged_low_coverage()
                self.report[field] = value
                with self.assertRaisesRegex(ValueError, 'unqualified'):
                    self.check([self.fixture_approval()])
        self.setUp()
        self.unchanged_low_coverage()
        self.report['variants']['ranker-a']['image'] = (
            'nexus.localhost:18185/search-api@sha256:' + '2' * 64)
        with self.assertRaisesRegex(ValueError, 'this source build image'):
            self.check([self.fixture_approval()])

    def test_low_coverage_approval_cannot_be_retargeted(self):
        self.unchanged_low_coverage()
        original = self.fixture_approval()
        for field, value in [('source_sha', 'f' * 40), ('report_sha256', 'f' * 64),
                             ('policy_sha256', 'f' * 64), ('selection_sha256', 'f' * 64)]:
            with self.subTest(field=field):
                approval = {key: item for key, item in original.items() if key != 'signature'}
                approval[field] = value
                with self.assertRaisesRegex(ValueError, 'another decision'):
                    self.check([sign(approval, APPROVAL_KEY)])
        forged = dict(original, signature='0' * 64)
        with self.assertRaisesRegex(ValueError, 'signature differs'):
            self.check([forged])

    def test_low_coverage_exception_rejects_non_admin_approval(self):
        self.unchanged_low_coverage()
        report, selection = canonical(self.report), canonical(self.selection)
        evidence = attest(report, SOURCE, self.build, EVIDENCE_KEY, STAMP)
        with patch('variant_gate_issue.GiteaIdentity') as identity:
            identity.return_value.verify.return_value = {'username': 'engineer', 'is_admin': False}
            with self.assertRaisesRegex(ValueError, 'administrator'):
                issue_approval(report, self.policy, selection, evidence, self.build,
                    'elastic-agent/delivery-source', 'ranker-a',
                    'Accept this unchanged fixture with disclosed judgement gaps.',
                    SOURCE, 'engineer', 'test-password', EVIDENCE_KEY, APPROVAL_KEY,
                    sha(self.policy), STAMP)

    def test_normal_coverage_is_not_marked_as_coverage_exception(self):
        verdict = self.check()
        self.assertFalse(verdict['variants'][0]['coverage_exception'])


if __name__ == '__main__':
    unittest.main()
