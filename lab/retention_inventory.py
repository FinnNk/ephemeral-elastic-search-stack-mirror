"""Read-only inventory of retained inputs needed for replay and rescoring."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from contracts import release_files, sha_file, validate_envelope


def blob_service():
    connection = os.environ.get('DATA_BLOB_CONNECTION_STRING')
    if not connection:
        raise ValueError('Supply the local read credential through DATA_BLOB_CONNECTION_STRING.')
    from azure.storage.blob import BlobServiceClient
    return BlobServiceClient.from_connection_string(connection)


def blob_status(service, container, name, digest, size=None):
    from azure.core.exceptions import ResourceNotFoundError
    blob = service.get_blob_client(container, name)
    try:
        properties = blob.get_blob_properties()
    except ResourceNotFoundError:
        return 'missing'
    if properties.metadata.get('sha256') == digest and \
            (size is None or properties.size == size):
        return 'present'
    # Older retained recipes predate hash metadata; verify those bytes directly.
    payload = blob.download_blob().readall()
    return 'present' if hashlib.sha256(payload).hexdigest() == digest and \
        (size is None or len(payload) == size) else 'mismatch'


def inventory(release_dir, manifest_dir, references, recipe_shas, image_file):
    service = blob_service()
    release_dir, manifest_dir = Path(release_dir), Path(manifest_dir)
    legacy, files = release_files(release_dir)
    result = {'release': legacy['release'], 'entries': [],
              'external_backups': ['Gitea desired-state history', 'Nexus volume and image layers',
                                   'Elasticsearch snapshot repository', 'control PVC and credentials']}
    for path in sorted(manifest_dir.glob('*.json')):
        manifest_bytes = path.read_bytes()
        manifest = validate_envelope(json.loads(manifest_bytes))
        kind, content = manifest['kind'], manifest['content']
        file = files.get(kind)
        if kind == 'traffic-trace':
            file = None
        local = 'present' if file and sha_file(file) == content['sha256'] else \
            'external' if file is None else 'mismatch'
        remote = blob_status(service, 'datasets', content['object'],
                             content['sha256'], content['bytes'])
        digest = hashlib.sha256(manifest_bytes).hexdigest()
        manifest_remote = blob_status(service, 'datasets',
            f'manifests/{kind}/{digest}.json', digest, len(manifest_bytes))
        result['entries'].append({'kind': kind, 'sha256': content['sha256'],
                                  'dependencies': manifest['dependencies'],
                                  'local': local, 'blob': remote,
                                  'manifest_blob': manifest_remote})
    for path in references:
        reference = json.loads(Path(path).read_bytes())
        container, name = reference['blob'].split('/', 1)
        result['entries'].append({'kind': reference['kind'], 'sha256': reference['sha256'],
                                  'blob': blob_status(service, container, name,
                                                      reference['sha256'], reference['bytes'])})
    for digest in recipe_shas:
        result['entries'].append({'kind': 'index-recipe', 'sha256': digest,
                                  'blob': blob_status(service, 'datasets',
                                                      'index-recipes/' + digest + '.json', digest)})
    if image_file:
        for name, value in json.loads(Path(image_file).read_bytes()).items():
            image = value['image'].replace('nexus.localhost:18185', '127.0.0.1:18185')
            observed = subprocess.run(['docker', 'manifest', 'inspect', '--insecure', image],
                                      capture_output=True, text=True)
            result['entries'].append({'kind': 'tool-image', 'name': name,
                                      'sha256': value['image'].split('@sha256:')[1],
                                      'registry': 'present' if observed.returncode == 0 else 'missing'})
    result['missing'] = [row for row in result['entries'] if
                         'missing' in row.values() or 'mismatch' in row.values()]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', required=True, type=Path)
    parser.add_argument('--manifest-dir', required=True, type=Path)
    parser.add_argument('--reference', action='append', type=Path, default=[])
    parser.add_argument('--recipe-sha', action='append', default=[])
    parser.add_argument('--image-file', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    value = inventory(args.release_dir, args.manifest_dir, args.reference,
                      args.recipe_sha, args.image_file)
    payload = json.dumps(value, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    print(json.dumps({'release': value['release'], 'checked': len(value['entries']),
                      'missing': len(value['missing'])}))
    if value['missing']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
