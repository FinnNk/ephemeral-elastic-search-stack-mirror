"""Retained run evidence cannot claim seven-day coverage from a short segment."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from export_window import assemble, read_probes


POLICY = json.loads((Path(__file__).parent / 'policies/search-slo-v1.json').read_bytes())
AT = datetime(2026, 9, 28, 7, 0, tzinfo=timezone.utc)


class ExportTests(unittest.TestCase):
    def test_overlapping_probe_files_do_not_double_count_a_sample(self):
        with TemporaryDirectory() as directory:
            first = Path(directory) / 'first.jsonl'
            second = Path(directory) / 'second.jsonl'
            line = json.dumps({'observed_at': AT.isoformat(), 'collector_ok': True}) + '\n'
            first.write_text(line, encoding='utf-8')
            second.write_text(line, encoding='utf-8')
            self.assertEqual(len(read_probes([first, second])[AT]), 1)

    def test_complete_run_segment_is_still_unknown_for_seven_days(self):
        arrivals = {AT: 100}
        probes = {AT: [{'collector_ok': True}] * 6}
        counters = {'eligible': {AT: 100}, 'success_good': {AT: 100},
                    'responsive_good': {AT: 100}}
        document, verdict = assemble(arrivals, probes, counters, POLICY)
        self.assertEqual(verdict['run_segment']['status'], 'matched-exact')
        self.assertEqual(verdict['coverage'], 'unverified')
        self.assertEqual(verdict['objectives']['search-success']['status'], 'unverified')
        self.assertFalse(document['source_verified'])

    def test_collector_gap_and_counter_loss_fail_run_segment(self):
        arrivals = {AT: 10, AT + timedelta(minutes=1): 20}
        probes = {AT: [{'collector_ok': True}] * 6,
                  AT + timedelta(minutes=1): [{'collector_ok': False}] * 6}
        counters = {'eligible': {AT: 10, AT + timedelta(minutes=1): 19},
                    'success_good': {AT: 10, AT + timedelta(minutes=1): 19},
                    'responsive_good': {AT: 10, AT + timedelta(minutes=1): 19}}
        _document, verdict = assemble(arrivals, probes, counters, POLICY)
        self.assertEqual(verdict['run_segment']['status'], 'unverified')
        self.assertEqual(verdict['run_segment']['healthy_arrival_minutes'], 1)
        self.assertEqual(len(verdict['run_segment']['counter_mismatch_minutes']), 1)

    def test_export_shift_can_match_run_total_without_green_window(self):
        arrivals = {AT: 10, AT + timedelta(minutes=1): 20}
        probes = {at: [{'collector_ok': True}] * 6 for at in arrivals}
        counters = {'eligible': {AT: 8, AT + timedelta(minutes=1): 22},
                    'success_good': {AT: 8, AT + timedelta(minutes=1): 22},
                    'responsive_good': {AT: 8, AT + timedelta(minutes=1): 22}}
        _document, verdict = assemble(arrivals, probes, counters, POLICY)
        self.assertEqual(verdict['run_segment']['status'], 'matched-total-only')
        self.assertEqual(verdict['coverage'], 'unverified')


if __name__ == '__main__':
    unittest.main()
