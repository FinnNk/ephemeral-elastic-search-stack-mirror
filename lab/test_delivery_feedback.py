import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from delivery_operations import Operations, execute_next
from delivery_gates import EvidenceFailure, performance_failure
from operation_telemetry import event_sink


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Operations(Path(self.temp.name) / 'operations.sqlite3')
        self.identity = {'username': 'reviewer', 'is_admin': True}

    def test_preparation_reuses_proposal_across_keys_and_tabs_but_new_release_is_new(self):
        context = {'staging': 'a', 'production': 'b', 'active': 'blue'}
        with patch('production_release.preparation_context', return_value=context):
            first = self.store.submit({'kind': 'prepare-production'}, self.identity, 'tab-1')
            self.store.update(first['id'], state='complete', result={'pr': 24})
            second = self.store.submit({'kind': 'prepare-production'}, self.identity, 'tab-2')
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(second['result']['pr'], 24)
        with patch('production_release.preparation_context', return_value={**context, 'staging': 'new'}):
            third = self.store.submit({'kind': 'prepare-production'}, self.identity, 'tab-3')
        self.assertNotEqual(first['id'], third['id'])

    def test_stale_queued_preparation_cannot_create_a_pr(self):
        with patch('production_release.preparation_context', return_value={'staging': 'old'}):
            row = self.store.submit({'kind': 'prepare-production'}, self.identity, 'prepare')
        with patch('delivery_operations.Operations', return_value=self.store), \
             patch('production_release.preparation_context', return_value={'staging': 'new'}), \
             patch('production_release.prepare') as prepare, patch('traceback.print_exc'):
            outcome = execute_next()
        self.assertEqual(outcome['state'], 'failed')
        prepare.assert_not_called()
        self.assertIsNone(event_sink.get())

    def test_queue_shows_active_blocker_and_logs_are_bounded_and_scoped(self):
        first = self.store.submit({'kind': 'preview', 'run': 1}, self.identity, 'one')
        self.store.next()
        second = self.store.submit({'kind': 'preview', 'run': 2}, self.identity, 'two')
        self.assertEqual(self.store.get(second['id'])['queue']['blocker']['id'], first['id'])
        for i in range(510):self.store.log(first['id'], 'Step ' + str(i))
        logs = self.store.logs(first['id'])
        self.assertEqual(len(logs), 100)
        self.assertEqual(logs[0]['message'], 'Step 10')
        self.assertEqual(self.store.logs(second['id']), [])
        self.assertTrue(all(x['sequence'] > logs[-1]['sequence'] for x in self.store.logs(first['id'], logs[-1]['sequence'])))

    def test_failed_gate_keeps_friendly_evidence_link(self):
        self.store.submit({'kind': 'promotion', 'target': 'staging', 'run': 2,
            'intent': 'ranking-change'}, self.identity, 'gate')
        reference = {'sha256': 'a'*64, 'blob': 'runs/failed.json'}
        with patch('delivery_operations.Operations', return_value=self.store), \
             patch('delivery_cli.execute', side_effect=EvidenceFailure('candidate peak p95_ms missed', reference)), \
             patch('traceback.print_exc'):
            outcome = execute_next()
        self.assertEqual(outcome['state'], 'failed')
        self.assertEqual(outcome['result']['report'], reference)
        self.assertTrue(outcome['report_url'].endswith('/report'))

    def test_budget_failure_names_side_phase_and_threshold(self):
        report = {'valid': True, 'same_workload': True, 'warmup_ready': True,
            'measured_phases': {'peak': {'budget': {'p95_ms': 400, 'failed_percent': 1},
                'baseline': {'p95_ms': 401, 'failed_percent': 1},
                'candidate': {'p95_ms': 80, 'failed_percent': 0}}}}
        detail = performance_failure(report)
        self.assertIn('baseline peak p95_ms: 401', detail)
        self.assertIn('baseline peak failed_percent: 1', detail)
        self.assertNotIn('candidate', detail)

    def test_coordinator_only_merges_preserve_stricter_review_and_extra_checks(self):
        import delivery_promote
        import json
        credentials = {'username': 'lab-admin', 'agent': {'username': 'elastic-agent'}}
        with patch('pathlib.Path.read_text', return_value=json.dumps(credentials)), \
             patch('delivery_promote.api', side_effect=[None, [{'rule_name':'main','required_approvals':2,
                'status_check_contexts':['extra/check']}], None]) as api:
            delivery_promote.protect()
        rule = api.call_args.args[2]
        self.assertEqual(rule['merge_whitelist_usernames'], ['elastic-agent'])
        self.assertTrue(rule['enable_merge_whitelist'])
        self.assertTrue(rule['block_admin_merge_override'])
        self.assertEqual(rule['required_approvals'], 2)
        self.assertIn('extra/check', rule['status_check_contexts'])


if __name__ == '__main__':unittest.main()
