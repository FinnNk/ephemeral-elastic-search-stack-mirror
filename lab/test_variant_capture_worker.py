"""Finite capture rejects an API that serves a different runtime choice."""

import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import variant_capture_worker as worker


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class VariantCaptureTests(unittest.TestCase):
    def test_explicit_selector_and_echo(self):
        row = {'query_id': 'q1', 'query': 'lamp', 'country': 'GB', 'currency': 'GBP'}
        target = {'environment': 'lab-ranker', 'selection': 'explicit',
                  'configuration_sha256': 'a' * 64}
        payload = {'query': 'lamp', 'country': 'GB', 'currency': 'GBP', 'filters': {},
                   'variant_id': 'ranker-b', 'configuration_sha256': 'a' * 64,
                   'ids': ['p1'], 'total': 1}
        with patch.object(worker.urllib.request, 'urlopen',
                          return_value=Response(json.dumps(payload).encode())) as call:
            self.assertEqual(worker.request('ranker-b', target, row)['ids'], ['p1'])
        self.assertEqual(call.call_args.args[0].get_header('X-lab-variant'), 'ranker-b')

    def test_wrong_configuration_fails_closed(self):
        row = {'query_id': 'q1', 'query': 'lamp', 'country': 'GB', 'currency': 'GBP'}
        target = {'environment': 'lab-ranker', 'selection': 'default',
                  'configuration_sha256': 'a' * 64}
        payload = {'query': 'lamp', 'country': 'GB', 'currency': 'GBP', 'filters': {},
                   'variant_id': 'ranker-b', 'configuration_sha256': 'b' * 64,
                   'ids': ['p1'], 'total': 1}
        with patch.object(worker.urllib.request, 'urlopen',
                          return_value=Response(json.dumps(payload).encode())):
            with self.assertRaisesRegex(ValueError, 'another variant'):
                worker.request('ranker-b', target, row)

    def test_public_api_twenty_results_are_retained_at_metric_depth(self):
        row = {'query_id': 'q1', 'query': 'lamp', 'country': 'GB', 'currency': 'GBP'}
        target = {'environment': 'lab-ranker', 'selection': 'default',
                  'configuration_sha256': 'a' * 64}
        payload = {'query': 'lamp', 'country': 'GB', 'currency': 'GBP', 'filters': {},
                   'variant_id': 'ranker-a', 'configuration_sha256': 'a' * 64,
                   'ids': ['p' + str(i) for i in range(20)], 'total': 240}
        with patch.object(worker.urllib.request, 'urlopen',
                          return_value=Response(json.dumps(payload).encode())):
            result = worker.request('ranker-a', target, row)
        self.assertEqual(result['ids'], payload['ids'][:10])
        self.assertEqual(result['total'], 240)


if __name__ == '__main__':
    unittest.main()
