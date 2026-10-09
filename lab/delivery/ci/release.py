"""Provider-independent immutable release format and publication. Python stdlib only."""
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
import urllib.error
import urllib.request

try:
    from .versioning import parse, declared, build_version
except ImportError:  # The source workflow invokes this file directly.
    from versioning import parse, declared, build_version


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def validate(release):
    if release.get('format') != 1 or not re.fullmatch(r'[a-f0-9]{40}', release.get('source_sha', '')):
        raise ValueError('Release must identify an exact Git source revision.')
    if not re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', release.get('image', '')):
        raise ValueError('Release image must be pinned by digest.')
    if not re.fullmatch(r'[a-f0-9]{64}', release.get('bundle_sha256', '')):
        raise ValueError('Release bundle checksum is missing.')
    files = release.get('files', {})
    if not all(name in files for name in ('chart/Chart.yaml', 'chart/templates/environment.yaml',
                                          'contracts/index.json', 'contracts/indexer.py', 'app/app.py', 'app/index.html')):
        raise ValueError('Release is missing deployment, schema or query-pipeline assets.')
    if any(not re.fullmatch(r'[a-f0-9]{64}', value) for value in files.values()):
        raise ValueError('Invalid release file checksum.')
    contract = release.get('index_contract', {})
    if (not contract.get('engine_version') or not contract.get('definitions') or
            not re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', contract.get('indexer_image', '')) or
            not re.fullmatch(r'[a-f0-9]{64}', contract.get('indexer_source_sha256', '')) or
            any(set(definition) != {'settings', 'mappings'} for definition in contract['definitions'])):
        raise ValueError('Index compatibility contract is incomplete.')
    if files['contracts/indexer.py'] != contract['indexer_source_sha256']:
        raise ValueError('Indexer source hash differs from the compatibility contract.')
    if 'version' in release:
        parse(release['version'])
        _, pre, metadata = parse(release.get('declared_version'))
        if pre or metadata or not re.fullmatch('[a-f0-9]{40}', release.get('source_tree', '')) or \
                files.get('VERSION') != digest((release['declared_version'] + '\n').encode()):
            raise ValueError('Version metadata differs from the versioned source tree or VERSION file.')
    return release


def bundle(root):
    files = sorted(p for folder in ('app', 'chart', 'contracts') for p in (root / folder).rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts)
    if (root / 'VERSION').exists():
        files.append(root / 'VERSION')
    hashes = {}
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        for path in files:
            if path.is_symlink():
                raise ValueError('Release bundles cannot contain symlinks.')
            name = path.relative_to(root).as_posix()
            content = path.read_bytes()
            hashes[name] = digest(content)
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
    return gzip.compress(output.getvalue(), mtime=0), hashes


def publish(base, path, content, username, password, check_only=False):
    auth = 'Basic ' + base64.b64encode((username + ':' + password).encode()).decode()
    url = base.rstrip('/') + '/' + path
    headers = {'Authorization': auth, 'Content-Type': 'application/octet-stream'}
    def read():
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
            return response.read()
    try:
        existing = read()
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        if check_only:
            return
    else:
        if existing != content:
            raise ValueError('Refusing to replace an immutable artifact: ' + path)
        return
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=content, method='PUT',
                                    headers=headers), timeout=60):
            pass
    except urllib.error.HTTPError as error:
        if error.code not in (400, 409) or read() != content:
            raise
    if read() != content:
        raise ValueError('Artifact read-back failed: ' + path)


def main():
    root = Path.cwd()
    version = declared(root)
    if (root / 'VERSION').read_bytes() != (version + '\n').encode():
        raise ValueError('VERSION must contain the version followed by one LF newline.')
    payload, hashes = bundle(root)
    metadata = json.loads((root / 'image-metadata.json').read_text())
    image = os.environ['REGISTRY'] + '/search-api@' + metadata['containerimage.digest']
    contract = json.loads((root / 'contracts/index.json').read_text())
    release = validate({'format': 1, 'source_repository': os.environ['SOURCE_REPOSITORY'],
        'source_sha': os.environ['SOURCE_SHA'], 'image': image, 'bundle_sha256': digest(payload),
        'files': hashes, 'index_contract': contract, 'declared_version': version,
        'source_tree': os.environ['SOURCE_TREE'], 'version': build_version(version, os.environ['EVENT_KIND'],
            os.environ['RUN_ID'], os.environ['RUN_ATTEMPT'], os.environ.get('PR_NUMBER'))})
    descriptor = canonical(release)
    release_id = digest(descriptor)
    def put(path, content, check_only=False):
        publish(os.environ['ARTIFACT_URL'], path, content,
                os.environ['NEXUS_USER'], os.environ['NEXUS_PASSWORD'], check_only)
    put('bundles/' + release['bundle_sha256'] + '.tar.gz', payload)
    put('releases/' + release_id + '.json', descriptor)
    # PRs check existing reservations without creating them. Main publication
    # atomically reserves the version in Nexus's ALLOW_ONCE repository.
    put('versions/' + version + '.json', canonical({'version': version,
        'source_repository': release['source_repository'], 'source_tree': release['source_tree']}),
        check_only=os.environ['EVENT_KIND'] == 'pull_request')
    # This receipt is written last. A failed job cannot leave a complete release receipt.
    receipt = {'format': 1, 'release_id': release_id, 'source_sha': release['source_sha'],
               'source_repository': release['source_repository'], 'image': image,
               'event_kind': os.environ['EVENT_KIND'], 'run_id': os.environ['RUN_ID'],
               'run_attempt': os.environ['RUN_ATTEMPT'], 'version': release['version']}
    if os.environ['EVENT_KIND'] == 'pull_request':
        receipt['pr_number'] = int(os.environ['PR_NUMBER'])
    put('builds/' + release['source_sha'] + '/' + receipt['run_id'] + '-' + receipt['run_attempt'] + '.json',
        canonical(receipt))
    print('RELEASE_ID=' + release_id)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
