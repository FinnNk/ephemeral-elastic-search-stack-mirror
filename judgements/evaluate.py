"""Resolve pooled judgement gaps, freeze the set, then score both API result lists."""

import argparse
import json
from pathlib import Path
import sys

from core import canonical, digest
from prepare import immutable, prepare, read_json, service_client
from telemetry import telemetry

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluation'))
from offline import evaluate as score


def run(observations, specification, catalogue, catalogue_manifest, query_manifest,
        source_judgements, source_manifest, output, predict, model, selection='gate'):
    output = Path(output)
    frozen = output / 'frozen'
    preparation = prepare(observations, specification, catalogue, catalogue_manifest,
                          query_manifest, source_judgements, source_manifest,
                          frozen, predict, model, selection=selection)
    report_path = output / 'evaluation.json'
    previous = read_json(report_path) if report_path.exists() else None
    report = score(observations, frozen / 'judgements.jsonl', specification,
                   catalogue_manifest, query_manifest, frozen / 'judgement-set.json',
                   evaluated_at=previous['evaluated_at'] if previous else None)
    if preparation['coverage']['pool']['failed']:
        report['complete'] = False
        report['inference_status'] = 'failed'
    else:
        report['inference_status'] = 'resolved_or_abstained'
    report['judgement_resolution_sha256'] = preparation['resolution']
    report['judgement_model'] = model
    report['model_input_shift'] = preparation['input_shift']
    immutable(report_path, canonical(report))
    telemetry.record_shift(model['version'], preparation['input_shift']['js_divergence'])
    telemetry.record_coverage(model['version'], preparation['coverage']['pool'])
    return {'report_sha256': digest(canonical(report)),
            'complete': report['complete'],
            'observation_sha256': report['observation_sha256'],
            'judgement_sha256': report['judgement_sha256'],
            'judgement_manifest_sha256': report['judgement_manifest_sha256'],
            'judgement_resolution_sha256': preparation['resolution'],
            'coverage_at_metric_cutoff': preparation['coverage'],
            'coverage_returned': report['coverage'], 'metrics': report['metrics'],
            'model_input_shift': preparation['input_shift']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('observations', 'specification', 'catalogue', 'catalogue-manifest',
                 'query-manifest', 'source-judgements', 'source-manifest', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--resolve-url', required=True)
    parser.add_argument('--selection', choices=('gate', 'exploratory'), default='gate')
    parser.add_argument('--resolve-timeout', type=float, default=10,
                        help='Seconds per resolution batch; use 130 for the v3 candidate')
    parser.add_argument('--model-name', required=True)
    parser.add_argument('--model-version', required=True)
    parser.add_argument('--model-artifact-sha256', required=True)
    args = parser.parse_args()
    model = {'name': args.model_name, 'version': args.model_version,
             'artifact_sha256': args.model_artifact_sha256}
    catalogue = read_json(args.catalogue_manifest)
    queries = read_json(args.query_manifest)
    context = {'catalogue_sha256': catalogue['content']['sha256'],
               'query_suite_sha256': queries['content']['sha256'], 'rubric': 'esci-v1'}
    telemetry.configure('judgement-evaluator')
    with telemetry.span('judgement.evaluate'):
        result = run(args.observations, args.specification, args.catalogue,
                     args.catalogue_manifest, args.query_manifest, args.source_judgements,
                     args.source_manifest, args.output,
                     service_client(args.resolve_url, context, model, timeout=args.resolve_timeout, selection=args.selection),
                     model, selection=args.selection)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
