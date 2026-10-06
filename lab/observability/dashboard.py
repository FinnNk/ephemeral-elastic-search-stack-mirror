"""Build and apply the SigNoz v2 search and operation SLO dashboard.

The committed JSON is the deployment input. This module generates it from the
same SLO policy used by the local evaluator and applies it idempotently.
"""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
POLICY = HERE / 'policies' / 'search-slo-v1.json'
SPEC = HERE / 'dashboards' / 'search-slo-v1.json'
NAME = 'relevance-lab-search-slo'


DEADLINE_KINDS = ('delivery.verify', 'environment.delete',
                  'environment.delete_many', 'environment.expire')


def metric(name, label, cohort='normal', hidden=True, deadlines_only=False):
    if deadlines_only:
        expression = 'lab.operation.kind IN [' + ', '.join(
            repr(kind) for kind in DEADLINE_KINDS) + ']'
    else:
        expression = (f"lab.traffic_class = '{cohort}' AND deployment.environment.name IN $environment"
                      if cohort else '')
    spec = {
        'name': label, 'signal': 'metrics', 'disabled': hidden, 'stepInterval': 60,
        'filter': {'expression': expression},
        'aggregations': [{'metricName': name, 'timeAggregation': 'increase',
                          'spaceAggregation': 'sum'}]}
    if cohort is None:
        spec['groupBy'] = [{'name': 'lab.operation.kind'}]
    return {'type': 'builder_query', 'spec': spec}


def formula(name, expression):
    return {'type': 'builder_formula', 'spec': {
        'name': name, 'expression': expression, 'disabled': False}}


def panel(title, queries, unit='none'):
    return {'kind': 'Panel', 'spec': {
        'display': {'name': title},
        'plugin': {'kind': 'signoz/TimeSeriesPanel', 'spec': {
            'visualization': {'timePreference': 'global_time'},
            'legend': {'position': 'bottom'},
            'chartAppearance': {'lineStyle': 'solid', 'lineInterpolation': 'linear',
                                'fillMode': 'none'},
            'formatting': {'unit': unit}}},
        'queries': [{'kind': 'time_series', 'spec': {'plugin': {
            'kind': 'signoz/CompositeQuery', 'spec': {'queries': queries}}}}]}}


def guidance(policy):
    targets = {item['id']: item['target'] for item in policy['objectives']}
    return {'kind': 'Panel', 'spec': {
        'display': {'name': 'Read this dashboard'},
        'plugin': {'kind': 'signoz/TextPanel', 'spec': {
            'mode': 'markdown',
            'text': ('**No data is unknown, not healthy.** An instrumented service with no requests has no activity. '
                     'A release without the OTLP endpoint exports no search metrics. Check the environment, '
                     'time window and collector before interpreting an empty panel. Check the eligible count and '
                     f'at least {policy["minimum_sample_count"]} normal requests before interpreting '
                     'search percentages. The current time picker sets the calculation window; '
                     f'the policy window is {policy["window_days"]} days, with '
                     f'{targets["search-success"]:.0%} success and '
                     f'{targets["responsive-search"]:.0%} responsiveness targets. A missing or partial '
                     'collection interval cannot be treated as good.\n\n'
                     'The charts show per-interval increases. Negative remaining budget '
                     'means the interval exceeded its allowance. Inspect the same service, '
                     'cohort and time in Traces and Logs, then open the immutable run report '
                     'for the promotion decision.'),
            'presentation': {'textAlign': 'left', 'verticalAlign': 'top'},
            'headerOptions': {'hide': False}}},
        'queries': []}}


def build():
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    target = {item['id']: item['target'] for item in policy['objectives']}
    success_budget = 1 - target['search-success']
    responsive_budget = 1 - target['responsive-search']
    eligible = lambda label='A': metric('lab.search.eligible', label)
    success = lambda label='B': metric('lab.search.success_good', label)
    responsive = lambda label='C': metric('lab.search.responsive_good', label)
    operation_eligible = lambda label='A': metric('lab.operation.eligible', label, None)
    operation_good = lambda label='B': metric('lab.operation.good', label, None)
    deadline_eligible = lambda label='A': metric('lab.operation.eligible', label, None,
                                                  deadlines_only=True)
    operation_deadline = lambda label='B': metric('lab.operation.deadline_good', label, None,
                                                  deadlines_only=True)
    definitions = [
        ('eligible', 'Normal search requests', [metric('lab.search.eligible', 'A', hidden=False)], 'none'),
        ('success_good', 'Successful searches',
         [metric('lab.search.success_good', 'A', hidden=False)], 'none'),
        ('responsive_good', 'Successful within 250 ms',
         [metric('lab.search.responsive_good', 'A', hidden=False)], 'none'),
        ('success_ratio', 'Search success / eligible',
         [eligible(), success(), formula('F1', '(B/A)*100')], 'percent'),
        ('responsive_ratio', 'Responsive / eligible',
         [eligible(), responsive('B'), formula('F1', '(B/A)*100')], 'percent'),
        ('success_remaining', 'Search success budget remaining',
         [eligible(), success(), formula('F1', f'A*{success_budget:.6g}-(A-B)')], 'none'),
        ('responsive_remaining', 'Responsiveness budget remaining',
         [eligible(), responsive('B'),
          formula('F1', f'A*{responsive_budget:.6g}-(A-B)')], 'none'),
        ('success_burn', 'Search success budget burn',
         [eligible(), success(),
          formula('F1', f'(A-B)/(A*{success_budget:.6g})')], 'none'),
        ('responsive_burn', 'Responsiveness budget burn',
         [eligible(), responsive('B'),
          formula('F1', f'(A-B)/(A*{responsive_budget:.6g})')], 'none'),
        ('operation_deadline', 'Accepted operations within deadline',
         [deadline_eligible(), operation_deadline(),
          formula('F1', '(B/A)*100')], 'percent'),
        ('operation_good', 'Accepted operations successful',
         [operation_eligible(), operation_good(), formula('F1', '(B/A)*100')], 'percent'),
    ]
    panels = {'guidance': guidance(policy)}
    panels.update({key: panel(title, queries, unit) for key, title, queries, unit in definitions})
    items = [{'x': 0, 'y': 0, 'width': 12, 'height': 3,
              'content': {'$ref': '#/spec/panels/guidance'}}]
    items += [{'x': (index % 2) * 6, 'y': 3 + (index // 2) * 6,
              'width': 6, 'height': 6, 'content': {'$ref': '#/spec/panels/' + key}}
             for index, (key, _, _, _) in enumerate(definitions)]
    return {'schemaVersion': 'v6', 'name': NAME,
            'tags': [{'key': 'lab', 'value': 'relevance'},
                     {'key': 'contract', 'value': 'search-slo-v1'}],
            'spec': {'display': {'name': 'Search and operation SLOs',
                                 'description': 'Normal search cohort and accepted operations. '
                                                'No data means unknown; check sample count and collection coverage.'},
                     'layouts': [{'kind': 'Grid', 'spec': {'items': items}}],
                     'panels': panels, 'variables': [{
                         'kind': 'ListVariable', 'spec': {
                             'name': 'environment', 'display': {'name': 'Search environment'},
                             'allowMultiple': True, 'allowAllValue': True,
                             'plugin': {'kind': 'signoz/DynamicVariable', 'spec': {
                                 'name': 'deployment.environment.name', 'signal': 'metrics'}}}}]}}


def request(url, token, method='GET', body=None):
    headers = {'Authorization': 'Bearer ' + token}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    command = Request(url, headers=headers, method=method,
                      data=json.dumps(body).encode() if body is not None else None)
    try:
        with urlopen(command, timeout=20) as response:
            return json.load(response)['data']
    except HTTPError as error:
        raise RuntimeError(f'SigNoz {method} returned HTTP {error.code}: '
                           f'{error.read(500).decode(errors="replace")}') from error


def apply(url, token):
    """Create once, then fully replace the named dashboard from committed JSON."""
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    if spec != build():
        raise RuntimeError('Dashboard JSON differs from the policy and builder; regenerate it.')
    endpoint = url.rstrip('/') + '/api/v2/dashboards'
    existing = []
    while True:
        page = request(endpoint + f'?limit=100&offset={len(existing)}', token)
        existing += page['dashboards']
        if len(existing) >= page['total']:
            break
    matches = [item for item in existing if item['name'] == NAME]
    if len(matches) > 1:
        raise RuntimeError('Multiple dashboards have the source-controlled name.')
    if matches:
        return request(endpoint + '/' + matches[0]['id'], token, 'PUT', spec)['id']
    return request(endpoint, token, 'POST', spec)['id']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-json', action='store_true', help='Regenerate committed v2 JSON')
    parser.add_argument('--apply', action='store_true', help='Apply committed JSON to SigNoz')
    parser.add_argument('--url', default=os.environ.get('SIGNOZ_URL', 'http://127.0.0.1:18090'))
    args = parser.parse_args()
    if args.write_json:
        SPEC.parent.mkdir(parents=True, exist_ok=True)
        SPEC.write_text(json.dumps(build(), indent=2) + '\n', encoding='utf-8')
    if args.apply:
        token = os.environ.get('SIGNOZ_ACCESS_TOKEN')
        if not token:
            raise SystemExit('Set SIGNOZ_ACCESS_TOKEN for an administrator session.')
        print('DASHBOARD_ID', apply(args.url, token))
