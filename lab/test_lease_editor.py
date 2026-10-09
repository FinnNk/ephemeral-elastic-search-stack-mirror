"""Manual lease edits preserve deadlines, reject stale forms and protect targets."""
from datetime import timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_lifecycle
from lease_expiry import deadline
from delivery_operations import validate, Operations
import preview_expiry


class FixedLease(unittest.TestCase):
    setUp = test_lifecycle.LifecycleContract.setUp
    def test_fixed_deadline_survives_activity_and_explicit_extension_resets_mode(self):
        row = self.service.create('lab-fixed', 3)
        chosen = (self.now[0] + timedelta(days=5)).isoformat()
        fixed = self.service.set_expiry(row['id'], chosen, row['expires_at'])
        self.assertEqual(fixed['expiry_mode'], 'fixed')
        self.now[0] += timedelta(hours=1)
        self.assertEqual(self.service.activity(row['id'])['expires_at'], chosen)
        rolling = self.service.activity(row['id'], explicit=True)
        self.assertEqual(rolling['expiry_mode'], 'activity')
        self.assertEqual(rolling['expires_at'], (self.now[0] + timedelta(hours=72)).isoformat().replace('+00:00', 'Z'))

    def test_stale_past_naive_and_expired_edits_are_rejected(self):
        row = self.service.create('lab-fixed', 3)
        for value in ('2020-01-01T00:00:00Z', '2026-01-05T00:00:00', 'not-a-date'):
            with self.assertRaises(ValueError): self.service.set_expiry(row['id'], value, row['expires_at'])
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.service.set_expiry(row['id'], '2026-01-05T00:00:00Z', 'old')
        self.now[0] += timedelta(days=4)
        with self.assertRaises(ValueError):
            self.service.set_expiry(row['id'], '2026-01-10T00:00:00Z', row['expires_at'])


class PreviewLease(unittest.TestCase):
    def test_protected_targets_and_timezone_validation(self):
        for name in ('lab-delivery-integration', 'lab-delivery-staging', 'lab-delivery-production-blue'):
            with self.assertRaises(ValueError): validate({'kind': 'set-preview-expiry', 'name': name,
                'fingerprint': 'a'*64, 'expires_at': '2099-01-01T00:00:00Z', 'new_expiry': '2099-01-02T00:00:00Z'})
        with self.assertRaises(ValueError): deadline('2099-01-01T00:00:00')

    def test_exact_preview_updates_only_its_annotation(self):
        name='lab-delivery-run-158-1234abcd'; old='2099-01-01T00:00:00Z'; new='2099-01-02T00:00:00Z'
        replies=[SimpleNamespace(stdout='{"metadata":{"labels":{"lab/delivery":"preview"},"annotations":{"lab/preview-expires-at":"'+old+'"}}}'),
                 SimpleNamespace(stdout='{"data":{"definition.json":"{\\"fingerprint\\":\\"'+ 'a'*64 +'\\"}"}}'),SimpleNamespace(stdout='')]
        with patch.object(preview_expiry,'Store',return_value=Mock(running_comparison_for=Mock(return_value=False))), \
                patch.object(preview_expiry,'k',side_effect=replies) as k:
            result=preview_expiry.expire(name,'a'*64,old,new)
            self.assertEqual(result['state'],'lease-updated')
            self.assertIn('lab/preview-expires-at=2099-01-02T00:00:00+00:00',k.call_args.args)
