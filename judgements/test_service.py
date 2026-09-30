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
        self.assertEqual(service.resolve(self.context, self.pairs)['results'][0]['grade'], 1)
        service.resolve(self.context, self.pairs)
        self.assertEqual(calls, [2])
        self.assertEqual(service.database.execute('SELECT count(*) FROM attempts').fetchone()[0], 2)

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
