"""Focused integrity checks for producer-owned input contracts."""

import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contracts import input_files, validate_envelope, validate_records
from generate_example import build
from publish import publish, upload
from azure.core.exceptions import ResourceExistsError


class InputContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.release = Path(self.temporary.name) / 'release'
        build(self.release)

    def test_independent_example_has_valid_references(self):
        files = input_files(self.release)
        self.assertFalse((self.release / 'manifest.json').exists())
        self.assertEqual(validate_records(files),
                         {'catalogue': 12, 'query-suite': 3, 'judgement-set': 12})

    def test_publication_uses_independent_inputs(self):
        output = Path(self.temporary.name) / 'artifacts'
        first = publish(self.release, output, 'example-producer', 'example-source')
        self.assertEqual(first, publish(self.release, output, 'example-producer',
                                        'example-source'))
        catalogue = validate_envelope(json.loads((output / 'catalogue.json').read_text()))
        judgement = validate_envelope(json.loads((output / 'judgement-set.json').read_text()))
        self.assertEqual(catalogue['producer']['source_release'], 'example-source')
        self.assertEqual(judgement['dependencies']['catalogue'],
                         catalogue['content']['sha256'])
        with self.assertRaisesRegex(ValueError, 'Existing artifact manifest differs'):
            publish(self.release, output, 'another-producer', 'example-source')

    def test_existing_content_address_without_metadata_is_verified(self):
        class ExistingBlob:
            def __init__(self, payload):
                self.payload = payload

            def upload_blob(self, *_args, **_kwargs):
                raise ResourceExistsError('Already exists')

            def get_blob_properties(self):
                return type('Properties', (), {'size': len(self.payload), 'metadata': {}})()

            def download_blob(self):
                return type('Download', (), {'chunks': lambda _self: iter([self.payload])})()

        class Client:
            def __init__(self, blob):
                self.blob = blob

            def get_blob_client(self, _container, _name):
                return self.blob

        payload = b'original synthetic input\n'
        digest = hashlib.sha256(payload).hexdigest()
        upload(Client(ExistingBlob(payload)), 'datasets', 'catalogue/' + digest,
               payload, digest, len(payload))
        with self.assertRaisesRegex(ValueError, 'different content hash'):
            upload(Client(ExistingBlob(b'forged!! synthetic input\n')), 'datasets',
                   'catalogue/' + digest, payload, digest, len(payload))

    def test_country_cannot_switch_currency_within_catalogue(self):
        files = input_files(self.release)
        altered = self.release / 'altered-products.jsonl'
        records = [json.loads(line) for line in files['catalogue'].read_text().splitlines()]
        records[1]['currency'] = 'EUR'
        altered.write_text(''.join(json.dumps(row) + '\n' for row in records))
        files['catalogue'] = altered
        with self.assertRaisesRegex(ValueError, 'more than one currency'):
            validate_records(files)

    def test_judgement_cannot_reference_unknown_product(self):
        files = input_files(self.release)
        altered = self.release / 'altered-judgements.jsonl'
        records = [json.loads(line) for line in files['judgement-set'].read_text().splitlines()]
        records[0]['product_id'] = 'missing'
        altered.write_text(''.join(json.dumps(row) + '\n' for row in records))
        files['judgement-set'] = altered
        with self.assertRaisesRegex(ValueError, 'unknown product'):
            validate_records(files)


if __name__ == '__main__':
    unittest.main()
