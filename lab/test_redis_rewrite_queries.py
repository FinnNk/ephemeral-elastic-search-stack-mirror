"""Keep focused query coverage aligned with the pinned catalogue's Redis rules."""
import json
import unittest

from common import ROOT
from data_versions import PAIRS, RULES
from query_sets import freeze


class RedisRewriteQueries(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'lab/delivery/bootstrap'
        self.selection = json.loads((self.root / 'examples/redis-rewrites/selection.json').read_text(encoding='utf-8'))
        self.item = next(item for item in self.selection['additional_query_sets'] if item['name'] == 'redis-rewrites')
        self.frozen = freeze({'additional_query_sets': [self.item]}, lambda path: (self.root / path).read_bytes())[0]

    def test_every_pinned_alias_has_lower_and_case_coverage(self):
        rules = PAIRS['esci-gb-v1']['rewrite']['rules']
        self.assertEqual(rules, RULES)
        rows = self.frozen['queries']
        self.assertEqual(len(rows), 18)
        self.assertEqual(len({row['query_id'] for row in rows}), len(rows))
        texts = {row['query'] for row in rows}
        for alias in rules:
            with self.subTest(alias=alias):
                self.assertIn(alias, texts)
                self.assertIn(alias.title(), texts)

    def test_controls_cover_targets_and_an_unmatched_query(self):
        rules = PAIRS['esci-gb-v1']['rewrite']['rules']
        controls = {row['query'] for row in self.frozen['queries'] if row['query_id'].startswith('redis-control-')}
        self.assertTrue({value[0] for value in rules.values()} <= controls)
        self.assertIn('wireless keyboard', controls)
        self.assertFalse(set(rules) & controls)
        self.assertTrue(all(row['country'] == 'GB' and row['currency'] == 'GBP' and row['filters'] == {} for row in self.frozen['queries']))

    def test_example_preserves_existing_selection_and_requires_no_invented_labels(self):
        self.assertEqual(self.selection['selected'], [{'variant': 'ranker-a', 'intent': 'preserve-results'}])
        self.assertEqual([item['name'] for item in self.selection['additional_query_sets']], ['sneakers', 'redis-rewrites'])
        self.assertFalse(self.item['required'])
        self.assertNotIn('judgements', self.item)
        self.assertEqual(self.frozen['judgements_rows'], [])


if __name__ == '__main__':
    unittest.main()
