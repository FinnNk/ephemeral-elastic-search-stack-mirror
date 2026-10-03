"""Freeze and run one exploratory judgement pass over unresolved recall pairs."""

import argparse
from collections import Counter
import json
from pathlib import Path
import time
from urllib import request

from core import canonical, digest, pool
from telemetry import telemetry
from prepare import immutable, read_json, read_rows, require_content, selected_products


def freeze(observations_path, specification_path, catalogue, catalogue_manifest,
           queries_manifest, source, source_manifest, previous, output):
    observations, specification = read_json(observations_path), read_json(specification_path)
    cm, qm, sm = (read_json(p) for p in (catalogue_manifest, queries_manifest, source_manifest))
    require_content(catalogue, cm, 'catalogue')
    require_content(source, sm, 'judgement-set')
    context = {'catalogue_sha256': cm['content']['sha256'],
               'query_suite_sha256': qm['content']['sha256'], 'rubric': 'esci-v1'}
    if (sm['dependencies'] != {'catalogue': context['catalogue_sha256'],
                              'query-suite': context['query_suite_sha256']} or
            observations['catalogue_sha256'] != context['catalogue_sha256'] or
            observations['query_suite_sha256'] != context['query_suite_sha256']):
        raise ValueError('Pass inputs refer to different frozen sources.')
    pairs, sides = pool(observations, specification)
    known = {(row['query_id'], row['product_id']) for row in read_rows(source)}
    previous_hashes = []
    for path in previous:
        prior = read_json(path)
        if prior['context'] != context or not prior['complete']:
            raise ValueError('Previous pass is incomplete or uses another source.')
        previous_hashes.append(digest(Path(path).read_bytes()))
        known.update((r['query_id'], r['product_id']) for r in prior['records']
                     if r['outcome'] == 'labelled')
    gaps = [p for p in pairs if (p['query_id'], p['product_id']) not in known]
    products = selected_products(catalogue, {p['product_id'] for p in gaps})
    frozen = {'kind': 'judgement-pass-inputs', 'context': context,
              'observation_sha256': digest(Path(observations_path).read_bytes()),
              'source_judgement_sha256': sm['content']['sha256'],
              'previous_passes': previous_hashes,
              'sides': {name: [list(k) for k in sorted(keys)] for name, keys in sides.items()},
              'known': [list(k) for k in sorted(known)],
              'pairs': [{**p, 'product': products[p['product_id']]} for p in gaps]}
    immutable(output, canonical(frozen))
    return {'gaps': len(gaps), 'queries': len({p['query_id'] for p in gaps}),
            'inputs_sha256': digest(canonical(frozen))}


def run(inputs, exclusions, url, model, output, timeout=130):
    frozen = read_json(inputs)
    excluded = read_json(exclusions)
    if excluded['inputs_sha256'] != digest(Path(inputs).read_bytes()):
        raise ValueError('Exclusion audit belongs to different pass inputs.')
    if excluded.get('audit_complete') is not True:
        raise ValueError('A complete protected-query audit is required.')
    blocked = set(excluded['query_ids'])
    pairs = [p for p in frozen['pairs'] if p['query_id'] not in blocked]
    target = Path(output)
    if target.exists():
        raise ValueError('Preserve previous passes; use a new output directory.')
    target.mkdir(parents=True)
    started = time.monotonic()
    records = []
    with (target / 'attempts.jsonl').open('xb') as stream:
        for offset in range(0, len(pairs), 64):
            batch = pairs[offset:offset + 64]
            body = canonical({'context': frozen['context'], 'pairs': batch,
                              'selection': 'exploratory'})
            with telemetry.span('judgement.pass.batch', kind='client'):
                headers = {'Content-Type': 'application/json'}
                telemetry.inject(headers)
                call = request.Request(url, body, headers)
                with request.urlopen(call, timeout=timeout) as response:
                    result = json.load(response)
            if result['model'] != model or result['selection'] != 'exploratory':
                raise ValueError('Pass API model or selection differs.')
            if len(result['results']) != len(batch):
                raise ValueError('Pass response count differs.')
            for pair, row in zip(batch, result['results'], strict=True):
                state = row['outcome']
                record = {k: v for k, v in row.items() if k not in
                          ('scope', 'grade', 'source', 'evidence_sha256', 'reason')}
                if state == 'unjudged':
                    record['outcome'] = 'abstain'
                elif state == 'inference_error':
                    record['outcome'] = 'error'
                record.update(query_id=pair['query_id'], product_id=pair['product_id'])
                if record['outcome'] == 'labelled' and record.get('gate_eligible') is not False:
                    raise ValueError('Exploratory candidate must remain unqualified.')
                records.append(record)
                stream.write(canonical(record))
            stream.flush()
            print(f'Pass: {len(records)}/{len(pairs)}', flush=True)
    known = {tuple(k) for k in frozen['known']}
    labelled = {(r['query_id'], r['product_id']) for r in records if r['outcome'] == 'labelled'}
    coverage = {}
    for name, rows in frozen['sides'].items():
        keys = {tuple(k) for k in rows}
        before, after = len(keys & known), len(keys & (known | labelled))
        coverage[name] = {'required': len(keys), 'before': before, 'after': after,
                          'fraction': after / len(keys), 'remaining': len(keys) - after}
    result = {'kind': 'judgement-pass', 'context': frozen['context'], 'complete': True,
              'inputs_sha256': digest(Path(inputs).read_bytes()),
              'exclusions_sha256': digest(Path(exclusions).read_bytes()),
              'model': model, 'records': records, 'selection': 'exploratory',
              'excluded_pairs': len(frozen['pairs']) - len(pairs),
              'counts': dict(Counter(r['outcome'] for r in records)),
              'coverage': coverage, 'seconds': time.monotonic() - started}
    immutable(target / 'pass.json', canonical(result))
    return {k: v for k, v in result.items() if k not in ('context', 'records')}


def import_pass(path, url):
    frozen = read_json(path)
    if not frozen['complete']:
        raise ValueError('Do not import an incomplete pass.')
    for offset in range(0, len(frozen['records']), 64):
        call = request.Request(url, canonical({'kind': 'judgement-pass',
            'context': frozen['context'], 'records': frozen['records'][offset:offset + 64]}),
            {'Content-Type': 'application/json'})
        with request.urlopen(call, timeout=30) as response:
            json.load(response)
    return {'imported': len(frozen['records']), 'pass_sha256': digest(Path(path).read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    frozen = sub.add_parser('freeze')
    for name in ('observations', 'specification', 'catalogue', 'catalogue-manifest',
                 'query-manifest', 'source-judgements', 'source-manifest', 'output'):
        frozen.add_argument('--' + name, type=Path, required=True)
    frozen.add_argument('--previous-pass', action='append', type=Path, default=[])
    execute = sub.add_parser('run')
    for name in ('inputs', 'exclusions', 'model', 'output'):
        execute.add_argument('--' + name, type=Path, required=True)
    execute.add_argument('--resolve-url', required=True)
    upload = sub.add_parser('import')
    upload.add_argument('--pass-file', type=Path, required=True)
    upload.add_argument('--import-url', required=True)
    args = parser.parse_args()
    telemetry.configure('judgement-gap-pass')
    if args.command == 'freeze':
        result = freeze(args.observations, args.specification, args.catalogue,
                        args.catalogue_manifest, args.query_manifest, args.source_judgements,
                        args.source_manifest, args.previous_pass, args.output)
    elif args.command == 'run':
        result = run(args.inputs, args.exclusions, args.resolve_url,
                     read_json(args.model), args.output)
    else:
        result = import_pass(args.pass_file, args.import_url)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
