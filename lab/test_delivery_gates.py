"""Promotion refuses stale, failed and incompatible inputs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from delivery_gates import check_report, validate_evidence
from delivery_runtime import compatible
from delivery_promote import validate_pr


class PromotionGateTests(unittest.TestCase):
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
