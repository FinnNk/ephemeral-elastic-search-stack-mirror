"""Resolve additional recall pools through the judgement API and retain one snapshot."""
import base64
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path
import tempfile
import time
from urllib import request

from blob_config import service, settings
from common import ROOT
sys.path.insert(0, str(ROOT))
from judgements.core import pool, resolve
from judgements.drift import input_shift
from operation_telemetry import judgement_pool
from variant_gate import canonical, sha


def call(url, path, body=None):
    headers = {'Content-Type': 'application/json'}
    # Propagate the comparison trace to the judgement service and KServe.
    from operation_telemetry import inject
    inject(headers)
    req = request.Request(url + path, None if body is None else canonical(body), headers)
    with request.urlopen(req, timeout=900) as response:
        return json.loads(response.read())


def products_for(manifest, ids):
    """Read original catalogue documents; verify their bytes before inference."""
    if not ids:
        return {}
    content = manifest['content']
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'catalogue'
        with path.open('wb') as stream:
            service().get_blob_client(settings()[1], content['object']).download_blob().readinto(stream)
        checksum = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                checksum.update(chunk)
        if checksum.hexdigest() != content['sha256']:
            raise ValueError('Frozen catalogue bytes differ.')
        opener = gzip.open if content['compression'] == 'gzip' else open
        found = {}
        with opener(path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                product = json.loads(line)
                if product['product_id'] in ids:
                    found[product['product_id']] = product
        if set(found) != ids:
            raise ValueError('Returned product is absent from the frozen catalogue.')
        return found


def resolve_extra(item, observations, specification, catalogue, retain):
    """Freeze one union of labels for every variant; ordinary calls reuse inference."""
    started = time.monotonic()
    url = os.environ.get('LAB_JUDGEMENT_URL',
        'http://judgement-service-million.lab-models.svc.cluster.local:18086').rstrip('/')
    health = call(url, '/health')
    context, model = health['context'], health['model']
    if context['catalogue_sha256'] != observations['catalogue_sha256'] or context['rubric'] != 'esci-v1':
        raise ValueError('Judgement service uses another catalogue or rubric.')
    registration = call(url, '/v1/queries:register', {
        'context': context, 'query_bytes': base64.b64encode(item['query_bytes']).decode(),
        'query_suite_sha256': item['query_sha256']})
    if registration['query_suite_sha256'] != item['query_sha256'] or set(registration['query_ids']) != {
            row['query_id'] for row in item['queries']}:
        raise ValueError('Judgement registration differs from the frozen queries.')
    empty_pool = not any(answer['ids'] for row in observations['observations'] for answer in row['results'].values())
    pairs = [] if empty_pool else pool(observations, json.loads(specification))[0]
    known = {(row['query_id'], row['product_id']) for row in item['judgements_rows']}
    products = products_for(catalogue, {pair['product_id'] for pair in pairs
                                     if (pair['query_id'], pair['product_id']) not in known})
    execution = {'response_errors': 0, 'inferred_pairs': 0, 'cache_hits': 0, 'stored_pairs': 0, 'requests': 0}
    selection = 'gate' if item['required'] else 'exploratory'

    def infer(items):
        unique = {}
        keys = []
        for pair in items:
            internal = registration['query_ids'][pair['query_id']]
            key = (internal, pair['product_id'])
            keys.append(key)
            unique[key] = {**pair, 'query_id': internal}
        execution['requests'] += 1
        try:
            answer = call(url, '/v1/judgements:resolve', {
                'context': context, 'pairs': list(unique.values()), 'selection': selection,
                'fresh_inference': False})
        except Exception:
            execution['response_errors'] += 1
            raise
        if answer['model'] != model or len(answer['results']) != len(unique):
            raise ValueError('Judgement model or response count changed during resolution.')
        for name in ('inferred_pairs', 'cache_hits'):
            execution[name] += answer['execution'][name]
        execution['stored_pairs'] += len(unique) - answer['execution']['inferred_pairs'] - answer['execution']['cache_hits']
        mapped = dict(zip(unique, answer['results']))
        return [{**mapped[key], 'query_id': item['query_id'],
                 'outcome': 'abstain' if mapped[key]['outcome'] == 'unjudged' else
                            'error' if mapped[key]['outcome'] == 'inference_error' else mapped[key]['outcome'],
                 'detail': mapped[key].get('reason', mapped[key].get('detail', ''))}
                for key, item in zip(keys, items)]

    if empty_pool:
        labels = item['judgements_rows']
        receipt = {'kind': 'judgement-resolution', 'schema_version': 1, 'selection': selection,
            'observation_sha256': sha(canonical(observations)), 'attempts': [],
            'counts': {'pool': {'required': 0, 'stored': 0, 'newly_labelled': 0, 'abstained': 0, 'failed': 0}}}
    else:
        labels, receipt = resolve(observations, json.loads(specification), item['judgements_rows'],
                                  products, infer, selection=selection)
    payload = b''.join(canonical(row) for row in labels)
    receipt.update(model=model, inference_identity=health['inference'],
                   query_registration=registration, execution={**execution, 'seconds': round(time.monotonic()-started, 3)})
    receipt['input_shift'] = input_shift(observations, receipt['attempts'])
    receipt['input_shift']['observed'] = 'gap_resolution_pairs'
    references = {'judgements': retain(payload, 'judgements.jsonl'),
                  'resolution': retain(canonical(receipt), 'judgement-resolution.json')}
    pool_keys = {(pair['query_id'], pair['product_id']) for pair in pairs}
    judged = len(pool_keys & {(row['query_id'], row['product_id']) for row in labels})
    judgement_pool(model['version'], selection, len(pool_keys), judged,
                   receipt['input_shift']['js_divergence'])
    return {**item, 'judgements_rows': labels, 'judgement_bytes': payload,
            'judgement_sha256': sha(payload), 'judgement_selection': selection,
            'judgement_resolution': receipt, 'resolved_references': references}
