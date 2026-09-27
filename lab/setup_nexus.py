"""Provision the lab's pinned Nexus/PostgreSQL services and scoped identities."""
import base64
import json
import secrets
import subprocess
import time
import urllib.error

from common import STATE, apply, guard, k, record
from nexus import CREDENTIALS, REGISTRY, api, request

NEXUS = 'sonatype/nexus3:3.96.3@sha256:a406f4e9dc149e050723a93bf57964311f6d1c88e1dcbed2e42ea373319a1772'
POSTGRES = 'postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24'
NETWORK = 'k3d-relevance-lab'


def docker(*args, body=None):
    result = subprocess.run(['docker', *args], input=body, capture_output=True,
                            text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Docker operation failed: ' + result.stderr[-1200:])
    return result.stdout.strip()


def ensure_container(name, image, args):
    names = docker('ps', '-a', '--format', '{{.Names}}').splitlines()
    if name not in names:
        docker('run', '-d', '--name', name, '--network', NETWORK,
               '--restart', 'unless-stopped', *args, image)
    else:
        details = json.loads(docker('inspect', name))[0]
        if details['Config']['Image'] != image:
            raise ValueError('Existing ' + name + ' uses a different image; inspect before upgrading.')
        if not details['State']['Running']:
            docker('start', name)


def wait_ready():
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            request('/service/rest/v1/status', identity={})
            return
        except (OSError, urllib.error.URLError):
            time.sleep(3)
    raise TimeoutError('Nexus did not become ready; inspect docker logs relevance-nexus.')


def ensure_services():
    if not CREDENTIALS.exists():
        value = {key: {'username': username, 'password': secrets.token_urlsafe(32)}
                 for key, username in [('agent', 'elastic-agent'), ('personal', 'finnnk'),
                                       ('publisher', 'lab-publisher'), ('reader', 'lab-reader'),
                                       ('bootstrap', 'admin'), ('database', 'nexus')]}
        CREDENTIALS.write_text(json.dumps(value, indent=2), encoding='utf-8')
    value = json.loads(CREDENTIALS.read_text(encoding='utf-8'))
    pg_env = STATE / 'nexus-postgres.env'
    pg_env.write_text('POSTGRES_DB=nexus\nPOSTGRES_USER=nexus\nPOSTGRES_PASSWORD=' +
                      value['database']['password'] + '\n', encoding='utf-8')
    ensure_container('relevance-nexus-db', POSTGRES, [
        '--memory', '512m', '--cpus', '1', '--env-file', str(pg_env),
        '-v', 'relevance-nexus-db:/var/lib/postgresql/data'])
    for _ in range(60):
        try:
            docker('exec', 'relevance-nexus-db', 'pg_isready', '-U', 'nexus', '-d', 'nexus')
            break
        except RuntimeError:
            time.sleep(2)
    else:
        raise TimeoutError('PostgreSQL did not become ready.')
    docker('exec', 'relevance-nexus-db', 'psql', '-U', 'nexus', '-d', 'nexus',
           '-c', 'CREATE EXTENSION IF NOT EXISTS pg_trgm;')
    nx_env = STATE / 'nexus.env'
    nx_env.write_text('\n'.join([
        'NEXUS_DATASTORE_NEXUS_JDBCURL=jdbc:postgresql://relevance-nexus-db:5432/nexus',
        'NEXUS_DATASTORE_NEXUS_USERNAME=nexus',
        'NEXUS_DATASTORE_NEXUS_ADVANCED=maximumPoolSize=20',
        'NEXUS_DATASTORE_NEXUS_PASSWORD=' + value['database']['password'],
        'INSTALL4J_ADD_VM_PARAMS=-Xms1536m -Xmx1536m -XX:MaxDirectMemorySize=1024m -Djava.util.prefs.userRoot=/nexus-data/javaprefs',
        '']), encoding='utf-8')
    ensure_container('relevance-nexus', NEXUS, ['--memory', '4g', '--cpus', '2',
        '--env-file', str(nx_env), '-v', 'relevance-nexus:/nexus-data',
        '-p', '127.0.0.1:18183:8081', '-p', '127.0.0.1:18185:5000'])
    wait_ready()
    return value


def configure(value):
    try:
        api('/security/users', identity='bootstrap')
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
        initial = docker('exec', 'relevance-nexus', 'cat', '/nexus-data/admin.password')
        request('/service/rest/v1/security/users/admin/change-password', 'PUT',
                value['bootstrap']['password'].encode(),
                {'username': 'admin', 'password': initial}, 'text/plain')
    eula = api('/system/eula', identity='bootstrap')
    if not eula['accepted']:
        api('/system/eula', 'POST', {**eula, 'accepted': True}, identity='bootstrap')
    api('/security/anonymous', 'PUT', {'enabled': False, 'userId': 'anonymous',
                                     'realmName': 'NexusAuthorizingRealm'}, identity='bootstrap')
    realms = api('/security/realms/active', identity='bootstrap')
    if 'DockerToken' not in realms:
        api('/security/realms/active', 'PUT', realms + ['DockerToken'], identity='bootstrap')
    repositories = {row['name'] for row in api('/repositories', identity='bootstrap')}
    for name, format_name in [('lab-images', 'docker'), ('lab-releases', 'raw')]:
        body = {'name': name, 'online': True, 'storage': {'blobStoreName': 'default',
                'strictContentTypeValidation': True, 'writePolicy': 'ALLOW_ONCE'}}
        if format_name == 'docker':
            body['docker'] = {'v1Enabled': False, 'forceBasicAuth': True, 'httpPort': 5000}
        if name not in repositories:
            api('/repositories/' + format_name + '/hosted', 'POST', body, identity='bootstrap')
    roles = {row['id'] for row in api('/security/roles', identity='bootstrap')}
    for role, actions in [('lab-reader', ['browse', 'read']),
                          ('lab-publisher', ['browse', 'read', 'add', 'edit'])]:
        body = {'id': role, 'name': role, 'description': 'Lab delivery ' + role,
                'privileges': ['nx-repository-view-' + fmt + '-' + repo + '-' + action
                    for fmt, repo in [('docker', 'lab-images'), ('raw', 'lab-releases')]
                    for action in actions], 'roles': []}
        api('/security/roles' + ('/' + role if role in roles else ''),
            'PUT' if role in roles else 'POST', body, identity='bootstrap')
    users = {row['userId'] for row in api('/security/users', identity='bootstrap')}
    for key in ('agent', 'personal', 'publisher', 'reader'):
        user = value[key]
        if user['username'] not in users:
            api('/security/users', 'POST', {'userId': user['username'],
                'firstName': user['username'], 'lastName': 'Lab',
                'emailAddress': user['username'] + '@lab.invalid',
                'password': user['password'], 'status': 'active',
                'roles': ['nx-admin' if key in ('agent', 'personal') else 'lab-' + key]},
                identity='bootstrap')


def configure_network():
    ip = json.loads(docker('inspect', 'relevance-nexus'))[0]['NetworkSettings']['Networks'][NETWORK]['IPAddress']
    apply({'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'nexus', 'namespace': 'platform'},
           'spec': {'ports': [{'name': 'ui', 'port': 8081, 'targetPort': 8081},
                              {'name': 'registry', 'port': 18185, 'targetPort': 5000}]}})
    apply({'apiVersion': 'discovery.k8s.io/v1', 'kind': 'EndpointSlice',
           'metadata': {'name': 'nexus', 'namespace': 'platform',
                        'labels': {'kubernetes.io/service-name': 'nexus',
                                   'endpointslice.kubernetes.io/managed-by': 'relevance-lab'}},
           'addressType': 'IPv4', 'ports': [{'name': 'ui', 'port': 8081, 'protocol': 'TCP'},
                {'name': 'registry', 'port': 5000, 'protocol': 'TCP'}],
           'endpoints': [{'addresses': [ip], 'conditions': {'ready': True}}]})
    k('patch', 'configmap/coredns-custom', '-n', 'kube-system', '--type=merge', '-p',
      json.dumps({'data': {'nexus.override': 'rewrite name exact nexus.localhost nexus.platform.svc.cluster.local\n'}}))
    # containerd reads this per-registry file when resolving a new image, without a node restart.
    host_config = 'server = "http://relevance-nexus:5000"\n[host."http://relevance-nexus:5000"]\n  capabilities = ["pull", "resolve"]\n'
    path = '/var/lib/rancher/k3s/agent/etc/containerd/certs.d/' + REGISTRY
    for node in ('k3d-relevance-lab-server-0', 'k3d-relevance-lab-agent-0'):
        docker('exec', node, 'mkdir', '-p', path)
        docker('exec', '-i', node, 'sh', '-c', 'cat > ' + path + '/hosts.toml', body=host_config)


def image_secret(namespace):
    value = json.loads(CREDENTIALS.read_text(encoding='utf-8'))['reader']
    auth = base64.b64encode((value['username'] + ':' + value['password']).encode()).decode()
    apply({'apiVersion': 'v1', 'kind': 'Secret', 'type': 'kubernetes.io/dockerconfigjson',
           'metadata': {'name': 'nexus-read', 'namespace': namespace},
           'stringData': {'.dockerconfigjson': json.dumps({'auths': {REGISTRY: {'auth': auth}}})}})


def main():
    guard()
    value = ensure_services()
    configure(value)
    configure_network()
    record('nexus-setup', {'nexus_image': NEXUS, 'postgres_image': POSTGRES,
        'ui': 'http://127.0.0.1:18183', 'registry': REGISTRY,
        'repositories': ['lab-images', 'lab-releases'], 'database': 'PostgreSQL',
        'anonymous': False, 'write_policy': 'ALLOW_ONCE'})
    print('Nexus ready at http://127.0.0.1:18183; credentials are in .lab/nexus.json.')


if __name__ == '__main__':
    main()
