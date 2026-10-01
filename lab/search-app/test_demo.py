import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from demo import DemoHandler


class DemoContract(unittest.TestCase):
    def test_offline_http_contract_and_dependency_boundary(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), DemoHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        try:
            # The real dependency method must never be called, even without ES settings.
            with patch.dict(os.environ, {key: value for key, value in os.environ.items() if not key.startswith('ES_')}, clear=True), \
                 patch('app.Handler.search_index', side_effect=AssertionError('Real backend called')):
                with urllib.request.urlopen(url + '/?q=running+shoes') as response:
                    self.assertIn('Standalone demo', response.read().decode())
                with urllib.request.urlopen(url + '/search?q=running+shoes&diagnostics=1') as response:
                    result = json.load(response)
                self.assertEqual(result['data_source'], 'standalone-mock')
                self.assertEqual(result['ids'], ['demo-01', 'demo-02'])
                self.assertEqual(result['currency'], 'GBP')
                self.assertIn('configuration_sha256', result)
                self.assertEqual(result['diagnostics']['retrieved_ids'], result['ids'])
                with urllib.request.urlopen(url + '/search?q=unmatched') as response:
                    self.assertEqual(json.load(response)['total'], 0)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(url + '/search?q=shoes&country=US')
                self.assertEqual(error.exception.code, 400)
                request = urllib.request.Request(url + '/search?q=shoes', headers={'X-Lab-Variant': 'missing'})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
