"""Reproduce coverage and scoring from packaged, accepted model judgements."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest

from query_sets import freeze, score_extra, canonical, sha


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'lab/delivery/bootstrap'


class AdvisoryJudgements(unittest.TestCase):
    def test_seeded_sets_reproduce_coverage_and_keep_model_provenance(self):
        selection = json.loads((TEMPLATE / 'gate/selection.json').read_text(encoding='utf-8'))
        items = freeze(selection, lambda path: (TEMPLATE / path).read_bytes())
        folder = TEMPLATE / 'evaluation/judgements'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(sha((folder / 'inputs.jsonl.gz').read_bytes()), manifest['inputs_sha256'])
        inputs = [json.loads(line) for line in gzip.decompress((folder / 'inputs.jsonl.gz').read_bytes()).splitlines()]
        indexed = {(i['set'], i['query_id'], i['product']['product_id']): i for i in inputs}
        for item in items:
            with self.subTest(query_set=item['name']):
                pin = manifest['sets'][item['name']]
                self.assertEqual(item['judgement_sha256'], pin['judgement_sha256'])
                capture = (folder / (item['name'] + '-observations.json.gz')).read_bytes()
                self.assertEqual(sha(capture), pin['observations_sha256'])
                observations = json.loads(gzip.decompress(capture))
                for row in item['judgements_rows']:
                    self.assertEqual(row['provenance']['input_sha256'], sha(canonical(indexed[item['name'], row['query_id'], row['product_id']])))
                    self.assertFalse(row['gate_eligible'])
                    self.assertEqual(row['provenance']['model'], 'gpt-6-luna')
                report = score_extra({**item, 'judgement_selection': 'exploratory'}, observations,
                    (ROOT / 'evaluation/specs/proxy-v2.json').read_bytes(),
                    canonical({'content': {'sha256': observations['catalogue_sha256']}}))
                self.assertTrue(report['relevance_available'])
                self.assertEqual(report['coverage'], pin['coverage'])
                self.assertEqual({c['fraction'] for c in report['coverage'].values()}, {.9})
                self.assertGreater(report['unqualified_judgements'], 0)
                # Accepted model judgements cannot silently become required gate labels.
                changed = deepcopy(selection)
                next(i for i in changed['additional_query_sets'] if i['name'] == item['name'])['required'] = True
                with self.assertRaisesRegex(ValueError, 'advisory only'):
                    freeze(changed, lambda path: (TEMPLATE / path).read_bytes())
                other = {**observations, 'catalogue_sha256': '0' * 64}
                with self.assertRaisesRegex(ValueError, 'another frozen catalogue'):
                    score_extra(item, other, b'', b'')

    def test_unaccepted_model_labels_are_rejected(self):
        selection = json.loads((TEMPLATE / 'gate/selection.json').read_text(encoding='utf-8'))
        def read(path):
            payload = (TEMPLATE / path).read_bytes()
            if path.endswith('judgements/sneakers.jsonl'):
                rows = [json.loads(line) for line in payload.splitlines()]
                rows[0]['provenance'].pop('acceptance')
                return b''.join(canonical(row) for row in rows)
            return payload
        with self.assertRaisesRegex(ValueError, 'explicit acceptance'):
            freeze(selection, read)
