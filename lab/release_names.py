"""Readable release identity and optional source-pinned changelog links."""
from functools import lru_cache
from urllib.parse import quote

from delivery_provider import api, endpoint, SOURCE


def label(deployment):
    fields = deployment.get('fields', {})
    return ((fields.get('software_version') or 'Version not recorded') + ' · ' +
            (fields.get('source_sha', '')[:12] or 'Commit not recorded') +
            ' · build ' + str(deployment.get('build_run', '?')))


@lru_cache(maxsize=128)
def _changelog(source):
    if not source:
        return None
    try:
        value = api(endpoint(SOURCE, '/contents/CHANGELOG.md?ref=' + quote(source, safe='')))
        if value.get('type') == 'file':
            return 'https://gitea.localhost:34443/elastic-agent/delivery-source/src/commit/' + source + '/CHANGELOG.md'
    except RuntimeError as error:
        if getattr(error, 'status_code', None) != 404:
            raise
    return None


def changelog(source):
    try:
        return _changelog(source)
    except (RuntimeError, OSError):
        # Retry transient provider failures on the next refresh.
        return None
