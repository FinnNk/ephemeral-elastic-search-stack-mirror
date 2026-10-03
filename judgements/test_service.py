"""Stored-label precedence and failed/abstained inference semantics."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import json

from service import JudgementService, kserve_predict


class ServiceTests(unittest.TestCase):
    def test_predict_timeout_is_explicit_and_identity_still_checked(self):
        with patch('service.request.urlopen') as open_url:
            reply = MagicMock()
            reply.read.return_value = json.dumps({'model': self.model, 'predictions': []}).encode()
            open_url.return_value.__enter__.return_value = reply
            self.assertEqual(kserve_predict('http://example.invalid/predict', [], self.model,
                                           timeout=120), [])
            self.assertEqual(open_url.call_args.kwargs['timeout'], 120)
            with self.assertRaises(ValueError):
                kserve_predict('http://example.invalid/predict', [], self.model,
                               timeout=float('nan'))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / 'labels.db'
        self.context = {'catalogue_sha256': 'a' * 64,
                        'query_suite_sha256': 'b' * 64, 'rubric': 'esci-v1'}
        self.model = {'name': 'synthetic-esci-judge', 'version': '1',
                      'artifact_sha256': 'c' * 64}
        self.pairs = [{'query_id': 'q1', 'product_id': pid,
                       'request': {'query': 'lamp', 'country': 'GB', 'currency': 'GBP',
                                   'filters': {}},
                       'product': {'product_id': pid, 'title': pid, 'country': 'GB',
                                   'currency': 'GBP'}} for pid in ('p1', 'p2')]
        self.query_rows = [{'query_id': 'q1', 'query': 'lamp',
                            'country': 'GB', 'currency': 'GBP'}]
        self.product_rows = [pair['product'] for pair in self.pairs]

    def test_stored_label_wins_and_abstention_is_not_persisted(self):
        calls = []

        def infer(pairs):
            calls.append(len(pairs))
            return [{'outcome': 'abstain'} for _ in pairs]

        service = JudgementService(self.database,
            [{'query_id': 'q1', 'product_id': 'p1', 'grade': 3}],
            self.query_rows, self.product_rows,
            self.context, self.model, infer)
        self.addCleanup(service.database.close)
        first = service.resolve(self.context, self.pairs)['results']
        second = service.resolve(self.context, self.pairs)['results']
        self.assertEqual(calls, [1, 1])
        self.assertEqual(first[0]['label'], 'E')
        self.assertEqual(first[1]['outcome'], 'unjudged')
        self.assertEqual(second[1]['outcome'], 'unjudged')

    def test_model_label_is_cached_for_exact_version(self):
        calls = []

        def infer(pairs):
            calls.append(len(pairs))
            return [{'outcome': 'labelled', 'label': 'C'} for _ in pairs]

        service = JudgementService(self.database, [], self.query_rows,
                                   self.product_rows, self.context, self.model, infer)
        self.addCleanup(service.database.close)
        self.assertEqual(service.resolve(self.context, self.pairs, 'exploratory')['results'][0]['grade'], 1)
        service.resolve(self.context, self.pairs, 'exploratory')
        self.assertEqual(calls, [2])
        self.assertEqual(service.database.execute('SELECT count(*) FROM evidence').fetchone()[0], 2)

    def test_passes_survive_restart_and_gate_selection_excludes_them(self):
        service = JudgementService(self.database,
            [{'query_id': 'q1', 'product_id': 'p1', 'grade': 3}],
            self.query_rows, self.product_rows, self.context, self.model,
            lambda pairs: [{'outcome': 'abstain'} for _ in pairs])
        provenance = {'kind': 'model', 'source_id': 'first-model', 'model': self.model,
                      'pass_id': 'pass-one', 'policy_sha256': 'd' * 64,
                      'release_sha256': 'e' * 64}
        first = {'query_id': 'q1', 'product_id': 'p2', 'outcome': 'labelled',
                 'label': 'S', 'confidence': 0.95, 'gate_eligible': False,
                 'provenance': provenance}
        payload = {'kind': 'judgement-pass', 'context': self.context, 'records': [first]}
        receipt = service.import_pass(payload)
        self.assertEqual(service.import_pass(payload), receipt)
        service.import_pass({**payload, 'records': [{**first, 'label': 'E',
            'provenance': {**provenance, 'source_id': 'second-model', 'pass_id': 'pass-two',
                           'model': {**self.model, 'version': '2'}}}]})
        self.assertIsNone(service.lookup('q1', 'p2', 'gate'))
        self.assertEqual(service.lookup('q1', 'p2', 'exploratory')['label'], 'S')
        self.assertEqual(service.lookup('q1', 'p1')['source'], 'published')
        service.database.close()
        second = JudgementService(self.database, [], [], [], self.context, self.model,
                                  lambda _: [])
        self.addCleanup(second.database.close)
        records = second.records(self.context, [{'query_id': 'q1', 'product_id': 'p2'}])
        self.assertEqual(len(records['results'][0]['evidence']), 2)
        self.assertEqual(records['results'][0]['evidence'][0]['confidence'], 0.95)
        self.assertIsNone(second.lookup('q1', 'p2', 'gate'))
        with self.assertRaisesRegex(ValueError, 'unqualified'):
            second.import_pass({**payload, 'records': [{**first, 'gate_eligible': True}]})

    def test_frozen_candidate_source_is_not_promoted_on_import(self):
        candidate = {'query_id': 'q1', 'product_id': 'p2', 'grade': 2,
                     'gate_eligible': False, 'provenance': {'kind': 'model',
                     'source_id': 'candidate', 'model': self.model, 'pass_id': 'first',
                     'policy_sha256': 'd' * 64}}
        service = JudgementService(self.database, [candidate], self.query_rows,
            self.product_rows, self.context, self.model, lambda _: [])
        self.addCleanup(service.database.close)
        self.assertIsNone(service.lookup('q1', 'p2', 'gate'))
        self.assertFalse(service.lookup('q1', 'p2', 'exploratory')['gate_eligible'])

    def test_other_context_is_rejected(self):
        service = JudgementService(self.database, [], self.query_rows,
                                   self.product_rows, self.context, self.model,
                                   lambda _: [])
        self.addCleanup(service.database.close)
        with self.assertRaisesRegex(ValueError, 'differs'):
            service.resolve({**self.context, 'rubric': 'other'}, self.pairs)

    def test_request_and_product_must_match_frozen_inputs(self):
        calls = []
        service = JudgementService(self.database, [], self.query_rows,
                                   self.product_rows, self.context, self.model,
                                   lambda pairs: calls.extend(pairs) or [])
        self.addCleanup(service.database.close)
        for changed in (
                {**self.pairs[0], 'request': {**self.pairs[0]['request'], 'query': 'desk'}},
                {**self.pairs[0], 'product': {**self.pairs[0]['product'], 'title': 'desk'}}):
            with self.assertRaisesRegex(ValueError, 'frozen'):
                service.resolve(self.context, [changed])
        self.assertEqual(calls, [])

    def test_completed_import_is_reused_after_restart(self):
        first = JudgementService(self.database,
            [{'query_id': 'q1', 'product_id': 'p1', 'grade': 3}],
            self.query_rows, self.product_rows, self.context, self.model,
            lambda _: [])
        first.database.close()
        second = JudgementService(self.database, iter(()), iter(()), iter(()),
                                  self.context, self.model, lambda _: [])
        self.addCleanup(second.database.close)
        self.assertEqual(second.resolve(self.context, [self.pairs[0]])['results'][0]['label'], 'E')


if __name__ == '__main__':
    unittest.main()
