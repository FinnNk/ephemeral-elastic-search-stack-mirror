"""Verify or recreate the single shared baseline index from a frozen recipe."""
import json
import time
import urllib.error

from data_contract import elastic
from index_recipe import load as load_recipe, shared_index_name, validate
from load_release import DATA, RELEASE, index_job, publish_blobs
from index_recovery import clone_from_live, restore_snapshot, save_snapshot, verify as verify_recovered
from input_selection import fetch_manifest


def ensure_shared_index(release_id, dataset_sha256, recipe_sha256):
    recipe = load_recipe(recipe_sha256)
    index = shared_index_name(recipe, recipe_sha256)
    if recipe['format'] == 2:
        catalogue = fetch_manifest('catalogue', recipe['catalogue_manifest_sha256'])
        validate(recipe, release_id=release_id, engine_version=elastic('/')['version']['number'],
                 catalogue_manifest=catalogue)
        count = catalogue['record_count']
        blob_path = catalogue['content']['object']
    else:
        data = DATA if release_id == RELEASE else DATA.parent / release_id
        manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
        validate(recipe, release_id, manifest, elastic('/')['version']['number'])
        count = manifest['count']
        blob_path = None
    if recipe['index_kind'] != 'shared' or recipe['product_sha256'] != dataset_sha256:
        raise ValueError('Shared index recipe differs from the environment request.')
    definition = recipe['index_definition']
    try:
        existing = elastic('/' + index)[index]
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        existing = None
    if existing:
        mapping = dict(existing['mappings'])
        marker = mapping.pop('_meta', {}).get('index_recipe_sha256')
        marker_mismatch = (marker != recipe_sha256 if recipe['format'] == 2
                           else bool(marker and marker != recipe_sha256))
        if mapping != definition['mappings'] or marker_mismatch:
            raise ValueError('Shared index has a different historical mapping or recipe.')
        settings = existing['settings']['index']
        if any(str(settings.get(key)) != str(value) for key, value in definition['settings'].items()):
            raise ValueError('Shared index has different historical settings.')
        if settings.get('blocks', {}).get('write') != 'true' or \
                elastic('/' + index + '/_count')['count'] != count:
            raise ValueError('Shared index is not frozen with the expected document count.')
        if marker:
            verify_recovered(index, recipe, recipe_sha256)
        errors = []
        try:
            save_snapshot(index, recipe, recipe_sha256)
        except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
            errors.append('snapshot save: ' + type(error).__name__ + ': ' + str(error))
        return {'index': index, 'created': False, 'count': count,
                'materialisation': 'reuse', 'seconds': 0, 'recovery_errors': errors}
    errors = []
    for method in (clone_from_live, restore_snapshot):
        try:
            recovered = method(index, recipe, recipe_sha256)
            if recovered:
                if recovered['source'] == 'clone':
                    try:
                        save_snapshot(index, recipe, recipe_sha256)
                    except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
                        errors.append('snapshot save: ' + type(error).__name__ + ': ' + str(error))
                return {'index': index, 'created': True, 'count': count,
                        'materialisation': recovered['source'], 'seconds': recovered['seconds'],
                        'recovery_errors': errors}
        except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
            errors.append(type(error).__name__ + ': ' + str(error))
    if blob_path is None:
        blob_path = publish_blobs(manifest, data)
    definition = json.loads(json.dumps(definition))
    definition['mappings']['_meta'] = {'index_recipe_sha256': recipe_sha256}
    started = time.monotonic()
    elastic('/' + index, 'PUT', definition)
    try:
        index_job(blob_path, dataset_sha256, index=index, role='retail-shared-indexer',
                  expected_count=count, compression=recipe['compression'],
                  deadline_seconds=1500 if count >= 1_000_000 else 300,
                  worker_source=recipe['indexer']['source'], worker_image=recipe['indexer']['image'])
        elastic('/' + index + '/_settings', 'PUT', {'index.blocks.write': True})
        if elastic('/' + index + '/_count')['count'] != count:
            raise ValueError('Recreated shared index has the wrong document count.')
    except Exception:
        elastic('/' + index, 'DELETE')
        raise
    try:
        save_snapshot(index, recipe, recipe_sha256)
    except (ValueError, RuntimeError, TimeoutError, urllib.error.HTTPError) as error:
        errors.append('snapshot save: ' + type(error).__name__ + ': ' + str(error))
    return {'index': index, 'created': True, 'count': count,
            'materialisation': 'rebuild', 'seconds': round(time.monotonic() - started, 3),
            'recovery_errors': errors}
