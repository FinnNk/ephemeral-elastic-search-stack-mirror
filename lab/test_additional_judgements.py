"""Exercise additional resolution against the real service and persistent cache."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from additional_judgements import resolve_extra
from variant_gate import canonical, sha
from service import JudgementService
from test_service import INFERENCE


class AdditionalResolutionTests(unittest.TestCase):
    def test_published_lookup_inference_abstention_and_repeat(self):
        context = {'catalogue_sha256': 'a'*64, 'query_suite_sha256': 'b'*64, 'rubric': 'esci-v1'}
        model = {'name': 'judge', 'version': '1', 'artifact_sha256': 'c'*64}
        queries = [{'query_id': 'one', 'query': 'lamp', 'country': 'GB', 'currency': 'GBP', 'filters': {}},
                   {'query_id': 'two', 'query': 'lamp', 'country': 'GB', 'currency': 'GBP', 'filters': {}}]
        payload = b''.join(canonical(r) for r in queries)
        item = {'name': 'lamps', 'required': False, 'query_bytes': payload,
                'query_sha256': sha(payload), 'queries': queries, 'judgements_rows': []}
        products = {pid: {'product_id': pid, 'title': pid, 'country': 'GB', 'currency': 'GBP'}
                    for pid in ('p1', 'p2', 'p3')}
        captured = {'captured_depth': 10, 'variants': {'baseline': {}, 'candidate': {}},
            'catalogue_sha256': 'a'*64, 'observations': [{'query_id': r['query_id'],
            'request': {k: r[k] for k in ('query', 'country', 'currency', 'filters')},
            'results': {'baseline': {'ids': ['p1', 'p2']}, 'candidate': {'ids': ['p2', 'p3']}}}
            for r in queries]}
        predictions = []
        def predict(pairs):
            predictions.extend(pairs)
            return [{'outcome': 'abstain'} if p['product_id'] == 'p3' else
                    {'outcome': 'labelled', 'label': 'S'} for p in pairs]
        with tempfile.TemporaryDirectory() as directory:
            api = JudgementService(Path(directory)/'cache.db',
                [{'query_id': 'published', 'product_id': 'p1', 'grade': 3}],
                [{**queries[0], 'query_id': 'published'}], products.values(), context, model,
                predict, inference_identity=INFERENCE)
            try:
                def call(url, path, body=None):
                    if path == '/health':
                        return {'context': context, 'model': model, 'inference': INFERENCE}
                    if path.endswith(':register'):
                        import base64
                        return api.register_queries(body['context'], base64.b64decode(body['query_bytes']), body['query_suite_sha256'])
                    return api.resolve(body['context'], body['pairs'], body['selection'])
                with patch('additional_judgements.call', side_effect=call), \
                        patch('additional_judgements.products_for', return_value=products), \
                        patch('additional_judgements.judgement_pool') as observed:
                    first = resolve_extra(item, captured, canonical({'metrics': ['nDCG@10']}), {},
                        lambda payload, name: {'sha256': sha(payload), 'blob': 'runs/'+sha(payload)+'/'+name})
                    second = resolve_extra(item, captured, canonical({'metrics': ['nDCG@10']}), {},
                        lambda payload, name: {'sha256': sha(payload), 'blob': 'runs/'+sha(payload)+'/'+name})
                self.assertEqual(observed.call_count, 2)
                self.assertEqual(observed.call_args.args, ('1', 'exploratory', 6, 4, 0.0))
                self.assertEqual(second['judgement_resolution']['input_shift']['observed'], 'gap_resolution_pairs')
                self.assertEqual(len(predictions), 2)
                self.assertEqual(second['judgement_resolution']['execution']['inferred_pairs'], 0)
                self.assertEqual(second['judgement_resolution']['execution']['cache_hits'], 2)
                self.assertEqual(first['judgement_resolution']['counts']['pool']['abstained'], 2)
                self.assertEqual({r['query_id'] for r in first['judgements_rows']}, {'one', 'two'})
                self.assertEqual(first['judgement_bytes'], second['judgement_bytes'])
                with patch('additional_judgements.call', side_effect=lambda url, path, body=None:
                        call(url,path,body) if not path.endswith(':resolve') else (_ for _ in ()).throw(TimeoutError())), \
                        patch('additional_judgements.products_for', return_value=products):
                    failed = resolve_extra(item, captured, canonical({'metrics': ['nDCG@10']}), {},
                        lambda payload, name: {'sha256': sha(payload), 'blob': 'runs/'+name})
                self.assertEqual(failed['judgement_resolution']['counts']['pool']['failed'], 6)
                self.assertEqual(failed['judgement_resolution']['execution']['response_errors'], 1)

                self.assertEqual({r['provenance']['kind'] for r in first['judgements_rows']}, {'published', 'model'})
                self.assertTrue(any(r['gate_eligible'] is False for r in first['judgements_rows']))
                with self.assertRaisesRegex(ValueError, 'differ'):
                    api.register_queries(context, payload, 'd'*64)
                modified = [{**queries[0], 'query': 'phone'}]
                other = b''.join(canonical(r) for r in modified)
                ids = api.register_queries(context, other, sha(other))['query_ids']
                self.assertNotEqual(ids['one'], 'published')
            finally:
                api.database.close()
