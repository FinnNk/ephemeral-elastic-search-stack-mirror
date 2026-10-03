"""Add native OIDC sign-in while keeping existing Gitea accounts and roles."""
import json
from urllib.parse import urlencode
import yaml

from common import HELM, STATE, apply, guard, k, run
from install_oidc import ISSUER, admin_token, api, vault_secret
from keyvault import value_of

SOURCE = 'lab-identity'
CLIENT = 'gitea'
CALLBACK = 'https://gitea.localhost:34443/user/oauth2/' + SOURCE + '/callback'


def install():
    guard()
    token = admin_token()
    secret = value_of(vault_secret('platform', 'gitea-oidc-client', ['clientSecret']), 'clientSecret')
    definition = {'clientId': CLIENT, 'protocol': 'openid-connect', 'enabled': True,
        'publicClient': False, 'secret': secret, 'standardFlowEnabled': True,
        'directAccessGrantsEnabled': False, 'redirectUris': [CALLBACK],
        'webOrigins': ['https://gitea.localhost:34443']}
    found = api('/admin/realms/relevance-lab/clients?' + urlencode({'clientId': CLIENT}), token=token)
    if found:
        api('/admin/realms/relevance-lab/clients/' + found[0]['id'], 'PUT', {**found[0], **definition}, token)
    else:
        api('/admin/realms/relevance-lab/clients', 'POST', definition, token)
    edge = json.loads(k('get', 'service/lab-oidc-edge', '-n', 'lab-ingress', '-o', 'json').stdout)['spec']['clusterIP']
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap',
        'metadata': {'name': 'gitea-oidc-ca', 'namespace': 'platform'},
        'data': {'root.pem': (STATE / 'https-ingress/root.pem').read_text(encoding='ascii')}})
    # Read current values so existing storage, resources and runtime configuration survive.
    values = json.loads(run([HELM, 'get', 'values', 'gitea', '-n', 'platform',
        '--kubeconfig', str(STATE / 'kubeconfig.yaml'), '-o', 'json']).stdout)
    values.setdefault('gitea', {}).setdefault('config', {})['oauth2_client'] = {
        'ENABLE_AUTO_REGISTRATION': False, 'ACCOUNT_LINKING': 'login', 'USERNAME': 'preferred_username'}
    def upsert(rows, value, key='name'):
        rows[:] = [row for row in rows if row.get(key) != value[key]] + [value]
    upsert(values.setdefault('extraVolumes', []), {'name': 'oidc-ca', 'configMap': {'name': 'gitea-oidc-ca'}})
    upsert(values.setdefault('extraContainerVolumeMounts', []), {'name': 'oidc-ca', 'mountPath': '/etc/lab-oidc', 'readOnly': True})
    upsert(values.setdefault('deployment', {}).setdefault('env', []), {'name': 'SSL_CERT_FILE', 'value': '/etc/lab-oidc/root.pem'})
    aliases = values.setdefault('global', {}).setdefault('hostAliases', [])
    aliases[:] = [row for row in aliases if 'identity.localhost' not in row.get('hostnames', [])]
    aliases.append({'ip': edge, 'hostnames': ['identity.localhost']})
    path = STATE / 'oidc/gitea-values.yaml'
    path.write_text(yaml.safe_dump(values), encoding='utf-8')
    run([HELM, 'upgrade', 'gitea', 'gitea', '--repo', 'https://dl.gitea.com/charts/',
         '--version', '12.7.0', '-n', 'platform', '-f', str(path), '--wait', '--timeout', '5m',
         '--kubeconfig', str(STATE / 'kubeconfig.yaml')])
    listed = k('exec', '-n', 'platform', 'deployment/gitea', '-c', 'gitea', '--', 'gitea', 'admin', 'auth', 'list').stdout
    ids = [line.split()[0] for line in listed.splitlines() if SOURCE in line.split()]
    if len(ids) > 1:
        raise ValueError('Multiple managed Gitea authentication sources found.')
    args = ['exec', '-n', 'platform', 'deployment/gitea', '-c', 'gitea', '--', 'gitea', 'admin', 'auth',
            'update-oauth' if ids else 'add-oauth', '--name', SOURCE, '--provider', 'openidConnect',
            '--key', CLIENT, '--secret', secret, '--auto-discover-url', ISSUER + '/.well-known/openid-configuration',
            '--scopes', 'profile', '--scopes', 'email']
    if ids:
        args += ['--id', ids[0]]
    # Credentials are passed only to the Gitea process; never print command arguments or errors containing them.
    result = k(*args, check=False)
    if result.returncode:
        raise RuntimeError('Gitea OIDC source reconciliation failed; inspect the server with secret values redacted.')
    print('Gitea OIDC is configured: https://gitea.localhost:34443/user/login')
    print('First sign-in requires linking to your existing Gitea account. Automatic account matching is disabled.')


if __name__ == '__main__':
    install()
