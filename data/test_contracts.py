"""Focused integrity checks for producer-owned input contracts."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contracts import release_files, validate_records
from generate_example import build


class InputContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.release = Path(self.temporary.name) / 'release'
        build(self.release)

    def test_independent_example_has_valid_references(self):
        _, files = release_files(self.release)
        self.assertEqual(validate_records(files),
                         {'catalogue': 12, 'query-suite': 3, 'judgement-set': 12})

    def test_country_cannot_switch_currency_within_catalogue(self):
        _, files = release_files(self.release)
        altered = self.release / 'altered-products.jsonl'
        records = [json.loads(line) for line in files['catalogue'].read_text().splitlines()]
        records[1]['currency'] = 'EUR'
        altered.write_text(''.join(json.dumps(row) + '\n' for row in records))
        files['catalogue'] = altered
        with self.assertRaisesRegex(ValueError, 'more than one currency'):
            validate_records(files)

    def test_judgement_cannot_reference_unknown_product(self):
        _, files = release_files(self.release)
        altered = self.release / 'altered-judgements.jsonl'
        records = [json.loads(line) for line in files['judgement-set'].read_text().splitlines()]
        records[0]['product_id'] = 'missing'
        altered.write_text(''.join(json.dumps(row) + '\n' for row in records))
        files['judgement-set'] = altered
        with self.assertRaisesRegex(ValueError, 'unknown product'):
            validate_records(files)


if __name__ == '__main__':
    unittest.main()
