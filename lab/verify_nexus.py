"""Live artifact permissions, persistence and private Kubernetes image-pull checks."""
import json
import time
import urllib.error

from common import STATE, apply, guard, k, record, run
from nexus import REGISTRY, api, credentials, publish, request
from setup_nexus import docker, image_secret, wait_ready


def denied(function):
    try:
        function()
    except urllib.error.HTTPError as error:
        if error.code not in (400, 401, 403, 409):
            raise
        return error.code
    raise AssertionError('Operation unexpectedly succeeded.')


def main():
    guard()
    marker = str(time.time_ns())
    path = 'verification/' + marker + '.txt'
    content = ('Frozen artifact ' + marker).encode()
    digest = publish(path, content)
    assert publish(path, content) == digest
    url = '/repository/lab-releases/' + path
    assert request(url, identity='reader') == content
    checks = {
        'reader_write_status': denied(lambda: request('/repository/lab-releases/forbidden.txt',
                  'PUT', b'not allowed', 'reader', 'text/plain')),
        'overwrite_status': denied(lambda: request(url, 'PUT', b'changed', 'publisher', 'text/plain')),
        'publisher_delete_status': denied(lambda: request(url, 'DELETE', identity='publisher')),
        'anonymous_read_status': denied(lambda: request(url, identity={})),
        'publisher_admin_status': denied(lambda: api('/security/users', identity='publisher'))}
    started = time.monotonic()
    docker('restart', 'relevance-nexus')
    wait_ready()
    assert request(url, identity='reader') == content
    checks['restart_to_read_seconds'] = round(time.monotonic() - started, 3)
    checks['artifact_sha256'] = digest
    # Build from a digest-pinned tiny base on the existing lab runner.
    publisher = credentials()['publisher']
    result = run(['kubectl', '--kubeconfig', str(STATE / 'kubeconfig.yaml'), '-n', 'platform',
        'exec', '-i', 'deployment/build-runner', '--', 'docker', 'login', REGISTRY,
        '--username', publisher['username'], '--password-stdin'], body=publisher['password'])
    tag = REGISTRY + '/verification:probe-' + marker
    build = k('-n', 'platform', 'exec', '-i', 'deployment/build-runner', '--',
        'sh', '-c', 'docker build --provenance=false -t ' + tag + ' - <<\'DOCKERFILE\'\n'
        'FROM python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844\n'
        'LABEL lab.verification="' + marker + '"\nDOCKERFILE\n' +
        'docker push ' + tag + '\ndocker image inspect ' + tag + ' --format "{{json .RepoDigests}}"')
    image = next(value for value in json.loads(build.stdout.strip().splitlines()[-1]) if value.startswith(REGISTRY))
    namespace = 'lab-nexus-verification'
    apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': namespace}})
    image_secret(namespace)
    name = 'pull-' + marker
    apply({'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': name, 'namespace': namespace},
           'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 90,
                    'template': {'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                        'imagePullSecrets': [{'name': 'nexus-read'}],
                        'containers': [{'name': 'verify', 'image': image, 'imagePullPolicy': 'Always',
                            'command': ['python', '-c', 'print("private digest pull passed")'],
                            'resources': {'requests': {'cpu': '10m', 'memory': '24Mi'},
                                          'limits': {'cpu': '100m', 'memory': '64Mi'}}}]}}}})
    try:
        k('-n', namespace, 'wait', '--for=condition=complete', 'job/' + name, '--timeout=100s')
        assert 'private digest pull passed' in k('-n', namespace, 'logs', 'job/' + name).stdout
    finally:
        k('delete', 'namespace', namespace, '--wait=false', check=False)
    checks.update({'private_image': image, 'kubernetes_digest_pull': True,
                   'database_version': docker('exec', 'relevance-nexus-db', 'psql', '-U', 'nexus',
                                               '-d', 'nexus', '-Atc', 'SHOW server_version;')})
    record('nexus-verification', checks)
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
