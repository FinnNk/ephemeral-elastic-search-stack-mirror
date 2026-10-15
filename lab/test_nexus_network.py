"""Installer wiring for automatic Nexus route repair."""
import unittest
from unittest.mock import patch

import setup_nexus as nexus


class NexusNetwork(unittest.TestCase):
    def test_install_streams_unix_script_and_uses_existing_node_hook(self):
        with patch.object(nexus, 'docker', return_value='/bin/k3d-entrypoint-*.sh') as command:
            nexus.install_route_reconciler()
        calls = command.call_args_list
        self.assertEqual(len(calls), 4)
        import base64
        script = base64.b64decode(calls[1].kwargs['body']).decode('utf-8')
        self.assertNotIn('\r', script)
        self.assertIn('start-stop-daemon', script)
        self.assertEqual(calls[-1].args[-1], '/bin/k3d-entrypoint-zz-lab-nexus.sh')

    def test_unknown_node_entrypoint_is_not_modified(self):
        with patch.object(nexus, 'docker', return_value='unexpected') as command:
            with self.assertRaisesRegex(RuntimeError, 'expected startup hook'):
                nexus.install_route_reconciler()
        self.assertEqual(command.call_count, 1)

    def test_network_setup_also_installs_restart_repair(self):
        import json
        details = [{'NetworkSettings': {'Networks': {nexus.NETWORK: {'IPAddress': '172.30.0.9'}}}}]
        with patch.object(nexus, 'docker', return_value=json.dumps(details)), \
             patch.object(nexus, 'apply'), patch.object(nexus, 'k'), \
             patch.object(nexus, 'configure_node_registries'), \
             patch.object(nexus, 'install_route_reconciler') as install:
            nexus.configure_network()
        install.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
