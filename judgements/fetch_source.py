"""Fetch a pinned judgement set from Blob for the judgement API."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from core import canonical


def client():
    from azure.storage.blob import BlobServiceClient
    connection = os.environ.get('DATA_BLOB_CONNECTION_STRING')
    if connection:
        return BlobServiceClient.from_connection_string(connection)
    url = os.environ.get('DATA_BLOB_ACCOUNT_URL', '')
    if not url.startswith('https://'):
        raise ValueError('Azure Blob needs HTTPS and workload identity outside the lab.')
    from azure.identity import DefaultAzureCredential
    return BlobServiceClient(account_url=url, credential=DefaultAzureCredential())


def fetch(judgement_sha, catalogue_sha, query_sha, output, blob=None,
          container='datasets'):
    blob = blob or client()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for kind, expected in [('catalogue', catalogue_sha), ('query-suite', query_sha),
                           ('judgement-set', judgement_sha)]:
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Input manifest SHA-256 is invalid.')
        manifest_bytes = blob.get_blob_client(container,
            f'manifests/{kind}/{expected}.json').download_blob().readall()
        if hashlib.sha256(manifest_bytes).hexdigest() != expected:
            raise ValueError(kind + ' manifest bytes differ from the pinned hash.')
        manifest = json.loads(manifest_bytes)
        if manifest.get('kind') != kind or manifest.get('schema_version') != 1:
            raise ValueError('Selected manifest has another kind or schema.')
        content = manifest['content']
        filename = {'catalogue': 'products.content', 'query-suite': 'queries.jsonl',
                    'judgement-set': 'judgements.jsonl'}[kind]
        target = output / filename
        checksum = hashlib.sha256()
        with target.open('wb') as stream:
            for chunk in blob.get_blob_client(container, content['object']).download_blob().chunks():
                checksum.update(chunk)
                stream.write(chunk)
        if checksum.hexdigest() != content['sha256']:
            target.unlink()
            raise ValueError(kind + ' bytes differ from the selected manifest.')
        manifests[kind] = manifest
    manifest = manifests['judgement-set']
    if manifest['dependencies'] != {
            'catalogue': manifests['catalogue']['content']['sha256'],
            'query-suite': manifests['query-suite']['content']['sha256']}:
        raise ValueError('Judgement source references another catalogue or query suite.')
    (output / 'context.json').write_bytes(canonical({
        'catalogue_sha256': manifest['dependencies']['catalogue'],
        'query_suite_sha256': manifest['dependencies']['query-suite'],
        'rubric': 'esci-v1'}))
    return {'judgement_manifest_sha256': judgement_sha,
            'judgement_sha256': manifest['content']['sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--judgement-manifest-sha256', required=True)
    parser.add_argument('--catalogue-manifest-sha256', required=True)
    parser.add_argument('--query-manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(fetch(args.judgement_manifest_sha256,
                           args.catalogue_manifest_sha256,
                           args.query_manifest_sha256, args.output), sort_keys=True))
