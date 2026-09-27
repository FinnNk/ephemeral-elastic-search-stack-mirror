"""Reject mismatched or insufficient retained observations before scoring."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline import canonical, evaluate, sha


class OfflineContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        catalogue_sha = 'a' * 64
        query_sha = 'b' * 64
        self.write('catalogue.json', {'kind': 'catalogue', 'content': {'sha256': catalogue_sha}})
        self.write('queries.json', {'kind': 'query-suite', 'content': {'sha256': query_sha}})
        self.write('observations.json', {'kind': 'search-observation-set', 'schema_version': 1,
                   'baseline_fingerprint': 'c' * 64, 'candidate_fingerprint': 'd' * 64,
                   'catalogue_sha256': catalogue_sha, 'query_suite_sha256': query_sha,
                   'request_adapter': 'search-api-v1', 'captured_depth': 10, 'errors': [],
                   'observations': [{'query_id': 'q1', 'request': {'query': 'lamp',
                       'country': 'GB', 'currency': 'GBP', 'filters': {}},
                       'baseline': {'ids': ['p1'], 'total': 1},
                       'candidate': {'ids': ['p1'], 'total': 1}}]})
        self.write('judgements.jsonl', {'query_id': 'q1', 'product_id': 'p1', 'grade': 3})
        self.write('judgement-manifest.json', {'kind': 'judgement-set', 'schema_version': 1,
                   'content': {'sha256': sha((self.root / 'judgements.jsonl').read_bytes())},
                   'dependencies': {'catalogue': catalogue_sha, 'query-suite': query_sha},
                   'record_count': 1})
        self.write('specification.json', {'kind': 'evaluation-specification', 'schema_version': 1,
                   'metrics': ['nDCG@10'], 'aggregation': 'macro',
                   'unjudged_policy': 'unknown; metric library treats missing qrels as zero'})

    def write(self, name, value):
        (self.root / name).write_bytes(canonical(value))

    def evaluate(self):
        return evaluate(self.root / 'observations.json', self.root / 'judgements.jsonl',
                        self.root / 'specification.json', self.root / 'catalogue.json',
                        self.root / 'queries.json', self.root / 'judgement-manifest.json')

    def test_valid_pair_scores(self):
        self.assertTrue(self.evaluate()['complete'])

    def test_other_catalogue_cannot_be_scored(self):
        self.write('catalogue.json', {'kind': 'catalogue', 'content': {'sha256': 'e' * 64}})
        with self.assertRaisesRegex(ValueError, 'another catalogue'):
            self.evaluate()

    def test_top_ten_metric_rejects_top_five_capture(self):
        value = json.loads((self.root / 'observations.json').read_bytes())
        value['captured_depth'] = 5
        self.write('observations.json', value)
        with self.assertRaisesRegex(ValueError, 'cut-off exceeds'):
            self.evaluate()


if __name__ == '__main__':
    unittest.main()
