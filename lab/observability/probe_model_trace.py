"""Trace one small synthetic frozen evaluation through judgement and KServe.

Stage the already pinned synthetic /inputs files from the 10k judgement Pod in
an ignored directory. This probe creates new local artefacts; it never changes
the source release or a retained comparison.
"""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'data'))
sys.path.insert(0, str(ROOT / 'judgements'))
from contracts import envelope  # noqa: E402
from core import canonical  # noqa: E402
from evaluate import run  # noqa: E402
from service import read_rows  # noqa: E402
from prepare import service_client  # noqa: E402
from telemetry import telemetry  # noqa: E402


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))
    return path


def fixture(inputs, output):
    inputs, output = Path(inputs), Path(output)
    context = json.loads((inputs / 'context.json').read_bytes())
    queries = list(read_rows(inputs / 'queries.jsonl'))
    products = list(read_rows(inputs / 'products.content'))
    labels = list(read_rows(inputs / 'judgements.jsonl'))
    by_query = defaultdict(list)
    for row in labels:
        by_query[row['query_id']].append(row['product_id'])
    short = next(row for row in queries if len(row['query'].split()) == 1)
    long = next(row for row in queries if len(row['query'].split()) >= 2
                and len(by_query[row['query_id']]) >= 5)
    known = set(by_query[short['query_id']])
    missing = [row['product_id'] for row in products
               if row['country'] == short['country'] and
               row['currency'] == short['currency'] and row['product_id'] not in known][:5]
    if len(missing) != 5:
        raise ValueError('The frozen catalogue has fewer than five gap pairs.')
    catalogue = envelope('catalogue', inputs / 'products.content', 'model-telemetry-probe',
                         provenance={'source_release': 'retail-gb-10k-v1'})
    query_suite = envelope('query-suite', inputs / 'queries.jsonl', 'model-telemetry-probe',
                           provenance={'source_release': 'retail-gb-10k-v1'})
    dependencies = {'catalogue': catalogue['content']['sha256'],
                    'query-suite': query_suite['content']['sha256']}
    source = envelope('judgement-set', inputs / 'judgements.jsonl', 'model-telemetry-probe',
                      dependencies, len(labels), {'source_release': 'retail-gb-10k-v1'})
    if context != {'catalogue_sha256': dependencies['catalogue'],
                   'query_suite_sha256': dependencies['query-suite'], 'rubric': 'esci-v1'}:
        raise ValueError('Staged synthetic inputs differ from the live service scope.')
    def observation(query, ids):
        request = {key: query[key] for key in ('query', 'country', 'currency')}
        request['filters'] = query.get('filters', {})
        answer = {'ids': ids, 'total': len(ids)}
        return {'query_id': query['query_id'], 'request': request,
                'baseline': answer, 'candidate': answer}
    observations = {'kind': 'search-observation-set', 'schema_version': 1,
                    'captured_depth': 5, 'request_adapter': 'search-api-v1', 'errors': [],
                    'baseline_fingerprint': 'synthetic-model-probe-baseline',
                    'candidate_fingerprint': 'synthetic-model-probe-candidate',
                    'catalogue_sha256': dependencies['catalogue'],
                    'query_suite_sha256': dependencies['query-suite'],
                    'observations': [
                        observation(short, missing),
                        observation(long, by_query[long['query_id']][:5])]}
    specification = {'kind': 'evaluation-specification', 'schema_version': 1,
                     'metrics': ['nDCG@5'], 'aggregation': 'macro',
                     'unjudged_policy': 'unknown; metric library treats missing qrels as zero'}
    return {'observations': write(output / 'observations.json', observations),
            'specification': write(output / 'specification.json', specification),
            'catalogue': inputs / 'products.content',
            'catalogue_manifest': write(output / 'catalogue-manifest.json', catalogue),
            'query_manifest': write(output / 'query-manifest.json', query_suite),
            'source_judgements': inputs / 'judgements.jsonl',
            'source_manifest': write(output / 'source-manifest.json', source),
            'context': context}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resolve-url', default='http://127.0.0.1:18086/v1/judgements:resolve')
    args = parser.parse_args()
    paths = fixture(args.inputs, args.output)
    model = {'name': 'synthetic-esci-judge', 'version': '1',
             'artifact_sha256': '364d0b0961e682ba1440ff570a6288631486c1362e2b68f328aafcf270e5d894'}
    telemetry.configure('judgement-evaluator')
    with telemetry.span('judgement.evaluate'):
        from opentelemetry import trace
        span_context = trace.get_current_span().get_span_context()
        trace_id = format(span_context.trace_id, '032x') if span_context.is_valid else None
        result = run(paths['observations'], paths['specification'], paths['catalogue'],
                     paths['catalogue_manifest'], paths['query_manifest'],
                     paths['source_judgements'], paths['source_manifest'],
                     args.output / 'result',
                     service_client(args.resolve_url, paths['context'], model), model)
    from opentelemetry import metrics, trace
    trace.get_tracer_provider().force_flush(5000)
    metrics.get_meter_provider().force_flush(5000)
    print(json.dumps({'trace_id': trace_id, 'report_sha256': result['report_sha256'],
                      'pool': result['coverage_at_metric_cutoff']['pool'],
                      'input_shift': result['model_input_shift']}, sort_keys=True))


if __name__ == '__main__':
    main()
