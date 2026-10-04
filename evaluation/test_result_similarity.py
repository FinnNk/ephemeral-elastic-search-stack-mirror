import unittest
from result_similarity import jaccard, rbo


class SimilarityTests(unittest.TestCase):
    def test_order_and_membership_are_distinct(self):
        first = list('abcdefghij')
        second = list(reversed(first))
        self.assertEqual(jaccard(first, second), 1)
        self.assertLess(rbo(first, second), 0.6)
        self.assertEqual(rbo(first, first), 1)
        self.assertEqual(rbo(first, list('klmnopqrst')), 0)

    def test_short_and_empty_lists(self):
        self.assertEqual(rbo([], []), 1)
        self.assertEqual(rbo([], ['a']), 0)
        self.assertEqual(rbo(['a'], ['a']), 1)
        self.assertGreater(rbo(['a'], ['a', 'b']), 0)
        self.assertLess(rbo(['a'], ['a', 'b']), 1)


if __name__ == '__main__':
    unittest.main()
