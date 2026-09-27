"""Validate and publish synthetic input artifacts without the control runtime."""

import argparse
import json
import os
from pathlib import Path

from contracts import canonical, envelope, input_files, sha_file, validate_records


def upload(client, container, object_name, payload, digest, size):
    blob = client.get_blob_client(container, object_name)
    try:
        blob.upload_blob(payload, overwrite=False, metadata={'sha256': digest})
    except Exception as error:
        from azure.core.exceptions import ResourceExistsError
        if not isinstance(error, ResourceExistsError):
            raise
        existing = blob.get_blob_properties()
        if existing.metadata.get('sha256') != digest or existing.size != size:
            raise ValueError('Existing Blob object has a different content hash.') from None


def blob_client(url):
    from azure.storage.blob import BlobServiceClient
    connection = os.environ.get('DATA_BLOB_CONNECTION_STRING')
    if connection:
        return BlobServiceClient.from_connection_string(connection)
    if not url.startswith('https://'):
        raise ValueError('Use HTTPS and workload identity outside the local emulator.')
    from azure.identity import DefaultAzureCredential
    return BlobServiceClient(account_url=url, credential=DefaultAzureCredential())


def publish(directory, output, producer, source_release, traffic=None, blob_url=None,
            container='datasets'):
    directory, output = Path(directory), Path(output)
    files = input_files(directory)
    if traffic is not None:
        files['traffic-trace'] = Path(traffic)
    counts = validate_records(files, traffic)
    provenance = {'source_release': source_release}
    output.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for kind, path in files.items():
        dependencies = {}
        if kind in ('judgement-set', 'traffic-trace'):
            dependencies['query-suite'] = manifests['query-suite']['content']['sha256']
        if kind == 'judgement-set':
            dependencies['catalogue'] = manifests['catalogue']['content']['sha256']
        manifest = envelope(kind, path, producer, dependencies, counts[kind], provenance)
        manifests[kind] = manifest
        target = output / (kind + '.json')
        payload = canonical(manifest)
        if target.exists() and target.read_bytes() != payload:
            raise ValueError('Existing artifact manifest differs: ' + str(target))
        if not target.exists():
            target.write_bytes(payload)
    if blob_url:
        client = blob_client(blob_url)
        from azure.core.exceptions import ResourceExistsError
        try:
            client.create_container(container)
        except ResourceExistsError:
            pass
        for kind, path in files.items():
            manifest = manifests[kind]
            digest = manifest['content']['sha256']
            with path.open('rb') as source:
                upload(client, container, manifest['content']['object'], source, digest,
                       path.stat().st_size)
            manifest_bytes = canonical(manifest)
            manifest_digest = sha_file(output / (kind + '.json'))
            upload(client, container, f'manifests/{kind}/{manifest_digest}.json',
                   manifest_bytes, manifest_digest, len(manifest_bytes))
    return {kind: {'content_sha256': value['content']['sha256'],
                   'manifest_sha256': sha_file(output / (kind + '.json'))}
            for kind, value in manifests.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--producer', required=True)
    parser.add_argument('--source-release', required=True,
                        help='Stable identity of the synthetic source pack')
    parser.add_argument('--traffic', type=Path)
    parser.add_argument('--blob-url')
    parser.add_argument('--container', default='datasets')
    args = parser.parse_args()
    print(json.dumps(publish(args.input_dir, args.output, args.producer,
                             args.source_release, args.traffic, args.blob_url,
                             args.container), indent=2))


if __name__ == '__main__':
    main()
