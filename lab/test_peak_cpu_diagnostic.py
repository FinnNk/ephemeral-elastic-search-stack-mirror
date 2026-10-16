"""Check disposable preview boundaries without creating Kubernetes resources."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('peak_cpu_diagnostic',
    Path(__file__).parent / 'experiments/peak-cpu-headroom/run.py')
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class PeakCpuDiagnosticTests(unittest.TestCase):
    def original(self):
        return {'apiVersion': 'apps/v1', 'kind': 'Deployment',
                'metadata': {'name': 'search', 'namespace': diagnostic.SOURCE},
                'spec': {'replicas': 1, 'template': {'metadata': {'labels': {'app': 'search'}},
                    'spec': {'volumes': [{'name': 'status', 'configMap': {'name': 'status', 'optional': True}}],
                        'containers': [{'name': 'api', 'image': 'registry.test/api@sha256:' + 'a'*64,
                            'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'},
                                          'limits': {'cpu': '250m', 'memory': '96Mi'}},
                            'env': [{'name': 'ES_INDEX', 'value': 'frozen'},
                                    {'name': 'LAB_DEPLOYMENT_TIER', 'value': diagnostic.SOURCE}]}]}}}}

    def test_preview_keeps_image_memory_and_data_with_only_cpu_headroom_changed(self):
        original = self.original();before = deepcopy(original)
        def command(*args):
            return SimpleNamespace(stdout='{"items":[]}' if args[:2] == ('get', 'networkpolicies') else '')
        with patch.object(diagnostic, 'k', side_effect=command), patch.object(diagnostic, 'apply') as apply:
            diagnostic.preview('lab-peak-cpu-test-1000m', '1', 'test', original, 'same-node')
        self.assertEqual(original, before)
        objects = [call.args[0] for call in apply.call_args_list]
        namespace = next(o for o in objects if o['kind'] == 'Namespace')
        self.assertNotIn('lab', namespace['metadata']['labels'])
        deployment = next(o for o in objects if o['kind'] == 'Deployment')
        template = deployment['spec']['template']['spec']
        container = template['containers'][0]
        self.assertEqual(container['image'], before['spec']['template']['spec']['containers'][0]['image'])
        self.assertEqual(container['resources']['limits'], {'cpu': '1', 'memory': '96Mi'})
        self.assertEqual(container['env'][0], {'name': 'ES_INDEX', 'value': 'frozen'})
        self.assertFalse(template['automountServiceAccountToken'])
        self.assertEqual(template['nodeName'], 'same-node')
        self.assertFalse(any(o['kind'] in ('Ingress', 'RoleBinding') for o in objects))

    def test_required_dependency_is_not_silently_skipped(self):
        original = self.original()
        original['spec']['template']['spec']['volumes'][0]['configMap']['optional'] = False
        with patch.object(diagnostic, 'k', return_value=SimpleNamespace(stdout='')), \
             patch.object(diagnostic, 'apply'), self.assertRaisesRegex(ValueError, 'Missing required'):
            diagnostic.preview('lab-peak-cpu-test', '1', 'test', original, 'node')

    def test_timing_overlay_is_only_one_method(self):
        import ast
        tree = ast.parse(diagnostic.timing_method())
        self.assertEqual(len(tree.body), 1)
        self.assertEqual(tree.body[0].name, 'search_index')
        self.assertIn('elasticsearch.took_ms', diagnostic.timing_method())


if __name__ == '__main__':
    unittest.main()
