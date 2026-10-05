"""Check finite retries, endpoint isolation and recovery without stored search results."""
import io
import json
import unittest
import threading
import time
from unittest.mock import patch
from urllib.error import HTTPError

from adaptive_pacing import Pacer, retry_after
import evaluation_worker


class PacingTests(unittest.TestCase):
    def test_retry_after_rejects_nonfinite_and_handles_dates(self):
        for value in (None, 'no', 'nan', 'inf', '-inf'):
            self.assertIsNone(retry_after(value))
        self.assertEqual(retry_after('2'), 2)
        self.assertEqual(retry_after('Wed, 21 Oct 2015 07:28:00 GMT'), 0)

    def test_permanent_error_has_one_attempt(self):
        pacer = Pacer()
        with patch('adaptive_pacing.request.urlopen', side_effect=
                   HTTPError('http://test', 400, 'invalid request', {}, None)) as call:
            with self.assertRaises(HTTPError):
                pacer.fetch('http://test', {})
        self.assertEqual(call.call_count, 1)
        self.assertEqual(pacer.summary()['terminal_failures'], 1)
        self.assertEqual(pacer.summary()['successes'], 0)

    def test_persistent_overload_is_finite_and_visible(self):
        pacer = Pacer()
        with patch('adaptive_pacing.request.urlopen', side_effect=lambda *a, **kw:
                   (_ for _ in ()).throw(HTTPError('http://test', 503, 'busy',
                                                  {'Retry-After': '0'}, None))) as call:
            with self.assertRaises(HTTPError):
                pacer.fetch('http://test', {})
        self.assertEqual(call.call_count, 3)
        self.assertEqual(pacer.summary()['retries'], 2)
        self.assertEqual(pacer.summary()['transient_failures'], 3)

    def test_retry_after_beyond_budget_does_not_launch_again(self):
        pacer = Pacer()
        with patch('adaptive_pacing.request.urlopen', side_effect=
                   HTTPError('http://test', 429, 'busy', {'Retry-After': '60'}, None)) as call:
            with self.assertRaises(TimeoutError):
                pacer.fetch('http://test', {}, budget=.1)
        self.assertEqual(call.call_count, 1)

    def test_recovery_and_other_endpoint_are_independent(self):
        busy, healthy = Pacer(), Pacer()
        with patch('adaptive_pacing.time.monotonic', side_effect=range(6)):
            for _ in range(6):
                busy.failure(0, True)
        self.assertEqual(busy.interval, .25)
        self.assertEqual(healthy.interval, 0)
        for _ in range(48):
            busy.success()
        self.assertEqual(busy.interval, 0)

    def test_one_concurrent_burst_does_not_multiply_the_slowdown(self):
        pacer = Pacer()
        with patch('adaptive_pacing.time.monotonic', return_value=1):
            for _ in range(8):
                pacer.failure(.2, True)
        self.assertEqual(pacer.interval, .05)
        self.assertEqual(pacer.summary()['transient_failures'], 8)

    def test_duplicate_requests_are_fresh(self):
        pacer = Pacer()
        with patch('adaptive_pacing.request.urlopen', side_effect=lambda *a, **kw:
                   io.BytesIO(json.dumps({'ids': []}).encode())) as call:
            for _ in range(2):
                self.assertEqual(pacer.fetch('http://test', {}), {'ids': []})
        self.assertEqual(call.call_count, 2)
        self.assertEqual(pacer.summary()['successes'], 2)

    def test_retry_recovery_counts_one_success(self):
        pacer = Pacer()
        with patch('adaptive_pacing.request.urlopen', side_effect=[
                HTTPError('http://test', 503, 'busy', {'Retry-After': '0'}, None),
                io.BytesIO(b'{"ids": []}')]):
            self.assertEqual(pacer.fetch('http://test', {}), {'ids': []})
        stats = pacer.summary()
        self.assertEqual((stats['attempts'], stats['successes'], stats['retries']), (2, 1, 1))
        self.assertEqual((stats['transient_failures'], stats['terminal_failures']), (1, 0))

    def test_capture_has_eight_workers_and_independent_endpoint_records(self):
        lock = threading.Lock()
        active, peak = 0, 0
        seen = []

        def answer(name, row, pacer):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                seen.append((name, row['query_id'], id(pacer)))
            time.sleep(.01)
            with lock:
                active -= 1
            return {'ids': [], 'total': 0}

        diagnostics = {}
        rows = [{'query_id': str(i)} for i in range(32)]
        with patch.object(evaluation_worker, 'request', side_effect=answer):
            result = evaluation_worker.run(rows, 'baseline', 'candidate', diagnostics=diagnostics)
        self.assertEqual(peak, 8)
        self.assertEqual([row['query_id'] for row in result], [row['query_id'] for row in rows])
        self.assertEqual(len(seen), 64)
        baseline = {pacer for name, _, pacer in seen if name == 'baseline'}
        candidate = {pacer for name, _, pacer in seen if name == 'candidate'}
        self.assertEqual(len(baseline), 1)
        self.assertEqual(len(candidate), 1)
        self.assertTrue(baseline.isdisjoint(candidate))
        self.assertEqual(set(diagnostics), {'baseline', 'candidate'})


if __name__ == '__main__':
    unittest.main()
