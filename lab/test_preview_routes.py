"""Check route ownership, lifecycle and URL publication without cluster changes."""
import copy
import unittest

from control_api import environment_view
from preview_routes import OWNER, objects, reconcile, url


class Client:
    def __init__(self):
        self.resources = {}
        self.service = {'spec': {'selector': {'app': 'search'}, 'ports': [{'port': 8080}]}}
        self.calls = []

    def request(self, path, method='GET', body=None):
        self.calls.append((method, path))
        if path.startswith('/api/v1/namespaces?'):
            return {'items': [{'metadata': {'name': 'lab-test'}, 'status': {'phase': 'Active'}}]}
        if path.endswith('/services/search'):
            return self.service
        if method == 'POST':
            self.resources[path + '/lab-preview'] = copy.deepcopy(body)
        elif method == 'PATCH':
            self.resources[path] = copy.deepcopy(body)
        elif method == 'DELETE':
            self.resources.pop(path)
        return self.resources.get(path)


class PreviewRoutes(unittest.TestCase):
    def test_create_repeat_remove_and_recreate(self):
        client = Client()
        self.assertEqual(reconcile(client), [url('lab-test')])
        self.assertEqual(len(client.resources), 2)
        client.calls.clear()
        reconcile(client)
        self.assertTrue(all(method == 'GET' for method, _ in client.calls))
        saved = client.service
        client.service = None
        self.assertEqual(reconcile(client), [])
        self.assertEqual(client.resources, {})
        client.service = saved
        reconcile(client)
        self.assertEqual(len(client.resources), 2)

    def test_foreign_route_is_not_adopted(self):
        client = Client()
        ingress = objects('lab-test')[0]
        ingress['metadata']['labels'] = {'app.kubernetes.io/managed-by': 'another-controller'}
        client.resources['/apis/networking.k8s.io/v1/namespaces/lab-test/ingresses/lab-preview'] = ingress
        with self.assertRaisesRegex(ValueError, 'Refusing to adopt'):
            reconcile(client)
        self.assertEqual(len(client.resources), 1)

    def test_only_search_service_port_is_eligible(self):
        client = Client()
        client.service['spec']['ports'] = [{'port': 9000}]
        self.assertEqual(reconcile(client), [])
        self.assertFalse(client.resources)

    def test_ready_card_has_url_but_deleted_card_does_not(self):
        self.assertEqual(environment_view({'name': 'lab-test', 'state': 'ready'})['browser_url'], url('lab-test'))
        self.assertIsNone(environment_view({'name': 'lab-test', 'state': 'deleted'})['browser_url'])
        for invalid in ('../other', 'bad.name', 'A', 'x' * 64):
            with self.assertRaises(ValueError):
                url(invalid)


if __name__ == '__main__':
    unittest.main()
