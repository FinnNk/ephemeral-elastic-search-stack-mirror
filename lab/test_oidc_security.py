"""Guard against replacing another provider or enabling password-grant clients."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from install_oidc import realm, server_configuration


class IdentitySecurity(unittest.TestCase):
    def test_foreign_issuer_prevents_server_mutation(self):
        previous = 'kube-apiserver-arg:\n- oidc-issuer-url=https://organisation.example/realm\n'
        with patch('install_oidc.run', return_value=SimpleNamespace(stdout=previous)) as process:
            with self.assertRaisesRegex(ValueError, 'Another OIDC issuer'):
                server_configuration('10.43.1.1', None)
            self.assertEqual(process.call_count, 1)

    def test_browser_clients_cannot_use_password_grants(self):
        clients = realm()['clients']
        self.assertEqual({client['clientId'] for client in clients}, {'headlamp', 'argocd'})
        for client in clients:
            self.assertFalse(client['directAccessGrantsEnabled'])
            self.assertFalse(client['publicClient'])
            self.assertTrue(all(uri.startswith('https://') and '*' not in uri for uri in client['redirectUris']))
        self.assertEqual(clients[0]['attributes']['pkce.code.challenge.method'], 'S256')


if __name__ == '__main__':
    unittest.main()
