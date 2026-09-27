import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

sys.path.insert(0, 'research/platform-spike')
from blob_config import DEFAULT_POD_URL, DEFAULT_URL, settings, signed_read_url
import blob_config


class BlobConfigurationContract(unittest.TestCase):
    def test_local_defaults_and_read_only_sas(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(settings(), (DEFAULT_URL, 'datasets', DEFAULT_POD_URL, True))
            url = signed_read_url('release/products.jsonl',
                                  datetime.now(timezone.utc) + timedelta(minutes=15))
        self.assertTrue(url.startswith(DEFAULT_POD_URL + '/datasets/release/products.jsonl?'))
        self.assertIn('sp=r', url)

    def test_azure_endpoint_needs_https_and_uses_it_for_pods(self):
        with patch.dict(os.environ, {'LAB_BLOB_ACCOUNT_URL': 'http://example.blob.core.windows.net'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                settings()
        with patch.dict(os.environ, {'LAB_BLOB_ACCOUNT_URL': 'https://example.blob.core.windows.net',
                                     'LAB_BLOB_CONTAINER': 'frozen-releases'}, clear=True):
            self.assertEqual(settings(), ('https://example.blob.core.windows.net',
                'frozen-releases', 'https://example.blob.core.windows.net', False))
        with patch.dict(os.environ, {'LAB_BLOB_ACCOUNT_URL': 'https://example.blob.core.windows.net',
                                     'LAB_BLOB_POD_URL': 'http://example.blob.core.windows.net'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                settings()

    def test_azure_signed_read_uses_user_delegation(self):
        client = Mock()
        client.get_user_delegation_key.return_value = object()
        with patch.dict(os.environ, {'LAB_BLOB_ACCOUNT_URL': 'https://example.blob.core.windows.net',
                                     'LAB_BLOB_CONTAINER': 'frozen-releases'}, clear=True), \
                patch.object(blob_config, 'service', return_value=client), \
                patch.object(blob_config, 'generate_blob_sas', return_value='signed=read') as signing:
            url = signed_read_url('release/products.jsonl',
                                  datetime.now(timezone.utc) + timedelta(minutes=15))
        self.assertEqual(url, 'https://example.blob.core.windows.net/frozen-releases/'
                              'release/products.jsonl?signed=read')
        self.assertEqual(signing.call_args.kwargs['user_delegation_key'],
                         client.get_user_delegation_key.return_value)


if __name__ == '__main__':
    unittest.main()
