"""Seven-day bucket arithmetic and fail-closed coverage checks."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from window import assess


POLICY = json.loads((Path(__file__).parent / 'policies/search-slo-v1.json').read_bytes())
START = datetime(2026, 9, 21, tzinfo=timezone.utc)


def fixture(requests=6):
    buckets = [{
        'start': (START + timedelta(hours=index)).isoformat(),
        'collector_ok': True, 'expected_requests': requests,
        'eligible': requests, 'success_good': requests,
        'responsive_good': requests,
    } for index in range(168)]
    return {'window_start': START.isoformat(),
            'window_end': (START + timedelta(days=7)).isoformat(),
            'interval_seconds': 3600, 'source_verified': True,
            'buckets': buckets}


class WindowTests(unittest.TestCase):
    def test_fast_slow_error_deadline_and_retry_attempts(self):
        document = fixture()
        # One retry adds an attempt; a slow HTTP 200 spends latency only.
        first = document['buckets'][0]
        first.update(expected_requests=7, eligible=7, success_good=7,
                     responsive_good=6)
        # An HTTP error and an expired deadline spend both budgets.
        second = document['buckets'][1]
        second.update(success_good=4, responsive_good=4)
        result = assess(document, POLICY)
        self.assertEqual(result['coverage'], 'complete')
        self.assertEqual(result['eligible'], 1009)
        self.assertEqual(result['objectives']['search-success']['bad'], 2)
        self.assertEqual(result['objectives']['responsive-search']['bad'], 3)
        self.assertEqual(result['objectives']['search-success']['status'], 'met')

    def test_missing_collector_or_source_coverage_cannot_be_green(self):
        document = fixture()
        document['buckets'][20]['collector_ok'] = False
        result = assess(document, POLICY)
        self.assertEqual(result['gap_count'], 1)
        self.assertEqual(result['objectives']['search-success']['status'], 'unverified')
        document = fixture()
        document['source_verified'] = False
        self.assertEqual(assess(document, POLICY)['coverage'], 'unverified')

    def test_missing_bucket_or_counter_mismatch_cannot_be_green(self):
        document = fixture()
        document['buckets'].pop()
        self.assertEqual(assess(document, POLICY)['gap_count'], 1)
        document = fixture()
        document['buckets'][0]['expected_requests'] = 7
        result = assess(document, POLICY)
        self.assertEqual(result['mismatch_count'], 1)
        self.assertEqual(result['objectives']['responsive-search']['status'], 'unverified')

    def test_low_sample_and_no_data_cannot_be_green(self):
        document = fixture(0)
        result = assess(document, POLICY)
        self.assertEqual(result['objectives']['search-success']['status'], 'no-data')
        document['buckets'][0].update(expected_requests=1, eligible=1,
                                      success_good=1, responsive_good=1)
        result = assess(document, POLICY)
        self.assertTrue(result['low_sample_count'])
        self.assertEqual(result['objectives']['search-success']['status'], 'unverified')

    def test_duplicate_and_invalid_counter_are_rejected(self):
        document = fixture()
        document['buckets'].append(document['buckets'][0].copy())
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            assess(document, POLICY)
        document = fixture()
        document['buckets'][0]['eligible'] = -1
        with self.assertRaisesRegex(ValueError, 'non-negative'):
            assess(document, POLICY)


if __name__ == '__main__':
    unittest.main()
