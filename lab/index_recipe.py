"""Immutable input contract for recreating a frozen Elasticsearch index."""
import hashlib
import json
import re
from pathlib import Path

from azure.core.exceptions import ResourceExistsError

from blob_config import service, settings
from load_release import BASELINE_MAPPING, INDEXER_IMAGE
from load_million_release import MAPPING as MILLION_MAPPING
from input_selection import fetch_manifest


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def catalogue_digest(value):
    """Match the newline-terminated v1 data contract manifest bytes."""
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()).hexdigest()


def current_recipe(release_id, index_kind, release_manifest, engine_version, mapping=None):
    if mapping is None:
        mapping = MILLION_MAPPING if release_manifest.get('compression') == 'gzip' else BASELINE_MAPPING
    product_name = 'products.jsonl.gz' if release_manifest.get('compression') == 'gzip' else 'products.jsonl'
    worker = (Path(__file__).resolve().parent.parent / 'research/platform-spike/index_job.py').read_text(encoding='utf-8')
    return {
        'format': 1, 'release_id': release_id, 'index_kind': index_kind,
        'release_manifest_sha256': digest(release_manifest),
        'product_object': product_name, 'product_sha256': release_manifest['sha256'][product_name],
        'document_count': release_manifest['count'], 'compression': release_manifest.get('compression', 'none'),
        'index_definition': mapping, 'engine_version': engine_version,
        'indexer': {'image': INDEXER_IMAGE, 'source_sha256': hashlib.sha256(worker.encode('utf-8')).hexdigest(),
                    'source': worker},
    }


def catalogue_recipe(release_id, index_kind, catalogue_manifest, engine_version, mapping=None):
    """Build a v2 recipe pinned to catalogue bytes, independent of qrels/queries."""
    if catalogue_manifest.get('kind') != 'catalogue' or \
            catalogue_manifest.get('schema_version') != 1:
        raise ValueError('A v1 catalogue artifact manifest is required.')
    content = catalogue_manifest['content']
    if content['format'] != 'jsonl' or content['compression'] not in ('gzip', 'none'):
        raise ValueError('Unsupported catalogue encoding for the indexer.')
    if mapping is None:
        mapping = MILLION_MAPPING if content['compression'] == 'gzip' else BASELINE_MAPPING
    worker = (Path(__file__).resolve().parent.parent / 'research/platform-spike/index_job.py').read_text(encoding='utf-8')
    recipe = {'format': 2, 'release_id': release_id, 'index_kind': index_kind,
              'catalogue_manifest_sha256': catalogue_digest(catalogue_manifest),
              'product_object': Path(content['object']).name,
              'product_sha256': content['sha256'],
              'document_count': catalogue_manifest['record_count'],
              'compression': content['compression'], 'index_definition': mapping,
              'engine_version': engine_version,
              'indexer': {'image': INDEXER_IMAGE,
                          'source_sha256': hashlib.sha256(worker.encode('utf-8')).hexdigest(),
                          'source': worker}}
    return validate(recipe, release_id=release_id, catalogue_manifest=catalogue_manifest,
                    engine_version=engine_version)


def validate(recipe, release_id=None, release_manifest=None, engine_version=None,
             catalogue_manifest=None):
    kind = recipe.get('index_kind', '')
    if recipe.get('format') not in (1, 2) or \
            (kind != 'shared' and not re.fullmatch(r'[a-z0-9-]+-v[0-9]+', kind)):
        raise ValueError('Unsupported frozen index recipe.')
    if release_id is not None and recipe['release_id'] != release_id:
        raise ValueError('Frozen index recipe belongs to another release.')
    if engine_version is not None and recipe['engine_version'] != engine_version:
        raise ValueError('Frozen index recipe requires a different Elasticsearch version.')
    worker = recipe['indexer']
    if hashlib.sha256(worker['source'].encode('utf-8')).hexdigest() != worker['source_sha256']:
        raise ValueError('Frozen indexer source hash differs.')
    if '@sha256:' not in worker['image']:
        raise ValueError('Frozen indexer image must use a digest.')
    if release_manifest is not None:
        product_name = 'products.jsonl.gz' if release_manifest.get('compression') == 'gzip' else 'products.jsonl'
        if ((recipe['format'] == 1 and recipe['release_manifest_sha256'] != digest(release_manifest)) or
                recipe['product_object'] != product_name or
                recipe['product_sha256'] != release_manifest['sha256'][product_name] or
                recipe['document_count'] != release_manifest['count'] or
                recipe['compression'] != release_manifest.get('compression', 'none')):
            raise ValueError('Frozen release differs from the index recipe.')
    if recipe['format'] == 2:
        identifier = recipe.get('catalogue_manifest_sha256', '')
        if len(identifier) != 64 or any(c not in '0123456789abcdef' for c in identifier):
            raise ValueError('Catalogue recipe has no pinned manifest.')
        if catalogue_manifest is not None:
            content = catalogue_manifest['content']
            if (catalogue_digest(catalogue_manifest) != identifier or
                    content['sha256'] != recipe['product_sha256'] or
                    Path(content['object']).name != recipe['product_object'] or
                    catalogue_manifest['record_count'] != recipe['document_count'] or
                    content['compression'] != recipe['compression']):
                raise ValueError('Catalogue artifact differs from the index recipe.')
    if set(recipe['index_definition']) != {'settings', 'mappings'}:
        raise ValueError('Frozen index recipe has no complete index definition.')
    return recipe


def blob_name(recipe_sha256):
    if len(recipe_sha256) != 64 or any(c not in '0123456789abcdef' for c in recipe_sha256):
        raise ValueError('Invalid frozen index recipe SHA-256.')
    return f'index-recipes/{recipe_sha256}.json'


def shared_index_name(recipe, recipe_sha256):
    """Keep historical shared names while isolating each independent recipe."""
    if recipe['index_kind'] != 'shared':
        raise ValueError('A dedicated recipe has no shared index name.')
    blob_name(recipe_sha256)
    return (recipe['release_id'] if recipe['format'] == 1 else
            recipe['release_id'] + '-r' + recipe_sha256[:24])


def publish(recipe):
    validate(recipe)
    payload = canonical(recipe)
    recipe_sha = hashlib.sha256(payload).hexdigest()
    account = service()
    _, container, _, _ = settings()
    try:
        account.create_container(container)
    except ResourceExistsError:
        pass
    blob = account.get_blob_client(container, blob_name(recipe_sha))
    try:
        blob.upload_blob(payload, overwrite=False, length=len(payload))
    except ResourceExistsError:
        pass
    if blob.download_blob().readall() != payload:
        raise ValueError('Stored frozen index recipe differs from the pinned content.')
    return recipe_sha


def load(recipe_sha256):
    _, container, _, _ = settings()
    payload = service().get_blob_client(container, blob_name(recipe_sha256)).download_blob().readall()
    if hashlib.sha256(payload).hexdigest() != recipe_sha256:
        raise ValueError('Stored frozen index recipe hash differs.')
    recipe = json.loads(payload)
    if canonical(recipe) != payload:
        raise ValueError('Stored frozen index recipe encoding differs.')
    return validate(recipe)


def verify_catalogue_manifest(recipe):
    """Admit a new v2 recipe only when its independent catalogue is retained."""
    if recipe.get('format') != 2:
        raise ValueError('Only a v2 catalogue recipe can introduce a new index recipe.')
    manifest = fetch_manifest('catalogue', recipe['catalogue_manifest_sha256'])
    validate(recipe, catalogue_manifest=manifest)
    _, container, _, _ = settings()
    content = manifest['content']
    retained = service().get_blob_client(container, content['object'])
    checksum, size = hashlib.sha256(), 0
    for chunk in retained.download_blob().chunks():
        checksum.update(chunk)
        size += len(chunk)
    if checksum.hexdigest() != content['sha256'] or size != content['bytes']:
        raise ValueError('Retained catalogue bytes differ from the pinned manifest.')
    return manifest
