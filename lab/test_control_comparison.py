import unittest
from unittest.mock import patch
import json

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

    def test_frozen_relevance_reports_coverage_without_inventing_labels(self):
        baseline = {'id': 'a', 'name': 'baseline', 'state': 'ready',
                    'fingerprint': 'fa', 'source_sha': 'sa', 'release_id': 'retail-gb-1m-v1'}
        candidate = {'id': 'b', 'name': 'candidate', 'state': 'ready',
                     'fingerprint': 'fb', 'source_sha': 'sb', 'release_id': 'retail-gb-1m-v1'}
        suite = [{'query_id': 'q1', 'query': 'shirt', 'country': 'GB', 'currency': 'GBP'}]
        definitions = {'baseline': {'fingerprint': 'fa', 'dataset_sha256': 'frozen', 'engine': '9.5.4'},
                       'candidate': {'fingerprint': 'fb', 'dataset_sha256': 'frozen', 'engine': '9.5.4'}}
        published = []
        def store(_container, _name, payload):
            published.append(payload)
            return 'runs/report'
        with patch.object(control_comparison, 'definition', side_effect=lambda name: definitions[name]), \
             patch.object(control_comparison, 'frozen_suite', return_value=(suite, b'', 'suite',
                 {'sha256': {'queries.jsonl': 'queries'}})), \
             patch.object(control_comparison, 'frozen_judgements', return_value=(suite,
                 [{'query_id': 'q1', 'product_id': 'p1', 'grade': 3}],
                 {'sha256': {'judgements.jsonl': 'j'}, 'judgement_pool': {'source': 'old runs'}})), \
             patch.object(control_comparison, 'response', return_value={'ids': ['p1'], 'total': 1}), \
             patch('evaluation_job.run', return_value=([{'query_id': 'q1',
                 'baseline': {'ids': ['p1'], 'total': 1},
                 'candidate': {'ids': ['p2'], 'total': 1}}], {'execution': 'job', 'seconds': 1})), \
             patch.object(control_comparison, 'score', return_value={'nDCG@10': 0.5}), \
             patch.object(control_comparison, 'query_ndcg', side_effect=[{'q1': 1.0}, {'q1': 0.0}]), \
             patch.object(control_comparison, 'search', return_value=None), \
             patch.object(control_comparison, 'immutable_blob', side_effect=store):
            summary = control_comparison.evaluate_pair(baseline, candidate, 'relevance', 'quick')
        report = json.loads(published[-1])
        self.assertTrue(summary['complete'])
        self.assertEqual(report['judgement_coverage']['candidate']['fraction'], 0.0)
        self.assertEqual(report['queries'][0]['candidate']['unjudged_top_10_ids'], ['p2'])
        self.assertFalse(report['judgement_provenance']['independent_of_evaluated_candidate'])
        self.assertEqual(report['queries'][0]['ndcg_delta_at_10'], -1.0)


if __name__ == '__main__':
    unittest.main()
