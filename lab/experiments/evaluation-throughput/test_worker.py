"""Scheduling must preserve fresh requests, bounds and visible failures."""
import concurrent.futures
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
import unittest
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'search-app'))
from worker import capture


class Fixture(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    lock = threading.Lock()
    calls = {}
    active = peak = 0
    failure = None
    unstable = False
    delays = {}

    def log_message(self, *_args):
        pass

    def do_GET(self):
        cls = type(self)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        variant = self.headers.get('X-Lab-Variant', 'ranker-a')
        key = (params['q'][0], variant)
        with cls.lock:
            cls.calls[key] = cls.calls.get(key, 0) + 1
            attempt = cls.calls[key]
            cls.active += 1
            cls.peak = max(cls.peak, cls.active)
        time.sleep(cls.delays.get(variant, .005))
        status = 503 if cls.failure == 'transient' and attempt == 1 else 400 if cls.failure == 'permanent' else 200
        value = {'query': params['q'][0], 'country': params['country'][0],
            'currency': params['currency'][0], 'filters': json.loads(params['filters'][0]),
            'variant_id': variant, 'configuration_sha256': variant[-1] * 64,
            'ids': [str(attempt if cls.unstable else 1)], 'total': 1}
        payload = json.dumps(value).encode()
        with cls.lock:
            cls.active -= 1
        self.send_response(status)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class SchedulerContract(unittest.TestCase):
    def setUp(self):
        Fixture.calls, Fixture.active, Fixture.peak = {}, 0, 0
        Fixture.failure, Fixture.unstable, Fixture.delays = None, False, {}
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.rows = [{'query_id': 'q' + str(i), 'query': 'term' + str(i), 'country': 'GB',
                      'currency': 'GBP', 'filters': {'category': ['apparel']}} for i in range(15)]
        self.spec = {'limit': 8, 'seed': 42, 'variants': {
            name: {'url': f'http://127.0.0.1:{self.server.server_port}',
                   'selection': 'default' if name == 'ranker-a' else 'explicit',
                   'configuration_sha256': name[-1] * 64} for name in ('ranker-a','ranker-b')}}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_strategies_preserve_results_and_issue_every_search_fresh(self):
        hashes = set()
        for strategy, client in (('thread-query','urllib'),('thread-query','httpx'),
                ('thread-flat','httpx'),('async-query','httpx'),('async-flat','httpx'),('adaptive','httpx')):
            Fixture.peak = 0
            result = capture(self.rows, {**self.spec, 'strategy': strategy, 'client': client})
            self.assertEqual(result['errors'], 0)
            self.assertEqual(result['request_count'], 30)
            self.assertLessEqual(Fixture.peak, 8)
            self.assertEqual([row['query_id'] for row in result['observations']],
                             [row['query_id'] for row in self.rows])
            hashes.add(result['semantic_sha256'])
        self.assertEqual(len(hashes), 1)
        self.assertEqual(sum(Fixture.calls.values()), 180)

    def test_retry_is_bounded_and_permanent_errors_remain_visible(self):
        Fixture.failure = 'transient'
        result = capture(self.rows, {**self.spec, 'strategy': 'adaptive', 'client': 'httpx'})
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['retries'], 30)
        self.assertEqual(sum(Fixture.calls.values()), 60)
        Fixture.calls = {}
        Fixture.failure = 'permanent'
        result = capture(self.rows, {**self.spec, 'strategy': 'async-flat', 'client': 'httpx'})
        self.assertEqual(result['errors'], 30)
        self.assertEqual(result['retries'], 0)
        self.assertEqual(sum(Fixture.calls.values()), 30)

    def test_slow_variant_and_overlapping_captures_remain_bounded(self):
        Fixture.delays = {'ranker-b': .03}
        spec = {**self.spec, 'strategy': 'thread-query', 'client': 'httpx'}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as jobs:
            results = list(jobs.map(lambda _: capture(self.rows, spec), range(2)))
        self.assertLessEqual(Fixture.peak, 16)  # Two allocations of eight, aggregate budget 32.
        self.assertEqual(sum(Fixture.calls.values()), 60)
        self.assertTrue(all(result['errors'] == 0 for result in results))
        self.assertEqual(results[0]['semantic_sha256'], results[1]['semantic_sha256'])

    def test_adaptive_retries_cause_backoff_without_starving_a_variant(self):
        Fixture.failure = 'transient'
        rows = self.rows * 4
        # Distinct identities keep the fixture's first-attempt failure per request.
        rows = [{**row, 'query_id': 'q' + str(i), 'query': 'term' + str(i)} for i, row in enumerate(rows)]
        result = capture(rows, {**self.spec, 'strategy': 'adaptive', 'client': 'httpx', 'limit': 32})
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['retries'], 120)
        self.assertTrue(any(item.get('reason') == 'backoff' for item in result['concurrency_history']))
        self.assertEqual(result['request_count'], 120)
        self.assertLessEqual(Fixture.peak, 8)

    def test_non_deterministic_results_are_not_hidden(self):
        Fixture.unstable = True
        spec = {**self.spec, 'strategy': 'thread-query', 'client': 'urllib'}
        first, second = capture(self.rows, spec), capture(self.rows, spec)
        self.assertNotEqual(first['semantic_sha256'], second['semantic_sha256'])
        self.assertEqual(sum(Fixture.calls.values()), 60)


if __name__ == '__main__':
    unittest.main()
