"""Publish a synthetic release to Floci and freeze its dedicated Elasticsearch index."""
import hashlib
import json
import secrets
import sys
import time
import urllib.error
from datetime import datetime, timedelta, timezone

sys.path.insert(0, 'research/platform-spike')
from common import ROOT, STATE, apply, guard, k, record
from data_contract import DEMO_KEY, elastic
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas

RELEASE = 'retail-gb-10k-v1'
INDEX = RELEASE
DATA = STATE / 'releases' / RELEASE


def publish_blobs(manifest):
    account = BlobServiceClient(account_url='http://127.0.0.1:14577/devstoreaccount1', credential=DEMO_KEY)
    try:
        account.create_container('datasets')
    except ResourceExistsError:
        pass
    for name in ('products.jsonl', 'queries.jsonl', 'judgements.jsonl', 'manifest.json'):
        payload = (DATA / name).read_bytes()
        if name != 'manifest.json':
            assert hashlib.sha256(payload).hexdigest() == manifest['sha256'][name]
        path = f'{RELEASE}/{name}'
        blob = account.get_blob_client('datasets', path)
        try:
            blob.upload_blob(payload, overwrite=False)
        except ResourceExistsError:
            pass
        assert blob.download_blob().readall() == payload, f'Blob differs: {path}'
    return f'{RELEASE}/products.jsonl'


def create_index():
    mapping = {
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
    try:
        elastic('/' + INDEX, 'PUT', mapping)
        return True
    except urllib.error.HTTPError as error:
        if error.code != 400:
            raise
        existing = elastic('/' + INDEX)
        assert existing[INDEX]['mappings'] == mapping['mappings'], 'Existing index mapping differs'
        return False


def index_job(blob_path, digest):
    password = secrets.token_urlsafe(24)
    role = 'retail-baseline-indexer'
    sas = generate_blob_sas('devstoreaccount1', 'datasets', blob_path, account_key=DEMO_KEY,
        permission=BlobSasPermissions(read=True), expiry=datetime.now(timezone.utc) + timedelta(minutes=15))
    elastic('/_security/role/' + role, 'PUT', {'indices': [{'names': [INDEX], 'privileges': ['write']} ]})
    elastic('/_security/user/' + role, 'PUT', {'password': password, 'roles': [role]})
    try:
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': role, 'namespace': 'platform'},
            'stringData': {'ES_USER': role, 'ES_PASSWORD': password, 'ES_INDEX': INDEX,
                'DATASET_URL': 'http://floci.platform.svc:4577/devstoreaccount1/datasets/' + blob_path + '?' + sas,
                'DATASET_SHA256': digest}})
        cert = json.loads(k('get', 'secret/shared-es-http-certs-public', '-n', 'platform', '-o', 'json').stdout)['data']
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': role + '-ca', 'namespace': 'platform'}, 'data': cert})
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': role, 'namespace': 'platform'},
            'data': {'index_job.py': (ROOT / 'research/platform-spike/index_job.py').read_text()}})
        apply({'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': role, 'namespace': 'platform'},
            'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300, 'template': {'spec': {
                'automountServiceAccountToken': False, 'restartPolicy': 'Never',
                'containers': [{'name': 'index', 'image': 'python:3.13.7-alpine3.22',
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
        k('wait', '--for=condition=complete', 'job/' + role, '-n', 'platform', '--timeout=315s')
        result = json.loads(k('logs', 'job/' + role, '-n', 'platform').stdout)
        assert result == {'indexed': 10000, 'dataset_sha256': digest}, result
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
