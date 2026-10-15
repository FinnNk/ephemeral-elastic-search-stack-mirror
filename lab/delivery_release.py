"""Verify retained release descriptors, bundles and successful provider build receipts."""
import io
from functools import lru_cache
import json
from pathlib import PurePosixPath
import tarfile

from delivery.ci.release import canonical, digest, validate
from delivery_provider import SOURCE, api, endpoint
from nexus import request


def validate_bundle(release, content):
    if digest(content) != release['bundle_sha256']:
        raise ValueError('Release bundle checksum differs.')
    result = {}
    with tarfile.open(fileobj=io.BytesIO(content), mode='r:gz') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or '..' in path.parts or
                    '\\' in member.name or member.name in result or member.size > 4_000_000):
                raise ValueError('Unsafe or duplicated release bundle member.')
            result[member.name] = archive.extractfile(member).read()
    if {name: digest(data) for name, data in result.items()} != release['files']:
        raise ValueError('Release files differ from the descriptor.')
    if json.loads(result['contracts/index.json']) != release['index_contract']:
        raise ValueError('Index contract differs from the descriptor.')
    if digest(result['contracts/indexer.py']) != release['index_contract']['indexer_source_sha256']:
        raise ValueError('Indexer source differs from the contract.')
    if release.get('version') and result.get('VERSION') != (release['declared_version'] + '\n').encode():
        raise ValueError('Version file differs from the release descriptor.')
    return result


def load_descriptor(release_id):
    if len(release_id) != 64 or any(c not in '0123456789abcdef' for c in release_id):
        raise ValueError('Invalid release ID.')
    descriptor = request('/repository/lab-releases/releases/' + release_id + '.json', identity='reader')
    if digest(descriptor) != release_id:
        raise ValueError('Release descriptor checksum differs.')
    release = validate(json.loads(descriptor))
    if canonical(release) != descriptor:
        raise ValueError('Release encoding differs.')
    return release


def load(release_id):
    release = load_descriptor(release_id)
    bundle = request('/repository/lab-releases/bundles/' + release['bundle_sha256'] + '.tar.gz', identity='reader')
    return release, validate_bundle(release, bundle)


def from_run(run_id):
    """Return a verified receipt, release and files for an exact successful build."""
    receipt, release, files, _payload = from_run_bytes(run_id)
    return receipt, release, files


def from_run_bytes(run_id):
    """Also retain the original receipt bytes for evidence signing."""
    run = api(endpoint(SOURCE, '/actions/runs/' + str(run_id)))
    if run['status'] != 'completed' or run['conclusion'] != 'success':
        raise ValueError('Source build has not succeeded.')
    path = 'builds/' + run['head_sha'] + '/' + str(run['id']) + '-' + str(run['run_attempt']) + '.json'
    payload = request('/repository/lab-releases/' + path, identity='reader')
    receipt = json.loads(payload)
    release, files = load(receipt['release_id'])
    validate_receipt(run, receipt, release)
    return receipt, release, files, payload


def validate_receipt(run, receipt, release):
    """Bind displayed and deployed metadata to the same exact successful build."""
    if (receipt['source_sha'] != run['head_sha'] or release['source_sha'] != run['head_sha'] or
            receipt['event_kind'] != run['event'] or receipt['source_repository'] != 'elastic-agent/' + SOURCE or
            release['source_repository'] != receipt['source_repository'] or receipt['image'] != release['image'] or
            str(receipt['run_id']) != str(run['id']) or str(receipt['run_attempt']) != str(run['run_attempt'])):
        raise ValueError('Build receipt does not match the exact successful source run.')
    if release.get('version'):
        from delivery.ci.versioning import build_version
        expected = build_version(release['declared_version'], run['event'], run['id'], run['run_attempt'],
                                 receipt.get('pr_number'))
        if receipt.get('version') != release['version'] or expected != release['version']:
            raise ValueError('Version differs from the exact successful build.')


def build_metadata(run):
    """Read successful-build identity without downloading its source bundle."""
    if run.get('status') != 'completed' or run.get('conclusion') != 'success':
        return {}
    return dict(_build_metadata(run['id'], run['run_attempt'], run['head_sha'], run['event']))


@lru_cache(maxsize=128)
def _build_metadata(identifier, attempt, source, event):
    run = {'id': identifier, 'run_attempt': attempt, 'head_sha': source, 'event': event}
    path = f'builds/{source}/{identifier}-{attempt}.json'
    receipt = json.loads(request('/repository/lab-releases/' + path, identity='reader'))
    release = load_descriptor(receipt['release_id'])
    validate_receipt(run, receipt, release)
    return {'version': release.get('version'), 'release_id': receipt['release_id']}
