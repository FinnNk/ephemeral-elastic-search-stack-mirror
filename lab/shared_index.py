"""Verify or recreate the single shared baseline index from a frozen recipe."""
import json
import time
import urllib.error

from data_contract import elastic
from index_recipe import load as load_recipe, validate
from load_release import DATA, RELEASE, index_job, publish_blobs
from index_recovery import clone_from_live, restore_snapshot, save_snapshot, verify as verify_recovered


def ensure_shared_index(release_id, dataset_sha256, recipe_sha256):
    recipe = load_recipe(recipe_sha256)
    data = DATA if release_id == RELEASE else DATA.parent / release_id
    manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
    validate(recipe, release_id, manifest, elastic('/')['version']['number'])
    if recipe['index_kind'] != 'shared' or recipe['product_sha256'] != dataset_sha256:
        raise ValueError('Shared index recipe differs from the environment request.')
    definition = recipe['index_definition']
    try:
        existing = elastic('/' + release_id)[release_id]
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        existing = None
    if existing:
        mapping = dict(existing['mappings'])
        marker = mapping.pop('_meta', {}).get('index_recipe_sha256')
        if mapping != definition['mappings'] or (marker and marker != recipe_sha256):
            raise ValueError('Shared index has a different historical mapping or recipe.')
        settings = existing['settings']['index']
        if any(str(settings.get(key)) != str(value) for key, value in definition['settings'].items()):
            raise ValueError('Shared index has different historical settings.')
        if settings.get('blocks', {}).get('write') != 'true' or \
                elastic('/' + release_id + '/_count')['count'] != manifest['count']:
            raise ValueError('Shared index is not frozen with the expected document count.')
        if marker:
            verify_recovered(release_id, recipe, recipe_sha256)
        errors = []
        try:
            save_snapshot(release_id, recipe, recipe_sha256)
        except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
            errors.append('snapshot save: ' + type(error).__name__ + ': ' + str(error))
        return {'index': release_id, 'created': False, 'count': manifest['count'],
                'materialisation': 'reuse', 'seconds': 0, 'recovery_errors': errors}
    errors = []
    for method in (clone_from_live, restore_snapshot):
        try:
            recovered = method(release_id, recipe, recipe_sha256)
            if recovered:
                if recovered['source'] == 'clone':
                    try:
                        save_snapshot(release_id, recipe, recipe_sha256)
                    except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
                        errors.append('snapshot save: ' + type(error).__name__ + ': ' + str(error))
                return {'index': release_id, 'created': True, 'count': manifest['count'],
                        'materialisation': recovered['source'], 'seconds': recovered['seconds'],
                        'recovery_errors': errors}
        except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
            errors.append(type(error).__name__ + ': ' + str(error))
    blob_path = publish_blobs(manifest, data)
    definition = json.loads(json.dumps(definition))
    definition['mappings']['_meta'] = {'index_recipe_sha256': recipe_sha256}
    started = time.monotonic()
    elastic('/' + release_id, 'PUT', definition)
    try:
        index_job(blob_path, dataset_sha256, index=release_id, role='retail-shared-indexer',
                  expected_count=manifest['count'], compression=recipe['compression'],
                  deadline_seconds=1500 if manifest['count'] >= 1_000_000 else 300,
                  worker_source=recipe['indexer']['source'], worker_image=recipe['indexer']['image'])
        elastic('/' + release_id + '/_settings', 'PUT', {'index.blocks.write': True})
        if elastic('/' + release_id + '/_count')['count'] != manifest['count']:
            raise ValueError('Recreated shared index has the wrong document count.')
    except Exception:
        elastic('/' + release_id, 'DELETE')
        raise
    try:
        save_snapshot(release_id, recipe, recipe_sha256)
    except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
        errors.append('snapshot save: ' + type(error).__name__ + ': ' + str(error))
    return {'index': release_id, 'created': True, 'count': manifest['count'],
            'materialisation': 'rebuild', 'seconds': round(time.monotonic() - started, 3),
            'recovery_errors': errors}
