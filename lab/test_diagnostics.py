import unittest

from compare_diagnostics import difference, verdict


class DiagnosticComparison(unittest.TestCase):
    def test_order_membership_and_incomplete_verdicts(self):
        before = {'ids': ['a', 'b'], 'total': 2}
        same = {'ids': ['a', 'b'], 'total': 2}
        reordered = {'ids': ['b', 'a'], 'total': 2}
        replaced = {'ids': ['a', 'c'], 'total': 2}
        self.assertTrue(difference(before, same)['equal_top_10'])
        self.assertFalse(difference(before, reordered)['equal_top_10'])
        self.assertEqual(difference(before, reordered)['jaccard_at_10'], 1)
        self.assertEqual(difference(before, replaced)['added_ids'], ['c'])
        self.assertEqual(verdict([], []), 'incomplete')
        self.assertEqual(verdict([{'preservation': difference(before, same)}] * 51,
                                 [{'query_id': 'q1'}]), 'incomplete')
        self.assertEqual(verdict([{'preservation': difference(before, reordered)}] * 51, []), 'changed')


if __name__ == '__main__':
    unittest.main()
