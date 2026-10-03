"""An expanded recall set creates a new snapshot and preserves the old one."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from contracts import envelope
from core import canonical
from prepare import prepare


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalogue = self.root / 'products.jsonl'
        self.catalogue.write_bytes(b''.join(canonical({
            'product_id': pid, 'title': pid, 'country': 'GB', 'currency': 'GBP'})
            for pid in ('p1', 'p2', 'p3')))
        self.catalogue_manifest = envelope('catalogue', self.catalogue, 'fixture',
                                            record_count=3,
                                            provenance={'source_release': 'fixture'})
        self.queries = self.root / 'queries.jsonl'
        self.queries.write_bytes(canonical({'query_id': 'q1', 'query': 'lamp',
                                            'country': 'GB', 'currency': 'GBP'}))
        self.query_manifest = envelope('query-suite', self.queries, 'fixture',
                                        record_count=1,
                                        provenance={'source_release': 'fixture'})
        self.source = self.root / 'source.jsonl'
        self.source.write_bytes(canonical({'query_id': 'q1', 'product_id': 'p1',
                                           'grade': 3}))
        self.dependencies = {'catalogue': self.catalogue_manifest['content']['sha256'],
                             'query-suite': self.query_manifest['content']['sha256']}
        self.source_manifest = envelope('judgement-set', self.source, 'fixture',
                                         self.dependencies, 1,
                                         {'source_release': 'fixture'})
        self.specification = self.root / 'spec.json'
        self.specification.write_bytes(canonical({'metrics': ['nDCG@2']}))
        self.cm = self.write('catalogue-manifest.json', self.catalogue_manifest)
        self.qm = self.write('query-manifest.json', self.query_manifest)
        self.sm = self.write('source-manifest.json', self.source_manifest)
        self.model = {'name': 'synthetic-esci-judge', 'version': '1',
                      'artifact_sha256': 'c' * 64}

    def write(self, name, value):
        path = self.root / name
        path.write_bytes(canonical(value))
        return path

    def run_case(self, candidate, output, infer):
        observations = self.write('observations-' + candidate + '.json', {
            'captured_depth': 10, 'catalogue_sha256': self.dependencies['catalogue'],
            'query_suite_sha256': self.dependencies['query-suite'],
            'variants': {'ranker-a': {}, 'ranker-b': {}},
            'observations': [{'query_id': 'q1',
              'request': {'query': 'lamp', 'country': 'GB', 'currency': 'GBP',
                          'filters': {}},
              'results': {'ranker-a': {'ids': ['p1', 'p2']},
                          'ranker-b': {'ids': ['p1', candidate]}}}]})
        return prepare(observations, self.specification, self.catalogue, self.cm,
                       self.qm, self.source, self.sm, self.root / output,
                       infer, self.model)

    def test_abstention_then_new_recall_label(self):
        first = self.run_case('p2', 'snapshot-one',
                              lambda items: [{'outcome': 'abstain'} for _ in items])
        first_bytes = (self.root / 'snapshot-one/judgements.jsonl').read_bytes()
        second = self.run_case('p3', 'snapshot-two',
                               lambda items: [{'outcome': 'labelled', 'label': 'S', 'gate_eligible': True,
                     'provenance': {'kind': 'model', 'source_id': 'fixture'}}
                                              for _ in items])
        self.assertNotEqual(first['judgements'], second['judgements'])
        self.assertEqual((self.root / 'snapshot-one/judgements.jsonl').read_bytes(),
                         first_bytes)
        self.assertEqual(first['coverage']['pool']['abstained'], 1)
        self.assertEqual(second['coverage']['pool']['newly_labelled'], 2)
        self.assertEqual(second['input_shift']['feature'], 'query_length')
        self.assertEqual(second['input_shift']['observed_count'], 2)
        self.assertEqual(json.loads((self.root / 'snapshot-two/judgement-set.json').read_bytes())
                         ['dependencies'], self.dependencies)

    def test_resolution_retains_published_source_provenance(self):
        producer = self.source_manifest['producer']
        producer.update(synthetic=False, sources=[{'repository': 'published-fixture', 'sha256': 'a' * 64}])
        self.write('source-manifest.json', self.source_manifest)
        self.run_case('p2', 'published-snapshot', lambda items: [{'outcome': 'abstain'} for _ in items])
        derived = json.loads((self.root / 'published-snapshot/judgement-set.json').read_bytes())['producer']
        self.assertFalse(derived['synthetic'])
        self.assertEqual(derived['sources'], producer['sources'])
        self.assertEqual(derived['name'], 'pooled-judgement-resolution')


if __name__ == '__main__':
    unittest.main()
