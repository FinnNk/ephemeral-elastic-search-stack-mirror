"""Known good, slow and failed synthetic events exercise both budgets."""

from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from slo import analyse

POLICY = json.loads((Path(__file__).parent / 'policies/search-slo-v1.json').read_bytes())


class SloTests(unittest.TestCase):
    def event(self, success, responsive, cohort='normal'):
        return {'event': 'search.completed', 'observed_at': datetime.now(timezone.utc).isoformat(),
                'traffic_class': cohort, 'success_good': success,
                'responsive_good': responsive}

    def test_slow_success_spends_latency_budget_only(self):
        events = [self.event(True, True) for _ in range(970)]
        events += [self.event(True, False) for _ in range(30)]
        events += [self.event(False, False, 'stress')]
        result = analyse(events, POLICY, coverage_complete=True)
        self.assertEqual(result['eligible'], 1000)
        self.assertEqual(result['objectives']['search-success']['bad'], 0)
        self.assertEqual(result['objectives']['responsive-search']['bad'], 30)
        self.assertAlmostEqual(result['objectives']['responsive-search']['budget_consumed'], 0.6)
        self.assertEqual(result['objectives']['responsive-search']['status'], 'met')

    def test_no_data_and_unverified_coverage_are_not_green(self):
        empty = analyse([], POLICY, coverage_complete=True)
        self.assertEqual(empty['objectives']['search-success']['status'], 'no-data')
        self.assertIsNone(empty['objectives']['search-success']['observed_sli'])
        observed = analyse([self.event(True, True)], POLICY)
        self.assertEqual(observed['objectives']['search-success']['status'], 'unverified')
        self.assertTrue(observed['low_sample_count'])
        low_sample = analyse([self.event(True, True)], POLICY, coverage_complete=True)
        self.assertEqual(low_sample['objectives']['search-success']['status'], 'unverified')

    def test_failure_spends_both_budgets(self):
        events = [self.event(True, True) for _ in range(989)]
        events += [self.event(False, False) for _ in range(11)]
        result = analyse(events, POLICY, coverage_complete=True)
        self.assertEqual(result['objectives']['search-success']['status'], 'breached')
        self.assertLess(result['objectives']['search-success']['remaining_budget'], 0)
        self.assertEqual(result['objectives']['responsive-search']['bad'], 11)


if __name__ == '__main__':
    unittest.main()
