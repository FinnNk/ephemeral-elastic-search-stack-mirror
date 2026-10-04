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
        self.write('observations.json', {'kind': 'search-variant-observation-set', 'schema_version': 1,
                   'default_variant': 'ranker-a', 'baseline_variant': 'ranker-b',
                   'variants': {
                       'ranker-a': {'environment_fingerprint': 'c' * 64,
                                    'image': 'nexus.localhost:18185/search-api@sha256:' + '1' * 64,
                                    'configuration_sha256': 'e' * 64},
                       'ranker-b': {'environment_fingerprint': 'd' * 64,
                                    'image': 'nexus.localhost:18185/search-api@sha256:' + '2' * 64,
                                    'configuration_sha256': 'f' * 64}},
                   'catalogue_sha256': catalogue_sha, 'query_suite_sha256': query_sha,
                   'request_adapter': 'search-api-variant-v1', 'captured_depth': 10, 'errors': [],
                   'observations': [{'query_id': 'q1', 'request': {'query': 'lamp',
                       'country': 'GB', 'currency': 'GBP', 'filters': {}},
                       'results': {
                           'ranker-a': {'variant_id': 'ranker-a',
                                        'configuration_sha256': 'e' * 64,
                                        'ids': ['p1'], 'total': 1},
                           'ranker-b': {'variant_id': 'ranker-b',
                                        'configuration_sha256': 'f' * 64,
                                        'ids': ['p1'], 'total': 1}}}]})
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

    def test_default_may_differ_from_baseline(self):
        report = self.evaluate()
        self.assertTrue(report['complete'])
        self.assertEqual(report['default_variant'], 'ranker-a')
        self.assertEqual(report['baseline_variant'], 'ranker-b')
        self.assertEqual(report['delta_from_baseline']['ranker-a']['nDCG@10'], 0)

    def test_missing_or_wrong_variant_echo_is_invalid(self):
        value = json.loads((self.root / 'observations.json').read_bytes())
        value['observations'][0]['results']['ranker-a']['variant_id'] = 'ranker-b'
        self.write('observations.json', value)
        with self.assertRaisesRegex(ValueError, 'result list is invalid'):
            self.evaluate()

    def test_three_variants_share_one_judgement_set(self):
        value = json.loads((self.root / 'observations.json').read_bytes())
        value['variants']['ranker-c'] = {'environment_fingerprint': '1' * 64,
                                         'image': 'nexus.localhost:18185/search-api@sha256:' + '3' * 64,
                                         'configuration_sha256': '2' * 64}
        value['observations'][0]['results']['ranker-c'] = {
            'variant_id': 'ranker-c', 'configuration_sha256': '2' * 64,
            'ids': ['p1'], 'total': 1}
        self.write('observations.json', value)
        report = self.evaluate()
        self.assertEqual(set(report['metrics']), {'ranker-a', 'ranker-b', 'ranker-c'})
        self.assertEqual(report['coverage']['ranker-c']['judged'], 1)

    def test_pair_shaped_input_is_rejected_without_adapter(self):
        value = json.loads((self.root / 'observations.json').read_bytes())
        value['kind'] = 'search-observation-set'
        self.write('observations.json', value)
        with self.assertRaisesRegex(ValueError, 'Unsupported observation contract'):
            self.evaluate()

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

    def test_demo_sources_remain_distinct_and_only_observed_queries_are_counted(self):
        model = {'kind': 'model', 'source_id': 'demo-pass',
                 'model': {'name': 'judge', 'version': '4', 'artifact_sha256': 'c' * 64},
                 'pass_id': 'demo', 'policy_sha256': 'd' * 64,
                 'qualification': 'lab-demo-authorised'}
        published = {'kind': 'published', 'source_id': 'esci'}
        rows = [
            {'query_id': 'q1', 'product_id': 'p1', 'grade': 3,
             'provenance': published, 'gate_eligible': True},
            {'query_id': 'q1', 'product_id': 'p2', 'grade': 0,
             'provenance': model, 'gate_eligible': False},
            {'query_id': 'q1', 'product_id': 'p3', 'grade': 2,
             'provenance': model, 'gate_eligible': False},
            {'query_id': 'q-unused', 'product_id': 'p4', 'grade': 1,
             'provenance': model, 'gate_eligible': False}]
        payload = b''.join(canonical(row) for row in rows)
        (self.root / 'judgements.jsonl').write_bytes(payload)
        manifest = json.loads((self.root / 'judgement-manifest.json').read_bytes())
        manifest.update(record_count=4, producer={'selection': 'demo', 'rubric': 'esci-v1'})
        manifest['content']['sha256'] = sha(payload)
        self.write('judgement-manifest.json', manifest)
        report = self.evaluate()
        self.assertEqual(report['judgement_selection'], 'demo')
        self.assertEqual(report['judgement_rubric'], 'esci-v1')
        self.assertEqual(report['unqualified_judgements'], 2)
        by_kind = {source['provenance']['kind']: source for source in report['judgement_sources']}
        self.assertEqual(by_kind['published'], {
            'provenance': published, 'gate_eligible': True, 'count': 1})
        self.assertEqual(by_kind['model'], {
            'provenance': model, 'gate_eligible': False, 'count': 2})

    def test_selected_eligibility_cannot_be_truthy_text(self):
        row = {'query_id': 'q1', 'product_id': 'p1', 'grade': 3,
               'gate_eligible': 'false'}
        self.write('judgements.jsonl', row)
        manifest = json.loads((self.root / 'judgement-manifest.json').read_bytes())
        manifest['content']['sha256'] = sha((self.root / 'judgements.jsonl').read_bytes())
        self.write('judgement-manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'provenance or eligibility'):
            self.evaluate()


if __name__ == '__main__':
    unittest.main()
