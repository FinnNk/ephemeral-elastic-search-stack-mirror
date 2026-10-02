"""Importer checks use small source-shaped fixtures; they are not source data."""
import json
from pathlib import Path
import tempfile
import unittest

from contracts import input_files, rows, validate_records, validate_envelope
from import_esci import import_records, price_minor
from publish import publish


class ImportTests(unittest.TestCase):
    def run_import(self, path, limit=3, queries=1):
        originals = [{'product_id': x, 'product_locale': 'us', 'product_title': 'Original ' + x,
                      'product_description': None, 'product_bullet_point': 'Original bullets',
                      'product_brand': 'Original brand', 'product_color': 'Gray'} for x in ('A', 'B', 'C')]
        examples = [{'product_locale': 'us', 'large_version': 1, 'split': 'test', 'query_id': 1,
                     'query': ' gray  shirt ', 'product_id': x, 'esci_label': label}
                    for x, label in [('A', 'E'), ('B', 'S')]]
        # Excluded training and other-market records must not contaminate the suite.
        examples += [{**examples[0], 'split': 'train', 'query_id': 2},
                     {**examples[0], 'product_locale': 'jp', 'query_id': 3}]
        extended = [{'asin': 'A', 'title': 'Later changed title', 'price': '$19.99',
                     'category': ['Clothing', 'Shirts'], 'attrs': {'Material': 'Cotton'},
                     'stars': '4.3 out of 5 stars', 'ratings': '1,116 ratings'}]
        return import_records(iter(originals), iter(examples), iter(extended), path,
                              'fixture', queries, limit, {'licence': 'fixture'})

    def test_numeric_prices_ranges_and_missing(self):
        self.assertEqual(price_minor('$19.99'), 1999)
        self.assertEqual(price_minor('$1,234.50 - $2,000.00'), 123450)
        for value in ('', 'unavailable', '£19.99', '$19.999', None):
            self.assertIsNone(price_minor(value))

    def test_source_text_labels_and_provenance_survive(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)/'release'
            manifest = self.run_import(directory)
            products = list(rows(directory/'products.jsonl.gz'))
            self.assertEqual(products[0]['title'], 'Original A')
            self.assertEqual(products[0]['price_minor'], 1999)
            self.assertEqual(products[0]['currency'], 'GBP')
            self.assertEqual(products[0]['colour'], 'Gray')
            self.assertEqual(products[0]['review_count'], 1116)
            self.assertEqual(products[1]['attrs']['price_source'], 'synthetic')
            self.assertEqual(validate_records(input_files(directory)),
                             {'catalogue': 3, 'query-suite': 1, 'judgement-set': 2})
            labels=list(rows(directory/'judgements.jsonl'))
            self.assertEqual([x['grade'] for x in labels], [3,2])
            publish(directory, Path(temporary)/'artifacts', 'esci-import', 'fixture', provenance=manifest['producer'])
            frozen=validate_envelope(json.loads((Path(temporary)/'artifacts/catalogue.json').read_text()))
            self.assertFalse(frozen['producer']['synthetic'])
            self.assertEqual(frozen['producer']['sources'], {'licence':'fixture'})

    def test_demo_cannot_drop_judged_products(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError,'cannot hold'):
                self.run_import(Path(temporary)/'release',limit=1)

    def test_import_is_reproducible_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            a=self.run_import(Path(temporary)/'a')
            b=self.run_import(Path(temporary)/'b')
            self.assertEqual(a,b)
            with self.assertRaisesRegex(ValueError,'cannot be overwritten'):
                self.run_import(Path(temporary)/'a')


if __name__ == '__main__':
    unittest.main()
