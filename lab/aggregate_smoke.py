"""Aggregate three explicitly paired five-minute Gatling smoke runs."""
import argparse
import hashlib
import json
import statistics

from common import STATE, record
from compare_gatling import compare
from compare_search import immutable_blob


def baseline_spread(p95_values):
    median = statistics.median(p95_values)
    return round((max(p95_values) - min(p95_values)) / median * 100, 3) if median else float('inf')


def aggregate(pairs, execution='docker'):
    if len(pairs) != 3:
        raise ValueError('Exactly three explicit baseline:candidate run pairs are required.')
    if execution not in ('docker', 'job'):
        raise ValueError('Execution must be docker or job.')
    prefix = 'gatling-job-smoke' if execution == 'job' else 'gatling-smoke'
    summaries = []
    changes = []
    baseline_p95 = []
    workload = None
    identity = None
    seen = set()
    for left_id, right_id in pairs:
        if left_id in seen or right_id in seen:
            raise ValueError('A run may appear in only one pair.')
        seen.update((left_id, right_id))
        first = json.loads((STATE / 'evidence' / (prefix + '-baseline-' + left_id + '.json')).read_text())
        second = json.loads((STATE / 'evidence' / (prefix + '-candidate-' + right_id + '.json')).read_text())
        if first['run_id'] != left_id or second['run_id'] != right_id:
            raise ValueError('Run evidence ID differs from requested pair.')
        row = compare(first, second)
        if workload is None:
            workload = row['workload_sha256']
        if row['workload_sha256'] != workload:
            raise ValueError('All pairs must use identical workload bytes.')
        pair_identity = (first['fingerprint'], second['fingerprint'], first['runner_image'],
                         first.get('simulation_sha256'), first.get('release_id'))
        if identity is None:
            identity = pair_identity
        if pair_identity != identity:
            raise ValueError('All pairs must use the same two environments and runner revision.')
        summaries.append(row)
        changes.append(row['measured_phases']['normal']['candidate_p95_increase_percent'])
        baseline_p95.append(row['measured_phases']['normal']['baseline']['p95_ms'])
    median_change = round(statistics.median(changes), 3)
    valid = all(row['valid'] for row in summaries)
    budgets = all(row['verdict'] == 'within-budget' for row in summaries)
    spread = baseline_spread(baseline_p95)
    stable = spread <= 10
    return {'kind': 'three-pair-smoke', 'execution': execution,
            'workload_sha256': workload, 'pair_identity': identity, 'pairs': summaries,
            'median_candidate_p95_increase_percent': median_change,
            'baseline_p95_spread_percent': spread, 'baseline_stable': stable,
            'valid': valid and stable, 'absolute_budgets_met': budgets,
            'relative_budget_met': valid and stable and median_change <= 10,
            'verdict': 'pass' if valid and stable and budgets and median_change <= 10 else
                       'inconclusive' if not valid or not stable else 'budget-missed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', action='append', required=True,
                        help='Explicit baseline-run-id:candidate-run-id; supply three times')
    parser.add_argument('--execution', choices=('docker', 'job'), default='docker')
    args = parser.parse_args()
    pairs = [value.split(':', 1) for value in args.pair]
    report = aggregate(pairs, args.execution)
    payload = (json.dumps(report, sort_keys=True, indent=2) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    report['report_sha256'] = digest
    report['report_blob'] = immutable_blob('runs', digest + '/three-pair-smoke.json', payload)
    release_id = report['pair_identity'][4] or 'retail-gb-10k-v1'
    record('gatling-smoke-three-pair-' + release_id + '-' + args.execution, report)
    print(json.dumps({'valid': report['valid'], 'verdict': report['verdict'],
                      'median_candidate_p95_increase_percent': report['median_candidate_p95_increase_percent'],
                      'report_sha256': digest, 'report_blob': report['report_blob']}, indent=2))
