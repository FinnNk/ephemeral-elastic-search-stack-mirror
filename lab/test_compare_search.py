import unittest

from compare_search import jaccard, rbo


class ResultMetrics(unittest.TestCase):
    def test_identical_and_disjoint(self):
        a = list(range(10))
        b = list(range(10, 20))
        self.assertEqual(jaccard(a, a), 1)
        self.assertEqual(rbo(a, a), 1)
        self.assertEqual(jaccard(a, b), 0)
        self.assertEqual(rbo(a, b), 0)
        self.assertEqual(jaccard([], []), 1)
        self.assertEqual(rbo([], []), 1)

    def test_reorder_has_full_membership_but_lower_rank_overlap(self):
        a = list(range(10))
        reversed_a = list(reversed(a))
        self.assertEqual(jaccard(a, reversed_a), 1)
        self.assertLess(rbo(a, reversed_a), 1)
        self.assertGreater(rbo(a, reversed_a), 0)


if __name__ == '__main__':
    unittest.main()
