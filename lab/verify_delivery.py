"""Exercise protected promotion and stale-PR rejection in demonstration repositories only."""
import argparse
import json
from pathlib import Path

from delivery_provider import DESIRED, SOURCE, api, endpoint, merge_demo
from common import record
from delivery_runtime import TARGETS, checkout, read_target, resolve, writer
from delivery_promote import demonstrate_merge, propose, validate_pr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-run', type=int, required=True)
    parser.add_argument('--candidate-run', type=int, required=True)
    parser.add_argument('--dataset', default='retail-gb-1m-v1')
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    with writer():
        baseline = resolve(args.baseline_run, args.dataset)
        candidate = resolve(args.candidate_run, args.dataset)
        checkout()
        if any(read_target(target) != baseline for target in TARGETS):
            raise ValueError('Walkthrough expects all targets at the specified baseline; use reviewed rollback to reset.')
        evidence = json.loads(args.evidence.read_text())
        initial_runs = api(endpoint(SOURCE, '/actions/runs?limit=1'))['total_count']
        first = propose('integration', candidate, evidence)
        print('Integration proposal: ' + first['url'], flush=True)
        assert first['validation']['passed'], first['validation']
        try:
            merge_demo(DESIRED, first['pr'], first['head_sha'])
        except RuntimeError as error:
            no_review = str(error)
        else:
            raise AssertionError('Protected promotion merged without a review.')
        second = propose('integration', candidate, evidence)
        assert second['validation']['passed'], second['validation']
        results = {'baseline': baseline, 'candidate': candidate, 'evidence': evidence,
                   'no_review_merge_denied': no_review, 'deployments': []}
        result = demonstrate_merge(first['pr'])
        results['deployments'].append(result)
        record('delivery-promotion', results)
        stale = validate_pr(second['pr'])
        assert not stale['passed'], stale
        results['stale_proposal'] = {**stale, 'url': second['url']}
        api(endpoint(DESIRED, '/pulls/' + str(second['pr'])), 'PATCH', {'state': 'closed'})
        for target in ('staging', 'production'):
            pr = propose(target, candidate, evidence)
            assert pr['validation']['passed'], pr['validation']
            print(target + ' proposal: ' + pr['url'], flush=True)
            results['deployments'].append(demonstrate_merge(pr['pr']))
            record('delivery-promotion', results)
        final_runs = api(endpoint(SOURCE, '/actions/runs?limit=1'))['total_count']
        assert final_runs == initial_runs, 'Promotion unexpectedly triggered a source rebuild.'
        results['source_run_count_before'] = initial_runs
        results['source_run_count_after'] = final_runs
        assert all(row['deployment'] == candidate for row in results['deployments'])
        record('delivery-promotion', results)
        print(json.dumps({'all_targets_verified': True, 'no_rebuilds': True,
            'seconds': {row['environment']: row['merge_to_verified_seconds'] for row in results['deployments']},
            'stale_proposal_blocked': True, 'review_required': True}, indent=2))


if __name__ == '__main__':
    main()
