import unittest
from unittest.mock import patch

import control_comparison


class ControlledComparisonPreflight(unittest.TestCase):
    def test_incompatible_candidate_stops_before_full_suite(self):
        baseline = {'id': 'a', 'name': 'baseline', 'state': 'ready',
                    'fingerprint': 'fa', 'source_sha': 'sa', 'release_id': 'retail-gb-1m-v1'}
        candidate = {'id': 'b', 'name': 'candidate', 'state': 'ready',
                     'fingerprint': 'fb', 'source_sha': 'sb', 'release_id': 'retail-gb-1m-v1'}
        suite = [{'query_id': f'q{i:04d}', 'query': 'shirt', 'country': 'GB', 'currency': 'GBP'}
                 for i in range(1, 1001)]
        definitions = {'baseline': {'fingerprint': 'fa', 'dataset_sha256': 'frozen', 'engine': '9.5.4'},
                       'candidate': {'fingerprint': 'fb', 'dataset_sha256': 'frozen', 'engine': '9.5.4'}}
        def probe(name, _query):
            if name == 'candidate':
                raise KeyError('total')
            return {'ids': [], 'total': 0}
        with patch.object(control_comparison, 'definition', side_effect=lambda name: definitions[name]), \
             patch.object(control_comparison, 'frozen_suite', return_value=(suite, b'queries', 'suite',
                 {'sha256': {'queries.jsonl': 'queries', 'judgements.jsonl': 'judgements'}})), \
             patch.object(control_comparison, 'response', side_effect=probe) as calls, \
             patch.object(control_comparison, 'immutable_blob', return_value='runs/report'):
            report = control_comparison.evaluate_pair(baseline, candidate, 'result-regression')
        self.assertFalse(report['complete'])
        self.assertEqual(report['completed_query_count'], 0)
        self.assertEqual(report['errors'][0]['detail'], "'total'")
        self.assertEqual(calls.call_count, 2)


if __name__ == '__main__':
    unittest.main()
