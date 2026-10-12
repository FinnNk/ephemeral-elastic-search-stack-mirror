"""Catalogue dates and physical index creation times, outside frozen data hashes."""
from datetime import datetime, timezone
from catalogue import PROFILES
from data_contract import elastic


def catalogue_metadata(release):
    """Return the reviewed simulated data timestamp for a configured catalogue."""
    profile = PROFILES['releases'].get(release, {})
    # Protected legacy recipes also receive an explicit simulated baseline date.
    return {'catalogue_timestamp': profile.get('catalogue_timestamp', '2026-01-01T00:00:00Z'),
            'catalogue_timestamp_kind': profile.get('catalogue_timestamp_kind', 'synthetic')}


def index_metadata(index, release, actual):
    """Prefer Elasticsearch's creation date; never present a fallback as observed."""
    created = actual.get('settings', {}).get('index', {}).get('creation_date')
    catalogue = catalogue_metadata(release)
    timestamp = (datetime.fromtimestamp(int(created)/1000, timezone.utc)
                 .isoformat(timespec='seconds').replace('+00:00', 'Z')) if created else catalogue['catalogue_timestamp']
    return {'index': index, 'release': release, **catalogue,
            'index_created_at': timestamp,
            'index_timestamp_kind': 'observed' if created else 'synthetic'}


def record_index_metadata(index, release, actual=None, *, client=None):
    """Preserve recipe markers while attaching dates to a verified lab index."""
    client = client or elastic
    actual = actual or client('/' + index)[index]
    old = actual.get('mappings', {}).get('_meta', {})
    dates = index_metadata(index, release, actual)
    metadata = {**old, **{key: dates[key] for key in (
        'catalogue_timestamp', 'catalogue_timestamp_kind', 'index_created_at', 'index_timestamp_kind')}}
    if metadata != old:
        client('/' + index + '/_mapping', 'PUT', {'_meta': metadata})
    return dates


def existing_indices(release):
    """List recipes available for restoration, with their current index timestamps."""
    if release not in PROFILES['releases']:
        raise ValueError('Choose a configured catalogue.')
    from index_recipe import load
    values = elastic('/_all?filter_path=*.mappings._meta,*.settings.index.creation_date')
    recipes, rows = {}, []
    for name, actual in values.items():
        marker = actual.get('mappings', {}).get('_meta', {}).get('index_recipe_sha256')
        recipe = None
        if marker:
            if marker not in recipes:
                recipes[marker] = load(marker)
            recipe = recipes[marker]
            if recipe['release_id'] != release:
                continue
        elif name != release and not name.startswith(release + '-r'):
            continue
        rows.append({**index_metadata(name, release, actual), 'recipe_sha256': marker,
                     'index_kind': recipe['index_kind'] if recipe else 'shared'})
    return sorted(rows, key=lambda row: (row['index_created_at'], row['index']), reverse=True)
