"""Check optional control permissions during fresh DNS installation."""
import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import install_preview_urls as setup


class PreviewInstallTests(unittest.TestCase):
    def test_missing_control_role_does_not_create_permissions(self):
        with patch.object(setup, 'k', return_value=SimpleNamespace(stdout='')) as command, \
             patch.object(setup, 'apply') as apply:
            setup.configure_control_role()
        command.assert_called_once_with('get', 'clusterrole/lab-control-namespace-manager',
                                        '-o', 'json', '--ignore-not-found')
        apply.assert_not_called()

    def test_existing_role_retains_unrelated_permissions_and_is_repeatable(self):
        role = {'rules': [
            {'resources': ['clusterroles'], 'verbs': ['bind'], 'resourceNames': ['lab-control-environment']},
            {'resources': ['namespaces'], 'verbs': ['create']}]}
        with patch.object(setup, 'k') as command, patch.object(setup, 'apply') as apply:
            command.return_value = SimpleNamespace(stdout=json.dumps(role))
            setup.configure_control_role()
            updated = copy.deepcopy(apply.call_args.args[0])
            command.return_value = SimpleNamespace(stdout=json.dumps(updated))
            setup.configure_control_role()
            self.assertEqual(apply.call_args.args[0], updated)
        self.assertEqual(updated['rules'][1], role['rules'][1])
        self.assertEqual(updated['rules'][0]['resourceNames'],
                         ['lab-control-environment', 'lab-preview-route-writer'])

    def test_api_failure_is_not_treated_as_absent_role(self):
        with patch.object(setup, 'k', side_effect=RuntimeError('Forbidden')), \
             patch.object(setup, 'apply') as apply:
            with self.assertRaisesRegex(RuntimeError, 'Forbidden'):
                setup.configure_control_role()
        apply.assert_not_called()


if __name__ == '__main__':
    unittest.main()
