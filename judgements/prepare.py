"""Freeze pooled judgements after resolving both search versions' recall sets."""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
from urllib import request

from core import canonical, digest, pool, resolve, selected
from drift import input_shift
from telemetry import telemetry

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from contracts import envelope, validate_envelope


def read_json(path):
    return json.loads(Path(path).read_bytes())


def read_rows(path):
    with Path(path).open('rb') as probe:
        opener = gzip.open if probe.read(2) == b'\x1f\x8b' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def selected_products(path, ids):
    if not ids:
        return {}
    found = {}
    with Path(path).open('rb') as probe:
        opener = gzip.open if probe.read(2) == b'\x1f\x8b' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            product = json.loads(line)
            if product['product_id'] in ids:
                found[product['product_id']] = product
    if set(found) != set(ids):
        raise ValueError('Pooled product is absent from the frozen catalogue.')
    return found


def require_content(path, manifest, kind):
    validate_envelope(manifest)
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    if manifest['kind'] != kind or checksum.hexdigest() != manifest['content']['sha256']:
        raise ValueError('Selected ' + kind + ' bytes differ from the manifest.')


def service_client(url, context, model_identity, timeout=10, selection='gate'):
    if not math.isfinite(timeout) or not 0 < timeout <= 900:
        raise ValueError('Resolution timeout must be between zero and 900 seconds.')
    if not url.startswith(('http://', 'https://')):
        raise ValueError('KServe URL needs an HTTP(S) scheme.')

    def predict(items):
        body = canonical({'context': context, 'pairs': items, 'selection': selection})
        with telemetry.span('judgement.resolve', kind='client'):
            headers = {'Content-Type': 'application/json'}
            telemetry.inject(headers)
            call = request.Request(url, body, headers)
            with request.urlopen(call, timeout=timeout) as response:
                value = json.loads(response.read())
        if value.get('model') != model_identity:
            raise ValueError('Judgement service uses another model version.')
        return [{**row}
                if row['outcome'] == 'labelled' else
                {'outcome': 'abstain' if row['outcome'] == 'unjudged' else 'error',
                 'detail': row.get('reason', '')}
                for row in value['results']]

    return predict


def immutable(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError('Existing frozen artefact differs: ' + str(path))
    else:
        path.write_bytes(payload)


def prepare(observation_path, specification_path, catalogue_path, catalogue_manifest_path,
            query_manifest_path, source_path, source_manifest_path, output,
            predict, model_identity, selection='gate'):
    observation_bytes = Path(observation_path).read_bytes()
    observations = json.loads(observation_bytes)
    specification = read_json(specification_path)
    catalogue_manifest = read_json(catalogue_manifest_path)
    query_manifest = read_json(query_manifest_path)
    source_manifest = read_json(source_manifest_path)
    require_content(catalogue_path, catalogue_manifest, 'catalogue')
    require_content(source_path, source_manifest, 'judgement-set')
    if source_manifest['dependencies'] != {
            'catalogue': catalogue_manifest['content']['sha256'],
            'query-suite': query_manifest['content']['sha256']} or \
            observations['catalogue_sha256'] != catalogue_manifest['content']['sha256'] or \
            observations['query_suite_sha256'] != query_manifest['content']['sha256']:
        raise ValueError('Selected frozen inputs do not match the observations.')
    needed, _ = pool(observations, specification)
    known = {(row['query_id'], row['product_id']) for row in read_rows(source_path)
             if selected(row, selection)}
    missing_ids = {pair['product_id'] for pair in needed
                   if (pair['query_id'], pair['product_id']) not in known}
    products = selected_products(catalogue_path, missing_ids)
    source_rows = read_rows(source_path)
    for row in source_rows:
        if 'provenance' not in row:
            row.update(source='published', gate_eligible=True, provenance={
                'kind': 'published', 'source_id': source_manifest['content']['sha256']})
    frozen, attempts = resolve(observations, specification, source_rows,
                               products, predict, selection=selection)
    attempts['input_shift'] = input_shift(observations, attempts['attempts'])
    attempts['model'] = model_identity
    attempts['source_judgement_sha256'] = source_manifest['content']['sha256']
    attempts['observation_sha256'] = digest(observation_bytes)
    output = Path(output)
    rows_path = output / 'judgements.jsonl'
    receipt_path = output / 'resolution.json'
    manifest_path = output / 'judgement-set.json'
    immutable(rows_path, b''.join(canonical(row) for row in frozen))
    immutable(receipt_path, canonical(attempts))
    demo_sources = [row['provenance'] for row in frozen if
                    row.get('gate_eligible') is False and selection == 'demo']
    demo_metadata = {}
    if demo_sources:
        policies = {row['policy_sha256'] for row in demo_sources}
        approvals = {canonical(row['authorisation']) for row in demo_sources}
        if len(policies) != 1 or len(approvals) != 1:
            raise ValueError('Freeze one authorised demo policy per judgement snapshot.')
        demo_metadata = {'demo_policy_sha256': next(iter(policies)),
                         'authorisation': demo_sources[0]['authorisation']}
    manifest = envelope('judgement-set', rows_path, 'pooled-judgement-resolution',
                        source_manifest['dependencies'], len(frozen),
                        {**{key: value for key, value in source_manifest['producer'].items() if key != 'name'},
                         'source_judgement_sha256': source_manifest['content']['sha256'],
                         'observation_sha256': digest(observation_bytes),
                         'resolution_sha256': digest(canonical(attempts)),
                         'model': model_identity, 'selection': selection, 'rubric': 'esci-v1', **demo_metadata})
    immutable(manifest_path, canonical(manifest))
    return {'judgements': manifest['content']['sha256'],
            'manifest': digest(canonical(manifest)),
            'resolution': digest(canonical(attempts)),
            'coverage': attempts['counts'], 'input_shift': attempts['input_shift']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('observations', 'specification', 'catalogue', 'catalogue-manifest',
                 'query-manifest', 'source-judgements', 'source-manifest', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--resolve-url', required=True)
    parser.add_argument('--selection', choices=('gate', 'exploratory', 'demo'), default='gate')
    parser.add_argument('--resolve-timeout', type=float, default=10,
                        help='Seconds per resolution batch; use 130 for the v3 candidate')
    parser.add_argument('--model-name', required=True)
    parser.add_argument('--model-version', required=True)
    parser.add_argument('--model-artifact-sha256', required=True)
    args = parser.parse_args()
    model = {'name': args.model_name, 'version': args.model_version,
             'artifact_sha256': args.model_artifact_sha256}
    catalogue_manifest = read_json(args.catalogue_manifest)
    query_manifest = read_json(args.query_manifest)
    context = {'catalogue_sha256': catalogue_manifest['content']['sha256'],
               'query_suite_sha256': query_manifest['content']['sha256'],
               'rubric': 'esci-v1'}
    result = prepare(args.observations, args.specification, args.catalogue,
                     args.catalogue_manifest, args.query_manifest,
                     args.source_judgements, args.source_manifest, args.output,
                     service_client(args.resolve_url, context, model, timeout=args.resolve_timeout, selection=args.selection),
                     model, selection=args.selection)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
