import json
import hashlib
import threading
import urllib.error
import urllib.request
import urllib.parse
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from control_api import Handler
from control_identity import Sessions


class EmptyStore:
    def all(self):
        return []

    def get(self, instance_id):
        if instance_id == 'known':
            return {'id': 'known', 'name': 'lab-demo', 'state': 'ready',
                    'owner': 'alice', 'expires_at': '2099-01-01T00:00:00Z'}
        if instance_id == 'other':
            return {'id': 'other', 'name': 'lab-other', 'state': 'ready',
                    'owner': 'bob', 'expires_at': '2099-01-01T00:00:00Z'}
        return None

    def get_comparison(self, comparison_id):
        if comparison_id == 'notebook-demo':
            payload = b'{"cells":[],"nbformat":4}'
            return {'id': comparison_id, 'baseline_id': 'known', 'candidate_id': 'known',
                    'summary': {'notebook': {'state': 'complete',
                        'executed_blob': 'runs/notebooks/demo.ipynb',
                        'executed_sha256': hashlib.sha256(payload).hexdigest()}}}
        return None


class EmptyController:
    store = EmptyStore()
    last_comparison = None

    def create_many(self, names, build_run, owner, release_id):
        return [{'id': name, 'name': name, 'owner': owner, 'build_run': build_run,
                 'release_id': release_id, 'state': 'ready'} for name in names]

    def delete_many(self, ids):
        return [self.store.get(instance_id) for instance_id in ids]

    def compare(self, baseline_id, candidate_id, mode, **options):
        self.last_comparison = (baseline_id, candidate_id, mode, options)
        return {'state': 'complete', 'verdict': 'unchanged'}


class FakeIdentity:
    def verify(self, username, password):
        if password != 'test-password':
            raise ValueError('Invalid credentials')
        return {'username': username, 'is_admin': username == 'admin'}


class LocalControlApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = TemporaryDirectory()
        cls.drain_patch = patch('control_api.DRAIN', Path(cls.state.name) / 'control-drain')
        cls.drain_patch.start()
        Handler.controller = EmptyController()
        Handler.sessions = Sessions()
        Handler.identity_provider = FakeIdentity()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.drain_patch.stop()
        cls.state.cleanup()

    def test_loopback_reads(self):
        with urllib.request.urlopen(self.base + '/api/health') as response:
            self.assertEqual(json.load(response), {'ready': True})
            self.assertIn("connect-src 'self'", response.headers['Content-Security-Policy'])
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.base + '/api/environments')
        self.assertEqual(error.exception.code, 401)
        with urllib.request.urlopen(self.base + '/') as response:
            self.assertIn(b'Search environments', response.read())

    def test_selected_input_hashes_reach_comparison(self):
        cookie = self.login('admin')
        inputs = urllib.request.Request(self.base + '/api/input-sets', headers={'Cookie': cookie})
        with urllib.request.urlopen(inputs) as response:
            self.assertIn('retail-gb-10k-v1', json.load(response))
        request = urllib.request.Request(self.base + '/api/comparisons', method='POST',
            data=json.dumps({'baseline_id': 'known', 'candidate_id': 'other',
                             'mode': 'relevance', 'query_manifest_sha256': 'a' * 64,
                             'judgement_manifest_sha256': 'b' * 64,
                             'notebook': 'comparison-explorer.ipynb'}).encode(),
            headers={'Cookie': cookie, 'Content-Type': 'application/json', 'X-Lab-Intent': '1'})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 201)
        self.assertEqual(Handler.controller.last_comparison[3]['query_manifest_sha'], 'a' * 64)
        self.assertEqual(Handler.controller.last_comparison[3]['judgement_manifest_sha'], 'b' * 64)
        self.assertEqual(Handler.controller.last_comparison[3]['notebook'], 'comparison-explorer.ipynb')

    def test_search_proxy_preserves_filters_and_rejects_mismatched_echo(self):
        cookie = self.login()
        filters = {'category': ['clothing'], 'price_minor': {'lte': 2500}}
        url = self.base + '/api/environments/known/search?' + urllib.parse.urlencode(
            {'q': 'shirt', 'filters': json.dumps(filters)})
        request = urllib.request.Request(url, headers={'Cookie': cookie, 'X-Lab-Intent': '1'})
        with patch('control_api.search', return_value={'ids': [], 'filters': filters}) as search, \
                patch.object(Handler.controller, 'activity', create=True) as activity:
            with urllib.request.urlopen(request) as response:
                self.assertEqual(json.load(response)['filters'], filters)
            search.assert_called_once_with('lab-demo', 'shirt', filters=filters)
            activity.assert_called_once_with('known')
            activity.reset_mock()
            search.return_value = {'ids': [], 'filters': {}}
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, 502)
            activity.assert_not_called()
            search.reset_mock()
            for suffix in ('&country=US', '&filters=null'):
                invalid = urllib.request.Request(url + suffix,
                    headers={'Cookie': cookie, 'X-Lab-Intent': '1'})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(invalid)
                self.assertEqual(error.exception.code, 400)
            search.assert_not_called()

    def test_executed_notebook_download_checks_owner_and_hash(self):
        cookie = self.login('alice')
        blob = Mock()
        blob.download_blob.return_value.readall.return_value = b'{"cells":[],"nbformat":4}'
        account = Mock()
        account.get_blob_client.return_value = blob
        with patch('control_api.service', return_value=account):
            request = urllib.request.Request(self.base + '/api/comparisons/notebook-demo/notebook',
                                             headers={'Cookie': cookie})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.headers['Content-Type'], 'application/x-ipynb+json')
                self.assertEqual(response.read(), b'{"cells":[],"nbformat":4}')
            blob.download_blob.return_value.readall.return_value = b'changed'
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, 502)

    def test_mutation_requires_json_intent_header(self):
        request = urllib.request.Request(self.base + '/api/environments', method='POST', data=b'{}',
                                         headers={'Content-Type': 'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 400)
        cookie = self.login()
        with self.assertRaises(urllib.error.HTTPError) as search_error:
            urllib.request.urlopen(urllib.request.Request(self.base + '/api/environments/known/search?q=shirt',
                                                          headers={'Cookie': cookie}))
        self.assertEqual(search_error.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as ownership_error:
            urllib.request.urlopen(urllib.request.Request(self.base + '/api/environments/other',
                                                          headers={'Cookie': cookie}))
        self.assertEqual(ownership_error.exception.code, 403)
        delete = urllib.request.Request(self.base + '/api/environments/other', method='DELETE', data=b'{}',
            headers={'Cookie': cookie, 'Content-Type': 'application/json', 'X-Lab-Intent': '1'})
        with self.assertRaises(urllib.error.HTTPError) as delete_error:
            urllib.request.urlopen(delete)
        self.assertEqual(delete_error.exception.code, 403)
        compare = urllib.request.Request(self.base + '/api/comparisons', method='POST',
            data=json.dumps({'baseline_id': 'known', 'candidate_id': 'other',
                             'mode': 'result-regression'}).encode(),
            headers={'Cookie': cookie, 'Content-Type': 'application/json', 'X-Lab-Intent': '1'})
        with self.assertRaises(urllib.error.HTTPError) as compare_error:
            urllib.request.urlopen(compare)
        self.assertEqual(compare_error.exception.code, 403)
        admin_cookie = self.login('admin')
        with urllib.request.urlopen(urllib.request.Request(self.base + '/api/environments/other',
                                                           headers={'Cookie': admin_cookie})) as response:
            self.assertEqual(json.load(response)['owner'], 'bob')

    def test_login_rejects_noncanonical_host(self):
        Handler.canonical_host = 'localhost:' + str(self.server.server_address[1])
        try:
            request = urllib.request.Request(self.base + '/api/login', method='POST',
                data=json.dumps({'username': 'alice', 'password': 'test-password'}).encode(),
                headers={'Content-Type': 'application/json', 'X-Lab-Intent': '1'})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, 421)
        finally:
            Handler.canonical_host = None

    def test_bulk_routes_keep_owner_boundary(self):
        cookie = self.login()
        headers = {'Cookie': cookie, 'Content-Type': 'application/json', 'X-Lab-Intent': '1'}
        create = urllib.request.Request(self.base + '/api/environments/batch', method='POST',
            data=json.dumps({'names': ['lab-one', 'lab-two'], 'build_run': 3}).encode(),
            headers=headers)
        with urllib.request.urlopen(create) as response:
            rows = json.load(response)
            self.assertEqual(response.status, 201)
            self.assertEqual([row['owner'] for row in rows], ['alice', 'alice'])
        delete = urllib.request.Request(self.base + '/api/environments/batch', method='DELETE',
            data=json.dumps({'ids': ['known', 'other']}).encode(), headers=headers)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(delete)
        self.assertEqual(error.exception.code, 403)

    def login(self, username='alice'):
        request = urllib.request.Request(self.base + '/api/login', method='POST',
            data=json.dumps({'username': username, 'password': 'test-password'}).encode(),
            headers={'Content-Type': 'application/json', 'X-Lab-Intent': '1'})
        with urllib.request.urlopen(request) as response:
            body = json.load(response)
            self.assertEqual(body['username'], username)
            self.assertNotIn('test-password', json.dumps(body))
            self.assertNotIn('lab_session', json.dumps(body))
            self.assertIn('HttpOnly', response.headers['Set-Cookie'])
            return response.headers['Set-Cookie'].split(';', 1)[0]


if __name__ == '__main__':
    unittest.main()
