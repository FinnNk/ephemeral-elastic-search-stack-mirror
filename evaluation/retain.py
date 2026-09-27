"""Retain immutable observation, judgement and evaluation files in Blob storage."""

import argparse
import hashlib
import json
import os
from pathlib import Path


KINDS = ('observation-set', 'judgement-set', 'judgement-manifest',
         'evaluation-specification', 'evaluation-report', 'promotion-policy')


def retain(path, kind, container):
    if kind not in KINDS:
        raise ValueError('Unsupported retained evaluation artifact kind.')
    connection = os.environ.get('DATA_BLOB_CONNECTION_STRING')
    if not connection:
        raise ValueError('Supply a scoped Blob connection through the environment.')
    from azure.core.exceptions import ResourceExistsError
    from azure.storage.blob import BlobServiceClient
    client = BlobServiceClient.from_connection_string(connection)
    try:
        client.create_container(container)
    except ResourceExistsError:
        pass
    path = Path(path)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    object_name = kind + '/' + digest + '/' + path.name
    blob = client.get_blob_client(container, object_name)
    try:
        blob.upload_blob(payload, overwrite=False, metadata={'sha256': digest})
    except ResourceExistsError:
        properties = blob.get_blob_properties()
        if properties.metadata.get('sha256') != digest or properties.size != len(payload):
            raise ValueError('Existing retained object differs.') from None
    return {'kind': kind, 'sha256': digest, 'bytes': len(payload),
            'blob': container + '/' + object_name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', required=True, type=Path)
    parser.add_argument('--kind', required=True,
                        choices=KINDS)
    parser.add_argument('--container', default='runs')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    value = retain(args.file, args.kind, args.container)
    payload = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and args.output.read_bytes() != payload:
        raise ValueError('Existing retained reference differs.')
    if not args.output.exists():
        args.output.write_bytes(payload)
    print(json.dumps(value))


if __name__ == '__main__':
    main()
