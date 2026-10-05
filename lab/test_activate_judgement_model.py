"""Activation rejects mismatched models and preserves API inputs and caches."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import activate_judgement_model as activation


class ActivationTests(unittest.TestCase):
    def test_patch_preserves_original_inputs_and_selects_the_loaded_predictor(self):
        deployment = {'spec': {'template': {'spec': {'containers': [{'name': 'judgement-service',
            'args': ['--database', '/state/evidence.sqlite3', '--predict-url', 'http://placeholder',
                     '--source-judgements', '/inputs/judgements.jsonl']}],
            'volumes': [{'name': 'cache'}]}}}}
        value = activation.api_patch(deployment, 'image', 'esci-v3-candidate')
        args = value['spec']['template']['spec']['containers'][0]['args']
        self.assertIn('/state/evidence.sqlite3', args)
        self.assertIn('/inputs/judgements.jsonl', args)
        self.assertIn('http://esci-v3-candidate-predictor.lab-models.svc/v1/models/judgement-model:predict', args)
        self.assertNotIn('volumes', value['spec']['template']['spec'])
        self.assertEqual(args.count('--inference-identity'), 1)
        self.assertEqual(args.count('--model-policy'), 1)
        deployment['spec']['template']['spec']['containers'][0]['args'] = args
        self.assertEqual(activation.api_patch(deployment, 'image', 'esci-v3-candidate'), value)

    def test_wrong_loaded_version_is_rejected_before_any_mutation(self):
        generated = {'items': [{'kind': 'InferenceService', 'spec': {'predictor': {'model':
            {'storageUri': 'registered/4', 'runtime': 'checked'}}}}]}
        loaded = {'spec': {'predictor': {'model': {'storageUri': 'registered/1', 'runtime': 'stub'}}},
                  'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}
        with tempfile.TemporaryDirectory() as directory, patch.object(activation, 'guard'), \
                patch.object(activation, 'render', return_value=generated), \
                patch.object(activation, 'k', return_value=SimpleNamespace(stdout=json.dumps(loaded))), \
                patch.object(activation, 'apply') as apply:
            with self.assertRaisesRegex(ValueError, 'checked model'):
                activation.activate({}, {}, 'runtime', 'nexus.localhost:18185/relevance-judge:test@sha256:'+'a'*64,
                                    'esci-v3-candidate', Path(directory)/'receipt')
            apply.assert_not_called()
            self.assertFalse((Path(directory)/'receipt').exists())
