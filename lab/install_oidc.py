"""Install a persistent local OIDC provider and native Headlamp/Argo sign-in."""
import argparse
import json
import os
import secrets
import ssl
import time
from urllib import request, parse

import yaml
from common import STATE, ROOT, HELM, apply, guard, k, run
from https_ingress import certificate, route
from install_preview_urls import corefile
from keyvault import external_secret, floci_forward, read_secret, seed, source_name, value_of, vault_request

NAMESPACE = 'lab-identity'
HOST = 'identity.localhost'
URL = 'https://' + HOST + ':34443'
ISSUER = URL + '/realms/relevance-lab'
SERVER = 'k3d-relevance-lab-server-0'
STATE_DIR = STATE / 'oidc'
KEYCLOAK_IMAGE = 'quay.io/keycloak/keycloak:26.6.4@sha256:0aae0de7fca85525f727d3354df17896092de8bb26ae4c12d89c77e5df8cbce4'
POSTGRES_IMAGE = 'postgres:17.6-alpine@sha256:ef257d85f76e48da1c64832459b59fcaba1a4dac97bf5d7450c77753542eee94'


def save_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    if os.name != 'nt':
        path.chmod(0o600)


def bootstrap():
    path = STATE_DIR / 'bootstrap.json'
    if not path.exists():
        save_private(path, {'username': 'bootstrap-admin', 'password': secrets.token_urlsafe(24)})
    return json.loads(path.read_bytes())


def vault_secret(namespace, name, keys):
    existing = read_secret(namespace, name)
    with floci_forward() as base:
        for key in keys:
            stored = vault_request(base, source_name(namespace, name, key))
            value = value_of(existing, key) if existing else stored['value'] if stored else secrets.token_urlsafe(32)
            seed(base, source_name(namespace, name, key), value)
    external_secret(namespace, name, keys, labels={'app.kubernetes.io/part-of': 'argocd'}
                    if namespace == 'argocd' else None)
    return read_secret(namespace, name)


def realm():
    groups = {'name': 'groups', 'protocol': 'openid-connect',
              'protocolMapper': 'oidc-group-membership-mapper',
              'config': {'claim.name': 'groups', 'full.path': 'false',
                         'id.token.claim': 'true', 'access.token.claim': 'true',
                         'userinfo.token.claim': 'true'}}
    clients = []
    for client, redirect, secret in [
        ('headlamp', 'https://headlamp.localhost:34443/oidc-callback', '${HEADLAMP_CLIENT_SECRET}'),
        ('argocd', 'https://argocd.localhost:34443/auth/callback', '${ARGOCD_CLIENT_SECRET}')]:
        clients.append({'clientId': client, 'protocol': 'openid-connect', 'enabled': True,
                        'publicClient': False, 'secret': secret, 'standardFlowEnabled': True,
                        'directAccessGrantsEnabled': False, 'redirectUris': [redirect],
                        'webOrigins': [redirect.split('/')[0] + '//' + redirect.split('/')[2]],
                        'protocolMappers': [groups],
                        'attributes': {'pkce.code.challenge.method': 'S256'} if client == 'headlamp' else {}})
    return {'realm': 'relevance-lab', 'enabled': True, 'registrationAllowed': False,
            'sslRequired': 'external', 'resetPasswordAllowed': False,
            'loginWithEmailAllowed': False, 'accessTokenLifespan': 300,
            'ssoSessionIdleTimeout': 3600, 'ssoSessionMaxLifespan': 43200,
            'groups': [{'name': name} for name in ('lab-admins', 'lab-readers')],
            'clients': clients}


def deploy_provider():
    apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE}})
    vault_secret(NAMESPACE, 'keycloak-database', ['password'])
    clients = {}
    for namespace, client in [('lab-headlamp', 'headlamp'), ('argocd', 'argocd')]:
        clients[client] = vault_secret(namespace, 'lab-oidc-client', ['clientSecret'])
    admin = bootstrap()
    apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'keycloak-bootstrap', 'namespace': NAMESPACE},
           'stringData': admin})
    # Client import placeholders are expanded by Keycloak from Secret-backed environment variables.
    with floci_forward() as base:
        for key, client in [('headlamp', 'headlamp'), ('argocd', 'argocd')]:
            seed(base, source_name(NAMESPACE, 'keycloak-clients', key),
                 value_of(clients[client], 'clientSecret'))
    external_secret(NAMESPACE, 'keycloak-clients', ['headlamp', 'argocd'])
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'keycloak-realm', 'namespace': NAMESPACE},
           'data': {'relevance-lab.json': json.dumps(realm())}})
    apply({'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim',
           'metadata': {'name': 'keycloak-database', 'namespace': NAMESPACE},
           'spec': {'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': '1Gi'}}}})
    def secret_env(name, secret, key):
        return {'name': name, 'valueFrom': {'secretKeyRef': {'name': secret, 'key': key}}}
    def deployment(name, container, volumes=None):
        return {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': name, 'namespace': NAMESPACE},
                'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'},
                         'selector': {'matchLabels': {'app': name}},
                         'template': {'metadata': {'labels': {'app': name}},
                                      'spec': {'nodeSelector': {'kubernetes.io/hostname': 'k3d-relevance-lab-agent-0'},
                                               'containers': [container], 'volumes': volumes or []}}}}
    apply(deployment('keycloak-database', {'name': 'postgres', 'image': POSTGRES_IMAGE,
        'env': [{'name': 'POSTGRES_DB', 'value': 'keycloak'}, {'name': 'POSTGRES_USER', 'value': 'keycloak'},
                {'name': 'PGDATA', 'value': '/var/lib/postgresql/data/pgdata'},
                secret_env('POSTGRES_PASSWORD', 'keycloak-database', 'password')],
        'ports': [{'containerPort': 5432}], 'resources': {'requests': {'cpu': '50m', 'memory': '64Mi'},
                                                       'limits': {'cpu': '500m', 'memory': '256Mi'}},
        'readinessProbe': {'exec': {'command': ['pg_isready', '-U', 'keycloak', '-d', 'keycloak']}},
        'volumeMounts': [{'name': 'data', 'mountPath': '/var/lib/postgresql/data'}]},
        [{'name': 'data', 'persistentVolumeClaim': {'claimName': 'keycloak-database'}}]))
    apply({'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'keycloak-database', 'namespace': NAMESPACE},
           'spec': {'selector': {'app': 'keycloak-database'}, 'ports': [{'port': 5432}]}})
    apply(deployment('keycloak', {'name': 'keycloak', 'image': KEYCLOAK_IMAGE,
        'args': ['start', '--import-realm'],
        'env': [{'name': 'KC_DB', 'value': 'postgres'},
                {'name': 'KC_DB_URL', 'value': 'jdbc:postgresql://keycloak-database/keycloak'},
                {'name': 'KC_DB_USERNAME', 'value': 'keycloak'},
                secret_env('KC_DB_PASSWORD', 'keycloak-database', 'password'),
                secret_env('KC_BOOTSTRAP_ADMIN_USERNAME', 'keycloak-bootstrap', 'username'),
                secret_env('KC_BOOTSTRAP_ADMIN_PASSWORD', 'keycloak-bootstrap', 'password'),
                secret_env('HEADLAMP_CLIENT_SECRET', 'keycloak-clients', 'headlamp'),
                secret_env('ARGOCD_CLIENT_SECRET', 'keycloak-clients', 'argocd'),
                {'name': 'KC_HOSTNAME', 'value': URL}, {'name': 'KC_HTTP_ENABLED', 'value': 'true'},
                {'name': 'KC_PROXY_HEADERS', 'value': 'xforwarded'},
                {'name': 'KC_HEALTH_ENABLED', 'value': 'true'},
                {'name': 'JAVA_OPTS_KC_HEAP', 'value': '-Xms128m -Xmx512m'}],
        'ports': [{'containerPort': 8080}, {'containerPort': 9000}],
        'resources': {'requests': {'cpu': '100m', 'memory': '384Mi'}, 'limits': {'cpu': '1500m', 'memory': '1Gi'}},
        'startupProbe': {'httpGet': {'path': '/health/ready', 'port': 9000}, 'failureThreshold': 90, 'periodSeconds': 5},
        'readinessProbe': {'httpGet': {'path': '/health/ready', 'port': 9000}},
        'volumeMounts': [{'name': 'realm', 'mountPath': '/opt/keycloak/data/import', 'readOnly': True}]},
        [{'name': 'realm', 'configMap': {'name': 'keycloak-realm'}}]))
    apply({'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'keycloak', 'namespace': NAMESPACE},
           'spec': {'selector': {'app': 'keycloak'}, 'ports': [{'port': 8080}]}})
    for name, port, source in [('keycloak', 8080, {'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': 'lab-ingress'}}}),
                               ('keycloak-database', 5432, {'podSelector': {'matchLabels': {'app': 'keycloak'}}})]:
        apply({'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
               'metadata': {'name': name, 'namespace': NAMESPACE},
               'spec': {'podSelector': {'matchLabels': {'app': name}}, 'policyTypes': ['Ingress'],
                        'ingress': [{'from': [source], 'ports': [{'protocol': 'TCP', 'port': port}]}]}})
    k('rollout', 'status', 'deployment/keycloak', '-n', NAMESPACE, '--timeout=450s')


def connectivity():
    cert, key, ca = certificate()
    route(cert, key)
    apply({'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'lab-oidc-edge', 'namespace': 'lab-ingress'},
           'spec': {'selector': {'app.kubernetes.io/instance': 'lab-traefik-lab-ingress', 'app.kubernetes.io/name': 'traefik'},
                    'ports': [{'name': 'https', 'port': 34443, 'targetPort': 8443}]}})
    edge = json.loads(k('get', 'svc/lab-oidc-edge', '-n', 'lab-ingress', '-o', 'json').stdout)['spec']['clusterIP']
    k('patch', 'configmap/lab-preview-code', '-n', 'lab-ingress', '--type=merge',
      '-p', json.dumps({'data': {'Corefile': corefile()}}))
    k('rollout', 'restart', 'deployment/lab-dns', '-n', 'lab-ingress')
    k('rollout', 'status', 'deployment/lab-dns', '-n', 'lab-ingress', '--timeout=120s')
    return edge, ca


def api(path, method='GET', body=None, token=None, form=None):
    data = parse.urlencode(form).encode() if form is not None else None if body is None else json.dumps(body).encode()
    headers = {'Content-Type': 'application/x-www-form-urlencoded' if form is not None else 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = request.Request(URL + path, data=data, headers=headers, method=method)
    with request.urlopen(req, context=ssl.create_default_context(cafile=str(STATE / 'https-ingress/root.pem')), timeout=30) as response:
        payload = response.read()
        return json.loads(payload) if payload else None


def admin_token():
    return api('/realms/master/protocol/openid-connect/token', 'POST',
               form={'grant_type': 'password', 'client_id': 'admin-cli', **bootstrap()})['access_token']


def reconcile_realm():
    """Reconcile owned realm settings and clients without resetting users or secrets."""
    token = admin_token()
    desired = realm()
    api('/admin/realms/relevance-lab', 'PUT',
        {key: value for key, value in desired.items() if key not in ('clients', 'groups')}, token)
    existing_groups = {g['name'] for g in api('/admin/realms/relevance-lab/groups', token=token)}
    for group in desired['groups']:
        if group['name'] not in existing_groups:
            api('/admin/realms/relevance-lab/groups', 'POST', group, token)
    for definition, namespace in zip(desired['clients'], ('lab-headlamp', 'argocd')):
        found = api('/admin/realms/relevance-lab/clients?' + parse.urlencode({'clientId': definition['clientId']}), token=token)
        if not found:
            raise ValueError('Managed OIDC client missing; inspect realm before continuing.')
        current = found[0]
        definition['secret'] = value_of(read_secret(namespace, 'lab-oidc-client'), 'clientSecret')
        mapper_ids = {m['name']: m['id'] for m in current.get('protocolMappers', [])}
        for mapper in definition['protocolMappers']:
            if mapper['name'] in mapper_ids:
                mapper['id'] = mapper_ids[mapper['name']]
        api('/admin/realms/relevance-lab/clients/' + current['id'], 'PUT', {**current, **definition}, token)


def create_users():
    token = admin_token()
    credentials_path = STATE_DIR / 'users.json'
    credentials = json.loads(credentials_path.read_bytes()) if credentials_path.exists() else {}
    groups = {g['name']: g['id'] for g in api('/admin/realms/relevance-lab/groups', token=token)}
    owner = json.loads((STATE / 'user-credentials.json').read_bytes())['username']
    for name, group in [(owner, 'lab-admins'), ('lab-reader', 'lab-readers')]:
        found = api('/admin/realms/relevance-lab/users?' + parse.urlencode({'username': name, 'exact': 'true'}), token=token)
        if not found:
            password = secrets.token_urlsafe(20)
            api('/admin/realms/relevance-lab/users', 'POST', {'username': name, 'enabled': True,
                'firstName': name, 'lastName': 'Lab', 'email': name + '@lab.invalid', 'emailVerified': True,
                'credentials': [{'type': 'password', 'value': password, 'temporary': True}]}, token)
            credentials[name] = {'username': name, 'password': password, 'group': group, 'temporary': True}
            save_private(credentials_path, credentials)
            found = api('/admin/realms/relevance-lab/users?' + parse.urlencode({'username': name, 'exact': 'true'}), token=token)
        api('/admin/realms/relevance-lab/users/' + found[0]['id'] + '/groups/' + groups[group], 'PUT', token=token)


def server_configuration(edge, ca):
    """Keep existing k3s settings and volumes; restart only after a real change."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    old = run(['docker', 'exec', SERVER, 'sh', '-c', 'cat /etc/rancher/k3s/config.yaml 2>/dev/null || true']).stdout
    configuration = yaml.safe_load(old) or {}
    args = configuration.get('kube-apiserver-arg', [])
    if isinstance(args, str):
        args = [args]
    issuers = [a.split('=', 1)[1] for a in args if a.startswith('oidc-issuer-url=')]
    if any(issuer != ISSUER for issuer in issuers):
        raise ValueError('Another OIDC issuer is configured; review it before installing lab identity.')
    retained = [a for a in args if not a.startswith('oidc-')]
    new = ['oidc-issuer-url=' + ISSUER, 'oidc-client-id=headlamp',
           'oidc-ca-file=/etc/rancher/k3s/lab-oidc-ca.pem', 'oidc-username-claim=sub',
           'oidc-username-prefix=lab-oidc:', 'oidc-groups-claim=groups', 'oidc-groups-prefix=lab-oidc:']
    configuration['kube-apiserver-arg'] = retained + new
    desired = yaml.safe_dump(configuration)
    hosts = run(['docker', 'exec', SERVER, 'cat', '/etc/hosts']).stdout
    updated = '\n'.join(line for line in hosts.splitlines() if not line.endswith('# relevance-lab-oidc')) + '\n' + edge + ' ' + HOST + ' # relevance-lab-oidc\n'
    hosts_file = STATE_DIR / 'server-hosts'
    hosts_file.write_text(updated, encoding='utf-8')
    run(['docker', 'cp', str(hosts_file), SERVER + ':/tmp/lab-oidc-hosts'])
    run(['docker', 'exec', SERVER, 'sh', '-c', 'cat /tmp/lab-oidc-hosts > /etc/hosts'])
    config_file = STATE_DIR / 'server-config.yaml'
    config_file.write_text(desired, encoding='utf-8')
    changed = configuration != (yaml.safe_load(old) or {})
    if changed:
        (STATE_DIR / 'server-config-before.yaml').write_text(old, encoding='utf-8')
        run(['docker', 'cp', str(ca), SERVER + ':/etc/rancher/k3s/lab-oidc-ca.pem'])
        run(['docker', 'cp', str(config_file), SERVER + ':/etc/rancher/k3s/config.yaml'])
        run(['docker', 'restart', SERVER])
        # Docker owns /etc/hosts; reapply this internal resolution after restart.
        run(['docker', 'exec', SERVER, 'sh', '-c', 'cat /tmp/lab-oidc-hosts > /etc/hosts'])
        for _ in range(90):
            if k('get', '--raw=/readyz', check=False).stdout.strip() == 'ok':
                break
            time.sleep(2)
        else:
            raise TimeoutError('API server did not become ready; see OIDC recovery guide.')
    for group, role in [('lab-admins', 'cluster-admin'), ('lab-readers', 'view')]:
        apply({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding',
               'metadata': {'name': 'oidc-' + group},
               'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': role},
               'subjects': [{'kind': 'Group', 'name': 'lab-oidc:' + group, 'apiGroup': 'rbac.authorization.k8s.io'}]})
    return changed


def headlamp_values(edge):
    values = yaml.safe_load((ROOT / 'lab/headlamp-values.yaml').read_text(encoding='utf-8'))
    values['env'] = [{'name': 'HEADLAMP_CONFIG_OIDC_CLIENT_ID', 'value': 'headlamp'},
                    {'name': 'HEADLAMP_CONFIG_OIDC_CLIENT_SECRET', 'valueFrom': {'secretKeyRef': {'name': 'lab-oidc-client', 'key': 'clientSecret'}}},
                    {'name': 'HEADLAMP_CONFIG_OIDC_IDP_ISSUER_URL', 'value': ISSUER},
                    {'name': 'HEADLAMP_CONFIG_OIDC_SCOPES', 'value': 'profile,email'},
                    {'name': 'SSL_CERT_FILE', 'value': '/etc/lab-oidc/root.pem'}]
    values['config']['oidc'].update(usePKCE=True, callbackURL='https://headlamp.localhost:34443/oidc-callback')
    values['volumes'] = [{'name': 'oidc-ca', 'configMap': {'name': 'lab-oidc-ca'}}]
    values['volumeMounts'] = [{'name': 'oidc-ca', 'mountPath': '/etc/lab-oidc', 'readOnly': True}]
    values['hostAliases'] = [{'ip': edge, 'hostnames': [HOST]}]
    return values


def reconcile_headlamp(edge=None):
    if edge is None:
        edge = json.loads(k('get', 'svc/lab-oidc-edge', '-n', 'lab-ingress', '-o', 'json').stdout)['spec']['clusterIP']
    file = STATE_DIR / 'headlamp-values.yaml'
    file.write_text(yaml.safe_dump(headlamp_values(edge)), encoding='utf-8')
    run([HELM, 'upgrade', 'headlamp', 'headlamp', '--repo', 'https://kubernetes-sigs.github.io/headlamp/',
         '--version', '0.45.0', '-n', 'lab-headlamp', '-f', str(file), '--kubeconfig', str(STATE / 'kubeconfig.yaml')])


def applications(edge, ca):
    aliases = [{'ip': edge, 'hostnames': [HOST]}]
    for namespace in ('lab-headlamp', 'argocd'):
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'lab-oidc-ca', 'namespace': namespace},
               'data': {'root.pem': ca.read_text(encoding='ascii')}})
    reconcile_headlamp(edge)
    oidc = {'name': 'Lab identity', 'issuer': ISSUER, 'clientID': 'argocd',
            'clientSecret': '$lab-oidc-client:clientSecret',
            'requestedScopes': ['openid', 'profile', 'email'], 'rootCA': ca.read_text(encoding='ascii')}
    k('patch', 'configmap/argocd-cm', '-n', 'argocd', '--type=merge', '-p',
      json.dumps({'data': {'url': 'https://argocd.localhost:34443', 'oidc.config': yaml.safe_dump(oidc)}}))
    current = json.loads(k('get', 'configmap/argocd-rbac-cm', '-n', 'argocd', '-o', 'json').stdout).get('data', {})
    rules = '\n'.join(line for line in current.get('policy.csv', '').splitlines()
                      if not line.startswith(('g, lab-admins,', 'g, lab-readers,')))
    current.update({'policy.csv': rules + '\ng, lab-admins, role:admin\ng, lab-readers, role:readonly\n',
                    'scopes': '[groups]', 'policy.default': 'role:unauthenticated'})
    k('patch', 'configmap/argocd-rbac-cm', '-n', 'argocd', '--type=merge', '-p', json.dumps({'data': current}))
    k('patch', 'deployment/argocd-server', '-n', 'argocd', '--type=merge',
      '-p', json.dumps({'spec': {'template': {'spec': {'hostAliases': aliases}}}}))
    for namespace, name in [('lab-headlamp', 'headlamp'), ('argocd', 'argocd-server')]:
        k('rollout', 'status', 'deployment/' + name, '-n', namespace, '--timeout=180s')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'credentials'])
    parser.add_argument('--user', help='Named account; required when explicitly displaying credentials')
    args = parser.parse_args()
    if args.action == 'credentials':
        if not args.user:
            parser.error('--user is required')
        data = bootstrap() if args.user == 'bootstrap-admin' else json.loads((STATE_DIR / 'users.json').read_bytes())[args.user]
        print(json.dumps(data, indent=2))
        return
    guard()
    deploy_provider()
    edge, ca = connectivity()
    reconcile_realm()
    create_users()
    changed = server_configuration(edge, ca)
    applications(edge, ca)
    print(json.dumps({'issuer': ISSUER, 'keycloak': URL, 'headlamp': 'https://headlamp.localhost:34443',
                      'argocd': 'https://argocd.localhost:34443', 'server_restarted': changed,
                      'credentials': 'python lab/install_oidc.py credentials --user <account>'}))


if __name__ == '__main__':
    main()
