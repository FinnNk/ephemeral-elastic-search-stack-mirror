"""Build and remove a dedicated frozen index from the canonical synthetic release."""
import hashlib
import json
import time
import urllib.error
from pathlib import Path

from load_release import DATA, RELEASE, index_job, publish_blobs
from data_contract import elastic

KIND = 'title-keyword-v1'
MAPPING = Path(__file__).with_name('mappings') / (KIND + '.json')


def mapping_contract(release_id=RELEASE):
    path = (Path(__file__).with_name('mappings') / 'title-keyword-1m-v1.json'
            if release_id == 'retail-gb-1m-v1' else MAPPING)
    mapping = json.loads(path.read_text(encoding='utf-8'))
    canonical = json.dumps(mapping, sort_keys=True, separators=(',', ':')).encode()
    return mapping, hashlib.sha256(canonical).hexdigest()


def index_name(environment_name):
    return environment_name + '-idx'


def _existing(index):
    try:
        return elastic('/' + index)[index]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def _frozen_count(index):
    settings = elastic('/' + index + '/_settings')[index]['settings']['index']
    return settings.get('blocks', {}).get('write') == 'true', elastic('/' + index + '/_count')['count']


def ensure_candidate_index(environment_name, expected_dataset_sha, release_id=RELEASE):
    index = index_name(environment_name)
    mapping, digest = mapping_contract(release_id)
    data = DATA if release_id == RELEASE else DATA.parent / release_id
    manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
    product_name = 'products.jsonl.gz' if manifest.get('compression') == 'gzip' else 'products.jsonl'
    assert manifest['release'] == release_id
    assert manifest['sha256'][product_name] == expected_dataset_sha
    existing = _existing(index)
    if existing:
        if existing['mappings'] != mapping['mappings']:
            raise ValueError('An existing candidate index has a different mapping.')
        frozen, count = _frozen_count(index)
        if frozen and count == manifest['count']:
            return {'index': index, 'mapping_sha256': digest, 'count': count,
                    'dataset_sha256': expected_dataset_sha, 'created': False, 'build_seconds': 0}
        elastic('/' + index, 'DELETE')
    blob_path = publish_blobs(manifest, data)
    started = time.monotonic()
    elastic('/' + index, 'PUT', mapping)
    try:
        index_job(blob_path, expected_dataset_sha, index=index, role=environment_name + '-indexer',
                  expected_count=manifest['count'], compression=manifest.get('compression', 'none'),
                  deadline_seconds=1500 if manifest['count'] >= 1_000_000 else 300)
        elastic('/' + index + '/_settings', 'PUT', {'index.blocks.write': True})
        frozen, count = _frozen_count(index)
        if not frozen or count != manifest['count']:
            raise RuntimeError('Candidate index count or write block failed verification.')
    except Exception:
        elastic('/' + index, 'DELETE')
        raise
    return {'index': index, 'mapping_sha256': digest, 'count': count,
            'dataset_sha256': expected_dataset_sha, 'created': True,
            'build_seconds': round(time.monotonic() - started, 3)}


def remove_candidate_index(environment_name):
    index = index_name(environment_name)
    if _existing(index):
        elastic('/' + index, 'DELETE')
