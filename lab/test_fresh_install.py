"""Exercise installation recovery and destructive cleanup boundaries without Docker writes."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cleanup_fresh_install as cleanup
import fresh_install as setup


class FreshInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / '.lab'
        self.state.mkdir()
        self.patches = [patch.object(module, 'ROOT', self.root) for module in (setup, cleanup)]
        for item in self.patches:
            item.start()
        self.args = argparse.Namespace(state_dir=str(self.state), corporate_ca=None,
            gitea_registry='docker.io/gitea/gitea', server_memory='6g', agent_memory='4g', through='access')

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.temp.cleanup()

    def record(self):
        value = {'format': 1, 'root': str(self.root), 'cluster': setup.CLUSTER,
                 'nodes': {name: name + '-original-id' for name in setup.NODES}, 'completed': []}
        setup.private_json(self.state / 'fresh-install.json', value)
        return value

    def test_foreign_state_is_rejected_before_changes(self):
        (self.state / 'credentials.json').write_text('{}')
        installer = setup.Installer(self.args)
        with patch.object(setup.shutil, 'which', return_value='/bin/tool'), \
             patch.object(installer, 'command', return_value='linux'), \
             patch.object(setup, 'inspect_nodes', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'Existing lab state'):
                installer.preflight()
        self.assertFalse(installer.path.exists())

    def test_changed_node_identity_is_rejected(self):
        self.record()
        installer = setup.Installer(self.args)
        with patch.object(setup.shutil, 'which', return_value='/bin/tool'), \
             patch.object(installer, 'command', return_value='linux'), \
             patch.object(setup, 'inspect_nodes', return_value={setup.NODES[0]: 'different'}):
            with self.assertRaisesRegex(RuntimeError, 'ownership differs'):
                installer.preflight()

    def test_failed_stage_is_not_marked_complete_and_lock_is_released(self):
        installer = setup.Installer(self.args)
        installer.record = self.record()
        with patch.object(installer, 'preflight'), patch.object(installer, 'cluster'), \
             patch.object(installer, 'platform', side_effect=RuntimeError('pull denied')), \
             patch.object(installer, 'diagnostics'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'pull denied'):
                installer.install()
        value = json.loads(installer.path.read_text())
        self.assertEqual(value['completed'], ['cluster'])
        self.assertFalse((self.state / 'fresh-install.lock').exists())

    def test_resume_retains_completed_platform_and_rechecks_cluster(self):
        installer = setup.Installer(self.args)
        installer.record = self.record()
        installer.record['completed'] = ['cluster', 'platform']
        with patch.object(installer, 'preflight'), patch.object(installer, 'cluster') as cluster, \
             patch.object(installer, 'platform') as platform, patch.object(installer, 'storage'), \
             patch.object(installer, 'reconcile_operator_image') as reconcile, \
             patch.object(installer, 'access'), contextlib.redirect_stdout(io.StringIO()):
            installer.install()
        cluster.assert_called_once()
        platform.assert_not_called()
        reconcile.assert_called_once()
        self.assertEqual(installer.record['completed'], list(setup.FOUNDATION))

    def test_second_installer_does_not_remove_first_lock(self):
        lock = self.state / 'fresh-install.lock'
        lock.write_text('1234')
        with self.assertRaisesRegex(RuntimeError, 'Another installer'):
            setup.Installer(self.args).install()
        self.assertEqual(lock.read_text(), '1234')

    def test_cleanup_without_record_never_deletes(self):
        with patch.object(cleanup, 'execute') as command:
            with self.assertRaisesRegex(ValueError, 'No installer ownership'):
                cleanup.cleanup(self.state)
        command.assert_not_called()

    def test_cleanup_rejects_replaced_nodes(self):
        self.record()
        with patch.object(cleanup, 'inspect_nodes', return_value={setup.NODES[0]: 'replacement'}), \
             patch.object(cleanup, 'execute') as command:
            with self.assertRaisesRegex(ValueError, 'identities differ'):
                cleanup.cleanup(self.state)
        command.assert_not_called()

    def test_cleanup_rejects_extended_lab(self):
        record = self.record()
        with patch.object(cleanup, 'inspect_nodes', return_value=record['nodes']), \
             patch.object(cleanup, 'execute', return_value='k3d-relevance-lab-agent-1') as command:
            with self.assertRaisesRegex(ValueError, 'Additional lab nodes'):
                cleanup.cleanup(self.state)
        self.assertFalse(any('delete' in call.args[0] for call in command.call_args_list))

    def test_cleanup_rejects_worktree_state_and_installer_lock(self):
        self.record()
        (self.state / 'worktrees').mkdir()
        with self.assertRaisesRegex(ValueError, 'worktrees'):
            cleanup.verify_ownership(self.state)
        (self.state / 'worktrees').rmdir()
        (self.state / 'fresh-install.lock').write_text('1234')
        with self.assertRaisesRegex(ValueError, 'lock exists'):
            cleanup.verify_ownership(self.state)

    def test_cleanup_archives_state_and_deletes_only_named_cluster(self):
        record = self.record()
        with patch.object(cleanup, 'inspect_nodes', return_value=record['nodes']), \
             patch.object(cleanup, 'execute', return_value='') as command, \
             contextlib.redirect_stdout(io.StringIO()):
            cleanup.cleanup(self.state)
        deletes = [call.args[0] for call in command.call_args_list if 'delete' in call.args[0]]
        self.assertEqual(deletes, [['k3d', 'cluster', 'delete', 'relevance-lab']])
        self.assertFalse(self.state.exists())
        self.assertEqual(len(list(self.root.glob('.lab-archived-*'))), 1)

    def test_cleanup_refuses_state_outside_checkout(self):
        with self.assertRaisesRegex(ValueError, 'restricted'):
            cleanup.verify_ownership(self.root)

    def test_cleanup_removes_only_recorded_volumes(self):
        record = self.record()
        owned = 'a' * 64
        other = 'b' * 64
        record['volumes'] = [owned]
        setup.private_json(self.state / 'fresh-install.json', record)
        def output(command, **options):
            return owned + '\n' + other if command[:3] == ['docker', 'volume', 'ls'] else ''
        with patch.object(cleanup, 'inspect_nodes', return_value=record['nodes']), \
             patch.object(cleanup, 'execute', side_effect=output) as command, \
             contextlib.redirect_stdout(io.StringIO()):
            cleanup.cleanup(self.state)
        removals = [call.args[0] for call in command.call_args_list if call.args[0][:3] == ['docker', 'volume', 'rm']]
        self.assertEqual(removals, [['docker', 'volume', 'rm', owned]])

    def test_volume_removal_failure_preserves_recovery_record(self):
        record = self.record()
        owned = 'a' * 64
        record['volumes'] = [owned]
        setup.private_json(self.state / 'fresh-install.json', record)
        def output(command, **options):
            if command[:3] == ['docker', 'volume', 'ls']:
                return owned
            if command[:3] == ['docker', 'volume', 'rm']:
                raise RuntimeError('volume in use')
            return ''
        with patch.object(cleanup, 'inspect_nodes', return_value={}), \
             patch.object(cleanup, 'execute', side_effect=output):
            with self.assertRaisesRegex(RuntimeError, 'volume in use'):
                cleanup.cleanup(self.state, purge=True)
        self.assertTrue((self.state / 'fresh-install.json').exists())

    def test_explicit_purge_removes_only_fixture_state(self):
        self.record()
        neighbour = self.root / 'keep.txt'
        neighbour.write_text('preserve')
        with patch.object(cleanup, 'inspect_nodes', return_value={}), \
             patch.object(cleanup, 'execute', return_value=''), \
             contextlib.redirect_stdout(io.StringIO()):
            cleanup.cleanup(self.state, purge=True)
        self.assertFalse(self.state.exists())
        self.assertEqual(neighbour.read_text(), 'preserve')

    def test_explicit_ingress_verification_rejects_missing_backend(self):
        import https_ingress
        with patch.object(https_ingress, 'k', return_value=argparse.Namespace(returncode=1)), \
             patch.object(https_ingress.ssl if hasattr(https_ingress, 'ssl') else setup.ssl,
                          'create_default_context'):
            with self.assertRaisesRegex(RuntimeError, 'backend is not installed'):
                https_ingress.verify(self.root / 'unused.pem', ['gitea'])

    def test_invalid_corporate_bundle_is_rejected(self):
        certificate = self.root / 'invalid.pem'
        certificate.write_text('not a certificate')
        import ssl
        with self.assertRaises(ssl.SSLError):
            setup.ca_bundle(self.state / 'bundle.pem', certificate)
        self.assertFalse((self.state / 'bundle.pem').exists())

    def test_operator_override_preserves_manager_settings(self):
        import yaml
        manifest = {'apiVersion': 'apps/v1', 'kind': 'StatefulSet',
                    'metadata': {'name': 'elastic-operator'}, 'spec': {'template': {'spec': {
                        'containers': [{'name': 'manager', 'image': 'docker.elastic.co/eck/eck-operator:3.5.0',
                                        'args': ['manager', '--config=/conf/eck.yaml']}]
                    }}}}
        result = yaml.safe_load(setup.operator_manifest(yaml.safe_dump(manifest)))
        manager = result['spec']['template']['spec']['containers'][0]
        self.assertEqual(manager['image'], setup.ECK_IMAGE)
        self.assertEqual(manager['args'], ['manager', '--config=/conf/eck.yaml'])

    def test_operator_override_refuses_unexpected_release(self):
        import yaml
        manifest = {'kind': 'StatefulSet', 'metadata': {'name': 'elastic-operator'},
                    'spec': {'template': {'spec': {'containers': [
                        {'name': 'manager', 'image': 'docker.elastic.co/eck/eck-operator:4.0.0'}]}}}}
        with self.assertRaisesRegex(ValueError, 'Unexpected upstream'):
            setup.operator_manifest(yaml.safe_dump(manifest))

    def test_elasticsearch_override_preserves_storage_and_version(self):
        import yaml
        original = yaml.safe_load((Path(__file__).resolve().parents[1] /
                                  'research/platform-spike/elasticsearch.yaml').read_text())
        result = yaml.safe_load(setup.elasticsearch_manifest(yaml.safe_dump(original)))
        self.assertEqual(result['spec'].pop('image'), setup.ELASTICSEARCH_IMAGE)
        self.assertEqual(result, original)

    def test_completed_storage_reconciles_image_without_reapplying_storage(self):
        installer = setup.Installer(self.args)
        installer.record = self.record()
        installer.record['completed'] = ['cluster', 'platform', 'storage']
        with patch.object(installer, 'preflight'), patch.object(installer, 'cluster'), \
             patch.object(installer, 'platform'), patch.object(installer, 'storage') as storage, \
             patch.object(installer, 'reconcile_operator_image'), \
             patch.object(installer, 'reconcile_elasticsearch_image') as reconcile, \
             patch.object(installer, 'access'), contextlib.redirect_stdout(io.StringIO()):
            installer.install()
        storage.assert_not_called()
        reconcile.assert_called_once()

    def test_old_operator_pull_failure_recovery_does_not_delete_healthy_or_current_pods(self):
        installer = setup.Installer(self.args)
        for image, reason, expected in [('old-image', 'ImagePullBackOff', True),
                                        ('old-image', None, False),
                                        (setup.ECK_IMAGE, 'ImagePullBackOff', False)]:
            pod = {'spec': {'containers': [{'name': 'manager', 'image': image}]},
                   'status': {'containerStatuses': [{'state': {'waiting': {'reason': reason}}}]}}
            controller = {'spec': {'template': {'spec': {'containers': [
                {'name': 'manager', 'image': setup.ECK_IMAGE}]}}}}
            with patch.object(installer, 'kubectl', side_effect=[json.dumps(pod), json.dumps(controller), '']) as command:
                installer.repair_failed_operator_pod()
            deletes = [call.args for call in command.call_args_list if call.args[0] == 'delete']
            self.assertEqual(bool(deletes), expected)

    def test_retained_elasticsearch_image_patch_changes_only_image(self):
        installer = setup.Installer(self.args)
        with patch.object(installer, 'kubectl', return_value=json.dumps(
                {'spec': {'version': '9.5.4'}, 'metadata': {'generation': 2}})) as command:
            installer.reconcile_elasticsearch_image()
        patches = [call.args for call in command.call_args_list if call.args[0] == 'patch']
        self.assertEqual(len(patches), 1)
        self.assertEqual(json.loads(patches[0][-1]), {'spec': {'image': setup.ELASTICSEARCH_IMAGE}})
        waits = [call.args for call in command.call_args_list if call.args[0] == 'wait']
        self.assertTrue(any('observedGeneration' in call[1] and call[1].endswith('=2') for call in waits))


if __name__ == '__main__':
    unittest.main()
