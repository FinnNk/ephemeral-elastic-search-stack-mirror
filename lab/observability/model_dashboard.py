"""Source-controlled SigNoz v2 model health and input-mix dashboard."""

import argparse
import json
import os
from pathlib import Path

from dashboard import formula, panel, request


SPEC = Path(__file__).resolve().parent / 'dashboards' / 'model-health-v1.json'
NAME = 'relevance-lab-model-health'


def metric(name, label, condition='', group=None, aggregation='increase', hidden=False):
    query = {'name': label, 'signal': 'metrics', 'disabled': hidden,
             'stepInterval': 60, 'filter': {'expression': condition},
             'aggregations': [{'metricName': name, 'timeAggregation': aggregation,
                               'spaceAggregation': 'avg' if aggregation == 'avg' else 'sum'}]}
    if group:
        query['groupBy'] = [{'name': group}]
    return {'type': 'builder_query', 'spec': query}


def text_panel():
    return {'kind': 'Panel', 'spec': {
        'display': {'name': 'Interpretation'},
        'plugin': {'kind': 'signoz/TextPanel', 'spec': {
            'mode': 'markdown',
            'text': ('**No data is unknown.** The current model abstains on every gap. '
                     'Prediction mix, inference failures, batch latency and judged coverage '
                     'are operational signals, not relevance accuracy. The label-mix panel '
                     'has no model-labelled values until a reviewed model produces them.\n\n'
                     '**Input shift** is Jensen–Shannon divergence (0 to 1) between query-length '
                     'buckets of the frozen observation queries and the pairs sent to the model. '
                     'It measures selection into inference, not drift against model training data. '
                     'Open a trace by `judgement.evaluate` or `judgement.http` and follow '
                     '`judgement.resolve` → `kserve.predict` → `model.http` → `model.predict`. '
                     'The frozen resolution report owns exact inputs and coverage.'),
            'presentation': {'textAlign': 'left', 'verticalAlign': 'top'},
            'headerOptions': {'hide': False}}}, 'queries': []}}


def build():
    predictions = lambda label='A': metric('lab.model.predictions', label, hidden=True)
    abstained = lambda label='B': metric('lab.model.predictions', label,
                                        "lab.model.outcome = 'abstain'", hidden=True)
    requests = lambda label='A': metric('lab.model.requests', label, hidden=True)
    failed = lambda label='B': metric('lab.model.requests', label,
                                     "lab.model.request_outcome = 'error'", hidden=True)
    definitions = [
        ('predictions', 'Predictions by outcome',
         [metric('lab.model.predictions', 'A', group='lab.model.outcome')], 'none'),
        ('abstention', 'Model abstention %',
         [predictions(), abstained(), formula('F1', '(B/A)*100')], 'percent'),
        ('requests', 'Inference requests by result',
         [metric('lab.model.requests', 'A', group='lab.model.request_outcome')], 'none'),
        ('error_rate', 'Inference request error %',
         [requests(), failed(), formula('F1', '(B/A)*100')], 'percent'),
        ('latency', 'Mean batch inference latency (ms)',
         [metric('lab.model.inference_duration.sum', 'A', hidden=True),
          metric('lab.model.inference_duration.count', 'B', hidden=True),
          formula('F1', 'A/B')], 'ms'),
        ('coverage', 'Pooled pairs with a label %',
         [metric('lab.judgement.pool_coverage_percent', 'A', aggregation='avg')], 'percent'),
        ('judgements', 'Judgement API responses by outcome',
         [metric('lab.judgement.results', 'A', group='lab.judgement.outcome')], 'none'),
        ('labels', 'Model label mix',
         [metric('lab.model.predictions', 'A', "lab.model.outcome = 'labelled'",
                 group='lab.model.label')], 'none'),
        ('shift', 'Query-length input shift (JSD)',
         [metric('lab.model.input_shift_jsd', 'A', aggregation='avg')], 'none'),
    ]
    panels = {'guidance': text_panel()}
    panels.update({key: panel(title, queries, unit) for key, title, queries, unit in definitions})
    items = [{'x': 0, 'y': 0, 'width': 12, 'height': 4,
              'content': {'$ref': '#/spec/panels/guidance'}}]
    items += [{'x': (index % 2) * 6, 'y': 4 + (index // 2) * 6,
               'width': 6, 'height': 6,
               'content': {'$ref': '#/spec/panels/' + key}}
              for index, (key, _, _, _) in enumerate(definitions)]
    return {'schemaVersion': 'v6', 'name': NAME,
            'tags': [{'key': 'lab', 'value': 'relevance'},
                     {'key': 'contract', 'value': 'model-health-v1'}],
            'spec': {'display': {'name': 'Model health and input shift',
                                 'description': 'Inference, abstention, coverage and frozen-input mix.'},
                     'layouts': [{'kind': 'Grid', 'spec': {'items': items}}],
                     'panels': panels, 'variables': []}}


def apply(url, token):
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    if spec != build():
        raise RuntimeError('Committed model dashboard differs from its builder.')
    endpoint = url.rstrip('/') + '/api/v2/dashboards'
    existing = []
    while True:
        page = request(endpoint + f'?limit=100&offset={len(existing)}', token)
        existing += page['dashboards']
        if len(existing) >= page['total']:
            break
    matches = [item for item in existing if item['name'] == NAME]
    if len(matches) > 1:
        raise RuntimeError('Multiple model dashboards have the source-controlled name.')
    if matches:
        return request(endpoint + '/' + matches[0]['id'], token, 'PUT', spec)['id']
    return request(endpoint, token, 'POST', spec)['id']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-json', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--url', default=os.environ.get('SIGNOZ_URL', 'http://127.0.0.1:18090'))
    args = parser.parse_args()
    if args.write_json:
        SPEC.write_text(json.dumps(build(), indent=2) + '\n', encoding='utf-8')
    if args.apply:
        token = os.environ.get('SIGNOZ_ACCESS_TOKEN')
        if not token:
            raise SystemExit('Set SIGNOZ_ACCESS_TOKEN outside Git.')
        print('DASHBOARD_ID', apply(args.url, token))
