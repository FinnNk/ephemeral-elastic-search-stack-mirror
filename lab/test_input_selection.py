"""Selected input hashes bind comparisons to one catalogue and query suite."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from contracts import canonical, envelope
from generate_example import build
import input_selection


class FakeBlobs:
    def __init__(self, objects):
        self.objects = objects

    def get_blob_client(self, _container, name):
        payload = self.objects[name]

        class Download:
            def readall(self):
                return payload

        class Blob:
            def download_blob(self):
                return Download()

        return Blob()


class InputSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        source = Path(self.temporary.name)
        build(source)
        products = source / 'products.jsonl'
        queries = source / 'queries.jsonl'
        judgements = source / 'judgements.jsonl'
        catalogue = envelope('catalogue', products, 'test-producer', record_count=12,
                             provenance={'source_release': 'test-pack'})
        suite = envelope('query-suite', queries, 'test-producer', record_count=3,
                         provenance={'source_release': 'test-pack'})
        labels = envelope('judgement-set', judgements, 'test-producer',
                          dependencies={'catalogue': catalogue['content']['sha256'],
                                        'query-suite': suite['content']['sha256']},
                          record_count=12, provenance={'source_release': 'test-pack'})
        self.objects = {}
        self.defaults = {}
        for kind, manifest, content in (('catalogue', catalogue, products),
                                        ('query-suite', suite, queries),
                                        ('judgement-set', labels, judgements)):
            payload = canonical(manifest)
            digest = hashlib.sha256(payload).hexdigest()
            self.defaults[kind] = digest
            self.objects[f'manifests/{kind}/{digest}.json'] = payload
            self.objects[manifest['content']['object']] = content.read_bytes()
        self.product_sha = catalogue['content']['sha256']

    def select(self, **kwargs):
        with patch.object(input_selection, 'DEFAULTS', {'test-pack': self.defaults}), \
             patch.object(input_selection, 'settings', return_value=('', 'datasets', '', True)):
            return input_selection.select('test-pack', self.product_sha,
                                          account=FakeBlobs(self.objects), **kwargs)

    def test_relevance_selection_pins_independent_inputs(self):
        selected = self.select(relevance=True)
        self.assertEqual(len(selected['queries']), 3)
        self.assertEqual(len(selected['judgements']), 12)
        self.assertEqual(selected['query_manifest_sha256'], self.defaults['query-suite'])

    def test_rejects_mismatched_catalogue_and_judgement_dependencies(self):
        with self.assertRaisesRegex(ValueError, 'differs'):
            with patch.object(input_selection, 'DEFAULTS', {'test-pack': self.defaults}), \
                 patch.object(input_selection, 'settings', return_value=('', 'datasets', '', True)):
                input_selection.select('test-pack', 'f' * 64, account=FakeBlobs(self.objects))
        changed = Path(self.temporary.name) / 'changed-queries.jsonl'
        original = json.loads((Path(self.temporary.name) / 'queries.jsonl').read_text().splitlines()[0])
        original['query'] = 'revised synthetic request'
        remaining = (Path(self.temporary.name) / 'queries.jsonl').read_text().splitlines()[1:]
        changed.write_bytes(canonical(original) + b'\n'.join(line.encode() for line in remaining) + b'\n')
        revised = envelope('query-suite', changed, 'test-producer', record_count=3,
                           provenance={'source_release': 'test-pack'})
        payload = canonical(revised)
        digest = hashlib.sha256(payload).hexdigest()
        self.objects[f'manifests/query-suite/{digest}.json'] = payload
        self.objects[revised['content']['object']] = changed.read_bytes()
        with self.assertRaisesRegex(ValueError, 'another catalogue or query suite'):
            self.select(query_manifest_sha=digest, relevance=True)

    def test_rejects_tampered_query_bytes(self):
        query_name = next(name for name in self.objects if name.startswith('query-suite/'))
        self.objects[query_name] += b'{}\n'
        with self.assertRaisesRegex(ValueError, 'Selected input bytes differ'):
            self.select()


if __name__ == '__main__':
    unittest.main()
