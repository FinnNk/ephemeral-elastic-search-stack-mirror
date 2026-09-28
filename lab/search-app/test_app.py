import unittest
import app
from telemetry import Telemetry, classify, traffic_class
from http.server import ThreadingHTTPServer
import http.client
import io
import json
import os
import threading
from contextlib import redirect_stdout
from unittest.mock import patch


class SearchContract(unittest.TestCase):
    def test_market_and_query_validation(self):
        self.assertEqual(app.validated_query('/search?q=+running++shoes+'), ('running shoes', 'GB', 'GBP'))
        with self.assertRaises(ValueError):
            app.validated_query('/search?q=running+shoes&country=US&currency=USD')
        with self.assertRaises(ValueError):
            app.validated_query('/search?q=')

    def test_query_filters_and_stable_sort(self):
        body = app.query_body('running shoes', 'GB', 'GBP')
        self.assertEqual(body['query']['bool']['filter'], [
            {'term': {'country': 'GB'}}, {'term': {'currency': 'GBP'}}, {'term': {'available': True}}])
        self.assertEqual(body['sort'][-1], {'product_id': 'asc'})

    def test_public_result_shape(self):
        hit = {'_id': 'gb-000001', '_source': {
            'product_id': 'gb-000001', 'title': 'Alder blue shirt', 'brand': 'Alder',
            'category': 'clothing', 'price_minor': 2500, 'currency': 'GBP', 'available': True,
            'description': 'Internal text', 'popularity': .4,
        }}
        response = app.api_response('shirt', 'GB', 'GBP', {'hits': {'total': {'value': 1}, 'hits': [hit]}}, 12.3456)
        self.assertEqual(response['ids'], ['gb-000001'])
        self.assertEqual(response['total'], 1)
        self.assertNotIn('description', response['results'][0])
        self.assertEqual(response['elapsed_ms'], 12.346)

    def test_diagnostics_do_not_change_query_or_result(self):
        self.assertEqual(app.understand('cotton shirt'), ('cotton shirt', 'none'))
        self.assertEqual(app.query_body('cotton shirt', 'GB', 'GBP')['query']['bool']['must'][0]['multi_match']['query'], 'cotton shirt')
        self.assertEqual(app.diagnostic_options('/search?q=shirt&diagnostics=1&request_id=q001-base'), 'q001-base')
        self.assertIsNone(app.diagnostic_options('/search?q=shirt'))
        with self.assertRaises(ValueError):
            app.diagnostic_options('/search?q=shirt&diagnostics=1&request_id=bad%20id')
        hit = {'_source': {'product_id': 'gb-000001'}}
        record = app.diagnostic_record(' shirt ', 'shirt', app.query_body('shirt', 'GB', 'GBP'),
                                       {'hits': {'hits': [hit]}}, 'q001-base', 12.5, 8.1)
        self.assertEqual(record['retrieved_ids'], ['gb-000001'])
        self.assertEqual(record['rewrite'], 'none')
        self.assertEqual(record['unavailable_stages'], ['reranker'])
        self.assertEqual(len(record['elasticsearch_request_sha256']), 64)

    def test_sli_classification_counts_slow_success_and_failure(self):
        self.assertEqual(classify(200, 249.9),
                         {'eligible': 1, 'success_good': 1, 'responsive_good': 1})
        self.assertEqual(classify(200, 251),
                         {'eligible': 1, 'success_good': 1, 'responsive_good': 0})
        self.assertEqual(classify(502, 20),
                         {'eligible': 1, 'success_good': 0, 'responsive_good': 0})
        with self.assertRaises(ValueError):
            classify(200, -1)
        self.assertEqual(traffic_class('peak'), 'peak')
        self.assertEqual(traffic_class('query-id-with-unbounded-values'), 'unspecified')

    def test_completion_log_retains_release_and_tier_without_query(self):
        output = io.StringIO()
        with patch.dict(os.environ, {'LAB_RELEASE_SHA': 'sha256:' + 'a' * 64,
                                      'LAB_DEPLOYMENT_TIER': 'integration'}), \
                redirect_stdout(output):
            Telemetry().record(200, 360, 'normal', request_id='synthetic-1')
        event = json.loads(output.getvalue())
        self.assertEqual(event['service_version'], 'sha256:' + 'a' * 64)
        self.assertEqual(event['deployment_tier'], 'integration')
        self.assertFalse(event['responsive_good'])
        self.assertNotIn('query', event)

    def test_public_http_result_stays_valid_with_telemetry_disabled(self):
        hit = {'_source': {'product_id': 'gb-1', 'title': 'Blue shirt', 'brand': 'Alder',
                           'category': 'clothing', 'price_minor': 2500,
                           'currency': 'GBP', 'available': True}}
        elastic = {'hits': {'total': {'value': 1}, 'hits': [hit]}}

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.dict(os.environ, {'ES_USER': 'reader', 'ES_PASSWORD': 'test',
                                          'ES_URL': 'https://example.invalid', 'ES_INDEX': 'test'}), \
                    patch.object(app.ssl, 'create_default_context', return_value=None), \
                    patch.object(app.urllib.request, 'urlopen', return_value=Response(json.dumps(elastic).encode())):
                client = http.client.HTTPConnection('127.0.0.1', server.server_port)
                client.request('GET', '/search?q=shirt', headers={'X-Lab-Traffic-Class': 'normal'})
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.load(response)['ids'], ['gb-1'])
                client.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
