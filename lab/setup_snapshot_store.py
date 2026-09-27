"""Attach a persistent local S3 repository to the self-managed shared ECK cluster."""
import json
import os
import secrets
import socket
import subprocess
import time

from common import KUBE, STATE, guard, k
from data_contract import elastic


IMAGE = 'ghcr.io/chrislusf/seaweedfs@sha256:ce9e796f1fe6f06968f4c04bdaf8f678dad9c8acdfef3d244133d71bfa6bf882'
CONTAINER = 'relevance-snapshot-store'
VOLUME = 'relevance-snapshot-store'
NETWORK = 'k3d-relevance-lab'
BUCKET = 'lab-index-snapshots'
SECRET = 'lab-s3-snapshot-client'
REPOSITORY = 'lab-s3'
ENDPOINT = 'http://' + CONTAINER + ':8333'
CREDENTIALS = STATE / 'snapshot-s3.json'


def docker(*args):
    return subprocess.run(['docker', *args], capture_output=True, text=True, check=True).stdout.strip()


def credentials():
    if CREDENTIALS.exists():
        return json.loads(CREDENTIALS.read_text(encoding='utf-8'))
    value = {'access_key': 'lab' + secrets.token_hex(12), 'secret_key': secrets.token_urlsafe(40)}
    CREDENTIALS.write_text(json.dumps(value), encoding='utf-8')
    return value


def ensure_store(value):
    if NETWORK not in docker('network', 'ls', '--format', '{{.Name}}').splitlines():
        raise RuntimeError('Create the k3d-relevance-lab network before setting up snapshots.')
    names = docker('ps', '-a', '--format', '{{.Names}}').splitlines()
    if CONTAINER not in names:
        docker('run', '--detach', '--name', CONTAINER, '--network', NETWORK,
               '--restart', 'unless-stopped', '-p', '127.0.0.1:18333:8333',
               '-v', VOLUME + ':/data', '-e', 'AWS_ACCESS_KEY_ID=' + value['access_key'],
               '-e', 'AWS_SECRET_ACCESS_KEY=' + value['secret_key'], '-e', 'S3_BUCKET=' + BUCKET,
               IMAGE)
    else:
        image = json.loads(docker('inspect', CONTAINER))[0]['Config']['Image']
        if image != IMAGE:
            raise ValueError('Existing snapshot container uses a different image; inspect it before reuse.')
        if CONTAINER not in docker('ps', '--format', '{{.Names}}').splitlines():
            docker('start', CONTAINER)
    for _ in range(40):
        try:
            with socket.create_connection(('127.0.0.1', 18333), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError('Local S3 endpoint did not open.')


def configure_eck(value):
    secret = {'apiVersion': 'v1', 'kind': 'Secret',
              'metadata': {'name': SECRET, 'namespace': 'platform'},
              'stringData': {'s3.client.lab.access_key': value['access_key'],
                             's3.client.lab.secret_key': value['secret_key']}}
    k('apply', '-f', '-', body=secret)
    resource = json.loads(k('get', 'elasticsearch/shared', '-n', 'platform', '-o', 'json').stdout)
    spec = resource['spec']
    node_sets = spec['nodeSets']
    for node_set in node_sets:
        node_set['config']['s3.client.lab.endpoint'] = ENDPOINT
    secure = spec.get('secureSettings', [])
    if not any(item['secretName'] == SECRET for item in secure):
        secure.append({'secretName': SECRET})
    k('patch', 'elasticsearch/shared', '-n', 'platform', '--type=merge', '-p',
      json.dumps({'spec': {'nodeSets': node_sets, 'secureSettings': secure}}))


def ensure_forward():
    try:
        with socket.create_connection(('127.0.0.1', 19200), timeout=1):
            return
    except OSError:
        pass
    log = (STATE / 'elasticsearch-forward.log').open('a', encoding='utf-8')
    process = subprocess.Popen(KUBE + ['-n', 'platform', 'port-forward',
        'svc/shared-es-http', '19200:9200', '--address', '127.0.0.1'],
        stdout=log, stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    (STATE / 'elasticsearch-forward.pid').write_text(str(process.pid), encoding='utf-8')
    for _ in range(40):
        if process.poll() is not None:
            raise RuntimeError('Shared Elasticsearch port-forward stopped.')
        try:
            with socket.create_connection(('127.0.0.1', 19200), timeout=1):
                log.close()
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError('Shared Elasticsearch port-forward did not open.')


def wait_eck():
    for _ in range(120):
        resource = json.loads(k('get', 'elasticsearch/shared', '-n', 'platform', '-o', 'json').stdout)
        status = resource.get('status', {})
        if (status.get('observedGeneration', 0) >= resource['metadata']['generation'] and
                status.get('health') == 'green' and status.get('phase') == 'Ready'):
            return
        time.sleep(3)
    raise TimeoutError('Shared ECK cluster did not finish applying snapshot settings.')


def register_repository():
    definition = {'type': 's3', 'settings': {'client': 'lab', 'bucket': BUCKET,
                  'base_path': 'shared-v1', 'path_style_access': True}}
    last_error = None
    for _ in range(90):
        try:
            if elastic('/_snapshot/' + REPOSITORY, 'PUT', definition)['acknowledged']:
                break
        except Exception as error:
            last_error = error
            time.sleep(2)
    else:
        raise TimeoutError('Shared Elasticsearch did not accept the S3 repository: '
                           + str(last_error))
    verified = elastic('/_snapshot/' + REPOSITORY + '/_verify', 'POST')
    if not verified.get('nodes'):
        raise ValueError('No Elasticsearch node verified the snapshot repository.')
    analysis = elastic('/_snapshot/' + REPOSITORY + '/_analyze?blob_count=100&max_blob_size=10mb&max_total_data_size=1gb&timeout=120s', 'POST')
    if analysis.get('issues_detected'):
        raise ValueError('Snapshot repository analysis detected a correctness issue.')
    return {'repository': REPOSITORY, 'verified_nodes': len(verified['nodes']),
            'analysis_blobs': analysis['blob_count'], 'analysis_issues': []}


def main():
    guard()
    value = credentials()
    ensure_store(value)
    configure_eck(value)
    wait_eck()
    ensure_forward()
    print(json.dumps(register_repository()))


if __name__ == '__main__':
    main()
