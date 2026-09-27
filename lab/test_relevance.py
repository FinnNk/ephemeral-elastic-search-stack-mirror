import unittest

from evaluate_relevance import score


class RelevanceMetrics(unittest.TestCase):
    def test_rank_and_unjudged_result_change_scores(self):
        qrels = [{'query_id': 'q1', 'product_id': 'relevant', 'grade': 3}]
        first = score(qrels, {'q1': ['relevant', 'unjudged']})
        second = score(qrels, {'q1': ['unjudged', 'relevant']})
        self.assertGreater(first['nDCG@10'], second['nDCG@10'])
        self.assertGreater(first['RR(rel=2)@10'], second['RR(rel=2)@10'])
        self.assertEqual(first['Judged@10'], second['Judged@10'])


if __name__ == '__main__':
    unittest.main()
