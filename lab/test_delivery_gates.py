"""Promotion refuses stale, failed and incompatible inputs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from delivery_gates import check_report, validate_evidence, validate_offline_addendum
from delivery_runtime import compatible
from delivery_promote import approved_head, validate_pr
from delivery_cli import execute, parser


class PromotionGateTests(unittest.TestCase):
    def test_separate_reviewer_must_approve_exact_head(self):
        review = {'state': 'APPROVED', 'commit_id': 'head',
                  'user': {'login': 'lab-admin'}}
        self.assertTrue(approved_head([review], 'head'))
        self.assertFalse(approved_head([review], 'new-head'))
        self.assertFalse(approved_head([{**review, 'user': {'login': 'elastic-agent'}}], 'head'))
        self.assertFalse(approved_head([{**review, 'user': {}}], 'head'))
        self.assertFalse(approved_head([{**review, 'state': 'COMMENT'}], 'head'))

    def test_rollback_carries_explicit_ranking_intent(self):
        args = parser().parse_args(['rollback', 'integration', '--fingerprint', 'a' * 64,
                                    '--evidence', 'reference.json', '--intent', 'ranking-change'])
        self.assertEqual(args.intent, 'ranking-change')

    def test_target_evaluation_uses_exact_current_and_historical_definitions(self):
        args = parser().parse_args(['evaluate-target', 'production', '--fingerprint', 'a' * 64,
                                    '--intent', 'ranking-change'])
        current = {'fingerprint': 'current'}
        old = {'fingerprint': 'old'}
        with patch('delivery_cli.checkout'), patch('delivery_cli.read_target', return_value=current), \
             patch('delivery_cli.historical', return_value=old) as history, \
             patch('delivery_cli.recorded_evaluation', return_value={'ok': True}) as record:
            self.assertEqual(execute(args), {'ok': True})
        history.assert_called_once_with('production', 'a' * 64)
        record.assert_called_once_with(current, old, 'ranking-change', 'production-load')

    def test_target_evaluation_resolves_new_candidate_against_current_target(self):
        args = parser().parse_args(['evaluate-target', 'integration', '--run', '21',
                                    '--dataset', 'retail-gb-1m-v1', '--recipe', 'recipe'])
        current = {'fingerprint': 'current'}
        candidate = {'fingerprint': 'new'}
        with patch('delivery_cli.checkout'), patch('delivery_cli.read_target', return_value=current), \
             patch('delivery_cli.resolve', return_value=candidate) as resolved, \
             patch('delivery_cli.recorded_evaluation', return_value={'ok': True}) as record:
            self.assertEqual(execute(args), {'ok': True})
        resolved.assert_called_once_with(21, 'retail-gb-1m-v1', 'recipe',
                                         query_manifest_sha=None, judgement_manifest_sha=None)
        record.assert_called_once_with(current, candidate, 'preserve-results', 'probe')

    def functional(self, mode='result-regression'):
        return {'mode': mode, 'scope': 'full', 'complete': True, 'query_count': 1000,
                'completed_query_count': 1000, 'verdict': 'unchanged',
                'baseline': {'fingerprint': 'B'}, 'candidate': {'fingerprint': 'C'}}

    def test_changed_results_need_explicit_ranking_intent(self):
        report = self.functional()
        report['verdict'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'changed query results'):
            check_report(report, 'result-regression', 'B', 'C', 'preserve-results')
        check_report(report, 'result-regression', 'B', 'C', 'ranking-change')

    def test_old_baseline_does_not_approve_new_target(self):
        with self.assertRaisesRegex(ValueError, 'different baseline'):
            check_report(self.functional(), 'result-regression', 'B2', 'C', 'preserve-results')

    def test_partial_suite_is_not_a_promotion_pass(self):
        report = self.functional()
        report['completed_query_count'] = 999
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            check_report(report, 'result-regression', 'B', 'C', 'preserve-results')

    def test_failed_gatling_is_not_a_promotion_pass(self):
        report = {**self.functional(), 'kind': 'paired-api-performance', 'valid': True,
                  'same_workload': True, 'warmup_ready': True, 'verdict': 'budget-missed',
                  'measured_phases': {'normal': {}}}
        with self.assertRaisesRegex(ValueError, 'Performance check failed'):
            check_report(report, 'performance', 'B', 'C', 'preserve-results')

    def test_expired_evidence_and_changed_intent_rejected(self):
        value = {'baseline': 'B', 'candidate': 'C', 'intent': 'preserve-results',
                 'completed_at': (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()}
        with patch('delivery_gates.read', return_value=value):
            with self.assertRaisesRegex(ValueError, 'three-day'):
                validate_evidence({}, 'B', 'C', 'preserve-results')
            with self.assertRaisesRegex(ValueError, 'stale'):
                validate_evidence({}, 'B', 'C', 'ranking-change')

    def test_promotion_rejects_other_selected_inputs_and_reports(self):
        selected = {'catalogue_manifest_sha256': 'a' * 64,
                    'query_manifest_sha256': 'b' * 64,
                    'judgement_manifest_sha256': 'c' * 64}
        evidence = {'baseline': 'B', 'candidate': 'C', 'intent': 'preserve-results',
                    'selected_inputs': selected, 'completed_at': datetime.now(timezone.utc).isoformat(),
                    'reports': {mode: {'sha256': mode} for mode in
                                ('result-regression', 'relevance', 'performance')}}
        with patch('delivery_gates.read', return_value=evidence):
            with self.assertRaisesRegex(ValueError, 'different catalogue, query or judgement'):
                validate_evidence({}, 'B', 'C', 'preserve-results',
                                  {**selected, 'query_manifest_sha256': 'd' * 64})
        result = {'query_manifest_sha256': 'd' * 64}
        with patch('delivery_gates.read', side_effect=[evidence, result]), \
             patch('delivery_gates.check_report'):
            with self.assertRaisesRegex(ValueError, 'different selected inputs'):
                validate_evidence({}, 'B', 'C', 'preserve-results', selected)

    def test_optional_offline_report_matches_delivery_capture_and_pinned_policy(self):
        from pathlib import Path
        import json
        policy = (Path(__file__).parent / 'delivery/policies/observation-evidence-v1.json').read_bytes()
        expected = {key: key for key in ('catalogue_sha256', 'query_suite_sha256',
                    'observation_sha256', 'judgement_sha256', 'judgement_manifest_sha256',
                    'specification_sha256', 'evaluator_sha256')}
        expected.update(baseline_fingerprint='B', candidate_fingerprint='C')
        now = datetime.now(timezone.utc).isoformat()
        report = {'kind': 'offline-evaluation-report', 'schema_version': 1, 'complete': True,
                  **expected, 'query_count': 2, 'observation_captured_at': now,
                  'evaluated_at': now, 'metrics': {'baseline': {'nDCG@10': 0.3, 'Judged@10': 0.2},
                                                  'candidate': {'nDCG@10': 0.4, 'Judged@10': 0.2}},
                  'coverage': {'baseline': {'fraction': 0.2}, 'candidate': {'fraction': 0.2}}}
        relevance = {'baseline': {'dataset_sha256': 'catalogue_sha256'},
                     'candidate': {'dataset_sha256': 'catalogue_sha256'},
                     'suite_sha256': 'query_suite_sha256',
                     'observation_sha256': 'observation_sha256'}
        addendum = {'expected': expected, 'report': {}, 'policy': {}}
        with patch('delivery_gates.read_offline', side_effect=[json.dumps(report).encode(), policy]):
            self.assertTrue(validate_offline_addendum(addendum, relevance, 'B', 'C')['review_required'])
        changed = {**relevance, 'observation_sha256': 'another-capture'}
        with self.assertRaisesRegex(ValueError, 'another delivery execution'):
            validate_offline_addendum(addendum, changed, 'B', 'C')
        with patch('delivery_gates.read_offline', side_effect=[json.dumps(report).encode(), b'{}']):
            with self.assertRaisesRegex(ValueError, 'pinned delivery policy'):
                validate_offline_addendum(addendum, relevance, 'B', 'C')

    def test_schema_engine_or_indexer_drift_rejected(self):
        recipe = {'engine_version': '9.5.4', 'index_definition': {'settings': {}, 'mappings': {}},
                  'indexer': {'image': 'image@sha256:A', 'source_sha256': 'A'}}
        release = {'index_contract': {'engine_version': '9.5.4', 'definitions': [recipe['index_definition']],
                                      'indexer_image': recipe['indexer']['image'], 'indexer_source_sha256': 'A'}}
        compatible(release, recipe)
        for field, changed in [('engine_version', '10'), ('index_definition', {'mappings': {'new': True}}),
                               ('indexer', {'image': 'other', 'source_sha256': 'B'})]:
            candidate = deepcopy(recipe)
            candidate[field] = changed
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'incompatible'):
                compatible(release, candidate)

    def test_head_change_never_receives_success(self):
        pr = {'head': {'sha': 'old'}, 'html_url': 'http://local/pr/1'}
        new = {'head': {'sha': 'new'}}
        with patch('delivery_promote.api', return_value=pr) as api, \
                patch('delivery_promote.inspect_pr', return_value=(new, {})):
            result = validate_pr(1)
            self.assertFalse(result['passed'])
            self.assertEqual(api.call_args.args[2]['state'], 'failure')


if __name__ == '__main__':
    unittest.main()
