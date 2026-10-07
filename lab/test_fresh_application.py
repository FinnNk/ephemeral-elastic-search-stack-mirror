"""Check fresh application recovery and data identity without touching a running lab."""
import argparse
import contextlib
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import fresh_application as app
import fresh_images as images
import fresh_install as setup
import cleanup_fresh_install as cleanup


class FreshApplications(unittest.TestCase):
    def test_child_script_preserves_environment_and_adds_repository_imports(self):
        with patch.dict(os.environ, {'PYTHONPATH': 'existing-path', 'SSL_CERT_FILE': 'corporate.pem'}), \
             patch.object(app, 'execute') as execute:
            app.run_script('lab/delivery_cli.py', '--help')
        env = execute.call_args.kwargs['env']
        self.assertEqual(env['PYTHONPATH'], str(app.ROOT) + os.pathsep + 'existing-path')
        self.assertEqual(env['SSL_CERT_FILE'], 'corporate.pem')

    def test_delivery_cli_imports_shared_evaluation_package_in_real_child(self):
        # --help imports the actual bootstrap dependency chain without making
        # API requests or changing the cluster or retained installer state.
        with contextlib.redirect_stdout(io.StringIO()) as output:
            app.run_script('lab/delivery_cli.py', '--help')
        self.assertIn('bootstrap', output.getvalue())

    def test_registry_dns_repair_preserves_other_rules_and_waits_for_dns(self):
        current = argparse.Namespace(stdout=json.dumps({'data': {'nexus.override': 'keep nexus', 'other.server': 'keep custom'}}))
        with patch.object(app, 'k', return_value=current) as command:
            self.assertTrue(app.registry_dns())
        patch_call = next(call for call in command.call_args_list if call.args[0] == 'patch')
        payload = json.loads(patch_call.args[-1])
        self.assertEqual(set(payload['data']), {'gitea.override'})
        self.assertIn('gitea-http.platform.svc.cluster.local', payload['data']['gitea.override'])
        self.assertTrue(any(call.args[:2] == ('rollout', 'status') for call in command.call_args_list))

    def test_registry_dns_repair_is_idempotent(self):
        current = argparse.Namespace(stdout=json.dumps({'data': {'gitea.override':
            'rewrite name exact gitea.localhost gitea-http.platform.svc.cluster.local\n'}}))
        with patch.object(app, 'k', return_value=current) as command:
            self.assertFalse(app.registry_dns())
        self.assertEqual(command.call_count, 1)

    def test_dns_recovery_retries_only_exact_push_commit_and_waits_for_new_attempt(self):
        failed = {'id': 2, 'head_sha': 'wanted', 'event': 'push', 'status': 'completed', 'conclusion': 'failure', 'run_attempt': 1}
        success = {**failed, 'conclusion': 'success', 'run_attempt': 2}
        unrelated = {**success, 'id': 99, 'head_sha': 'other'}
        from gitea import api
        replies = [{'workflow_runs': [failed, unrelated]}, {}, {'workflow_runs': [failed]}, {'workflow_runs': [success]}]
        with patch('gitea.api', side_effect=replies) as provider, patch.object(app.time, 'sleep'):
            self.assertEqual(app.wait_build('search-spike', 'wanted', retry_failed=True), 2)
        reruns = [call for call in provider.call_args_list if len(call.args) > 1 and call.args[1] == 'POST']
        self.assertEqual(len(reruns), 1)
        self.assertEqual(reruns[0].args[0], '/repos/elastic-agent/search-spike/actions/runs/2/rerun')

    def test_dns_recovery_stops_after_one_failed_retry(self):
        failed = {'id': 2, 'head_sha': 'wanted', 'event': 'push', 'status': 'completed', 'conclusion': 'failure', 'run_attempt': 1}
        repeated = {**failed, 'run_attempt': 2}
        with patch('gitea.api', side_effect=[{'workflow_runs': [failed]}, {}, {'workflow_runs': [repeated]}]) as provider, \
             patch.object(app.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'build 2 failed'):
                app.wait_build('search-spike', 'wanted', retry_failed=True)
        self.assertEqual(sum(len(call.args) > 1 and call.args[1] == 'POST' for call in provider.call_args_list), 1)

    def test_isolated_build_config_keeps_plugins_and_selected_local_daemon(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'desktop-config', root / 'isolated'
            source.mkdir(); target.mkdir()
            (source / 'config.json').write_text(json.dumps({'cliPluginsExtraDirs': [str(root / 'bundled-plugins')],
                'currentContext': 'desktop-linux', 'auths': {'registry': {'auth': 'private'}},
                'credsStore': 'desktop', 'proxies': {'default': {'httpProxy': 'private'}}}), encoding='utf-8')
            with patch.dict(images.os.environ, {'DOCKER_CONFIG': str(source), 'DOCKER_CONTEXT': 'desktop-linux'}, clear=True), \
                 patch.object(images, 'execute', return_value=json.dumps({'Host': 'unix:///desktop/docker.sock'})):
                environment = images.build_environment(target)
            config = json.loads((target / 'config.json').read_text(encoding='utf-8'))
            self.assertEqual(set(config), {'cliPluginsExtraDirs'})
            self.assertEqual(config['cliPluginsExtraDirs'], [str(root / 'bundled-plugins'), str(source / 'cli-plugins')])
            self.assertEqual(environment['DOCKER_HOST'], 'unix:///desktop/docker.sock')
            self.assertNotIn('DOCKER_CONTEXT', environment)
            self.assertIn('private', (source / 'config.json').read_text(encoding='utf-8'))

    def test_explicit_docker_host_and_user_plugin_directory_are_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'desktop-config', root / 'isolated'
            source.mkdir(); target.mkdir()
            with patch.dict(images.os.environ, {'DOCKER_CONFIG': str(source), 'DOCKER_HOST': 'npipe:////./pipe/docker_engine'}, clear=True), \
                 patch.object(images, 'execute') as command:
                environment = images.build_environment(target)
            command.assert_not_called()
            self.assertEqual(environment['DOCKER_HOST'], 'npipe:////./pipe/docker_engine')
            self.assertEqual(json.loads((target / 'config.json').read_text())['cliPluginsExtraDirs'], [str(source / 'cli-plugins')])

    def test_selected_remote_context_is_not_silently_replaced_by_local_engine(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(images.os.environ, {'DOCKER_CONFIG': str(root)}, clear=True), \
                 patch.object(images, 'execute', return_value=json.dumps({'Host': 'tcp://remote.example:2376'})):
                with self.assertRaisesRegex(ValueError, 'local Docker Desktop context'):
                    images.build_environment(root)

    def test_unix_forward_probe_enables_reuse_before_binding(self):
        with patch.object(app.sys, 'platform', 'darwin'), patch.object(app.socket, 'socket') as factory:
            probe = factory.return_value.__enter__.return_value
            app.require_free_port(14577)
            self.assertEqual([call[0] for call in probe.method_calls], ['setsockopt', 'bind'])
            probe.setsockopt.assert_called_once_with(app.socket.SOL_SOCKET, app.socket.SO_REUSEADDR, 1)

    def test_active_listener_still_blocks_forward_start(self):
        with patch.object(app.sys, 'platform', 'darwin'), patch.object(app.socket, 'socket') as factory:
            probe = factory.return_value.__enter__.return_value
            probe.bind.side_effect = OSError('address in use')
            with self.assertRaisesRegex(RuntimeError, '14577 is occupied'):
                app.require_free_port(14577)

    def test_windows_forward_probe_keeps_exclusive_binding_behaviour(self):
        with patch.object(app.sys, 'platform', 'win32'), patch.object(app.socket, 'socket') as factory:
            probe = factory.return_value.__enter__.return_value
            app.require_free_port(14577)
            probe.setsockopt.assert_not_called()
            probe.bind.assert_called_once_with(('127.0.0.1', 14577))

    def test_frozen_snapshot_matches_selected_inputs(self):
        payloads = app.snapshot_payloads(app.ROOT / 'data/fresh-judgements')
        self.assertEqual(len(payloads), 4)
        rows = [data for name, data in payloads if not name.startswith('manifests/')]
        self.assertEqual([len(data.splitlines()) for data in rows], [24088, 981])
        # Restoring a model prediction must retain its source, not turn it into published truth.
        self.assertTrue(any('model' in str(json.loads(row)) for row in rows[0].splitlines()))

    def test_changed_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(app.ROOT / 'data/fresh-judgements', root, dirs_exist_ok=True)
            path = root / 'esci-gb-v1.rows.jsonl.gz'
            path.write_bytes(gzip.compress(gzip.decompress(path.read_bytes()) + b'{}\n'))
            with self.assertRaisesRegex(ValueError, 'snapshot differs'):
                app.snapshot_payloads(root)

    def test_foreign_external_stores_are_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'ownership.json'
            with patch.object(app, 'SERVICES_RECORD', path), \
                 patch.object(app, 'store_ids', return_value={'relevance-nexus': 'foreign'}), \
                 patch.object(app, 'execute') as command:
                with self.assertRaisesRegex(ValueError, 'ownership'):
                    app.owned_services(lambda: self.fail('must not create stores'))
                command.assert_not_called()
            self.assertFalse(path.exists())

    def test_failed_creation_retains_new_store_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'ownership.json'
            with patch.object(app, 'SERVICES_RECORD', path), \
                 patch.object(app, 'store_ids', side_effect=[{}, {'relevance-nexus-db': 'new'}]), \
                 patch.object(app, 'execute', return_value=''):
                with self.assertRaisesRegex(RuntimeError, 'creation failed'):
                    app.owned_services(lambda: (_ for _ in ()).throw(RuntimeError('creation failed')))
            self.assertEqual(json.loads(path.read_text())['containers'], {'relevance-nexus-db': 'new'})

    def test_model_manifest_adaptation_preserves_serving_contract(self):
        import yaml
        image = 'nexus.localhost:18185/relevance-judge:fresh@sha256:' + 'a' * 64
        for name in ('register-model.yaml', 'kserve-model.yaml', 'judgement-service-million.yaml'):
            docs = list(yaml.safe_load_all((app.ROOT / 'judgements/kubernetes' / name).read_text()))
            result = app.replace_runtime(docs, image)
            self.assertNotIn('k3d-observability-0', json.dumps(result))
            self.assertIn(image, json.dumps(result))
            self.assertEqual(app.replace_runtime(result, image), result)
        self.assertEqual(result[-1]['spec']['template']['spec']['containers'][0]['args'],
                         docs[-1]['spec']['template']['spec']['containers'][0]['args'])

    def test_build_wait_uses_exact_push_commit(self):
        runs = [{'id': 1, 'head_sha': 'old', 'event': 'push', 'status': 'completed', 'conclusion': 'success'},
                {'id': 2, 'head_sha': 'new', 'event': 'pull_request', 'status': 'completed', 'conclusion': 'success'},
                {'id': 3, 'head_sha': 'new', 'event': 'push', 'status': 'completed', 'conclusion': 'success'}]
        with patch('gitea.api', return_value={'workflow_runs': runs}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(app.wait_build('delivery-source', 'new'), 3)
            runs[-1]['conclusion'] = 'failure'
            with self.assertRaisesRegex(RuntimeError, 'build 3 failed'):
                app.wait_build('delivery-source', 'new')

    def test_application_failure_retains_foundation_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = argparse.Namespace(state_dir=str(root / '.lab'), through='services')
            with patch.object(setup, 'ROOT', root):
                installer = setup.Installer(args)
                installer.state.mkdir()
                installer.record = {'completed': list(setup.FOUNDATION)}
                with patch.object(installer, 'preflight'), patch.object(installer, 'cluster'), \
                     patch.object(installer, 'reconcile_operator_image'), \
                     patch.object(installer, 'reconcile_elasticsearch_image'), \
                     patch.object(installer, 'command', side_effect=RuntimeError('application failed')), \
                     patch.object(installer, 'diagnostics'), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(RuntimeError, 'application failed'):
                        installer.install()
                self.assertEqual(json.loads(installer.path.read_text())['completed'], list(setup.FOUNDATION))
                self.assertFalse((installer.state / 'fresh-install.lock').exists())

    def test_custom_java_image_preserves_pinned_base_and_trust_verification(self):
        dockerfile = images.gatling_dockerfile()
        self.assertIn('FROM maven:3.9.11-eclipse-temurin-21@sha256:', dockerfile)
        self.assertIn('keytool -importcert -cacerts', dockerfile)
        self.assertNotIn('trustAll', dockerfile)
        self.assertNotIn('--insecure', dockerfile)
        python = images.trusted_dockerfile('FROM python:3.13-slim\nRUN pip install x\n')
        self.assertLess(python.index('ENV SSL_CERT_FILE='), python.index('RUN pip install'))
        self.assertIn('CURL_CA_BUNDLE=/usr/local/share/ca-certificates/fresh-lab.crt', python)

    def test_changed_store_blocks_cleanup_before_cluster_deletion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / '.lab'
            state.mkdir()
            (state / 'fresh-services.json').write_text(json.dumps({'format': 1, 'root': str(root.resolve()),
                'containers': {'relevance-nexus': 'original'}, 'volumes': list(app.STORES)}))
            (state / 'fresh-install.json').write_text('{}')
            with patch.object(cleanup, 'ROOT', root), patch.object(cleanup, 'verify_ownership', return_value=True), \
                 patch.object(cleanup, 'execute', return_value='changed') as command:
                with self.assertRaisesRegex(ValueError, 'identity changed'):
                    cleanup.cleanup(state, include_stores=True)
            self.assertFalse(any('delete' in call.args[0] or 'rm' in call.args[0] for call in command.call_args_list))

    def test_control_state_bundle_includes_comparison_image_receipts(self):
        spec = importlib.util.spec_from_file_location('fresh_control_install', app.ROOT / 'lab/control-runtime/install.py')
        control = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(control)
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            for name in ('releases', 'state-source', 'delivery-state', 'delivery', 'evidence'):
                (state / name).mkdir()
            receipt = b'{"lab-evaluator":{"image":"digest-pinned"}}'
            (state / 'tool-images-7j.json').write_bytes(receipt)
            (state / 'credentials.json').write_text('must not export')
            with patch.object(control, 'STATE', state):
                control.write_bundle(state / 'bundle.tar.gz')
            with tarfile.open(state / 'bundle.tar.gz') as archive:
                self.assertEqual(archive.extractfile('tool-images-7j.json').read(), receipt)
                self.assertNotIn('credentials.json', archive.getnames())

    def test_failed_fresh_activation_does_not_start_legacy_host_writers(self):
        spec = importlib.util.spec_from_file_location('fresh_control_activation', app.ROOT / 'lab/control-runtime/install.py')
        control = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(control)
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(control, 'STATE', Path(temporary)), \
                 patch.object(control, 'k', return_value=argparse.Namespace(returncode=1)), \
                 patch.object(app, 'assert_fresh'), patch.object(control, 'staged', return_value={}), \
                 patch.object(control, 'pause_host'), \
                 patch.object(control, 'transfer', side_effect=RuntimeError('transfer failed')), \
                 patch.object(control, 'release_transfer_pod'), \
                 patch.object(control, 'stop_browser_forward'), \
                 patch.object(control, 'browser_forward') as forward, \
                 patch.object(control, 'resume_host') as resume:
                with self.assertRaisesRegex(RuntimeError, 'transfer failed'):
                    control.activate('image', 1, fresh=True)
                forward.assert_not_called()
                resume.assert_not_called()


if __name__ == '__main__':
    unittest.main()
