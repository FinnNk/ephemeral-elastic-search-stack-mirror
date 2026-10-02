"""Resolve selected input manifests from immutable Blob objects."""

import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from contracts import validate_envelope
from blob_config import service, settings

DEFAULTS = json.loads(Path(__file__).with_name('default_inputs.json').read_text(encoding='utf-8'))
HASH = re.compile(r'[0-9a-f]{64}\Z')


def fetch_manifest(kind, manifest_sha, account=None):
    if kind not in ('catalogue', 'query-suite', 'judgement-set') or not isinstance(manifest_sha, str) or \
            not HASH.fullmatch(manifest_sha):
        raise ValueError('Select a valid independent input manifest SHA-256.')
    account = account or service()
    payload = account.get_blob_client(settings()[1],
        f'manifests/{kind}/{manifest_sha}.json').download_blob().readall()
    if hashlib.sha256(payload).hexdigest() != manifest_sha:
        raise ValueError('Selected input manifest bytes differ from their SHA-256.')
    manifest = validate_envelope(json.loads(payload))
    if manifest['kind'] != kind:
        raise ValueError('Selected input manifest has another kind.')
    return manifest


def fetch_rows(manifest, account=None):
    account = account or service()
    content = manifest['content']
    payload = account.get_blob_client(settings()[1], content['object']).download_blob().readall()
    if len(payload) != content['bytes'] or hashlib.sha256(payload).hexdigest() != content['sha256']:
        raise ValueError('Selected input bytes differ from their manifest.')
    if content['format'] != 'jsonl' or content['compression'] != 'none':
        raise ValueError('Selected query and judgement inputs must be uncompressed JSONL.')
    rows = [json.loads(line) for line in payload.splitlines()]
    if len(rows) != manifest['record_count']:
        raise ValueError('Selected input row count differs from its manifest.')
    return rows


def select(release_id, product_sha, query_manifest_sha=None, judgement_manifest_sha=None,
           relevance=False, account=None):
    if release_id not in DEFAULTS:
        raise ValueError('No default independent inputs are pinned for this catalogue.')
    defaults = DEFAULTS[release_id]
    account = account or service()
    catalogue = fetch_manifest('catalogue', defaults['catalogue'], account)
    if catalogue['content']['sha256'] != product_sha:
        raise ValueError('Selected catalogue differs from the frozen environments.')
    query_sha = query_manifest_sha or defaults['query-suite']
    queries_manifest = fetch_manifest('query-suite', query_sha, account)
    queries = fetch_rows(queries_manifest, account)
    if not queries or len({row.get('query_id') for row in queries}) != len(queries) or \
            any(not all(isinstance(row.get(key), str) and row[key]
                        for key in ('query_id', 'query', 'country', 'currency')) or
                not isinstance(row.get('filters', {}), dict) for row in queries):
        raise ValueError('Selected query suite is incomplete or duplicated.')
    result = {'catalogue': catalogue, 'query_manifest': queries_manifest,
              'query_manifest_sha256': query_sha, 'queries': queries}
    if relevance:
        judgement_sha = judgement_manifest_sha or defaults['judgement-set']
        judgements_manifest = fetch_manifest('judgement-set', judgement_sha, account)
        if judgements_manifest['dependencies'] != {
                'catalogue': product_sha,
                'query-suite': queries_manifest['content']['sha256']}:
            raise ValueError('Selected judgements belong to another catalogue or query suite.')
        judgements = fetch_rows(judgements_manifest, account)
        query_ids = {row['query_id'] for row in queries}
        if any(row.get('query_id') not in query_ids or
               not isinstance(row.get('product_id'), str) or
               type(row.get('grade')) is not int or row['grade'] not in range(4)
               for row in judgements):
            raise ValueError('Selected judgement records are invalid for this query suite.')
        if len({(row['query_id'], row['product_id']) for row in judgements}) != len(judgements):
            raise ValueError('Selected judgement set contains duplicate query/product pairs.')
        result.update(judgement_manifest=judgements_manifest,
                      judgement_manifest_sha256=judgement_sha, judgements=judgements)
    elif judgement_manifest_sha:
        raise ValueError('Judgements can only be selected for a relevance comparison.')
    return result
