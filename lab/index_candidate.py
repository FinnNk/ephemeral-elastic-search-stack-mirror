"""Build and remove a dedicated frozen index from the canonical frozen catalogue."""
import hashlib
import json
import re
import time
import urllib.error
from pathlib import Path

from load_release import DATA, RELEASE, index_job, publish_blobs
from data_contract import elastic
from index_recipe import current_recipe, digest, load as load_recipe, validate
from index_recovery import clone_from_live, restore_snapshot, save_snapshot, verify as verify_recovered
from input_selection import fetch_manifest

KIND = 'title-keyword-v1'
MAPPINGS = Path(__file__).with_name('mappings')


def available_kinds(release_id=RELEASE):
    return sorted(path.stem for path in MAPPINGS.glob('*.json')
                  if re.fullmatch(r'[a-z0-9-]+-v[0-9]+', path.stem))


def mapping_contract(release_id=RELEASE, index_kind=KIND):
    if index_kind not in available_kinds(release_id):
        raise ValueError('No versioned mapping exists for this release and index kind.')
    filename = index_kind + '.json'
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
    recipe = load_recipe(recipe_sha256) if recipe_sha256 else None
    if recipe and recipe['format'] == 2:
        catalogue = fetch_manifest('catalogue', recipe['catalogue_manifest_sha256'])
        validate(recipe, release_id=release_id, engine_version=elastic('/')['version']['number'],
                 catalogue_manifest=catalogue)
        count = catalogue['record_count']
        blob_path = catalogue['content']['object']
    else:
        data = DATA if release_id == RELEASE else DATA.parent / release_id
        manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
        product_name = 'products.jsonl.gz' if manifest.get('compression') == 'gzip' else 'products.jsonl'
        assert manifest['release'] == release_id
        recipe = recipe or current_recipe(release_id, index_kind, manifest,
            elastic('/')['version']['number'], mapping_contract(release_id, index_kind)[0])
        validate(recipe, release_id, manifest, elastic('/')['version']['number'])
        count = manifest['count']
        blob_path = None
    if recipe['product_sha256'] != expected_dataset_sha:
        raise ValueError('Dedicated index recipe differs from the environment catalogue.')
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
        if recipe_sha256 and marker != recipe_sha256:
            raise ValueError('An existing candidate index has a different recipe.')
        actual_settings = existing['settings']['index']
        if any(str(actual_settings.get(key)) != str(value) for key, value in mapping['settings'].items()):
            raise ValueError('An existing candidate index has different settings.')
        frozen, count = _frozen_count(index)
        if frozen and count == recipe['document_count']:
            if recipe_sha256:
                verify_recovered(index, recipe, recipe_sha256)
            errors = []
            if recipe_sha256:
                try:
                    save_snapshot(index, recipe, recipe_sha256)
                except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
                    errors.append('snapshot save: ' + type(error).__name__ + ': ' + str(error))
            return {'index': index, 'mapping_sha256': mapping_sha, 'count': count,
                    'dataset_sha256': expected_dataset_sha, 'created': False, 'build_seconds': 0,
                    'materialisation': 'reuse', 'recovery_errors': errors}
        elastic('/' + index, 'DELETE')
    recovery_errors = []
    if recipe_sha256:
        for method in (clone_from_live, restore_snapshot):
            try:
                recovered = method(index, recipe, recipe_sha256)
                if recovered:
                    if recovered['source'] == 'clone':
                        try:
                            save_snapshot(index, recipe, recipe_sha256)
                        except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
                            recovery_errors.append('snapshot save: ' + type(error).__name__ + ': ' + str(error))
                    return {'index': index, 'mapping_sha256': mapping_sha,
                            'count': recipe['document_count'], 'dataset_sha256': expected_dataset_sha,
                            'created': True, 'build_seconds': recovered['seconds'],
                            'materialisation': recovered['source'], 'recovery_errors': recovery_errors}
            except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
                recovery_errors.append(type(error).__name__ + ': ' + str(error))
    if blob_path is None:
        blob_path = publish_blobs(manifest, data)
    started = time.monotonic()
    definition = json.loads(json.dumps(mapping))
    if recipe_sha256:
        definition['mappings']['_meta'] = {'index_recipe_sha256': recipe_sha256}
    elastic('/' + index, 'PUT', definition)
    try:
        index_job(blob_path, expected_dataset_sha, index=index, role=environment_name + '-indexer',
                  expected_count=recipe['document_count'], compression=recipe['compression'],
                  deadline_seconds=1500 if recipe['document_count'] >= 1_000_000 else 300,
                  worker_source=recipe['indexer']['source'], worker_image=recipe['indexer']['image'])
        elastic('/' + index + '/_settings', 'PUT', {'index.blocks.write': True})
        frozen, count = _frozen_count(index)
        if not frozen or count != recipe['document_count']:
            raise RuntimeError('Candidate index count or write block failed verification.')
    except Exception:
        elastic('/' + index, 'DELETE')
        raise
    if recipe_sha256:
        try:
            save_snapshot(index, recipe, recipe_sha256)
        except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
            recovery_errors.append('snapshot save: ' + type(error).__name__ + ': ' + str(error))
    return {'index': index, 'mapping_sha256': mapping_sha, 'count': count,
            'dataset_sha256': expected_dataset_sha, 'created': True,
            'build_seconds': round(time.monotonic() - started, 3),
            'materialisation': 'rebuild', 'recovery_errors': recovery_errors}


def remove_candidate_index(environment_name):
    index = index_name(environment_name)
    if _existing(index):
        elastic('/' + index, 'DELETE')
