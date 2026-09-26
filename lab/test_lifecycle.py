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


if __name__ == '__main__':
    unittest.main()
