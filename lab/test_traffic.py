import csv
import json
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path

from traffic import ROOT, compile_profile, generate_trace, generate_million_trace, generate_million_trace_extended
import traffic


class FrozenTrafficContract(unittest.TestCase):
    def test_feeders_bind_market_and_filters_to_frozen_queries(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / 'trace.csv'
            queries = root / 'queries.jsonl'
            recipes = root / 'recipes.json'
            trace.write_bytes(b'timestamp,query_id,query\n2026-01-01T00:00:00Z,q1,shirt\n')
            filters = {'category': ['clothing'], 'price_minor': {'lte': 2500}}
            queries.write_text(json.dumps({'query_id': 'q1', 'query': 'shirt',
                'country': 'GB', 'currency': 'GBP', 'filters': filters}) + '\n', encoding='utf-8')
            recipes.write_text(json.dumps({'profiles': {'probe': [{'name': 'probe',
                'seconds': 1, 'source_start': 0, 'rate': 2}]}}), encoding='utf-8')
            (root / 'source-manifest-v1.json').write_text(json.dumps({
                'trace_sha256': traffic.sha(trace.read_bytes()),
                'query_sha256': traffic.sha(queries.read_bytes())}), encoding='utf-8')
            with patch('traffic.generate_catalogue_trace', return_value=(trace,root/'source-manifest-v1.json',queries)), \
                 patch.multiple(traffic, MILLION_RECIPES_EXT=recipes, OUTPUT=root/'workloads'):
                compiled = compile_profile('probe')
                with (Path(compiled['directory']) / 'probe.csv').open(encoding='utf-8', newline='') as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]['country'], 'GB')
                self.assertEqual(rows[0]['currency'], 'GBP')
                self.assertEqual(json.loads(rows[0]['filters']), filters)
                self.assertEqual(compiled, compile_profile('probe'))

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

    def test_million_query_trace_has_separate_frozen_identity(self):
        self.assertEqual(generate_million_trace()['events'], 4399)
        manifest = generate_million_trace_extended()
        self.assertEqual(manifest['events'], 13099)
        million = compile_profile('smoke', 'esci-gb-demo-v1')
        original = compile_profile('smoke')
        self.assertEqual(million['phase_counts']['normal'], 3000)
        self.assertNotEqual(million['source_sha256'], original['source_sha256'])
        self.assertNotEqual(million['workload_sha256'], original['workload_sha256'])
        normal = compile_profile('normal-full', 'esci-gb-v1')
        self.assertEqual(normal['duration_seconds'], 360)
        self.assertGreater(normal['phase_counts']['normal'], 2_000)
        self.assertEqual(compile_profile('sustained-peak', 'esci-gb-v1')['phase_counts']['peak'], 18_000)
        self.assertEqual(compile_profile('stress-full', 'esci-gb-v1')['phase_counts']['recovery'], 3_000)


if __name__ == '__main__':
    unittest.main()
