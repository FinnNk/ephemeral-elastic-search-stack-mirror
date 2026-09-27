import gzip
import json
import tempfile
import unittest
from pathlib import Path

from release_million import build, category_ranges, product_at, query_plans, sha_file


class MillionReleaseContract(unittest.TestCase):
    def test_distribution_queries_and_independent_products(self):
        ranges = category_ranges(10_000)
        self.assertEqual(sum(row['count'] for row in ranges), 10_000)
        self.assertEqual(len(ranges), 15)
        self.assertEqual(product_at(ranges[0], 7), product_at(ranges[0], 7))
        queries = query_plans(ranges)
        self.assertEqual(len(queries), 1000)
        self.assertEqual(len({row['query'] for row in queries}), 1000)
        self.assertEqual(sum(row['kind'] == 'zero' for row in queries), 20)

    def test_fixture_is_frozen_and_assessments_reference_products(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = build(root, count=10_000, release='fixture-gb-10k')
            self.assertEqual(build(root, count=10_000, release='fixture-gb-10k'), manifest)
            self.assertEqual(manifest['judgement_count'], 20_000)
            self.assertEqual(manifest['query_count'], 1000)
            with gzip.open(root / 'products.jsonl.gz', 'rt', encoding='utf-8') as handle:
                products = [json.loads(line) for line in handle]
            self.assertEqual(len(products), 10_000)
            ids = {row['product_id'] for row in products}
            self.assertEqual(len(ids), 10_000)
            assessments = [json.loads(line) for line in
                           (root / 'judgements.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertTrue(all(row['product_id'] in ids for row in assessments))
            self.assertEqual(sum(row['grade'] == 0 for row in assessments), 2_360)
            self.assertEqual(sha_file(root / 'products.jsonl.gz'), manifest['sha256']['products.jsonl.gz'])
            with self.assertRaises(ValueError):
                build(root, count=10_001, release='fixture-gb-10k')


if __name__ == '__main__':
    unittest.main()
