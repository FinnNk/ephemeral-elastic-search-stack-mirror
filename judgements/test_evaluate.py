"""Pooled resolution feeds the existing black-box offline evaluator."""

import json
from pathlib import Path
import unittest

from core import canonical
from evaluate import run
import test_prepare


class EvaluationIntegrationTests(unittest.TestCase):
    def test_both_versions_use_one_snapshot_and_abstentions_remain_unknown(self):
        fixture = test_prepare.PrepareTests('test_abstention_then_new_recall_label')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.specification.write_bytes(canonical({
            'kind': 'evaluation-specification', 'schema_version': 1,
            'metrics': ['nDCG@10', 'Judged@10'], 'aggregation': 'macro',
            'unjudged_policy': 'unknown; metric library treats missing qrels as zero'}))
        observation = fixture.write('complete-observations.json', {
            'kind': 'search-observation-set', 'schema_version': 1,
            'captured_depth': 10, 'request_adapter': 'search-api-v1', 'errors': [],
            'baseline_fingerprint': 'baseline', 'candidate_fingerprint': 'candidate',
            'catalogue_sha256': fixture.dependencies['catalogue'],
            'query_suite_sha256': fixture.dependencies['query-suite'],
            'observations': [{'query_id': 'q1',
                'request': {'query': 'lamp', 'country': 'GB', 'currency': 'GBP',
                            'filters': {}},
                'baseline': {'ids': ['p1', 'p2'], 'total': 2},
                'candidate': {'ids': ['p1', 'p3'], 'total': 2}}]})
        output = fixture.root / 'scored'
        report = run(observation, fixture.specification, fixture.catalogue,
                     fixture.cm, fixture.qm, fixture.source, fixture.sm, output,
                     lambda pairs: [{'outcome': 'abstain'} for _ in pairs],
                     fixture.model)
        self.assertEqual(report['coverage_at_metric_cutoff']['pool']['abstained'], 2)
        self.assertEqual(report['coverage_returned']['baseline']['judged'], 1)
        self.assertEqual(report['coverage_returned']['candidate']['judged'], 1)
        self.assertEqual(report['judgement_sha256'],
                         json.loads((output / 'evaluation.json').read_bytes())['judgement_sha256'])
        self.assertEqual(run(observation, fixture.specification, fixture.catalogue,
                             fixture.cm, fixture.qm, fixture.source, fixture.sm, output,
                             lambda pairs: [{'outcome': 'abstain'} for _ in pairs],
                             fixture.model), report)
        def unavailable(_):
            raise TimeoutError('predictor is unavailable')
        failed = run(observation, fixture.specification, fixture.catalogue,
                     fixture.cm, fixture.qm, fixture.source, fixture.sm,
                     fixture.root / 'failed', unavailable, fixture.model)
        self.assertEqual(failed['coverage_at_metric_cutoff']['pool']['failed'], 2)
        self.assertFalse(json.loads((fixture.root / 'failed/evaluation.json').read_bytes())
                         ['complete'])


if __name__ == '__main__':
    unittest.main()
