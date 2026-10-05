import json
import unittest

from query_sets import assemble, canonical, freeze, score_extra
import test_offline


class QuerySetTests(unittest.TestCase):
    def test_real_scoring_keeps_report_only_labels_unknown(self):
        fixture = test_offline.OfflineContractTests()
        fixture.setUp()
        try:
            item = freeze(self.selection(), lambda path: self.payload())[0]
            observations = json.loads((fixture.root / 'observations.json').read_bytes())
            observations['query_suite_sha256'] = item['query_sha256']
            observations['execution'] = {'seconds': 2.5, 'worker_count': 8}
            result = score_extra(item, observations,
                (fixture.root / 'specification.json').read_bytes(),
                (fixture.root / 'catalogue.json').read_bytes())
            self.assertEqual(result['execution'], observations['execution'])
            self.assertFalse(result['relevance_available'])
            self.assertIsNone(result['metrics'])
            self.assertEqual(result['result_similarity']['ranker-a']['rbo_at_10_p_0_9'], 1)
            labels = (fixture.root / 'judgements.jsonl').read_bytes()
            item.update(judgement_bytes=labels, judgement_sha256=test_offline.sha(labels),
                        judgements_rows=[json.loads(labels)])
            result = score_extra(item, observations,
                (fixture.root / 'specification.json').read_bytes(),
                (fixture.root / 'catalogue.json').read_bytes())
            self.assertEqual(result['execution'], observations['execution'])
            self.assertTrue(result['relevance_available'])
            self.assertEqual(result['metrics']['ranker-a']['nDCG@10'], 1)
        finally:
            fixture.doCleanups()
    def selection(self, required=False):
        return {'additional_query_sets': [{'name': 'rewrite', 'path': 'evaluation/queries/test.jsonl',
                                         'required': required}]}

    def payload(self):
        return canonical({'query_id': 'q1', 'query': 'lamp', 'country': 'GB', 'currency': 'GBP'})

    def test_required_set_without_labels_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'judgement file'):
            freeze(self.selection(True), lambda path: self.payload())

    def test_paths_and_duplicate_ids_are_rejected(self):
        selection = self.selection()
        selection['additional_query_sets'][0]['path'] = 'evaluation/../secret.jsonl'
        with self.assertRaisesRegex(ValueError, 'paths'):
            freeze(selection, lambda path: self.payload())
        with self.assertRaisesRegex(ValueError, 'distinct IDs'):
            freeze(self.selection(), lambda path: self.payload() * 2)

    def test_original_bytes_are_pinned_and_report_only_is_default(self):
        selection = self.selection()
        del selection['additional_query_sets'][0]['required']
        frozen = freeze(selection, lambda path: self.payload())
        self.assertEqual(frozen[0]['query_bytes'], self.payload())
        self.assertFalse(frozen[0]['required'])

    def test_combined_weighting_discloses_unlabelled_repeat(self):
        selection = self.selection()
        frozen = freeze(selection, lambda path: self.payload())
        metrics = {'a': {'nDCG@10': 0.8}, 'b': {'nDCG@10': 0.7}}
        similarity = {v: {'rbo_at_10_p_0_9': 1, 'jaccard_at_10': 1} for v in metrics}
        standard = {'query_count': 1, 'variants': {'a': {}, 'b': {}},
                    'complete': True, 'metrics': metrics, 'result_similarity': similarity,
                    'query_suite_sha256': 'a' * 64}
        extra = {**standard, 'relevance_available': False, 'metrics': None,
                 'result_similarity': {v: {'rbo_at_10_p_0_9': 0, 'jaccard_at_10': 0} for v in metrics}}
        result = assemble(standard, {'rewrite': extra}, frozen,
                          [json.loads(self.payload())], selection)
        self.assertEqual(result['combined']['repeated_request_count'], 1)
        self.assertEqual(result['combined']['unlabelled_query_count'], 1)
        self.assertEqual(result['combined']['result_similarity']['a']['rbo_at_10_p_0_9'], 0.5)
        self.assertEqual(result['metrics'], metrics)


if __name__ == '__main__':
    unittest.main()
