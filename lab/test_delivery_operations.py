"""Exercise durable requests through the real control HTTP handler."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch
from urllib import error, request

from control_api import Handler
from delivery_operations import Operations, validate, execute_next
from delivery_source_comparison import BuildPending
from delivery.ci.lab_delivery import Client


class DeliveryOperationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Operations(Path(self.directory.name) / 'operations.sqlite3')
        self.identity = {'username': 'actions', 'is_admin': False, 'is_reader': False,
                         'is_delivery_service': True, 'issuer': 'https://identity.test', 'subject': 'machine'}
        self.payload = {'kind': 'preview', 'run': 108}

    def tearDown(self):
        self.directory.cleanup()

    def test_retry_and_changed_payload(self):
        first = self.store.submit(self.payload, self.identity, 'fixture')
        self.assertEqual(first['id'], self.store.submit(self.payload, self.identity, 'fixture')['id'])
        with self.assertRaises(ValueError):
            self.store.submit({**self.payload, 'run': 109}, self.identity, 'fixture')
        other = self.store.submit(self.payload, {**self.identity, 'subject': 'another-machine'}, 'fixture')
        self.assertNotEqual(first['id'], other['id'])

    def test_claim_and_recovery_do_not_repeat_mutations(self):
        first = self.store.submit(self.payload, self.identity, 'fixture')
        self.assertEqual(self.store.next()['id'], first['id'])
        self.assertIsNone(self.store.next())
        self.store.recover()
        self.assertEqual(self.store.get(first['id'])['state'], 'interrupted')
        self.assertIsNone(self.store.next())

    def test_validation_rejects_arbitrary_paths_and_commands(self):
        for payload in ({'kind': 'shell', 'command': 'echo'}, {**self.payload, 'evidence': '/state/private'},
                        {**self.payload, 'run': True}, {'kind': 'promotion', 'target': 'production', 'run': 1},
                        {'kind': 'compare', 'pr': 1, 'source_sha': 'a'*40},
                        {**self.payload, 'recipe': '../private'}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate(payload)

    def test_http_client_and_scoped_authorisation(self):
        provider = Mock(verify=Mock(return_value=self.identity))
        with patch.object(Handler, 'oidc_provider', provider), patch.object(Handler, 'canonical_host', None), \
                patch('delivery_operations.Operations', return_value=self.store), \
                patch('control_api.DRAIN', Path(self.directory.name) / 'drain'):
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client = Client('https://control.test', 'https://identity.test', token_file=Path(self.directory.name)/'token')
                client.server = 'http://127.0.0.1:' + str(server.server_address[1])
                with patch.object(client, 'bearer', return_value='fixture'):
                    row = client.submit(self.payload, key='http', wait=False)
                    self.assertEqual(row['state'], 'queued')
                    self.store.update(row['id'], state='complete', result={'browser_url': 'https://preview.test'})
                    repeated = client.submit(self.payload, key='http', wait=True)
                    self.assertEqual(repeated['result']['browser_url'], 'https://preview.test')
                    with self.assertRaises(error.HTTPError) as failure:
                        client.call('/api/environments')
                    self.assertEqual(failure.exception.code, 403)
                    provider.verify.return_value = {'username': 'reader', 'is_admin': False, 'is_reader': True}
                    with self.assertRaises(error.HTTPError) as failure:
                        client.submit(self.payload, key='reader', wait=False)
                    self.assertEqual(failure.exception.code, 403)
                    provider.verify.return_value = {**self.identity, 'username': 'another'}
                    with self.assertRaises(error.HTTPError) as failure:
                        client.call('/api/delivery/operations/' + row['id'])
                    self.assertEqual(failure.exception.code, 403)
                    raw = request.Request(client.server + '/api/delivery/operations', data=json.dumps(self.payload).encode(),
                        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer fixture'})
                    with self.assertRaises(error.HTTPError) as failure:
                        request.urlopen(raw)
                    self.assertEqual(failure.exception.code, 400)
            finally:
                server.shutdown(); server.server_close(); thread.join(2)

    def test_tls_required(self):
        with self.assertRaises(ValueError):
            Client('http://control.test', 'https://identity.test')

    def test_waiting_build_releases_queue_and_terminal_failure_is_recorded(self):
        payload = {'kind': 'compare', 'pr': 1, 'source_sha': 'a'*40, 'baseline_sha': 'b'*40}
        row = self.store.submit(payload, self.identity, 'build')
        self.store.update(row['id'], state='queued', progress='Waiting')
        other = self.store.submit(self.payload, self.identity, 'preview')
        with patch('delivery_operations.Operations', return_value=self.store), \
                patch('delivery_source_comparison.compare', side_effect=BuildPending()):
            self.assertEqual(execute_next()['state'], 'queued')
        self.assertEqual(self.store.next()['id'], other['id'])
        with patch('delivery_operations.Operations', return_value=self.store), \
                patch('delivery_source_comparison.compare', side_effect=ValueError('fixture failure')), \
                patch('delivery_source_comparison.status') as status, patch('traceback.print_exc'):
            self.assertEqual(execute_next()['state'], 'failed')
        status.assert_called_once()

    def test_service_token_refresh_stays_off_disk(self):
        client = Client('https://control.test', 'https://identity.test', token_file=Path(self.directory.name)/'token')
        with patch.dict('os.environ', {'LAB_DELIVERY_CLIENT_SECRET': 'fixture-secret'}), \
                patch.object(client, 'token', return_value={'access_token': 'fixture', 'expires_in': 300}) as token:
            self.assertEqual(client.bearer(), 'fixture')
            self.assertFalse(client.token_file.exists())
            client.expires = 0
            self.assertEqual(client.bearer(), 'fixture')
            self.assertEqual(token.call_count, 2)


if __name__ == '__main__':
    unittest.main()
