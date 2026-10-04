"""Capture applies the frozen filter request and rejects inaccurate echoes."""
import io
import hashlib
import json
import unittest
import urllib.parse
from unittest.mock import patch

import evaluation_worker
import variant_capture_worker
import evaluation_job


class CaptureFilters(unittest.TestCase):
    def test_both_job_types_mount_and_fingerprint_the_contract(self):
        for variants in (False, True):
            with self.subTest(variants=variants), patch.object(evaluation_job, 'guard'), \
                    patch.object(evaluation_job, 'apply'), patch.object(evaluation_job, 'k') as command:
                command.return_value.stdout = '{"pacing":{"lab-base":{"attempts":1}}}\n[{"query_id":"q1"}]'
                suite = json.dumps({'query_id': 'q1'}).encode()
                if variants:
                    _, metadata = evaluation_job.run_variants(suite, self.variants)
                else:
                    _, metadata = evaluation_job.run(suite, 'lab-base', 'lab-change')
                config = next(call.kwargs['body'] for call in command.call_args_list
                              if call.args[0] == 'create')
                contract = config['data']['search_filters.py']
                self.assertEqual(metadata['request_contract_sha256'],
                                 hashlib.sha256(contract.encode()).hexdigest())
                self.assertIn('def validate_filters', contract)
                self.assertIn('class Pacer', config['data']['adaptive_pacing.py'])
                self.assertEqual(metadata['pacing']['lab-base']['attempts'], 1)
                self.assertEqual(metadata['adaptive_pacing_sha256'],
                                 hashlib.sha256(config['data']['adaptive_pacing.py'].encode()).hexdigest())

    def setUp(self):
        self.row = {'query_id': 'q1', 'query': 'lamp', 'country': 'GB', 'currency': 'GBP',
                    'filters': {'category': ['home'], 'price_minor': {'lte': 3500}}}
        self.variants = {name: {'environment': 'lab-' + name, 'selection': 'explicit',
                               'configuration_sha256': name[-1] * 64}
                         for name in ('ranker-a', 'ranker-b', 'ranker-c')}

    def test_every_named_variant_receives_identical_filters(self):
        seen = []
        def answer(request, **_kwargs):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
            seen.append(params)
            name = request.get_header('X-lab-variant')
            return io.BytesIO(json.dumps({'query': 'lamp', 'country': 'GB', 'currency': 'GBP',
                'filters': json.loads(params['filters'][0]), 'ids': [], 'total': 0,
                'variant_id': name, 'configuration_sha256': self.variants[name]['configuration_sha256']}).encode())
        with patch.object(variant_capture_worker.urllib.request, 'urlopen', side_effect=answer):
            result = variant_capture_worker.run([self.row], self.variants)
        self.assertNotIn('error', result[0])
        self.assertEqual(len(seen), 3)
        self.assertTrue(all(params == seen[0] for params in seen))
        self.assertEqual(json.loads(seen[0]['filters'][0]), self.row['filters'])

    def test_paired_capture_forwards_filters_and_rejects_wrong_or_missing_echo(self):
        payload = {'query': 'lamp', 'country': 'GB', 'currency': 'GBP', 'ids': [], 'total': 0}
        for echo in (None, {}, self.row['filters']):
            current = {**payload, **({'filters': echo} if echo is not None else {})}
            with patch.object(evaluation_worker.urllib.request, 'urlopen',
                              return_value=io.BytesIO(json.dumps(current).encode())) as call:
                if echo == self.row['filters']:
                    self.assertEqual(evaluation_worker.request('lab-base', self.row)['ids'], [])
                else:
                    with self.assertRaisesRegex(ValueError, 'frozen filters'):
                        evaluation_worker.request('lab-base', self.row)
            params = urllib.parse.parse_qs(urllib.parse.urlparse(call.call_args.args[0].full_url).query)
            self.assertEqual(json.loads(params['filters'][0]), self.row['filters'])

    def test_invalid_filters_never_dispatch_to_any_variant(self):
        row = {**self.row, 'filters': {'category': 'home'}}
        with patch.object(variant_capture_worker.urllib.request, 'urlopen') as call:
            variants = variant_capture_worker.run([row], self.variants)
            paired = evaluation_worker.run([row], 'lab-base', 'lab-candidate')
        call.assert_not_called()
        self.assertEqual(variants[0]['error']['kind'], 'ValueError')
        self.assertEqual(paired[0]['error']['kind'], 'ValueError')


if __name__ == '__main__':
    unittest.main()
