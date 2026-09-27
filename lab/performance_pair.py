"""Run two sequential, pinned Gatling Jobs for a controlled performance comparison."""
import hashlib
import json

from compare_gatling import compare
from compare_search import immutable_blob
from run_gatling_job import run


def evaluate_performance_pair(baseline, candidate, profile):
    release_id = baseline.get('release_id') or 'retail-gb-10k-v1'
    if release_id != (candidate.get('release_id') or 'retail-gb-10k-v1'):
        raise ValueError('Performance pair requires the same frozen release.')
    first = run(profile, 'baseline', baseline['name'], release_id=release_id)
    second = run(profile, 'candidate', candidate['name'], release_id=release_id)
    paired = compare(first, second)
    paired['baseline_runtime_id'] = baseline['id']
    paired['candidate_runtime_id'] = candidate['id']
    payload = (json.dumps(paired, sort_keys=True, indent=2) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    location = immutable_blob('runs', digest + '/performance-comparison.json', payload)
    return {'report_sha256': digest, 'report_blob': location, 'mode': 'performance',
            'profile': profile, 'complete': paired['valid'], 'verdict': paired['verdict'],
            'release_id': release_id, 'baseline_run_id': first['run_id'],
            'candidate_run_id': second['run_id'],
            'workload_sha256': paired['workload_sha256'],
            'first_stress_budget_breach': paired['first_stress_budget_breach'],
            'measured_phases': paired['measured_phases'],
            'baseline_native_report_blob': first['native_report_blob'],
            'candidate_native_report_blob': second['native_report_blob']}
