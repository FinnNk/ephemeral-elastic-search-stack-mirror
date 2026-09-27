import unittest
from unittest.mock import patch

import evaluation_worker
from pr_workflow import matching_comparison, opted_in, verdict_comment


class EvaluatorContract(unittest.TestCase):
    def test_worker_keeps_frozen_order_and_isolates_request_errors(self):
        rows = [{'query_id': 'q1', 'query': 'shoes', 'country': 'GB', 'currency': 'GBP'},
                {'query_id': 'q2', 'query': 'coat', 'country': 'GB', 'currency': 'GBP'}]
        def answer(side, row):
            if side == 'candidate' and row['query_id'] == 'q2':
                raise ValueError('bad candidate response')
            return {'ids': [side + row['query_id']], 'total': 1}
        with patch.object(evaluation_worker, 'request', side_effect=answer):
            result = evaluation_worker.run(rows, 'baseline', 'candidate', worker_count=2)
        self.assertEqual([row['query_id'] for row in result], ['q1', 'q2'])
        self.assertEqual(result[0]['baseline']['ids'], ['baselineq1'])
        self.assertEqual(result[1]['error']['kind'], 'ValueError')
        with self.assertRaises(ValueError):
            evaluation_worker.run(rows, 'baseline', 'candidate', worker_count=17)

    def test_pr_trigger_requires_open_opted_in_revision(self):
        pr = {'state': 'open', 'labels': [{'name': 'lab-evaluate'}]}
        self.assertTrue(opted_in(pr))
        pr['state'] = 'closed'
        self.assertFalse(opted_in(pr))

    def test_comparison_reuses_exact_pair_mode_scope_and_profile(self):
        row = {'id': 'report', 'baseline_id': 'a', 'candidate_id': 'b', 'mode': 'result-regression',
               'scope': 'quick', 'profile': None, 'state': 'complete'}
        class Store:
            def all_comparisons(self):
                return [row]
        class Controller:
            store = Store()
        self.assertEqual(matching_comparison(Controller(), {'id': 'a'}, {'id': 'b'},
                                             'result-regression', 'quick'), row)
        self.assertIsNone(matching_comparison(Controller(), {'id': 'a'}, {'id': 'b'},
                                              'result-regression', 'full'))

    def test_comment_links_exact_revision_and_report(self):
        environment = {'fingerprint': 'f' * 64, 'release_id': 'retail-gb-10k-v1'}
        row = {'id': 'a' * 36, 'state': 'complete', 'verdict': 'changed',
               'report_sha256': 'b' * 64, 'summary': {'query_count': 50, 'completed_query_count': 50}}
        body = verdict_comment({}, 'c' * 40, environment, environment,
                               [('Quick result check', row)], 3.0, 12.5)
        self.assertIn('relevance-lab:' + 'c' * 40, body)
        self.assertIn('?comparison=' + 'a' * 36, body)
        self.assertIn('50/50 queries', body)


if __name__ == '__main__':
    unittest.main()
