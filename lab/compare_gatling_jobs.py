"""Compare two explicit finite Gatling Job runs for one frozen profile."""
import argparse
import hashlib
import json

from common import STATE, record
from compare_gatling import compare
from compare_search import immutable_blob


def main(profile, baseline_id, candidate_id):
    paths = [STATE / 'evidence' / ('gatling-job-' + profile + '-' + side + '-' + run_id + '.json')
             for side, run_id in (('baseline', baseline_id), ('candidate', candidate_id))]
    first, second = [json.loads(path.read_text()) for path in paths]
    if first['run_id'] != baseline_id or second['run_id'] != candidate_id:
        raise ValueError('Explicit run IDs do not match their saved evidence.')
    report = compare(first, second)
    payload = (json.dumps(report, sort_keys=True, indent=2) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    report['report_sha256'] = digest
    report['report_blob'] = immutable_blob('runs', digest + '/performance-comparison.json', payload)
    record('gatling-job-' + profile + '-pair', report)
    print(json.dumps({'profile': profile, 'valid': report['valid'], 'verdict': report['verdict'],
        'measured_phases': report['measured_phases'], 'first_stress_budget_breach': report['first_stress_budget_breach'],
        'report_sha256': digest, 'report_blob': report['report_blob']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', choices=('probe', 'smoke', 'normal', 'peak', 'stress'))
    parser.add_argument('baseline_id')
    parser.add_argument('candidate_id')
    args = parser.parse_args()
    main(args.profile, args.baseline_id, args.candidate_id)
