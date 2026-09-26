import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lifecycle import LEASE, Lifecycle, Store, parse_stamp


class FakeBackend:
    def __init__(self):
        self.provisions = []
        self.deletions = []
        self.fail_provision = False
        self.fail_delete = False

    def build(self, run_id):
        return {'source_sha': 'a' * 40, 'image': 'registry/repo@sha256:' + 'b' * 64}

    def provision(self, row):
        self.provisions.append(row['name'])
        if self.fail_provision:
            raise RuntimeError('test provision failure')
        return 'c' * 64

    def delete(self, row):
        self.deletions.append(row['name'])
        if self.fail_delete:
            raise RuntimeError('test delete failure')


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

    def test_comparison_is_persisted_and_incomplete_cannot_pass(self):
        baseline = self.service.create('lab-baseline', 3)
        candidate = self.service.create('lab-candidate', 4)
        self.service.comparator = lambda _a, _b, mode: {
            'complete': True, 'verdict': 'unchanged', 'report_sha256': 'd' * 64,
            'report_blob': 'runs/' + 'd' * 64 + '/report.json', 'mode': mode}
        row = self.service.compare(baseline['id'], candidate['id'], 'result-regression')
        self.assertEqual(row['state'], 'complete')
        self.assertEqual(row['verdict'], 'unchanged')
        self.assertEqual(self.store.get_comparison(row['id'])['summary']['mode'], 'result-regression')
        self.service.comparator = lambda _a, _b, mode: {
            'complete': False, 'verdict': 'incomplete', 'report_sha256': 'e' * 64,
            'report_blob': 'runs/' + 'e' * 64 + '/report.json', 'mode': mode}
        partial = self.service.compare(baseline['id'], candidate['id'], 'result-regression')
        self.assertEqual(partial['state'], 'incomplete')
        self.assertEqual(partial['verdict'], 'incomplete')
        with self.assertRaises(ValueError):
            self.service.compare(baseline['id'], baseline['id'], 'relevance')


if __name__ == '__main__':
    unittest.main()
