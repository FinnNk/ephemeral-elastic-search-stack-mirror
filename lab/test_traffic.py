import csv
import json
import unittest
from pathlib import Path

from traffic import ROOT, compile_profile, generate_trace


class FrozenTrafficContract(unittest.TestCase):
    def test_trace_and_smoke_schedule_are_reproducible(self):
        trace = generate_trace()
        self.assertEqual(trace['events'], 4399)
        self.assertEqual(trace['trace_sha256'], json.loads(
            (ROOT / 'source-manifest-v1.json').read_text())['trace_sha256'])
        first = compile_profile('smoke')
        second = compile_profile('smoke')
        self.assertEqual(first, second)
        self.assertEqual(first['duration_seconds'], 390)
        self.assertEqual(first['phase_counts']['normal'], 3000)
        directory = Path(first['directory'])
        with (directory / 'schedule.csv').open(newline='', encoding='utf-8') as handle:
            schedule = list(csv.DictReader(handle))
        self.assertEqual(len(schedule), 390)
        self.assertEqual(sum(int(row['count']) for row in schedule if row['phase'] == 'normal'), 3000)

    def test_sustained_peak_is_distinct_from_normal(self):
        normal = compile_profile('normal')
        peak = compile_profile('peak')
        self.assertEqual(peak['phase_counts']['peak'], 2400)
        self.assertGreater(peak['phase_counts']['peak'], normal['phase_counts']['normal'])


if __name__ == '__main__':
    unittest.main()
