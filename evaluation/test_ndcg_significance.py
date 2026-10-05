"""Check paired inference, dependent request groups and bounded resampling."""
import unittest
from ndcg_significance import analyse


def fixture(deltas, queries=None, variants=('baseline', 'ranker-a')):
    requests = {str(i): {'query': (queries or [str(j) for j in range(len(deltas))])[i],
                          'country': 'GB', 'currency': 'GBP', 'filters': {}}
                for i in range(len(deltas))}
    scores = {v: {'nDCG@10': {str(i): .5 + (0 if v == 'baseline' else d)
                            for i, d in enumerate(deltas)}} for v in variants}
    return scores, requests


class SignificanceTests(unittest.TestCase):
    def analyse(self, deltas, queries=None):
        scores, requests = fixture(deltas, queries)
        return analyse(scores, requests, 'baseline', scores, set(requests))

    def test_identical_scores(self):
        result = self.analyse([0] * 10)['comparisons']['ranker-a']['nDCG@10']
        self.assertEqual(result['p_value'], 1)
        self.assertEqual(result['confidence_interval_95'], [0, 0])
        self.assertFalse(result['significant'])

    def test_positive_and_negative_effects_repeat_exactly(self):
        for sign in (1, -1):
            first = self.analyse([sign * .2] * 20)
            self.assertEqual(first, self.analyse([sign * .2] * 20))
            result = first['comparisons']['ranker-a']['nDCG@10']
            self.assertTrue(result['significant'])
            self.assertAlmostEqual(result['mean_difference'], sign * .2)
            self.assertAlmostEqual(result['confidence_interval_95'][0], sign * .2)

    def test_single_case_varied_request_is_insufficient(self):
        result = self.analyse([.2, .2], ['Shoes', 'shoes'])['comparisons']['ranker-a']['nDCG@10']
        self.assertEqual(result['request_groups'], 1)
        self.assertIsNone(result['p_value'])
        self.assertIsNone(result['significant'])

    def test_cluster_permutation_preserves_case_weighting(self):
        result = self.analyse([.2, .2, -.1], ['Shoes', 'shoes', 'lamp'])['comparisons']['ranker-a']['nDCG@10']
        self.assertEqual(result['request_groups'], 2)
        self.assertAlmostEqual(result['mean_difference'], .1)
        self.assertEqual(result['p_value'], 1)

    def test_holm_adjustment_and_exclusions(self):
        scores, requests = fixture([.2] * 6, variants=('baseline', 'ranker-a', 'ranker-b'))
        scores['ranker-b']['nDCG@10'].pop('0')
        result = analyse(scores, requests, 'baseline', scores, set(requests))
        a = result['comparisons']['ranker-a']['nDCG@10']
        b = result['comparisons']['ranker-b']['nDCG@10']
        self.assertEqual(result['tested_comparisons'], 2)
        self.assertEqual(a['p_value'], .03125)
        self.assertEqual(a['adjusted_p_value'], .0625)
        self.assertFalse(a['significant'])
        self.assertEqual(b['excluded_queries'], 1)

    def test_filtered_requests_are_distinct_and_no_positive_gain_is_excluded(self):
        scores, requests = fixture([.1, .1], ['lamp', 'lamp'])
        requests['1']['filters'] = {'brand': 'Acme'}
        result = analyse(scores, requests, 'baseline', scores, {'0'})['comparisons']['ranker-a']['nDCG@10']
        self.assertEqual(result['excluded_queries'], 1)
        result = analyse(scores, requests, 'baseline', scores, set(requests))['comparisons']['ranker-a']['nDCG@10']
        self.assertEqual(result['request_groups'], 2)


if __name__ == '__main__':
    unittest.main()
