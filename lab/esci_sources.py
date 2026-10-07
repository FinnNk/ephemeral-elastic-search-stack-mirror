"""Restore byte-identical ESCI sources from the retained GitHub release."""
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data/esci-retained.json'


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def valid(path, entry):
    return path.is_file() and path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256']


def download(url, path, entry):
    """Cache verified complete assets; retain them when a later asset fails."""
    if valid(path, entry):
        return
    temporary = path.with_name(path.name + '.download')
    request = urllib.request.Request(url, headers={'User-Agent': 'relevance-lab-installer/1'})
    count, last = 0, time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=120) as remote, temporary.open('wb') as out:
            for block in iter(lambda: remote.read(1024 * 1024), b''):
                count += len(block)
                if count > entry['bytes']:
                    raise ValueError('Asset exceeds pinned size: ' + path.name)
                out.write(block)
                if time.monotonic() - last >= 10:
                    print(f'  {path.name}: {count / 1024**2:.0f} / {entry["bytes"] / 1024**2:.0f} MiB', flush=True)
                    last = time.monotonic()
        if not valid(temporary, entry):
            raise ValueError('Downloaded asset checksum differs: ' + path.name)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def restore(directory, manifest_path=MANIFEST):
    """Reconstruct locked originals before the unchanged catalogue importer runs."""
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    original = json.loads((ROOT / 'data/esci-sources.json').read_text(encoding='utf-8'))
    locked = {item['file']: item for item in original['files']}
    if manifest['schema_version'] != 1 or manifest['repository'] != 'FinnNk/esci-s' or manifest['release'] != 'lab-sources-v1':
        raise ValueError('Unexpected retained source release.')
    if len(manifest['files']) != len(locked) or {item['file'] for item in manifest['files']} != set(locked):
        raise ValueError('Retained sources differ from the original lock.')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cache = directory / 'retained-assets'
    cache.mkdir(exist_ok=True)
    for item in manifest['files']:
        if any(item[key] != locked[item['file']][key] for key in ('sha256', 'bytes', 'url')):
            raise ValueError('Retained source identity differs: ' + item['file'])
        if item['encoding'] not in ('identity', 'zstd') or not item['assets']:
            raise ValueError('Invalid retained source encoding.')
        for asset in item['assets']:
            name = asset['name']
            if not name.startswith(item['file']) or '/' in name or '\\' in name or '..' in name:
                raise ValueError('Invalid asset filename.')
        destination = directory / item['file']
        if destination.exists():
            if not valid(destination, item):
                raise ValueError('Existing source differs; preserve it for inspection: ' + str(destination))
            print('Retained verified source: ' + item['file'], flush=True)
            continue
        print('Restoring source: ' + item['file'], flush=True)
        for asset in item['assets']:
            url = f'https://github.com/{manifest["repository"]}/releases/download/{manifest["release"]}/{asset["name"]}'
            download(url, cache / asset['name'], asset)
        temporary = destination.with_name(destination.name + '.restore')
        total = 0
        try:
            with temporary.open('wb') as out:
                for asset in item['assets']:
                    with (cache / asset['name']).open('rb') as inp:
                        if item['encoding'] == 'zstd':
                            import zstandard
                            stream = zstandard.ZstdDecompressor().stream_reader(inp)
                        else:
                            stream = inp
                        with stream:
                            for block in iter(lambda: stream.read(1024 * 1024), b''):
                                total += len(block)
                                if total > item['bytes']:
                                    raise ValueError('Reconstructed source exceeds pinned size.')
                                out.write(block)
            if not valid(temporary, item):
                raise ValueError('Reconstructed source checksum differs: ' + item['file'])
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
