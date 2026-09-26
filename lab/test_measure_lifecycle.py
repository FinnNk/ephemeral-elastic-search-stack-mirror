import unittest

from measure_lifecycle import summarise


class RemovalSummary(unittest.TestCase):
    def test_nearest_rank_p95_and_failure_gate(self):
        samples = [{'passed': True, 'delete_seconds': value} for value in range(1, 21)]
        result = summarise(samples)
        self.assertEqual(result['p95_delete_seconds'], 19)
        self.assertEqual(result['p50_delete_seconds'], 10.5)
        self.assertTrue(result['target_met'])
        samples[0] = {'passed': False, 'error_kind': 'TimeoutError'}
        result = summarise(samples)
        self.assertIsNone(result['p95_delete_seconds'])
        self.assertFalse(result['target_met'])


if __name__ == '__main__':
    unittest.main()
