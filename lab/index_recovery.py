"""Recover a pinned frozen index from an exact live copy or regular snapshot."""
import os
import re
import time
import urllib.error

from data_contract import elastic


SAMPLE = {'query': {'match_all': {}}, 'sort': [{'product_id': 'asc'}], 'size': 10}


def sample_ids(index):
    return [hit['_id'] for hit in elastic('/' + index + '/_search', 'POST', SAMPLE)['hits']['hits']]


def verify(index, recipe, recipe_sha, expected_sample=None):
    actual = elastic('/' + index)[index]
    mapping = dict(actual['mappings'])
    marker = mapping.pop('_meta', {}).get('index_recipe_sha256')
    definition = recipe['index_definition']
    settings = actual['settings']['index']
    if marker != recipe_sha or mapping != definition['mappings']:
        raise ValueError('Recovered index has a different recipe or mapping.')
    if any(str(settings.get(key)) != str(value) for key, value in definition['settings'].items()):
        raise ValueError('Recovered index settings differ from the recipe.')
    if settings.get('blocks', {}).get('write') != 'true':
        raise ValueError('Recovered index is not write blocked.')
    if elastic('/' + index + '/_count')['count'] != recipe['document_count']:
        raise ValueError('Recovered index document count differs from the recipe.')
    ordered = sample_ids(index)
    if len(ordered) != min(10, recipe['document_count']):
        raise ValueError('Recovered index ordered sample is incomplete.')
    if expected_sample is not None and ordered != expected_sample:
        raise ValueError('Recovered index ordered sample differs from its source.')
    return ordered


def _missing(path):
    try:
        return elastic(path)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def _repository():
    repository = os.environ.get('LAB_SNAPSHOT_REPOSITORY', '').strip()
    if repository and not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}', repository):
        raise ValueError('Invalid LAB_SNAPSHOT_REPOSITORY.')
    return repository


def snapshot_name(recipe_sha):
    if not re.fullmatch(r'[0-9a-f]{64}', recipe_sha):
        raise ValueError('Invalid index recipe hash.')
    return 'frozen-' + recipe_sha


def _repository_ready(repository):
    verified = elastic('/_snapshot/' + repository + '/_verify', 'POST')
    if not verified.get('nodes'):
        raise ValueError('Snapshot repository has no verified node.')


def clone_from_live(target, recipe, recipe_sha):
    """Only exact, write-blocked copies qualify; a clone keeps the source schema."""
    indices = elastic('/_cat/indices?format=json&h=index')
    names = sorted(item['index'] for item in indices if item['index'] != target and
                   (item['index'].endswith('-idx') or item['index'] == recipe['release_id']))
    for source in names:
        try:
            ordered = verify(source, recipe, recipe_sha)
        except (ValueError, urllib.error.HTTPError):
            continue
        started = time.monotonic()
        created = False
        try:
            elastic('/' + source + '/_clone/' + target + '?wait_for_active_shards=1', 'POST',
                    {'settings': {'index.number_of_replicas': recipe['index_definition']['settings']['number_of_replicas']}})
            created = True
            health = elastic('/_cluster/health/' + target + '?wait_for_status=yellow&timeout=120s')
            if health.get('timed_out'):
                raise TimeoutError('Cloned shard did not become active.')
            verify(target, recipe, recipe_sha, ordered)
            return {'source': 'clone', 'source_index': source,
                    'seconds': round(time.monotonic() - started, 3)}
        except Exception:
            if created or _missing('/' + target):
                elastic('/' + target, 'DELETE')
            raise
    return None


def restore_snapshot(target, recipe, recipe_sha):
    repository = _repository()
    if not repository:
        return None
    name = snapshot_name(recipe_sha)
    result = _missing('/_snapshot/' + repository + '/' + name)
    if not result:
        return None
    snapshot = result['snapshots'][0]
    metadata = snapshot.get('metadata') or {}
    if snapshot['state'] != 'SUCCESS' or len(snapshot['indices']) != 1 or \
            metadata.get('index_recipe_sha256') != recipe_sha or \
            metadata.get('product_sha256') != recipe['product_sha256'] or \
            metadata.get('engine_version') != recipe['engine_version'] or \
            not isinstance(metadata.get('ordered_sample'), list):
        raise ValueError('Snapshot metadata differs from the frozen recipe.')
    source = snapshot['indices'][0]
    if not re.fullmatch(r'[a-z0-9_-]+', source):
        raise ValueError('Snapshot source index has an invalid name.')
    _repository_ready(repository)
    started = time.monotonic()
    created = False
    try:
        elastic('/_snapshot/' + repository + '/' + name + '/_restore?wait_for_completion=true', 'POST', {
            'indices': source, 'include_global_state': False, 'include_aliases': False,
            'rename_pattern': source, 'rename_replacement': target})
        created = True
        health = elastic('/_cluster/health/' + target + '?wait_for_status=yellow&timeout=120s')
        if health.get('timed_out'):
            raise TimeoutError('Restored shard did not become active.')
        verify(target, recipe, recipe_sha, metadata['ordered_sample'])
        return {'source': 'snapshot', 'repository': repository, 'snapshot': name,
                'seconds': round(time.monotonic() - started, 3)}
    except Exception:
        if created or _missing('/' + target):
            elastic('/' + target, 'DELETE')
        raise


def save_snapshot(index, recipe, recipe_sha):
    """Keep one immutable copy per recipe, independent of runtime expiry."""
    repository = _repository()
    if not repository:
        return None
    name = snapshot_name(recipe_sha)
    ordered = verify(index, recipe, recipe_sha)
    existing = _missing('/_snapshot/' + repository + '/' + name)
    if existing:
        snapshot = existing['snapshots'][0]
        metadata = snapshot.get('metadata') or {}
        if snapshot['state'] != 'SUCCESS' or len(snapshot['indices']) != 1 or \
                metadata.get('index_recipe_sha256') != recipe_sha or \
                metadata.get('product_sha256') != recipe['product_sha256'] or \
                metadata.get('engine_version') != recipe['engine_version'] or \
                metadata.get('ordered_sample') != ordered:
            raise ValueError('Existing snapshot name has a different or incomplete artifact.')
        return name
    _repository_ready(repository)
    result = elastic('/_snapshot/' + repository + '/' + name + '?wait_for_completion=true', 'PUT', {
        'indices': index, 'include_global_state': False,
        'metadata': {'index_recipe_sha256': recipe_sha, 'product_sha256': recipe['product_sha256'],
                     'engine_version': recipe['engine_version'], 'ordered_sample': ordered}})
    if result['snapshot']['state'] != 'SUCCESS':
        raise ValueError('Frozen index snapshot did not complete.')
    return name
