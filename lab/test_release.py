import json
import tempfile
import unittest
from pathlib import Path

import release


class ReleaseContract(unittest.TestCase):
    def test_deterministic_catalogue_and_frozen_files(self):
        with tempfile.TemporaryDirectory() as directory:
            first = release.build(directory)
            second = release.build(directory)
            self.assertEqual(first, second)
            for name, digest in first['sha256'].items():
                self.assertEqual(release.sha256((Path(directory) / name).read_bytes()), digest)
            self.assertEqual(first['count'], 10_000)
            self.assertEqual(first['query_count'], 50)

    def test_market_and_judgement_references(self):
        catalogue = release.products()
        by_id = {product['product_id']: product for product in catalogue}
        queries, judgements = release.queries_and_judgements(catalogue)
        self.assertEqual(len(by_id), 10_000)
        self.assertEqual(len({p['sku'] for p in catalogue}), 10_000)
        self.assertEqual({(p['country'], p['currency']) for p in catalogue}, {('GB', 'GBP')})
        self.assertEqual({q['query_id'] for q in queries}, {j['query_id'] for j in judgements})
        self.assertTrue(all(j['product_id'] in by_id and by_id[j['product_id']]['available'] for j in judgements))
        self.assertTrue(all(1 <= j['grade'] <= 3 for j in judgements))


if __name__ == '__main__':
    unittest.main()
