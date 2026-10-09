"""Publish stable source tags after verifying successful merged-source releases."""
from urllib.parse import quote

from common import STATE
from delivery_provider import SOURCE, api, endpoint
from delivery_release import from_run
from delivery.ci.release import canonical
from gitea import GiteaHTTPError
from nexus import request


def ensure_tag(receipt, release):
    """Create a tag once; never move an existing tag to a different source tree."""
    if receipt['event_kind'] != 'push' or not release.get('version'):
        return None
    version = release['declared_version']
    claim = {'version': version, 'source_repository': release['source_repository'],
             'source_tree': release['source_tree']}
    if request('/repository/lab-releases/versions/' + version + '.json', identity='reader') != canonical(claim):
        raise ValueError('Published semantic version is bound to different source contents.')
    source = api(endpoint(SOURCE, '/git/commits/' + release['source_sha']))
    if source['commit']['tree']['sha'] != release['source_tree']:
        raise ValueError('Published source tree differs from its Git commit.')
    name = 'v' + version
    path = endpoint(SOURCE, '/tags/' + quote(name, safe=''))
    try:
        tag = api(path)
    except GiteaHTTPError as error:
        if error.status_code != 404:
            raise
        try:
            api(endpoint(SOURCE, '/tags'), 'POST', {'tag_name': name, 'target': release['source_sha'],
                'message': 'Delivery release ' + version + '\nRelease ID: ' + receipt['release_id']})
        except GiteaHTTPError as error:
            if error.status_code not in (409, 422):
                raise
        tag = api(path)
    commit = tag.get('commit') or {}
    sha = commit.get('sha') or commit.get('id')
    if not sha or api(endpoint(SOURCE, '/git/commits/' + sha))['commit']['tree']['sha'] != release['source_tree']:
        raise ValueError('Refusing to retarget a semantic version tag with different source contents.')
    return {'tag': name, 'source_sha': sha, 'source_tree': release['source_tree'],
            'version': release['version']}


def sync_tags():
    """Reconcile recent successful main builds; failures leave other work available."""
    results = []
    try:
        runs = api(endpoint(SOURCE, '/actions/runs?limit=50'))['workflow_runs']
    except (RuntimeError, OSError, KeyError, ValueError):
        return [{'state': 'version-tag-unavailable'}]
    folder = STATE / 'delivery/version-tags'
    checked = 0
    for run in runs:
        if run.get('event') != 'push' or run.get('path') != 'release.yaml@refs/heads/main' or \
                run.get('status') != 'completed' or run.get('conclusion') != 'success':
            continue
        record = folder / (str(run['id']) + '-' + str(run['run_attempt']) + '.json')
        if record.exists():
            continue
        if checked >= 5:
            break
        checked += 1
        try:
            receipt, release, _ = from_run(run['id'])
            tagged = ensure_tag(receipt, release)
            folder.mkdir(parents=True, exist_ok=True)
            record.write_bytes(canonical(tagged or {'state': 'unversioned'}))
            if tagged:
                results.append({'state': 'version-tag-published', **tagged})
        except Exception as error:
            # Provider tracebacks remain private; the watcher can retry next time.
            results.append({'state': 'version-tag-failed', 'run': run['id'], 'error': type(error).__name__})
    return results
