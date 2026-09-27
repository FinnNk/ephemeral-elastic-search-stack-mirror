import tempfile
import threading
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lifecycle import ActiveComparisonError, INDEX_KIND, LEASE, Lifecycle, Store, parse_stamp, wait_correct_search
from index_candidate import index_name, mapping_contract


class FakeBackend:
    def __init__(self):
        self.provisions = []
        self.deletions = []
        self.fail_provision = False
        self.fail_delete = False

    def build(self, run_id):
        return {'source_sha': 'a' * 40, 'image': 'registry/repo@sha256:' + 'b' * 64}

    def pin_index_recipe(self, release_id, index_kind, manifest, recipe_sha256=None):
        return {'sha256': recipe_sha256 or 'e' * 64,
                'mapping_sha256': mapping_contract(release_id)[1]}

    def provision(self, row):
        self.provisions.append(row['name'])
        if self.fail_provision:
            raise RuntimeError('test provision failure')
        return 'c' * 64

    def provision_many(self, rows):
        self.provisions.extend(row['name'] for row in rows)
        return {row['name']: {'fingerprint': 'c' * 64} for row in rows}

    def delete(self, row, heartbeat=None):
        self.deletions.append(row['name'])
        if heartbeat:
            heartbeat()
        if self.fail_delete:
            raise RuntimeError('test delete failure')

    def delete_many(self, rows, heartbeat=None):
        self.deletions.extend(row['name'] for row in rows)
        if heartbeat:
            heartbeat()


class LifecycleContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
        self.backend = FakeBackend()
        self.store = Store(Path(self.temp.name) / 'state.sqlite3')
        self.service = Lifecycle(self.store, self.backend, lambda: self.now[0])

    def test_create_activity_and_expiry(self):
        row = self.service.create('lab-demo', 3)
        self.assertEqual(row['state'], 'ready')
        self.assertEqual(row['source_sha'], 'a' * 40)
        self.assertEqual(row['fingerprint'], 'c' * 64)
        self.assertEqual(self.service.create('lab-demo', 3)['id'], row['id'])
        self.assertEqual(self.backend.provisions, ['lab-demo'])
        with self.assertRaises(ValueError):
            self.service.create('lab-demo', 4)
        self.now[0] += timedelta(hours=2)
        self.assertEqual(self.store.get(row['id'])['expires_at'], row['expires_at'])
        renewed = self.service.activity(row['id'])
        self.assertEqual(parse_stamp(renewed['expires_at']), self.now[0] + LEASE)
        self.now[0] += LEASE - timedelta(minutes=1)
        self.assertEqual(self.service.expire(), [])
        self.now[0] += timedelta(minutes=1)
        self.assertEqual(self.service.expire()[0]['state'], 'deleted')
        self.assertEqual(self.service.delete(row['id'])['state'], 'deleted')
        self.assertEqual(self.backend.deletions, ['lab-demo'])
        recreated = self.service.create('lab-demo', 3)
        self.assertNotEqual(recreated['id'], row['id'])

    def test_recovery_path_and_fallback_error_are_persisted(self):
        result = {'fingerprint': 'c' * 64,
                  'index': {'materialisation': 'snapshot', 'seconds': 1.203,
                            'recovery_errors': ['clone: no matching source']}}
        with patch.object(self.backend, 'provision', return_value=result):
            row = self.service.create('lab-restored', 3, index_kind=INDEX_KIND)
        self.assertEqual(row['index_materialisation'], 'snapshot')
        self.assertEqual(row['index_seconds'], 1.203)
        self.assertIn('no matching source', row['index_recovery_errors'])

    def test_concurrent_same_name_create_provisions_once(self):
        barrier = threading.Barrier(3)
        results = []
        errors = []

        def create():
            barrier.wait()
            try:
                results.append(self.service.create('lab-concurrent-name', 3)['id'])
            except Exception as error:
                errors.append(error)

        workers = [threading.Thread(target=create) for _ in range(2)]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join(2)
            self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(self.backend.provisions, ['lab-concurrent-name'])

    def test_restart_retries_partial_failures(self):
        self.backend.fail_provision = True
        row = self.service.create('lab-retry', 3)
        self.assertEqual(row['state'], 'failed')
        self.backend.fail_provision = False
        restarted = Lifecycle(Store(self.store.path), self.backend, lambda: self.now[0])
        row = restarted.reconcile(row['id'])
        self.assertEqual(row['state'], 'ready')
        self.backend.fail_delete = True
        row = restarted.delete(row['id'])
        self.assertEqual(row['state'], 'deleting')
        self.backend.fail_delete = False
        self.assertEqual(restarted.expire()[0]['state'], 'deleted')

    def test_invalid_inputs_and_expired_activity(self):
        for name in ('other', 'lab-UPPER', 'lab-'):
            with self.assertRaises(ValueError):
                self.service.create(name, 3)
        row = self.service.create('lab-valid', 3)
        self.now[0] += LEASE
        with self.assertRaises(ValueError):
            self.service.activity(row['id'])

    def test_release_is_immutable_and_cross_catalogue_comparison_is_rejected(self):
        first = self.service.create('lab-first', 3)
        second = self.service.create('lab-second', 3)
        with self.assertRaisesRegex(ValueError, 'different inputs'):
            self.service.create('lab-first', 3, release_id='retail-gb-1m-v1')
        self.store.update(second['id'], release_id='retail-gb-1m-v1', dataset_sha256='f' * 64)
        with self.assertRaisesRegex(ValueError, 'same frozen catalogue'):
            self.service.compare(first['id'], second['id'], 'result-regression')

    def test_failed_provision_is_cleaned_when_lease_expires(self):
        self.backend.fail_provision = True
        row = self.service.create('lab-partial', 3)
        self.assertEqual(row['state'], 'failed')
        self.now[0] += LEASE
        self.assertEqual(self.service.expire()[0]['state'], 'deleted')
        self.assertEqual(self.backend.deletions, ['lab-partial'])

    def test_concurrent_delete_claim_waits_for_active_cleanup(self):
        row = self.service.create('lab-race', 3)
        self.assertTrue(self.store.claim_delete(row['id'], self.now[0]))
        waiting = self.service.delete(row['id'])
        self.assertEqual(waiting['state'], 'deleting')
        self.assertEqual(self.backend.deletions, [])
        self.now[0] += timedelta(minutes=2)
        self.assertEqual(self.service.delete(row['id'])['state'], 'deleted')
        self.assertEqual(self.backend.deletions, ['lab-race'])

    def test_search_readiness_retries_after_argo_health(self):
        answers = iter([None, {'ids': []}, {'ids': list(range(10))}])
        self.assertEqual(len(wait_correct_search('lab-test', lambda _name, _query: next(answers), 5)['ids']), 10)

    def test_dedicated_index_request_is_pinned_and_cannot_change_in_place(self):
        row = self.service.create('lab-mapped', 3, index_kind=INDEX_KIND)
        persisted = Store(self.store.path).get(row['id'])
        self.assertEqual(persisted['index_name'], index_name('lab-mapped'))
        self.assertEqual(persisted['mapping_sha256'], mapping_contract()[1])
        self.assertEqual(persisted['index_recipe_sha256'], 'e' * 64)
        self.assertEqual(self.service.create('lab-mapped', 3, index_kind=INDEX_KIND)['id'], row['id'])
        with self.assertRaises(ValueError):
            self.service.create('lab-mapped', 3, index_kind='shared')
        with self.assertRaises(ValueError):
            self.service.create('lab-other', 3, index_kind='unknown')

    def test_deleted_environment_recipe_can_be_selected_again(self):
        old = self.service.create('lab-old-schema', 3, index_kind=INDEX_KIND)
        self.service.delete(old['id'])
        with self.assertRaisesRegex(ValueError, 'not pinned'):
            self.service.create('lab-forged', 3, index_kind=INDEX_KIND,
                                index_recipe_sha256='f' * 64)
        recreated = self.service.create('lab-recreated-schema', 3, index_kind=INDEX_KIND,
                                        index_recipe_sha256=old['index_recipe_sha256'])
        self.assertEqual(recreated['index_recipe_sha256'], old['index_recipe_sha256'])
        self.assertNotEqual(recreated['id'], old['id'])

    def test_comparison_is_persisted_and_incomplete_cannot_pass(self):
        baseline = self.service.create('lab-baseline', 3)
        candidate = self.service.create('lab-candidate', 4)
        self.service.comparator = lambda _a, _b, mode: {
            'complete': True, 'verdict': 'unchanged', 'report_sha256': 'd' * 64,
            'report_blob': 'runs/' + 'd' * 64 + '/report.json', 'mode': mode}
        row = self.service.compare(baseline['id'], candidate['id'], 'result-regression',
                                   query_manifest_sha='a' * 64)
        self.assertEqual(row['state'], 'complete')
        self.assertEqual(row['verdict'], 'unchanged')
        persisted = self.store.get_comparison(row['id'])
        self.assertEqual(persisted['summary']['mode'], 'result-regression')
        self.assertEqual(persisted['query_manifest_sha256'], 'a' * 64)
        self.assertIsNone(persisted['judgement_manifest_sha256'])
        relevance = self.service.compare(baseline['id'], candidate['id'], 'relevance',
                                         query_manifest_sha='a' * 64,
                                         judgement_manifest_sha='b' * 64)
        self.assertEqual(self.store.get_comparison(relevance['id'])['judgement_manifest_sha256'], 'b' * 64)
        self.service.comparator = lambda _a, _b, mode: {
            'complete': False, 'verdict': 'incomplete', 'report_sha256': 'e' * 64,
            'report_blob': 'runs/' + 'e' * 64 + '/report.json', 'mode': mode}
        partial = self.service.compare(baseline['id'], candidate['id'], 'result-regression')
        self.assertEqual(partial['state'], 'incomplete')
        self.assertEqual(partial['verdict'], 'incomplete')
        performance = self.service.compare(baseline['id'], candidate['id'], 'performance', profile='probe')
        self.assertEqual(performance['profile'], 'probe')
        with self.assertRaises(ValueError):
            self.service.compare(baseline['id'], candidate['id'], 'performance', profile='unknown')
        with self.assertRaises(ValueError):
            self.service.compare(baseline['id'], baseline['id'], 'relevance')

    def test_long_comparison_leaves_activity_responsive_and_pins_its_environments(self):
        baseline = self.service.create('lab-baseline', 3)
        candidate = self.service.create('lab-candidate', 4)
        entered = threading.Event()
        release = threading.Event()
        result = []

        def slow_comparison(_baseline, _candidate, _mode):
            entered.set()
            if not release.wait(2):
                raise TimeoutError('Test comparator was not released.')
            return {'complete': True, 'verdict': 'unchanged', 'report_sha256': 'd' * 64,
                    'report_blob': 'runs/report.json'}

        self.service.comparator = slow_comparison
        worker = threading.Thread(target=lambda: result.append(
            self.service.compare(baseline['id'], candidate['id'], 'result-regression')))
        worker.start()
        self.assertTrue(entered.wait(1))
        activity = threading.Event()
        activity_worker = threading.Thread(target=lambda: (self.service.activity(baseline['id']), activity.set()))
        activity_worker.start()
        try:
            self.assertTrue(activity.wait(1), 'Activity was blocked by the long comparison.')
            with self.assertRaises(ActiveComparisonError):
                self.service.delete(candidate['id'])
        finally:
            release.set()
            worker.join(2)
            activity_worker.join(2)
        self.assertEqual(result[0]['state'], 'complete')
        self.assertEqual(self.service.delete(candidate['id'])['state'], 'deleted')

    def test_interrupted_comparison_is_marked_failed_on_recovery(self):
        baseline = self.service.create('lab-baseline', 3)
        candidate = self.service.create('lab-candidate', 4)
        row = {'id': 'interrupted', 'baseline_id': baseline['id'], 'candidate_id': candidate['id'],
               'mode': 'result-regression', 'profile': None, 'state': 'running',
               'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z',
               'report_sha256': None, 'report_blob': None, 'verdict': None, 'summary': None, 'error': None}
        self.store.put_comparison(row)
        self.assertEqual(self.store.interrupt_running_comparisons(self.now[0]), 1)
        self.assertEqual(self.store.get_comparison('interrupted')['state'], 'failed')
        self.assertEqual(self.service.delete(candidate['id'])['state'], 'deleted')

    def test_bulk_create_and_delete_keep_unique_names_and_pinned_release(self):
        rows = self.service.create_many(['lab-fleet-one', 'lab-fleet-two'], 3,
                                        release_id='retail-gb-1m-v1')
        self.assertEqual([row['state'] for row in rows], ['ready', 'ready'])
        self.assertEqual([row['release_id'] for row in rows], ['retail-gb-1m-v1'] * 2)
        self.assertEqual(self.backend.provisions, ['lab-fleet-one', 'lab-fleet-two'])
        with self.assertRaises(ValueError):
            self.service.create_many(['lab-fleet-one', 'lab-fleet-three'], 3)
        with self.assertRaises(ValueError):
            self.service.create_many(['lab-duplicate', 'lab-duplicate'], 3)
        deleted = self.service.delete_many([row['id'] for row in rows])
        self.assertEqual([row['state'] for row in deleted], ['deleted', 'deleted'])
        self.assertEqual(self.backend.deletions, ['lab-fleet-one', 'lab-fleet-two'])
        self.assertEqual([row['state'] for row in self.service.delete_many([row['id'] for row in rows])],
                         ['deleted', 'deleted'])

    def test_deletion_heartbeat_prevents_another_controller_claiming_live_cleanup(self):
        row = self.service.create('lab-long-delete', 3)
        self.assertTrue(self.store.claim_delete(row['id'], self.now[0]))
        self.now[0] += timedelta(seconds=110)
        self.store.heartbeat_deleting([row['id']], self.now[0])
        self.now[0] += timedelta(seconds=110)
        self.assertFalse(Store(self.store.path).claim_delete(row['id'], self.now[0]))
        self.now[0] += timedelta(seconds=11)
        self.assertTrue(Store(self.store.path).claim_delete(row['id'], self.now[0]))


if __name__ == '__main__':
    unittest.main()
