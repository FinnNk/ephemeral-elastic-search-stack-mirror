"""Verify demo resource settings and telemetry semantics without deploying anything."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

HERE = Path(__file__).resolve().parent / 'observability'
spec = importlib.util.spec_from_file_location('demo_profile', HERE / 'demo_profile.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class DemoProfile(unittest.TestCase):
    def test_demo_settings_keep_pins_and_use_native_trusted_init(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / 'control-image.json').write_text(json.dumps({'image': 'nexus.localhost:18185/lab-control@sha256:' + 'a' * 64}))
            # A normal public/corporate bundle can exceed Linux's argument limit.
            (state / 'host-ca-bundle.pem').write_text('public corporate CA\n' * 20000)
            defaults = {'otelCollector': {'config': {'service': {'pipelines': {
                'traces': {'processors': ['spanmetrics', 'batch']},
                'metrics': {'processors': ['batch']}, 'logs': {'processors': ['batch']}}}}}}
            with patch('tarfile.open') as archive:
                archive.return_value.__enter__.return_value.extractfile.return_value = io.StringIO(yaml.safe_dump(defaults))
                values = demo.values(HERE, state)
        self.assertNotIn('nodeSelector', values['clickhouse'])
        self.assertEqual(values['clickhouse']['persistence']['size'], '10Gi')
        self.assertEqual(values['clickhouse']['zookeeper']['persistence']['size'], '1Gi')
        self.assertEqual(values['clickhouse']['zookeeper']['heapSize'], 128)
        self.assertEqual(values['clickhouse']['resources']['limits']['memory'], '2Gi')
        self.assertEqual(values['signoz']['persistence']['size'], '1Gi')
        self.assertIn('sha256:', values['signoz']['image']['tag'])
        self.assertIn('curl --cacert', values['clickhouse']['initContainers']['udf']['command'][2])
        command = values['clickhouse']['initContainers']['udf']['command'][2]
        self.assertIn('/usr/local/share/ca-certificates/fresh-lab.crt', command)
        self.assertNotIn('base64', command)
        self.assertLess(len(command.encode('utf-8')), 4096)
        self.assertEqual(values['clickhouse']['imagePullSecrets'], ['nexus-read'])
        self.assertEqual(values['otelCollector']['config']['service']['pipelines']['traces']['processors'],
                         ['memory_limiter', 'spanmetrics', 'batch'])

    def test_gateway_samples_traces_without_sampling_metrics_or_logs(self):
        resources = demo.agents(HERE)
        configs = [r for r in resources if r['kind'] == 'ConfigMap']
        gateway = next(r for r in configs if r['metadata']['name'] == 'lab-otel-gateway')
        config = yaml.safe_load(gateway['data']['config.yaml'])
        self.assertIn('probabilistic_sampler/demo', config['service']['pipelines']['traces']['processors'])
        for signal in ('metrics', 'logs'):
            self.assertNotIn('probabilistic_sampler/demo', config['service']['pipelines'][signal]['processors'])
        self.assertEqual(config['exporters']['otlp/backend']['sending_queue']['queue_size'], 128)
        for resource in resources:
            if resource['kind'] in ('Deployment', 'DaemonSet'):
                self.assertNotIn('nodeSelector', resource['spec']['template']['spec'])

    def test_storage_quantities_are_checked_in_bytes(self):
        self.assertEqual(demo.storage_bytes('1024Mi'), demo.storage_bytes('1Gi'))
        self.assertGreater(demo.storage_bytes('20Gi'), demo.storage_bytes('10Gi'))
        with self.assertRaises(ValueError):
            demo.storage_bytes('unrecognised')

    def test_operator_patch_bounds_both_existing_containers(self):
        containers = demo.operator_patch()['spec']['template']['spec']['containers']
        self.assertEqual([item['name'] for item in containers], ['operator', 'metrics-exporter'])
        self.assertEqual([item['resources']['limits']['memory'] for item in containers], ['128Mi', '64Mi'])


if __name__ == '__main__':
    unittest.main()
