"""Verify demo resource settings and telemetry semantics without deploying anything."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

import yaml

HERE = Path(__file__).resolve().parent / 'observability'
spec = importlib.util.spec_from_file_location('demo_profile', HERE / 'demo_profile.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
install_spec = importlib.util.spec_from_file_location('signoz_install', HERE / 'install.py')
installer = importlib.util.module_from_spec(install_spec)
install_spec.loader.exec_module(installer)


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
        self.assertEqual(values['clickhouse']['resources']['limits']['memory'], '4Gi')
        self.assertEqual(values['clickhouse']['resources']['requests']['memory'], '1Gi')
        self.assertEqual(values['clickhouse']['resources']['requests']['cpu'], '500m')
        self.assertEqual(values['clickhouse']['settings']['max_server_memory_usage'], '3221225472')
        self.assertEqual(values['clickhouse']['livenessProbe']['timeoutSeconds'], 5)
        self.assertEqual(values['clickhouse']['livenessProbe']['failureThreshold'], 12)
        self.assertEqual(values['clickhouse']['readinessProbe']['timeoutSeconds'], 5)
        self.assertEqual(values['signoz']['persistence']['size'], '1Gi')
        self.assertIn('sha256:', values['signoz']['image']['tag'])
        self.assertIn('curl --cacert', values['clickhouse']['initContainers']['udf']['command'][2])
        command = values['clickhouse']['initContainers']['udf']['command'][2]
        self.assertIn('/usr/local/share/ca-certificates/fresh-lab.crt', command)
        self.assertNotIn('base64', command)
        self.assertLess(len(command.encode('utf-8')), 4096)
        self.assertEqual(values['clickhouse']['imagePullSecrets'], ['nexus-read'])
        self.assertFalse(values['telemetryStoreMigrator']['upgradeHelmHooks'])
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

    def test_retry_preserves_logs_and_recreates_only_owned_migration_job(self):
        job = {'metadata': {'labels': {'app.kubernetes.io/name': 'signoz',
               'app.kubernetes.io/instance': 'signoz',
               'app.kubernetes.io/component': 'signoz-telemetrystore-migrator'}}}
        folder = MagicMock()
        with patch.object(installer.subprocess, 'run', side_effect=[
                Mock(stdout=json.dumps(job)), Mock(stdout=''),
                Mock(stdout='waiting for ClickHouse', stderr='')]), \
                patch.object(installer, 'run') as run:
            installer.reset_demo_migrator(folder)
        (folder / 'previous-migrator.log').write_text.assert_called_once_with(
            'waiting for ClickHouse', encoding='utf-8')
        self.assertIn('delete', run.call_args.args[0])
        self.assertIn('signoz-telemetrystore-migrator', run.call_args.args[0])

    def test_retry_rejects_foreign_job_and_handles_no_existing_job(self):
        with patch.object(installer.subprocess, 'run', return_value=Mock(stdout='')), \
                patch.object(installer, 'run') as run:
            installer.reset_demo_migrator(Mock())
            run.assert_not_called()
        with patch.object(installer.subprocess, 'run', return_value=Mock(
                stdout=json.dumps({'metadata': {'labels': {}}}))), \
                patch.object(installer, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'ownership'):
                installer.reset_demo_migrator(Mock())
            run.assert_not_called()

    def test_retry_recreates_old_hook_account_but_preserves_normal_account(self):
        labels = {'app.kubernetes.io/name': 'signoz', 'app.kubernetes.io/instance': 'signoz',
                  'app.kubernetes.io/component': 'signoz-telemetrystore-migrator'}
        for hook in (False, True):
            metadata = {'labels': labels, 'annotations': {'helm.sh/hook': 'pre-upgrade'} if hook else {}}
            with patch.object(installer.subprocess, 'run', side_effect=[Mock(stdout=''),
                    Mock(stdout=json.dumps({'metadata': metadata}))]), \
                    patch.object(installer, 'run') as run:
                installer.reset_demo_migrator(Mock())
                if hook:
                    self.assertIn('serviceaccount', run.call_args.args[0])
                else:
                    run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
