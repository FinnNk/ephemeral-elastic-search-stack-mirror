"""SSH onboarding preserves user files and pins the endpoint to the owned lab."""
import base64
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import gitea_ssh_client as client
import gitea_ssh_server as server

UID = '12345678-1234-1234-1234-123456789abc'
KEY = 'ssh-ed25519 ' + base64.b64encode(b'\0\0\0\x0bssh-ed25519\0\0\0\x20' + b'a' * 32).decode()
OTHER = 'ssh-ed25519 ' + base64.b64encode(b'\0\0\0\x0bssh-ed25519\0\0\0\x20' + b'b' * 32).decode()


def headless_service():
    return {'metadata': {'namespace': 'platform', 'name': 'gitea-ssh',
                         'annotations': {'meta.helm.sh/release-name': 'gitea'}},
            'spec': {'type': 'ClusterIP', 'clusterIP': 'None',
                     'selector': {'app.kubernetes.io/instance': 'gitea'},
                     'ports': [{'name': 'ssh', 'port': 22, 'targetPort': 2222}]}}


class Server(unittest.TestCase):
    def test_port_must_be_exactly_loopback_and_expected_port(self):
        self.assertFalse(server.exposed({}))
        self.assertTrue(server.exposed({'30022/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '31822'}]}))
        for ip, port in [('0.0.0.0', '31822'), ('127.0.0.1', '22')]:
            with self.assertRaises(ValueError):
                server.exposed({'30022/tcp': [{'HostIp': ip, 'HostPort': port}]})

    def test_host_key_is_taken_from_public_pod_file_and_compared(self):
        with patch.object(server, 'k', return_value=SimpleNamespace(stdout=KEY + '\n')) as k, \
             patch.object(server, 'run', return_value=SimpleNamespace(stdout='[127.0.0.1]:31822 ' + KEY)):
            self.assertEqual(server.host_key('ssh-keyscan'), KEY)
            self.assertEqual(k.call_args.args[-2:], ('cat', server.HOST_KEY + '.pub'))
        with patch.object(server, 'k', return_value=SimpleNamespace(stdout=KEY)), \
             patch.object(server, 'run', return_value=SimpleNamespace(stdout='host ' + OTHER)):
            with self.assertRaisesRegex(ValueError, 'does not present'):
                server.host_key('ssh-keyscan')

    def test_invalid_or_ambiguous_keys_are_rejected(self):
        for value in ('', 'host ssh-ed25519 garbage', 'host ' + KEY + '\nhost ' + OTHER):
            with self.assertRaises(ValueError):
                server.public_key(value)

    def test_active_delivery_or_actions_blocks_installation(self):
        with patch.object(server, 'run', return_value=SimpleNamespace(stdout=json.dumps(
                {'operations': 1, 'comparisons': 0, 'mutations': 0}))):
            with self.assertRaisesRegex(ValueError, 'active'):
                server.require_idle()
        with patch.object(server, 'run', return_value=SimpleNamespace(stdout=json.dumps(
                {'operations': 0, 'comparisons': 0, 'mutations': 0}))), \
             patch('gitea.api', return_value={'workflow_runs': [{'status': 'in_progress'}]}):
            with self.assertRaisesRegex(ValueError, 'Actions is active'):
                server.require_idle()

    def test_occupied_port_is_refused_before_helm(self):
        with patch.object(server, 'identity', return_value=UID), patch.object(server, 'require_idle'), \
             patch.object(server, 'bindings', return_value={}), patch.object(server, 'run') as run, \
             patch.object(server.socket, 'socket') as sock:
            sock.return_value.__enter__.return_value.bind.side_effect = OSError('occupied')
            with self.assertRaisesRegex(ValueError, 'occupied'):
                server.install()
            run.assert_not_called()

    def test_settings_preserve_other_services_and_use_rootless_builtin_port(self):
        values = server.settings()
        self.assertEqual(set(values), {'service', 'gitea'})
        config = values['gitea']['config']['server']
        self.assertFalse(config['DISABLE_SSH'])
        self.assertTrue(config['START_SSH_SERVER'])
        self.assertEqual(config['SSH_LISTEN_PORT'], 2222)
        self.assertEqual(config['SSH_PORT'], 31822)
        self.assertEqual(config['SSH_SERVER_HOST_KEYS'], server.HOST_KEY)
        self.assertEqual(values['service']['ssh']['type'], 'ClusterIP')
        self.assertEqual(values['service']['ssh']['clusterIP'], 'None')
        self.assertIsNone(values['service']['ssh']['nodePort'])

    def test_https_refresh_does_not_reapply_bootstrap_ssh_or_image_settings(self):
        import https_ingress
        with patch.object(https_ingress, 'run') as run:
            https_ingress.configure_gitea()
            args = run.call_args.args[0]
            self.assertIn('--reuse-values', args)
            self.assertNotIn('--values', args)
            self.assertNotIn('-f', args)
            self.assertEqual(args[args.index('--set-string') + 1],
                             'gitea.config.server.ROOT_URL=https://gitea.localhost:34443/')

    def test_another_service_nodeport_is_not_taken(self):
        value = {'items': [{'metadata': {'namespace': 'other', 'name': 'service'},
                            'spec': {'ports': [{'nodePort': 30022}]}}]}
        with patch.object(server, 'k', return_value=SimpleNamespace(stdout=json.dumps(value))), \
             patch.object(server, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'another service'):
                server.require_available_service(UID)
            run.assert_not_called()

    def test_existing_custom_server_host_keys_are_not_replaced(self):
        values = {'gitea': {'config': {'server': {'DISABLE_SSH': False,
                                                 'SSH_SERVER_HOST_KEYS': '/custom/key'}}}}
        with patch.object(server, 'k', return_value=SimpleNamespace(stdout=json.dumps({'items': [headless_service()]}))), \
             patch.object(server, 'run', return_value=SimpleNamespace(stdout=json.dumps(values))):
            with self.assertRaisesRegex(ValueError, 'other SSH host-key settings'):
                server.require_available_service(UID)

    def test_workstation_service_is_separate_and_repeatable(self):
        original = headless_service()
        with patch.object(server, 'k', return_value=SimpleNamespace(stdout=json.dumps({'items': [original]}))), \
             patch.object(server, 'run', return_value=SimpleNamespace(stdout='{}')):
            service = server.require_available_service(UID)
        self.assertEqual(service['metadata']['name'], server.SSH_SERVICE)
        self.assertEqual(service['spec']['selector'], original['spec']['selector'])
        self.assertEqual(service['spec']['ports'][0]['nodePort'], server.NODE_PORT)
        self.assertEqual(original['spec']['clusterIP'], 'None')
        with patch.object(server, 'k', return_value=SimpleNamespace(stdout=json.dumps({'items': [original, service]}))), \
             patch.object(server, 'run', return_value=SimpleNamespace(stdout='{}')):
            self.assertEqual(server.require_available_service(UID), service)
        service['metadata']['labels']['lab.relevance.test/cluster-uid'] = 'other-cluster'
        with patch.object(server, 'k', return_value=SimpleNamespace(stdout=json.dumps({'items': [original, service]}))):
            with self.assertRaisesRegex(ValueError, 'unexpected ownership'):
                server.require_available_service(UID)

    def test_original_service_must_be_owned_and_headless(self):
        original = headless_service()
        original['spec']['clusterIP'] = '10.43.0.1'
        with patch.object(server, 'k', return_value=SimpleNamespace(stdout=json.dumps({'items': [original]}))):
            with self.assertRaisesRegex(ValueError, 'owned headless'):
                server.require_available_service(UID)

    def test_modified_cached_chart_is_not_used_or_downloaded_over(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / 'gitea-12.7.0.tgz').write_bytes(b'not the pinned chart')
            with patch.object(server, 'run') as download:
                with self.assertRaisesRegex(ValueError, 'Retained Gitea chart differs'):
                    server.chart(Path(t))
                download.assert_not_called()

    def test_chart_uses_helm_with_explicit_ca_and_isolated_cache(self):
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            bundle = root / 'host-ca-bundle.pem'
            bundle.write_text('fixture CA')
            payload = b'pinned fixture chart'
            def download(args, **kwargs):
                self.assertEqual(args[:3], [server.HELM, 'pull', 'gitea'])
                self.assertEqual(args[args.index('--ca-file') + 1], str(bundle))
                staging = Path(args[args.index('--destination') + 1])
                self.assertEqual(Path(args[args.index('--repository-cache') + 1]).parent, staging)
                self.assertEqual(kwargs['timeout'], 120)
                (staging / 'gitea-12.7.0.tgz').write_bytes(payload)
            with patch.object(server, 'STATE', root), \
                 patch.object(server, 'CHART_SHA256', hashlib.sha256(payload).hexdigest()), \
                 patch.object(server, 'run', side_effect=download) as pull:
                archive = server.chart(root)
                self.assertEqual(archive.read_bytes(), payload)
                self.assertEqual(server.chart(root), archive)
                pull.assert_called_once()

    def test_chart_download_checksum_failure_does_not_cache_payload(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            def download(args, **kwargs):
                (Path(args[args.index('--destination') + 1]) / 'gitea-12.7.0.tgz').write_bytes(b'wrong')
            with patch.object(server, 'run', side_effect=download):
                with self.assertRaisesRegex(ValueError, 'Downloaded Gitea chart differs'):
                    server.chart(root)
            self.assertFalse((root / 'gitea-12.7.0.tgz').exists())
            self.assertEqual(list(root.iterdir()), [])


class Client(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home with spaces'
        self.home.mkdir()
        self.paths = client.layout(self.home, UID)
        self.paths['directory'].mkdir(parents=True)

    def test_additive_config_retains_original_bytes_and_is_repeatable(self):
        config = self.home / '.ssh/config'
        original = b'# personal settings\r\nHost example\r\n  IdentityFile ~/.ssh/personal\r\n'
        config.write_bytes(original)
        private = self.home / '.ssh/personal'
        private.write_bytes(b'untouched personal key fixture')
        client.configure(self.home, self.paths, UID, KEY)
        result = config.read_bytes()
        self.assertTrue(result.endswith(original))
        self.assertEqual(result.count(b'Include '), 1)
        self.assertIn(b'UseKeychain yes', self.paths['config'].read_bytes())
        self.assertIn(b'StrictHostKeyChecking yes', self.paths['config'].read_bytes())
        client.configure(self.home, self.paths, UID, KEY)
        self.assertEqual(config.read_bytes(), result)
        self.assertEqual(private.read_bytes(), b'untouched personal key fixture')
        self.assertEqual(len(list(self.paths['directory'].glob('config-before-*'))), 1)

    def test_new_cluster_uses_a_new_key_and_retains_old_files(self):
        client.configure(self.home, self.paths, UID, KEY)
        other = client.layout(self.home, '87654321-1234-1234-1234-123456789abc')
        client.configure(self.home, other, '87654321-1234-1234-1234-123456789abc', OTHER)
        self.assertNotEqual(self.paths['key'], other['key'])
        self.assertTrue(self.paths['config'].exists())
        self.assertTrue(other['config'].exists())

    def test_existing_host_trust_or_managed_config_is_never_overwritten(self):
        client.configure(self.home, self.paths, UID, KEY)
        with self.assertRaisesRegex(ValueError, 'Existing SSH file differs'):
            client.configure(self.home, self.paths, UID, OTHER)
        self.paths['config'].write_bytes(b'custom user edits')
        with self.assertRaisesRegex(ValueError, 'Existing SSH file differs'):
            client.configure(self.home, self.paths, UID, KEY)

    def test_existing_user_alias_is_not_overridden(self):
        config = self.home / '.ssh/config'
        config.write_bytes(b'Host relevance-lab-gitea\n  HostName another-host\n')
        before = config.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already has user settings'):
            client.configure(self.home, self.paths, UID, KEY)
        self.assertEqual(config.read_bytes(), before)

    def test_noninteractive_new_key_and_partial_key_are_refused(self):
        with patch.object(client.sys.stdin, 'isatty', return_value=False):
            with self.assertRaisesRegex(ValueError, 'Terminal'):
                client.preflight(self.paths)
        self.paths['key'].write_bytes(b'partial')
        with self.assertRaisesRegex(ValueError, 'half of the lab key pair'):
            client.preflight(self.paths)

    def test_managed_symlink_is_not_followed(self):
        with patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaisesRegex(ValueError, 'symbolic link'):
                client.retain(self.paths['key'], b'not written')
        self.assertFalse(self.paths['key'].exists())

    def test_key_registration_reuses_existing_public_key(self):
        account = {'username': 'fixture', 'gitea_password': 'fixture-secret'}
        with patch.object(client, 'user_api', side_effect=[{'login': 'fixture'},
                     [{'id': 9, 'key': KEY, 'title': 'existing'}]]) as api:
            self.assertEqual(client.register(account, UID, KEY), 9)
            self.assertEqual(api.call_count, 2)

    def test_key_registration_never_replaces_a_different_key(self):
        account = {'username': 'fixture'}
        with patch.object(client, 'user_api', side_effect=[{'login': 'fixture'},
                     [{'id': 9, 'key': OTHER, 'title': 'relevance-lab-' + UID}]]) as api:
            with self.assertRaisesRegex(ValueError, 'another key'):
                client.register(account, UID, KEY)
            self.assertEqual(api.call_count, 2)

    def test_keychain_uses_apple_client_without_passphrase_arguments(self):
        with patch.object(client.subprocess, 'run', side_effect=[
                SimpleNamespace(returncode=1, stdout=''), SimpleNamespace(returncode=0)]) as run:
            client.load_key(self.paths, {'ssh-add': '/usr/bin/ssh-add'}, KEY)
            self.assertEqual(run.call_args.args[0],
                             ['/usr/bin/ssh-add', '--apple-use-keychain', str(self.paths['key'])])

    def test_loaded_key_is_not_added_or_prompted_for_again(self):
        with patch.object(client.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout='256 ' + server.fingerprint(KEY) + ' fixture')) as run:
            client.load_key(self.paths, {'ssh-add': '/usr/bin/ssh-add'}, KEY)
            self.assertEqual(run.call_count, 1)

    def test_unencrypted_existing_key_is_rejected_without_replacing_it(self):
        key = self.paths['key']
        key.write_bytes(b'fixture private key')
        with patch.object(client.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
            with self.assertRaisesRegex(ValueError, 'no passphrase'):
                client.key_pair(self.paths, {'ssh-keygen': 'ssh-keygen'}, 'fixture')
        self.assertEqual(key.read_bytes(), b'fixture private key')

    def test_git_verification_is_noninteractive_and_uses_only_ssh_alias(self):
        with patch.dict(client.os.environ, {'GIT_SSH_COMMAND': 'unrelated-user-wrapper'}), \
             patch.object(client.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout='a' * 40 + '\tHEAD\n')) as run:
            self.assertEqual(client.verify({'git': 'git', 'ssh': 'ssh'}), 'a' * 40)
            args = run.call_args.args[0]
            self.assertIn(client.ALIAS + ':elastic-agent/delivery-source.git', args)
            self.assertIn('core.sshCommand=ssh -o BatchMode=yes -o ConnectTimeout=10', args)
            self.assertEqual(run.call_args.kwargs['env']['GIT_TERMINAL_PROMPT'], '0')
            self.assertNotIn('GIT_SSH_COMMAND', run.call_args.kwargs['env'])


if __name__ == '__main__':
    unittest.main()
