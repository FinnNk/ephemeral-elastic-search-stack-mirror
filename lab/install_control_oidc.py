"""Install browser OIDC and upgrade the control runtime without replacing its state."""
import argparse
import json
import re
from urllib.parse import urlencode

from common import STATE, apply, guard, k
from https_ingress import certificate, route
from install_oidc import ISSUER, admin_token, api, realm, vault_secret
from keyvault import value_of

NAMESPACE = 'lab-control'
CLIENT = 'lab-control'
URL = 'https://control.localhost:34443'
PROXY = 'lab-control-oidc'
IMAGE = 'quay.io/oauth2-proxy/oauth2-proxy:v7.15.5@sha256:8498b0d0ef0a7b29686414000a08aee467f02d0299c9ed1e006a8f33fc017916'


def configure():
    secret = value_of(vault_secret(NAMESPACE, PROXY, ['clientSecret', 'cookieSecret']), 'clientSecret')
    token = admin_token()
    definition = {'clientId': CLIENT, 'protocol': 'openid-connect', 'enabled': True,
        'publicClient': False, 'secret': secret, 'standardFlowEnabled': True,
        'directAccessGrantsEnabled': False, 'redirectUris': [URL + '/oauth2/callback'],
        'webOrigins': [URL], 'protocolMappers': realm()['clients'][0]['protocolMappers'],
        'attributes': {'pkce.code.challenge.method': 'S256'}}
    found = api('/admin/realms/relevance-lab/clients?' + urlencode({'clientId': CLIENT}), token=token)
    if found:
        api('/admin/realms/relevance-lab/clients/' + found[0]['id'], 'PUT', {**found[0], **definition}, token)
    else:
        api('/admin/realms/relevance-lab/clients', 'POST', definition, token)
    edge = json.loads(k('get', 'service/lab-oidc-edge', '-n', 'lab-ingress', '-o', 'json').stdout)['spec']['clusterIP']
    aliases = [{'ip': edge, 'hostnames': ['identity.localhost']}]
    container = {'name': 'oauth2-proxy', 'image': IMAGE,
        'args': ['--http-address=0.0.0.0:4180', '--provider=oidc', '--provider-display-name=Lab identity',
            '--oidc-issuer-url=' + ISSUER, '--redirect-url=' + URL + '/oauth2/callback',
            '--client-id=' + CLIENT, '--scope=openid profile email', '--code-challenge-method=S256',
            '--insecure-oidc-skip-nonce=false', '--email-domain=*', '--oidc-groups-claim=groups',
            '--allowed-group=lab-admins', '--allowed-group=lab-readers', '--allowed-group=lab-delivery-actions',
            '--skip-jwt-bearer-tokens=true',
            '--upstream=http://lab-control.lab-control.svc.cluster.local:18082',
            '--reverse-proxy=true', '--pass-authorization-header=true', '--pass-basic-auth=false',
            '--pass-user-headers=false', '--skip-provider-button=true',
            '--cookie-name=__Host-lab-control', '--cookie-secure=true', '--cookie-httponly=true',
            '--cookie-samesite=lax', '--cookie-expire=1h', '--cookie-refresh=5m',
            '--request-logging=false', '--provider-ca-file=/etc/lab-ca/root.pem'],
        'env': [{'name': name, 'valueFrom': {'secretKeyRef': {'name': PROXY, 'key': key}}}
                for name, key in [('OAUTH2_PROXY_CLIENT_SECRET', 'clientSecret'), ('OAUTH2_PROXY_COOKIE_SECRET', 'cookieSecret')]],
        'ports': [{'containerPort': 4180}],
        'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'}, 'limits': {'cpu': '500m', 'memory': '128Mi'}},
        'readinessProbe': {'httpGet': {'path': '/ready', 'port': 4180}},
        'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                            'capabilities': {'drop': ['ALL']}},
        'volumeMounts': [{'name': 'ca', 'mountPath': '/etc/lab-ca', 'readOnly': True}]}
    apply({'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': PROXY, 'namespace': NAMESPACE},
        'spec': {'replicas': 1, 'selector': {'matchLabels': {'app': PROXY}}, 'template': {
            'metadata': {'labels': {'app': PROXY}}, 'spec': {'automountServiceAccountToken': False,
                'hostAliases': aliases, 'containers': [container],
                'volumes': [{'name': 'ca', 'configMap': {'name': 'lab-internal-ca'}}]}}}})
    apply({'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': PROXY, 'namespace': NAMESPACE},
           'spec': {'selector': {'app': PROXY}, 'ports': [{'port': 4180}]}})
    apply({'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
        'metadata': {'name': PROXY, 'namespace': NAMESPACE}, 'spec': {
            'podSelector': {'matchLabels': {'app': PROXY}}, 'policyTypes': ['Ingress'],
            'ingress': [{'from': [{'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': 'lab-ingress'}}}],
                         'ports': [{'protocol': 'TCP', 'port': 4180}]}]}})
    k('rollout', 'status', 'deployment/' + PROXY, '-n', NAMESPACE, '--timeout=180s')
    return aliases


def install(image):
    guard()
    if not re.fullmatch(r'nexus\.localhost:18185/lab-control@sha256:[a-f0-9]{64}', image):
        raise ValueError('Use a published digest-pinned control image.')
    # Configure the proxy before changing the running API or its route.
    aliases = configure()
    before = json.loads(k('get', 'deployment/lab-control', '-n', NAMESPACE, '-o', 'json').stdout)
    aliases = [row for row in before['spec']['template']['spec'].get('hostAliases', [])
               if 'identity.localhost' not in row.get('hostnames', [])] + aliases
    snapshot = STATE / 'oidc/control-before.json'
    snapshot.write_text(json.dumps(before), encoding='utf-8')
    # Drain and wait for existing operations; the SQLite database stays on its PVC.
    k('exec', 'deployment/lab-control', '-n', NAMESPACE, '-c', 'api', '--', 'touch', '/state/control-drain')
    idle_script = ("import sqlite3,socket; c=sqlite3.connect('/state/lifecycle.sqlite3'); "
        "a=c.execute(\"select count(*) from environments where state in ('requested','provisioning','deleting')\").fetchone()[0]; "
        "b=c.execute(\"select count(*) from comparisons where state='running'\").fetchone()[0]; "
        "s=socket.socket(); s.bind(('127.0.0.1',18086)); print(a,b)")
    idle = k('exec', 'deployment/lab-control', '-n', NAMESPACE, '-c', 'api', '--', 'python', '-c', idle_script, check=False)
    if idle.returncode or idle.stdout.strip() != '0 0':
        k('exec', 'deployment/lab-control', '-n', NAMESPACE, '-c', 'api', '--', 'rm', '-f', '/state/control-drain')
        raise RuntimeError('Control operations are active; retry once they finish.')
    try:
        config = json.loads(k('get', 'configmap/lab-control-config', '-n', NAMESPACE, '-o', 'json').stdout)
        config['data'].update({'LAB_OIDC_ISSUER': ISSUER, 'LAB_OIDC_AUDIENCE': CLIENT,
            'LAB_OIDC_CA_FILE': '/etc/lab-ca/root.pem', 'LAB_CONTROL_PUBLIC_URL': URL})
        apply(config)
        patch = {'spec': {'template': {'spec': {'hostAliases': aliases,
            'containers': [{'name': c['name'], 'image': image} for c in before['spec']['template']['spec']['containers']]}}}}
        # Remove the drain before the Recreate rollout releases the old Pod.
        k('exec', 'deployment/lab-control', '-n', NAMESPACE, '-c', 'api', '--', 'rm', '-f', '/state/control-drain')
        k('patch', 'deployment/lab-control', '-n', NAMESPACE, '--type=strategic', '-p', json.dumps(patch))
        k('rollout', 'status', 'deployment/lab-control', '-n', NAMESPACE, '--timeout=240s')
        after = json.loads(k('get', 'deployment/lab-control', '-n', NAMESPACE, '-o', 'json').stdout)
        assert before['metadata']['uid'] == after['metadata']['uid']
        assert before['spec']['template']['spec']['volumes'] == after['spec']['template']['spec']['volumes']
        route(*certificate()[:2], browser_names=('control',))
        print(URL)
    finally:
        k('exec', 'deployment/lab-control', '-n', NAMESPACE, '-c', 'api', '--', 'rm', '-f', '/state/control-drain', check=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    install(parser.parse_args().image)
