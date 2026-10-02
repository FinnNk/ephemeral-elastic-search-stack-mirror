"""Reconcile HTTPS routes for search services without changing frozen releases."""

import json
from pathlib import Path
import re
import ssl
import time
import urllib.error
import urllib.request

DOMAIN = 'preview.relevance.test'
OWNER = {'app.kubernetes.io/managed-by': 'lab-preview-routes'}
NAME = 'lab-preview'


def url(namespace):
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', namespace):
        raise ValueError('Invalid preview namespace.')
    return f'https://{namespace}.{DOMAIN}:34443/'


class Kubernetes:
    def __init__(self):
        self.account = Path('/var/run/secrets/kubernetes.io/serviceaccount')
        self.context = ssl.create_default_context(cafile=str(self.account / 'ca.crt'))

    def request(self, path, method='GET', body=None):
        headers = {'Authorization': 'Bearer ' + (self.account / 'token').read_text().strip()}
        if body is not None:
            headers['Content-Type'] = 'application/merge-patch+json' if method == 'PATCH' else 'application/json'
        request = urllib.request.Request('https://kubernetes.default.svc' + path, method=method,
            headers=headers, data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(request, context=self.context, timeout=15) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise


def objects(namespace):
    metadata = {'name': NAME, 'namespace': namespace, 'labels': OWNER}
    host = url(namespace).split('://')[1].split(':')[0]
    return [
        {'apiVersion': 'networking.k8s.io/v1', 'kind': 'Ingress',
         'metadata': {**metadata, 'annotations': {
             'traefik.ingress.kubernetes.io/router.entrypoints': 'websecure'}},
         'spec': {'ingressClassName': 'traefik', 'tls': [{'hosts': [host]}],
                  'rules': [{'host': host, 'http': {'paths': [{'path': '/', 'pathType': 'Prefix',
                      'backend': {'service': {'name': 'search', 'port': {'number': 8080}}}}]}}]}},
        {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': metadata,
         'spec': {'podSelector': {'matchLabels': {'app': 'search'}}, 'policyTypes': ['Ingress'],
                  'ingress': [{'from': [{'namespaceSelector': {'matchLabels': {
                      'kubernetes.io/metadata.name': 'lab-ingress'}}, 'podSelector': {'matchLabels': {
                      'app.kubernetes.io/name': 'traefik'}}}],
                      'ports': [{'protocol': 'TCP', 'port': 8080}]}]}}
    ]


def reconcile(client):
    namespaces = client.request('/api/v1/namespaces?labelSelector=lab%3Dsearch-spike')['items']
    routes = []
    for namespace in namespaces:
        name = namespace['metadata']['name']
        if namespace.get('status', {}).get('phase') == 'Terminating':
            continue
        service = client.request(f'/api/v1/namespaces/{name}/services/search')
        enabled = bool(service and service['spec'].get('selector', {}).get('app') == 'search'
                       and any(port.get('port') == 8080 for port in service['spec'].get('ports', [])))
        for obj in objects(name):
            resource = 'ingresses' if obj['kind'] == 'Ingress' else 'networkpolicies'
            path = f'/apis/networking.k8s.io/v1/namespaces/{name}/{resource}'
            current = client.request(path + '/' + NAME)
            if current and current['metadata'].get('labels', {}).get('app.kubernetes.io/managed-by') != OWNER['app.kubernetes.io/managed-by']:
                raise ValueError(f'Refusing to adopt {name}/{resource}/{NAME}')
            if not enabled:
                if current:
                    client.request(path + '/' + NAME, 'DELETE')
            elif not current:
                client.request(path, 'POST', obj)
            elif current['spec'] != obj['spec']:
                client.request(path + '/' + NAME, 'PATCH', obj)
        if enabled:
            routes.append(url(name))
    return routes


def main():
    client = Kubernetes()
    while True:
        try:
            routes = reconcile(client)
            Path('/tmp/ready').touch()
            print(json.dumps({'preview_count': len(routes)}), flush=True)
        except Exception as error:
            print(json.dumps({'error': type(error).__name__, 'detail': str(error)}), flush=True)
        time.sleep(5)


if __name__ == '__main__':
    main()
