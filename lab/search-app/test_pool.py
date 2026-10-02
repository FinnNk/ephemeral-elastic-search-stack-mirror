"""Real HTTP fixtures prove upstream reuse without caching search results."""
import base64
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
import ssl
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import app


class ElasticFixture(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    calls = []
    status = 200

    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).calls.append({'port': self.client_address[1], 'body': body,
            'authorization': self.headers.get('Authorization'), 'traceparent': self.headers.get('traceparent')})
        product = {'product_id': 'fresh-' + str(len(type(self).calls)), 'title': 'Lamp',
                   'brand': 'Lumen', 'category': 'home', 'price_minor': 3200,
                   'currency': 'GBP', 'available': True}
        payload = json.dumps({'hits': {'total': {'value': 1}, 'hits': [{'_source': product}]}}).encode()
        self.send_response(type(self).status)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class PoolContract(unittest.TestCase):
    def setUp(self):
        ElasticFixture.calls, ElasticFixture.status = [], 200
        self.elastic = ThreadingHTTPServer(('127.0.0.1', 0), ElasticFixture)
        self.elastic_thread = threading.Thread(target=self.elastic.serve_forever, daemon=True)
        self.elastic_thread.start()
        self.environment = patch.dict(os.environ, {'ES_URL': f'http://127.0.0.1:{self.elastic.server_port}',
            'ES_USER': 'test-reader', 'ES_PASSWORD': 'synthetic-password', 'ES_INDEX': 'frozen-fixture'})
        self.environment.start()
        self.context = ssl.create_default_context()
        self.ssl_patch = patch.object(app.ssl, 'create_default_context', return_value=self.context)
        self.context_call = self.ssl_patch.start()
        self.server = app.SearchServer(('127.0.0.1', 0))
        self.api_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.api_thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}/search?q=lamp'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.assertTrue(self.server.elasticsearch.is_closed)
        self.api_thread.join(timeout=2)
        self.ssl_patch.stop()
        self.environment.stop()
        self.elastic.shutdown()
        self.elastic.server_close()
        self.elastic_thread.join(timeout=2)

    def test_reuses_connection_but_each_request_returns_a_fresh_response(self):
        parent = '00-' + 'a' * 32 + '-' + 'b' * 16 + '-01'
        def inject(headers):
            headers['traceparent'] = parent
        with patch.object(app.telemetry, 'inject', side_effect=inject), redirect_stdout(io.StringIO()):
            values = []
            for _ in range(3):
                with urllib.request.urlopen(self.url) as reply:
                    values.append(json.load(reply)['ids'])
        self.assertEqual(values, [['fresh-1'], ['fresh-2'], ['fresh-3']])
        self.assertEqual(len({call['port'] for call in ElasticFixture.calls}), 1)
        self.context_call.assert_called_once_with(cafile='/es-ca/tls.crt')
        auth = 'Basic ' + base64.b64encode(b'test-reader:synthetic-password').decode()
        self.assertTrue(all(call['authorization'] == auth and call['traceparent'] == parent for call in ElasticFixture.calls))
        self.assertTrue(all(call['body'] == app.query_body('lamp', 'GB', 'GBP') for call in ElasticFixture.calls))

    def test_upstream_errors_remain_failed_searches(self):
        ElasticFixture.status = 503
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url)
        self.assertEqual(error.exception.code, 502)
        self.assertEqual(len(ElasticFixture.calls), 1)
        self.assertNotIn('synthetic-password', error.exception.read().decode())

    def test_missing_trust_material_prevents_startup(self):
        with patch.object(app.ssl, 'create_default_context', side_effect=ssl.SSLError('bad trust material')):
            with self.assertRaises(ssl.SSLError):
                app.SearchServer(('127.0.0.1', 0))


if __name__ == '__main__':
    unittest.main()
