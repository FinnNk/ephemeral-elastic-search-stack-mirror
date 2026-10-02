"""Validate and publish input artifacts without the control runtime."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from contracts import canonical, envelope, input_files, sha_file, validate_records


def upload(client, container, object_name, payload, digest, size):
    blob = client.get_blob_client(container, object_name)
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

    def verify_existing(existing):
        if existing.size != size:
            raise ValueError('Existing Blob object has a different content hash.')
        if existing.metadata.get('sha256') != digest:
            checksum = hashlib.sha256()
            for chunk in blob.download_blob().chunks():
                checksum.update(chunk)
            if checksum.hexdigest() != digest:
                raise ValueError('Existing Blob object has a different content hash.')

    try:
        existing = blob.get_blob_properties()
    except ResourceNotFoundError:
        pass
    else:
        verify_existing(existing)
        return
    try:
        blob.upload_blob(payload, overwrite=False, metadata={'sha256': digest})
    except ResourceExistsError:
        verify_existing(blob.get_blob_properties())



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
            container='datasets', provenance=None, blob_service=None):
    directory, output = Path(directory), Path(output)
    files = input_files(directory)
    if traffic is not None:
        files['traffic-trace'] = Path(traffic)
    counts = validate_records(files, traffic)
    provenance = {**(provenance or {}), 'source_release': source_release}
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
        client = blob_service or blob_client(blob_url)
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
                        help='Stable identity of the source pack')
    parser.add_argument('--provenance', type=Path, help='JSON producer provenance, including published sources and augmentations')
    parser.add_argument('--traffic', type=Path)
    parser.add_argument('--blob-url')
    parser.add_argument('--container', default='datasets')
    args = parser.parse_args()
    print(json.dumps(publish(args.input_dir, args.output, args.producer,
                             args.source_release, args.traffic, args.blob_url,
                             args.container, json.loads(args.provenance.read_text(encoding='utf-8')) if args.provenance else None), indent=2))


if __name__ == '__main__':
    main()
