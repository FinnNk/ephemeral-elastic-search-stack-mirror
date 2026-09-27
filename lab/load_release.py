"""Publish a synthetic release to Floci and freeze its dedicated Elasticsearch index."""
import hashlib
import json
import secrets
import sys
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import ROOT, STATE, apply, guard, k, record
from data_contract import elastic
from blob_config import service, settings, signed_read_url
from azure.core.exceptions import ResourceExistsError

RELEASE = 'retail-gb-10k-v1'
INDEX = RELEASE
DATA = STATE / 'releases' / RELEASE
BASELINE_MAPPING = {
    'settings': {'number_of_shards': 1, 'number_of_replicas': 0},
    'mappings': {'properties': {
        'product_id': {'type': 'keyword'}, 'sku': {'type': 'keyword'},
        'title': {'type': 'text'}, 'description': {'type': 'text'},
        'brand': {'type': 'text'}, 'product_type': {'type': 'text'},
        'category': {'type': 'keyword'}, 'colour': {'type': 'keyword'},
        'material': {'type': 'keyword'}, 'country': {'type': 'keyword'},
        'currency': {'type': 'keyword'}, 'price_minor': {'type': 'integer'},
        'available': {'type': 'boolean'}, 'popularity': {'type': 'float'},
    }},
}
INDEXER_IMAGE = ('python:3.13.7-alpine3.22@sha256:'
                 '9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844')


def publish_blobs(manifest, data_dir=DATA):
    data_dir = Path(data_dir)
    release = manifest['release']
    product_name = 'products.jsonl.gz' if manifest.get('compression') == 'gzip' else 'products.jsonl'
    account = service()
    _, container, _, _ = settings()
    try:
        account.create_container(container)
    except ResourceExistsError:
        pass
    for name in (product_name, 'queries.jsonl', 'judgements.jsonl', 'manifest.json'):
        source = data_dir / name
        expected = manifest['sha256'].get(name)
        digest = hashlib.sha256()
        with source.open('rb') as local:
            for block in iter(lambda: local.read(1024 * 1024), b''):
                digest.update(block)
        local_hash = digest.hexdigest()
        if expected:
            assert local_hash == expected
        path = f'{release}/{name}'
        blob = account.get_blob_client(container, path)
        try:
            with source.open('rb') as local:
                blob.upload_blob(local, overwrite=False, length=source.stat().st_size)
        except ResourceExistsError:
            pass
        remote_hash = hashlib.sha256()
        remote_bytes = 0
        for chunk in blob.download_blob().chunks():
            remote_hash.update(chunk)
            remote_bytes += len(chunk)
        assert remote_bytes == source.stat().st_size and remote_hash.hexdigest() == local_hash, f'Blob differs: {path}'
    return f'{release}/{product_name}'


def create_index():
    mapping = BASELINE_MAPPING
    try:
        elastic('/' + INDEX, 'PUT', mapping)
        return True
    except urllib.error.HTTPError as error:
        if error.code != 400:
            raise
        existing = elastic('/' + INDEX)
        assert existing[INDEX]['mappings'] == mapping['mappings'], 'Existing index mapping differs'
        return False


def index_job(blob_path, digest, index=INDEX, role='retail-baseline-indexer',
              expected_count=10_000, compression='none', deadline_seconds=300,
              worker_source=None, worker_image=INDEXER_IMAGE):
    password = secrets.token_urlsafe(24)
    dataset_url = signed_read_url(blob_path,
        datetime.now(timezone.utc) + timedelta(seconds=deadline_seconds + 300))
    elastic('/_security/role/' + role, 'PUT', {'indices': [{'names': [index], 'privileges': ['write', 'maintenance']} ]})
    elastic('/_security/user/' + role, 'PUT', {'password': password, 'roles': [role]})
    try:
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': role, 'namespace': 'platform'},
            'stringData': {'ES_USER': role, 'ES_PASSWORD': password, 'ES_INDEX': index,
                'DATASET_URL': dataset_url,
                'DATASET_SHA256': digest, 'DATASET_COMPRESSION': compression}})
        cert = json.loads(k('get', 'secret/shared-es-http-certs-public', '-n', 'platform', '-o', 'json').stdout)['data']
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': role + '-ca', 'namespace': 'platform'}, 'data': cert})
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': role, 'namespace': 'platform'},
            'data': {'index_job.py': worker_source if worker_source is not None else
                     (ROOT / 'research/platform-spike/index_job.py').read_text(encoding='utf-8')}})
        apply({'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': role, 'namespace': 'platform'},
            'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': deadline_seconds, 'template': {'spec': {
                'automountServiceAccountToken': False, 'restartPolicy': 'Never',
                'containers': [{'name': 'index', 'image': worker_image,
                    'command': ['python', '/source/index_job.py'],
                    'envFrom': [{'secretRef': {'name': role}}],
                    'resources': {'requests': {'cpu': '100m', 'memory': '64Mi'},
                                  'limits': {'cpu': '1', 'memory': '256Mi'}},
                    'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000,
                        'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                    'volumeMounts': [{'name': 'source', 'mountPath': '/source'},
                                     {'name': 'ca', 'mountPath': '/es-ca'}]}],
                'volumes': [{'name': 'source', 'configMap': {'name': role}},
                            {'name': 'ca', 'secret': {'secretName': role + '-ca'}}],
            }}}})
        k('wait', '--for=condition=complete', 'job/' + role, '-n', 'platform',
          '--timeout=' + str(deadline_seconds + 15) + 's')
        result = json.loads(k('logs', 'job/' + role, '-n', 'platform').stdout)
        assert result['indexed'] == expected_count and result['dataset_sha256'] == digest, result
        return result
    finally:
        k('delete', 'job/' + role, '-n', 'platform', '--ignore-not-found', '--wait=true')
        elastic('/_security/user/' + role, 'DELETE')
        elastic('/_security/role/' + role, 'DELETE')
        k('delete', 'secret/' + role, '-n', 'platform', '--ignore-not-found')
        k('delete', 'secret/' + role + '-ca', '-n', 'platform', '--ignore-not-found')
        k('delete', 'configmap/' + role, '-n', 'platform', '--ignore-not-found')


def main():
    guard()
    manifest = json.loads((DATA / 'manifest.json').read_text())
    assert manifest['release'] == RELEASE and manifest['count'] == 10000
    blob_path = publish_blobs(manifest)
    started = time.monotonic()
    created = create_index()
    if created:
        try:
            index_job(blob_path, manifest['sha256']['products.jsonl'])
            elastic('/' + INDEX + '/_settings', 'PUT', {'index.blocks.write': True})
        except Exception:
            elastic('/' + INDEX, 'DELETE')
            raise
    settings = elastic('/' + INDEX + '/_settings')[INDEX]['settings']['index']
    assert settings['blocks']['write'] == 'true', 'Index is not frozen'
    count = elastic('/' + INDEX + '/_count')['count']
    assert count == manifest['count'], (count, manifest['count'])
    evidence = {'release': RELEASE, 'index': INDEX, 'count': count,
        'products_sha256': manifest['sha256']['products.jsonl'],
        'query_count': manifest['query_count'], 'judgement_count': manifest['judgement_count'],
        'frozen': True, 'created': created, 'elapsed_seconds': round(time.monotonic() - started, 3)}
    record('retail-release', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
