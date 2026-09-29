"""Check the input-shift calculation used by retained reports and SigNoz."""

import unittest

from drift import divergence, input_shift


class DriftTests(unittest.TestCase):
    def test_identical_and_disjoint_mix(self):
        self.assertEqual(divergence(['0-1', '2-3'], ['2-3', '0-1']), 0)
        self.assertEqual(divergence(['0-1'], ['16+']), 1)
        self.assertIsNone(divergence(['0-1'], []))

    def test_shift_is_from_frozen_queries_to_model_attempt_pairs(self):
        observations = {'observations': [
            {'query_id': 'q1', 'request': {'query': 'lamp'}},
            {'query_id': 'q2', 'request': {'query': 'small blue desk lamp'}}]}
        result = input_shift(observations, [
            {'query_id': 'q1'}, {'query_id': 'q1'}])
        self.assertEqual(result['reference_count'], 2)
        self.assertEqual(result['observed_count'], 2)
        self.assertGreater(result['js_divergence'], 0)
        self.assertLess(result['js_divergence'], 1)
        self.assertIsNone(input_shift(observations, [])['js_divergence'])


if __name__ == '__main__':
    unittest.main()
