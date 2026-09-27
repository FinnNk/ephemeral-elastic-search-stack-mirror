"""Build and remove a dedicated frozen index from the canonical synthetic release."""
import hashlib
import json
import re
import time
import urllib.error
from pathlib import Path

from load_release import DATA, RELEASE, index_job, publish_blobs
from data_contract import elastic
from index_recipe import current_recipe, digest, load as load_recipe, validate

KIND = 'title-keyword-v1'
MAPPINGS = Path(__file__).with_name('mappings')


def available_kinds(release_id=RELEASE):
    names = []
    for path in MAPPINGS.glob('*.json'):
        name = path.stem
        if '-1m-' not in name and re.fullmatch(r'[a-z0-9-]+-v[0-9]+', name) and \
                (release_id != 'retail-gb-1m-v1' or
                 (MAPPINGS / (name.replace('-v', '-1m-v') + '.json')).exists()):
            names.append(name)
    return sorted(names)


def mapping_contract(release_id=RELEASE, index_kind=KIND):
    if index_kind not in available_kinds(release_id):
        raise ValueError('No versioned mapping exists for this release and index kind.')
    filename = (index_kind.replace('-v', '-1m-v') if release_id == 'retail-gb-1m-v1'
                else index_kind) + '.json'
    path = MAPPINGS / filename
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


def ensure_candidate_index(environment_name, expected_dataset_sha, release_id=RELEASE,
                           recipe_sha256=None, index_kind=KIND):
    index = index_name(environment_name)
    data = DATA if release_id == RELEASE else DATA.parent / release_id
    manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
    product_name = 'products.jsonl.gz' if manifest.get('compression') == 'gzip' else 'products.jsonl'
    assert manifest['release'] == release_id
    assert manifest['sha256'][product_name] == expected_dataset_sha
    recipe = (load_recipe(recipe_sha256) if recipe_sha256 else
              current_recipe(release_id, index_kind, manifest, elastic('/')['version']['number'],
                             mapping_contract(release_id, index_kind)[0]))
    validate(recipe, release_id, manifest, elastic('/')['version']['number'])
    if recipe['index_kind'] != index_kind:
        raise ValueError('Frozen index recipe has a different index kind.')
    mapping = recipe['index_definition']
    mapping_sha = digest(mapping)
    existing = _existing(index)
    if existing:
        existing_mapping = dict(existing['mappings'])
        marker = existing_mapping.pop('_meta', {}).get('index_recipe_sha256')
        if existing_mapping != mapping['mappings']:
            raise ValueError('An existing candidate index has a different mapping.')
        if marker and marker != recipe_sha256:
            raise ValueError('An existing candidate index has a different recipe.')
        actual_settings = existing['settings']['index']
        if any(str(actual_settings.get(key)) != str(value) for key, value in mapping['settings'].items()):
            raise ValueError('An existing candidate index has different settings.')
        frozen, count = _frozen_count(index)
        if frozen and count == manifest['count']:
            return {'index': index, 'mapping_sha256': mapping_sha, 'count': count,
                    'dataset_sha256': expected_dataset_sha, 'created': False, 'build_seconds': 0}
        elastic('/' + index, 'DELETE')
    blob_path = publish_blobs(manifest, data)
    started = time.monotonic()
    definition = json.loads(json.dumps(mapping))
    if recipe_sha256:
        definition['mappings']['_meta'] = {'index_recipe_sha256': recipe_sha256}
    elastic('/' + index, 'PUT', definition)
    try:
        index_job(blob_path, expected_dataset_sha, index=index, role=environment_name + '-indexer',
                  expected_count=manifest['count'], compression=manifest.get('compression', 'none'),
                  deadline_seconds=1500 if manifest['count'] >= 1_000_000 else 300,
                  worker_source=recipe['indexer']['source'], worker_image=recipe['indexer']['image'])
        elastic('/' + index + '/_settings', 'PUT', {'index.blocks.write': True})
        frozen, count = _frozen_count(index)
        if not frozen or count != manifest['count']:
            raise RuntimeError('Candidate index count or write block failed verification.')
    except Exception:
        elastic('/' + index, 'DELETE')
        raise
    return {'index': index, 'mapping_sha256': mapping_sha, 'count': count,
            'dataset_sha256': expected_dataset_sha, 'created': True,
            'build_seconds': round(time.monotonic() - started, 3)}


def remove_candidate_index(environment_name):
    index = index_name(environment_name)
    if _existing(index):
        elastic('/' + index, 'DELETE')
