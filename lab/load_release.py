"""Publish a frozen catalogue to Azure Blob Storage and load its Elasticsearch index."""
import hashlib
import json
import secrets
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common import IN_CLUSTER, ROOT, STATE, apply, guard, k, record
from data_contract import elastic
from blob_config import service, settings, signed_read_url
from azure.core.exceptions import ResourceExistsError

from catalogue import DEFAULT_RELEASE
from catalogue_mapping import MAPPING

RELEASE = DEFAULT_RELEASE
INDEX = RELEASE
DATA = STATE / 'releases' / RELEASE
BASELINE_MAPPING = MAPPING
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


def index_job(blob_path, digest, index=INDEX, role='retail-baseline-indexer',
              expected_count=10_000, compression='none', deadline_seconds=300,
              worker_source=None, worker_image=INDEXER_IMAGE):
    namespace = 'lab-indexing' if IN_CLUSTER else 'platform'
    labels = {'app.kubernetes.io/managed-by': 'lab-control-indexing'} if IN_CLUSTER else {}
    if IN_CLUSTER:
        apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': namespace,
            'labels': {'lab': 'indexing'}}})
        # A previous control Pod may have stopped before the Job's finally block.
        for resource in ('job/' + role, 'secret/' + role,
                         'secret/' + role + '-ca', 'configmap/' + role):
            k('delete', resource, '-n', namespace, '--ignore-not-found', '--wait=true')
    password = secrets.token_urlsafe(24)
    dataset_url = signed_read_url(blob_path,
        datetime.now(timezone.utc) + timedelta(seconds=deadline_seconds + 300))
    elastic('/_security/role/' + role, 'PUT', {'indices': [{'names': [index], 'privileges': ['write', 'maintenance']} ]})
    elastic('/_security/user/' + role, 'PUT', {'password': password, 'roles': [role]})
    try:
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': role, 'namespace': namespace,
            'labels': labels},
            'stringData': {'ES_USER': role, 'ES_PASSWORD': password, 'ES_INDEX': index,
                'DATASET_URL': dataset_url,
                'DATASET_SHA256': digest, 'DATASET_COMPRESSION': compression}})
        cert = json.loads(k('get', 'secret/shared-es-http-certs-public', '-n', 'platform', '-o', 'json').stdout)['data']
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': role + '-ca', 'namespace': namespace,
            'labels': labels}, 'data': cert})
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': role, 'namespace': namespace,
            'labels': labels},
            'data': {'index_job.py': worker_source if worker_source is not None else
                     (ROOT / 'lab/index_job.py').read_text(encoding='utf-8')}})
        apply({'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': role, 'namespace': namespace,
            'labels': labels},
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
        k('wait', '--for=condition=complete', 'job/' + role, '-n', namespace,
          '--timeout=' + str(deadline_seconds + 15) + 's')
        result = json.loads(k('logs', 'job/' + role, '-n', namespace).stdout)
        assert result['indexed'] == expected_count and result['dataset_sha256'] == digest, result
        return result
    finally:
        k('delete', 'job/' + role, '-n', namespace, '--ignore-not-found', '--wait=true')
        elastic('/_security/user/' + role, 'DELETE')
        elastic('/_security/role/' + role, 'DELETE')
        k('delete', 'secret/' + role, '-n', namespace, '--ignore-not-found')
        k('delete', 'secret/' + role + '-ca', '-n', namespace, '--ignore-not-found')
        k('delete', 'configmap/' + role, '-n', namespace, '--ignore-not-found')


def main():
    import argparse
    from catalogue import RELEASES
    from index_recipe import catalogue_recipe, publish as publish_recipe
    from input_selection import DEFAULTS, fetch_manifest
    from shared_index import ensure_shared_index
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', choices=RELEASES, default=RELEASE)
    args = parser.parse_args()
    guard()
    catalogue = fetch_manifest('catalogue', DEFAULTS[args.release]['catalogue'])
    recipe = catalogue_recipe(args.release, 'shared', catalogue, elastic('/')['version']['number'])
    recipe_sha = publish_recipe(recipe)
    result = ensure_shared_index(args.release, recipe['product_sha256'], recipe_sha)
    evidence = {**result, 'release': args.release, 'products_sha256': recipe['product_sha256'],
                'index_recipe_sha256': recipe_sha, 'frozen': True}
    record('catalogue-release', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
