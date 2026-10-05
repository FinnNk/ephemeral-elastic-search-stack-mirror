"""Verify inference reuse without suppressing errors or changing frozen decisions."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import unittest

from core import canonical, digest
from service import JudgementService
import test_service as fixtures


class ReuseTests(unittest.TestCase):
    setUp = fixtures.ServiceTests.setUp

    def create(self, predict, **changes):
        values = {'database': self.database, 'source_rows': [], 'query_rows': self.query_rows,
            'product_rows': self.product_rows, 'context': self.context, 'model': self.model,
            'predict': predict, 'inference_identity': fixtures.INFERENCE, **changes}
        service = JudgementService(**values)
        self.addCleanup(service.database.close)
        return service

    def test_restart_reuses_labels_and_abstentions(self):
        calls = []
        def predict(pairs):
            calls.extend(pairs)
            return [{'outcome': 'labelled', 'label': 'C'}, {'outcome': 'abstain'}]
        first = self.create(predict)
        answer = first.resolve(self.context, self.pairs, 'exploratory')
        second = self.create(lambda _: self.fail('Cache miss after restart'))
        repeat = second.resolve(self.context, self.pairs, 'exploratory')
        self.assertEqual(repeat['execution']['inferred_pairs'], 0)
        self.assertEqual(repeat['execution']['cache_hits'], 2)
        self.assertEqual(answer['results'], repeat['results'])
        self.assertEqual(len(calls), 2)

    def test_fresh_attempt_does_not_replace_canonical_prediction(self):
        predictions = iter(['C', 'E'])
        api = self.create(lambda pairs: [{'outcome': 'labelled', 'label': next(predictions)}])
        pair = self.pairs[:1]
        self.assertEqual(api.resolve(self.context, pair, 'exploratory')['results'][0]['label'], 'C')
        self.assertEqual(api.resolve(self.context, pair, 'exploratory', True)['results'][0]['label'], 'E')
        self.assertEqual(api.resolve(self.context, pair, 'exploratory')['results'][0]['label'], 'C')
        self.assertEqual(api.database.execute('SELECT count(*) FROM inference_attempts').fetchone()[0], 2)

    def test_threshold_change_reuses_scores(self):
        def policy(threshold):
            acceptance = {'format': 'esci-abstention-v1', 'labels': list('ESCI'), 'thresholds': dict.fromkeys('ESCI', threshold)}
            return {'acceptance': acceptance, 'pass_id': str(threshold),
                'policy_sha256': digest(canonical(acceptance)), 'gate_eligible': False}
        raw = {'outcome': 'abstain', 'probabilities': [.1, .6, .2, .1]}
        first = self.create(lambda pairs: [raw], model_policy=policy(.9))
        self.assertEqual(first.resolve(self.context, self.pairs[:1], 'exploratory')['results'][0]['outcome'], 'unjudged')
        second = self.create(lambda _: self.fail('Threshold change reinferred'), model_policy=policy(.5))
        answer = second.resolve(self.context, self.pairs[:1], 'exploratory')
        self.assertEqual(answer['results'][0]['label'], 'S')
        self.assertFalse(answer['results'][0]['gate_eligible'])
        self.assertEqual(len(second.evidence.records('q1', 'p1')), 2)

    def test_errors_are_retryable_and_not_cached(self):
        outputs = iter([{'outcome': 'error'}, {'outcome': 'abstain'}])
        api = self.create(lambda _: [next(outputs)])
        self.assertEqual(api.resolve(self.context, self.pairs[:1])['results'][0]['outcome'], 'inference_error')
        self.assertEqual(api.resolve(self.context, self.pairs[:1])['execution']['inferred_pairs'], 1)
        self.assertEqual(api.resolve(self.context, self.pairs[:1])['execution']['inferred_pairs'], 0)

    def test_identity_changes_miss_and_unchanged_inputs_cross_source_scopes(self):
        api = self.create(lambda _: [{'outcome': 'abstain'}])
        pair = self.pairs[:1]
        api.resolve(self.context, pair)
        for identity in [{**fixtures.INFERENCE, 'protocol_sha256': 'f' * 64},
                         {**fixtures.INFERENCE, 'runtime_image': 'another/image@sha256:' + 'a' * 64}]:
            changed = self.create(lambda _: [{'outcome': 'abstain'}], inference_identity=identity)
            self.assertEqual(changed.resolve(self.context, pair)['execution']['inferred_pairs'], 1)
        changed = self.create(lambda _: [{'outcome': 'abstain'}], model={**self.model, 'version': '2'})
        self.assertEqual(changed.resolve(self.context, pair)['execution']['inferred_pairs'], 1)
        context = {**self.context, 'catalogue_sha256': 'f' * 64}
        other = self.create(lambda _: self.fail('Unchanged input reinferred'), context=context)
        self.assertEqual(other.resolve(context, pair)['execution']['cache_hits'], 1)
        modified = deepcopy(self.pairs[0]); modified['product']['title'] = 'another lamp'
        self.assertNotEqual(api.inference.key(modified), api.inference.key(self.pairs[0]))

    def test_concurrent_requests_infer_each_key_once(self):
        calls = []
        def predict(pairs):
            calls.extend(pairs)
            return [{'outcome': 'abstain'} for _ in pairs]
        api = self.create(predict)
        with ThreadPoolExecutor(max_workers=2) as pool:
            answers = list(pool.map(lambda _: api.resolve(self.context, self.pairs), range(2)))
        self.assertEqual(len(calls), 2)
        self.assertEqual(sum(r['execution']['cache_hits'] for r in answers), 2)

    def test_published_labels_win_even_with_fresh_inference(self):
        api = self.create(lambda _: self.fail('Published label reinferred'),
            source_rows=[{'query_id': 'q1', 'product_id': 'p1', 'grade': 3}])
        result = api.resolve(self.context, self.pairs[:1], 'exploratory', True)
        self.assertEqual(result['results'][0]['source'], 'published')
        self.assertEqual(result['execution']['inferred_pairs'], 0)


if __name__ == '__main__':
    unittest.main()
