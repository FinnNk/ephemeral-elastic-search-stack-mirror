"""Behavioural checks for pooled judgement resolution."""

import unittest

from core import pool, resolve


class JudgementResolutionTests(unittest.TestCase):
    def setUp(self):
        self.observations = {'captured_depth': 10,
            'variants': {'ranker-a': {}, 'ranker-b': {}, 'ranker-c': {}},
            'observations': [{
            'query_id': 'q1', 'request': {'query': 'desk lamp', 'country': 'GB',
                                          'currency': 'GBP', 'filters': {}},
            'results': {'ranker-a': {'ids': ['p1', 'p2']},
                        'ranker-b': {'ids': ['p3', 'p1']},
                        'ranker-c': {'ids': ['p2', 'p3']}}}]}
        self.specification = {'metrics': ['nDCG@2', 'Judged@2']}
        self.products = {key: {'product_id': key, 'title': key,
                               'country': 'GB', 'currency': 'GBP'}
                         for key in ('p1', 'p2', 'p3')}
        self.source = [{'query_id': 'q1', 'product_id': 'p1', 'grade': 3}]

    def test_union_resolves_only_gaps_and_abstention_is_not_a_label(self):
        calls = []

        def infer(items):
            calls.append([item['product_id'] for item in items])
            return [{'outcome': 'abstain'} for _ in items]

        frozen, receipt = resolve(self.observations, self.specification,
                                  self.source, self.products, infer)
        self.assertEqual(calls, [['p2', 'p3']])
        self.assertEqual(frozen, self.source)
        self.assertEqual(receipt['counts']['pool'], {
            'required': 3, 'stored': 1, 'newly_labelled': 0,
            'abstained': 2, 'failed': 0})
        self.assertEqual(receipt['counts']['ranker-a']['judged'], 1)
        self.assertEqual(receipt['counts']['ranker-b']['judged'], 1)

    def test_model_label_is_shared_by_both_sides(self):
        def infer(items):
            return [{'outcome': 'labelled', 'label': 'S', 'gate_eligible': True,
                     'provenance': {'kind': 'model', 'source_id': 'fixture'}} for _ in items]

        frozen, receipt = resolve(self.observations, self.specification,
                                  self.source, self.products, infer)
        self.assertEqual({row['product_id']: row['grade'] for row in frozen},
                         {'p1': 3, 'p2': 2, 'p3': 2})
        self.assertEqual(receipt['counts']['ranker-a']['judged'], 2)
        self.assertEqual(receipt['counts']['ranker-b']['judged'], 2)

    def test_inference_failure_does_not_become_irrelevant(self):
        def infer(_):
            raise TimeoutError('slow')

        frozen, receipt = resolve(self.observations, self.specification,
                                  self.source, self.products, infer)
        self.assertEqual(frozen, self.source)
        self.assertEqual(receipt['counts']['pool']['failed'], 2)

    def test_cutoff_limits_pool(self):
        pairs, sides = pool(self.observations, {'metrics': ['RR@1:rel=2']})
        self.assertEqual({p['product_id'] for p in pairs}, {'p1', 'p2', 'p3'})
        self.assertEqual(len(sides['ranker-a']), 1)


if __name__ == '__main__':
    unittest.main()
