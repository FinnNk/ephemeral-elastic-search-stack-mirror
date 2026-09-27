"""Compare black-box Gatling runs with workload validity and phase-specific budgets."""
import hashlib
import json

from common import STATE, record
from compare_search import immutable_blob

BUDGETS = {
    'normal': {'p95_ms': 250, 'p99_ms': 500, 'failed_percent': 1.0},
    'peak': {'p95_ms': 400, 'p99_ms': 800, 'failed_percent': 1.0},
    'recovery': {'p95_ms': 250, 'p99_ms': 500, 'failed_percent': 1.0},
}


def measure_phase(metrics, budget):
    return {'p95_ms': metrics['p95_ms'], 'p99_ms': metrics['p99_ms'],
            'failed_percent': metrics['failed_percent'], 'offered_rps': metrics['offered_rps'],
            'request_count': metrics['requests'],
            'within_budget': all(metrics[key] <= limit if key != 'failed_percent' else metrics[key] < limit
                                 for key, limit in budget.items())}


def compare(first, second):
    same_workload = first.get('release_id') == second.get('release_id') and \
        first['workload_sha256'] == second['workload_sha256'] and \
        first['source_sha256'] == second['source_sha256'] and first['recipe_sha256'] == second['recipe_sha256'] and \
        first.get('workload_archive_sha256') == second.get('workload_archive_sha256')
    warmup_ok = all(run['phases'].get('warmup', {}).get('failed') == 0 for run in (first, second))
    valid = bool(same_workload and first['valid'] and second['valid'] and warmup_ok and
                 first['runner_image'] == second['runner_image'] and
                 first.get('simulation_sha256') == second.get('simulation_sha256') and
                 first['fingerprint'] != second['fingerprint'])
    measured = {}
    stress_breach = None
    for phase in first['phases']:
        if phase in ('warmup', 'ramp'):
            continue
        if phase not in second['phases']:
            valid = False
            continue
        left, right = first['phases'][phase], second['phases'][phase]
        budget = BUDGETS.get(phase, BUDGETS['normal'])
        measured[phase] = {'baseline': measure_phase(left, budget),
                           'candidate': measure_phase(right, budget), 'budget': budget,
                           'candidate_p95_increase_percent': round((right['p95_ms'] / left['p95_ms'] - 1) * 100, 3)
                           if left['p95_ms'] else None}
        if phase.startswith('stress-') and stress_breach is None and \
                (not measured[phase]['baseline']['within_budget'] or
                 not measured[phase]['candidate']['within_budget']):
            stress_breach = phase
    if not measured:
        valid = False
    verdict = 'invalid' if not valid else 'within-budget' if all(
        result[side]['within_budget'] for phase, result in measured.items()
        if not phase.startswith('stress-') for side in ('baseline', 'candidate')) else 'budget-missed'
    return {'kind': 'paired-api-performance', 'profile': first['profile'], 'valid': valid,
            'verdict': verdict, 'same_workload': same_workload,
            'warmup_ready': warmup_ok,
            'workload_sha256': first['workload_sha256'], 'source_sha256': first['source_sha256'],
            'recipe_sha256': first['recipe_sha256'], 'baseline': first, 'candidate': second,
            'measured_phases': measured, 'first_stress_budget_breach': stress_breach,
            'warmup_excluded_from_verdict': True,
            'stress_interpretation': 'No budget breach at the maximum offered rate' if
                first['profile'] in ('stress', 'stress-full') and stress_breach is None else None}


def main(profile):
    first = json.loads((STATE / 'evidence' / ('gatling-' + profile + '-baseline.json')).read_text())
    second = json.loads((STATE / 'evidence' / ('gatling-' + profile + '-candidate.json')).read_text())
    report = compare(first, second)
    payload = (json.dumps(report, sort_keys=True, indent=2) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    report['report_sha256'] = digest
    report['report_blob'] = immutable_blob('runs', digest + '/performance-comparison.json', payload)
    record('gatling-' + profile + '-comparison', report)
    print(json.dumps({'profile': profile, 'valid': report['valid'], 'verdict': report['verdict'],
                      'workload_sha256': report['workload_sha256'], 'report_sha256': digest,
                      'report_blob': report['report_blob'], 'measured_phases': report['measured_phases'],
                      'first_stress_budget_breach': report['first_stress_budget_breach']}, indent=2))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', choices=('probe', 'smoke', 'normal', 'peak', 'stress',
                                            'normal-full', 'sustained-peak', 'stress-full'))
    main(parser.parse_args().profile)
