import json
import threading
import urllib.error
import urllib.request
import unittest
from http.server import ThreadingHTTPServer

from control_api import Handler


class EmptyStore:
    def all(self):
        return []

    def get(self, instance_id):
        if instance_id == 'known':
            return {'id': 'known', 'name': 'lab-demo', 'state': 'ready',
                    'expires_at': '2099-01-01T00:00:00Z'}
        return None


class EmptyController:
    store = EmptyStore()


class LocalControlApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Handler.controller = EmptyController()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_loopback_reads(self):
        with urllib.request.urlopen(self.base + '/api/health') as response:
            self.assertEqual(json.load(response), {'ready': True})
        with urllib.request.urlopen(self.base + '/api/environments') as response:
            self.assertEqual(json.load(response), [])
        with urllib.request.urlopen(self.base + '/') as response:
            self.assertIn(b'Search environments', response.read())

    def test_mutation_requires_json_intent_header(self):
        request = urllib.request.Request(self.base + '/api/environments', method='POST', data=b'{}',
                                         headers={'Content-Type': 'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as search_error:
            urllib.request.urlopen(self.base + '/api/environments/known/search?q=shirt')
        self.assertEqual(search_error.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
