"""Early expiry protects delivery targets and binds cleanup to a preview release."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import preview_expiry
from delivery_operations import Operations, validate


class ExpiryTests(unittest.TestCase):
    name = 'lab-delivery-run-158-1234abcd'
    fingerprint = 'a'*64
    expiry = '2027-01-01T00:00:00+00:00'

    def test_protected_environments_and_arbitrary_names_are_rejected(self):
        for name in ('lab-delivery-integration', 'lab-delivery-staging', 'lab-delivery-production-blue',
                     'lab-delivery-production-green', self.name + '/other'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate({'kind': 'expire-preview', 'name': name, 'fingerprint': self.fingerprint, 'expires_at': self.expiry})
        validate({'kind': 'expire-preview', 'name': self.name, 'fingerprint': self.fingerprint, 'expires_at': self.expiry})

    def test_live_comparison_prevents_expiry(self):
        with patch.object(preview_expiry, 'Store', return_value=Mock(running_comparison_for=Mock(return_value=True))), \
                patch.object(preview_expiry, 'k') as k:
            with self.assertRaisesRegex(ValueError, 'running comparison'):
                preview_expiry.expire(self.name, self.fingerprint, self.expiry)
            k.assert_not_called()

    def test_actions_identity_cannot_end_a_preview_lease(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            store = Operations(Path(directory) / 'operations.sqlite3')
            request = {'kind': 'expire-preview', 'name': self.name, 'fingerprint': self.fingerprint, 'expires_at': self.expiry}
            with self.assertRaisesRegex(ValueError, 'human lab administrator'):
                store.submit(request, {'username': 'actions', 'is_admin': True, 'is_delivery_service': True}, 'expiry')
            first = store.submit(request, {'username': 'admin', 'is_admin': True}, 'expiry')
            self.assertEqual(first['id'], store.submit(request, {'username': 'admin', 'is_admin': True}, 'expiry')['id'])

    def test_owned_exact_preview_lease_is_ended(self):
        app = {'metadata': {'labels': {'lab/delivery': 'preview'},
                            'annotations': {'lab/preview-expires-at': self.expiry}}}
        definition = {'data': {'definition.json': json.dumps({'fingerprint': self.fingerprint, 'expires_at': self.expiry})}}
        with patch.object(preview_expiry, 'Store', return_value=Mock(running_comparison_for=Mock(return_value=False))), \
                patch.object(preview_expiry, 'k', side_effect=[SimpleNamespace(stdout=json.dumps(app)),
                    SimpleNamespace(stdout=json.dumps(definition)), Mock()]) as k:
            self.assertEqual(preview_expiry.expire(self.name, self.fingerprint, self.expiry)['state'], 'expiring')
            self.assertEqual(k.call_args.args[:2], ('annotate', 'application/' + self.name))
            self.assertLess(preview_expiry.datetime.fromisoformat(k.call_args.args[4].split('=', 1)[1]).year, 2027)

    def test_changed_or_foreign_preview_cannot_expire(self):
        for label, fingerprint in (('other', self.fingerprint), ('preview', 'b'*64)):
            app = {'metadata': {'labels': {'lab/delivery': label}, 'annotations': {'lab/preview-expires-at': self.expiry}}}
            definition = {'data': {'definition.json': json.dumps({'fingerprint': fingerprint})}}
            with patch.object(preview_expiry, 'Store', return_value=Mock(running_comparison_for=Mock(return_value=False))), \
                    patch.object(preview_expiry, 'k', side_effect=[SimpleNamespace(stdout=json.dumps(app)),
                        SimpleNamespace(stdout=json.dumps(definition))]) as k:
                with self.assertRaises(ValueError): preview_expiry.expire(self.name, self.fingerprint, self.expiry)
                self.assertTrue(all(call.args[0] == 'get' for call in k.call_args_list))

    def test_already_removed_preview_is_idempotent(self):
        with patch.object(preview_expiry, 'Store', return_value=Mock(running_comparison_for=Mock(return_value=False))), \
                patch.object(preview_expiry, 'k', return_value=SimpleNamespace(stdout='')) as k:
            self.assertEqual(preview_expiry.expire(self.name, self.fingerprint, self.expiry)['state'], 'expired')
            self.assertEqual(k.call_count, 1)

    def test_changed_lease_requires_refresh(self):
        app = {'metadata': {'labels': {'lab/delivery': 'preview'},
                            'annotations': {'lab/preview-expires-at': '2028-01-01T00:00:00+00:00'}}}
        with patch.object(preview_expiry, 'Store', return_value=Mock(running_comparison_for=Mock(return_value=False))), \
                patch.object(preview_expiry, 'k', return_value=SimpleNamespace(stdout=json.dumps(app))) as k:
            with self.assertRaisesRegex(ValueError, 'lease changed'):
                preview_expiry.expire(self.name, self.fingerprint, self.expiry)
            self.assertEqual(k.call_count, 1)
