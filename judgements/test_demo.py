"""Demo decisions remain scoped, source-distinct and excluded from strict gates."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from core import selected
from demo import replay, validate_record
INFERENCE = {'runtime_image': 'example.test/judge@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', 'protocol_sha256': 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', 'input_contract': 'judgement-pair-v1'}

from service import JudgementService


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((Path(__file__).parent / 'policies/esci-lab-demo.json').read_bytes())
        self.row = {'query_id': 'q', 'product_id': 'p', 'outcome': 'abstain', 'label': None,
                    'confidence': .6, 'probabilities': [.1, .6, .2, .1],
                    'gate_eligible': False, 'provenance': {'kind': 'model', 'source_id': 'original',
                    'model': self.policy['model'], 'pass_id': 'original', 'policy_sha256': 'a' * 64}}
        self.saved = {'kind': 'judgement-pass', 'complete': True, 'model': self.policy['model'],
                      'context': self.policy['context'], 'records': [self.row]}

    def test_rescore_selection_and_scope(self):
        row = replay(self.saved, self.policy, 'b' * 64)['records'][0]
        self.assertEqual(row['label'], 'S')
        self.assertFalse(row['gate_eligible'])
        self.assertFalse(selected(row, 'gate'))
        self.assertTrue(selected(row, 'demo'))
        self.assertFalse(selected(self.row, 'demo'))
        for field in ('model', 'context'):
            bad = deepcopy(self.saved)
            bad[field] = {}
            with self.assertRaises(ValueError):
                replay(bad, self.policy, 'b' * 64)
        forged = deepcopy(row)
        forged['provenance']['authorisation']['reviewer'] = 'invented'
        with self.assertRaises(ValueError):
            validate_record(forged, self.policy)
        tampered = {**row, 'label': 'E'}
        with self.assertRaises(ValueError):
            validate_record(tampered, self.policy)

    def test_boundary_and_abstention(self):
        saved = deepcopy(self.saved)
        saved['records'][0]['probabilities'] = [.75, .1, .1, .05]
        self.assertEqual(replay(saved, self.policy, 'b' * 64)['records'][0]['label'], 'E')
        saved['records'][0]['probabilities'] = [.749, .101, .1, .05]
        self.assertEqual(replay(saved, self.policy, 'b' * 64)['records'][0]['outcome'], 'abstain')
        saved['records'] *= 2
        with self.assertRaises(ValueError):
            replay(saved, self.policy, 'b' * 64)

    def test_import_precedence_and_restart(self):
        demo = replay(self.saved, self.policy, 'b' * 64)['records'][0]
        query = {'query_id': 'q', 'query': 'lamp', 'country': 'GB', 'currency': 'GBP'}
        product = {'product_id': 'p', 'title': 'lamp', 'country': 'GB', 'currency': 'GBP'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.sqlite3'
            def create(source):
                return JudgementService(path, source, [query], [product], self.policy['context'],
                    self.policy['model'], lambda pairs: [{'outcome': 'abstain'} for _ in pairs],
                    demo_policy=self.policy, inference_identity=INFERENCE)
            api = create([])
            payload = {'kind': 'judgement-pass', 'context': self.policy['context'], 'records': [demo]}
            api.import_pass(payload)
            self.assertIsNone(api.lookup('q', 'p', 'gate'))
            self.assertEqual(api.lookup('q', 'p', 'demo')['label'], 'S')
            api.database.close()
            api = create([])
            self.assertEqual(api.lookup('q', 'p', 'demo')['label'], 'S')
            api.database.close()
            # Recreate disposable API with an authoritative published label.
            path.unlink()
            api = create([{'query_id': 'q', 'product_id': 'p', 'grade': 3}])
            api.import_pass(payload)
            self.assertEqual(api.lookup('q', 'p', 'demo')['source'], 'published')
            bad = deepcopy(payload)
            bad['records'][0]['probabilities'] = [.1, .1, .7, .1]
            with self.assertRaises(ValueError):
                api.import_pass(bad)
            api.database.close()


if __name__ == '__main__':
    unittest.main()
