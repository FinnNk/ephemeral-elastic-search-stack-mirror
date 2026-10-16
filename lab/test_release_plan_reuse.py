"""Reusing selections never reuses approval or duplicates a queued check."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from delivery_operations import Operations, validate
import release_plan_reuse as reuse


class PlanReuse(unittest.TestCase):
    def setUp(self):
        self.pin = {'target': 'staging', 'candidate': {'build_run': 207, 'fingerprint': 'new',
            'fields': {'dataset_release': 'catalogue'}}, 'baseline': {'fingerprint': 'old'},
            'primary_query_sets': ['standard'], 'policy_sha256': 'policy'}
        self.suggestion = {'binding': self.pin, 'variants': [{'variant': 'a', 'intent': 'preserve-results'}],
            'suites': [{'id': 'x', 'required': False}, {'id': 'y', 'required': True}]}
        self.previous = {'suggestion': {'binding': {**self.pin, 'target': 'integration'}},
            'reviewer': 'reviewer', 'edits': {'variants': [{'variant': 'a', 'intent': 'ranking-change'}],
                'suites': [{'id': 'x', 'disposition': 'report_only', 'reason': ''},
                           {'id': 'y', 'disposition': 'retired', 'reason': 'A previous environment-specific decision.'}],
                'additional_query_sets': [], 'reason': 'Additional checks remain informational for this release.'}}

    def recommend(self):
        import release_check_plans as plans
        pr = {'number': 32, 'merged': True, 'merge_commit_sha': 'merge'}
        with patch.object(plans, 'pulls', return_value=[pr]), \
                patch.object(plans, 'inspect', return_value=(pr, 'path', b'original', self.previous)), \
                patch.object(plans, 'content', return_value=b'original'), \
                patch.object(plans, 'approval') as approval, patch.object(plans, 'build_plan'):
            result = reuse.recommend(self.suggestion)
        return result, approval

    def test_same_release_reuses_intents_but_keeps_new_required_sets(self):
        result, approval = self.recommend()
        self.assertEqual(result['carried_from']['pr'], 32)
        self.assertEqual(result['recommended_edits']['variants'][0]['intent'], 'ranking-change')
        self.assertEqual(result['recommended_edits']['suites'][1]['disposition'], 'required')
        self.assertIn('current destination baseline', result['recommended_edits']['reason'])
        approval.assert_called_once()

    def test_candidate_data_or_policy_change_prevents_reuse(self):
        for field in ('candidate', 'primary_query_sets', 'policy_sha256'):
            with self.subTest(field=field):
                previous = deepcopy(self.previous)
                self.previous['suggestion']['binding'][field] = 'changed'
                result, approval = self.recommend()
                self.assertNotIn('carried_from', result)
                approval.assert_not_called()
                self.previous = previous

    def test_durable_checks_deduplicate_across_record_retries_and_administrators(self):
        record = {'id': 'a'*64, 'run': 207, 'plan': {'suggestion': {'binding': self.pin}}}
        with tempfile.TemporaryDirectory() as folder:
            store = Operations(Path(folder) / 'ops.db')
            first = reuse.queue_checks(record, {'username': 'reviewer', 'is_admin': True}, store)
            second = reuse.queue_checks(record, {'username': 'another-admin', 'is_admin': True}, store)
            self.assertEqual(first['id'], second['id'])
            self.assertEqual(len(store.active()), 1)
            child = store.get(first['id'])
            self.assertEqual(child['request']['target'], 'staging')
            self.assertEqual(child['request']['run'], 207)
            self.assertEqual(child['request']['_check_plan_id'], record['id'])
            self.assertEqual(child['identity']['username'], 'reviewer')
            record['plan']['suggestion']['binding']['target'] = 'production'
            record['id'] = 'b'*64
            prod = reuse.queue_checks(record, {'username': 'reviewer', 'is_admin': True}, store)
            self.assertEqual(store.get(prod['id'])['request']['kind'], 'release-production')

    def test_internal_plan_binding_cannot_be_forged_in_public_request(self):
        with self.assertRaises(ValueError):
            validate({'kind': 'release-production', 'run': 207, '_check_plan_id': 'a'*64})
        with self.assertRaises(ValueError):
            validate({'kind': 'accept-release-plan', 'pr': 32, 'run_checks': 'yes'})

    def test_record_worker_queues_checks_only_after_successful_approval(self):
        import delivery_operations as operations
        record = {'id': 'a'*64, 'run': 207, 'target': 'staging', 'pr': 32,
                  'plan': {'suggestion': {'binding': self.pin}}}
        for rejected in (False, True):
            with self.subTest(rejected=rejected), tempfile.TemporaryDirectory() as folder, \
                    patch.object(operations, 'STATE', Path(folder)), \
                    patch('release_check_plans.record', return_value=record,
                          side_effect=ValueError('Approval changed') if rejected else None), \
                    patch('delivery_cli.execute') as execute:
                store = Operations()
                parent = store.submit({'kind': 'accept-release-plan', 'pr': 32, 'run_checks': True},
                                      {'username': 'reviewer', 'is_admin': True}, 'record')
                operations.execute_next()
                row = store.get(parent['id'])
                self.assertEqual(row['state'], 'failed' if rejected else 'complete')
                self.assertEqual(len(store.active()), 0 if rejected else 1)
                if not rejected:
                    self.assertEqual(row['result']['checks_operation']['id'], store.active()[0]['id'])
                execute.assert_not_called()

    def test_queued_checks_reject_a_replacement_plan_before_evaluating(self):
        import delivery_operations as operations
        record = {'id': 'a'*64, 'run': 207, 'plan': {'suggestion': {'binding': self.pin}}}
        with tempfile.TemporaryDirectory() as folder, patch.object(operations, 'STATE', Path(folder)), \
                patch('release_check_plans.scope', return_value=({}, {})), \
                patch('release_check_plans.require', return_value=({}, {'id': 'b'*64})), \
                patch('delivery_cli.execute') as execute:
            store = Operations()
            child = reuse.queue_checks(record, {'username': 'reviewer', 'is_admin': True}, store)
            operations.execute_next()
            self.assertEqual(store.get(child['id'])['state'], 'failed')
            self.assertIn('plan changed', store.get(child['id'])['error'])
            execute.assert_not_called()

    def test_unlabelled_duplicate_is_only_suggested_for_retirement(self):
        suggestion = deepcopy(self.suggestion)
        suggestion['suites'] = [
            {'id': 'old', 'name': 'sneakers', 'query_sha256': 'same', 'required': False},
            {'id': 'new', 'name': 'sneakers', 'query_sha256': 'same', 'required': False, 'judgements': 'labels'},
            {'id': 'required', 'name': 'sneakers', 'query_sha256': 'same', 'required': True}]
        edits = reuse.defaults(suggestion)
        self.assertEqual([s['disposition'] for s in edits['suites']], ['retired', 'report_only', 'required'])
        self.assertIn('same queries', edits['suites'][0]['reason'])
        self.assertFalse(edits['reason'])  # The human still supplies the overall review reason.
