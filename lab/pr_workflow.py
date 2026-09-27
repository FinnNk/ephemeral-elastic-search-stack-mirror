"""Opt-in Gitea PR revision to frozen candidate and three check reports."""
import argparse
import json
import os
import socket
import sys
import time

sys.path.insert(0, 'research/platform-spike')
from common import STATE, guard, record
from environments import build_record
from gitea import api
from deploy_baseline import successful_run
from lifecycle import local_lifecycle

REPO = '/repos/elastic-agent/search-spike'
LABEL = 'lab-evaluate'
CONTROL = os.environ.get('LAB_CONTROL_PUBLIC_URL', 'http://localhost:18082/').rstrip('/') + '/'


def opted_in(pr):
    return pr['state'] == 'open' and any(label['name'] == LABEL for label in pr.get('labels', []))


def matching_comparison(controller, baseline, candidate, mode, scope='full', profile=None):
    for row in controller.store.all_comparisons():
        if (row['baseline_id'] == baseline['id'] and row['candidate_id'] == candidate['id'] and
                row['mode'] == mode and row.get('scope') == (scope if mode != 'performance' else None) and
                row.get('profile') == profile and row['state'] == 'complete'):
            return row
    return None


def compare_once(controller, baseline, candidate, mode, scope='full', profile='probe'):
    existing = matching_comparison(controller, baseline, candidate, mode, scope,
                                   profile if mode == 'performance' else None)
    return existing or controller.compare(baseline['id'], candidate['id'], mode,
                                          scope=scope if mode != 'performance' else 'full', profile=profile)


def verdict_comment(pr, sha, baseline, candidate, checks, ready_seconds, check_seconds, stale=False):
    lines = [f'<!-- relevance-lab:{sha} -->', f'### Frozen search evaluation · `{sha[:12]}`', '',
             f'Baseline `{baseline["fingerprint"]}`; candidate `{candidate["fingerprint"]}`.',
             f'Synthetic release `{candidate["release_id"]}`. Workflow trigger to first correct candidate search: '
             f'{ready_seconds:.1f} s; checks after readiness: {check_seconds:.1f} s.', '']
    for label, row in checks:
        summary = row.get('summary') or {}
        details = f'{summary.get("completed_query_count", "–")}/{summary.get("query_count", "–")} queries'
        if label == 'Gatling probe':
            details = 'short load probe'
        elif summary.get('judgement_coverage_status') == 'insufficient':
            details += ' · judgement coverage insufficient for a strong relevance claim'
        link = CONTROL + '?comparison=' + row['id']
        lines.append(f'- **{label}: {row.get("verdict") or row["state"]}** · {details} · [inspect report]({link})')
        if row.get('report_sha256'):
            lines.append(f'  - Report SHA-256 `{row["report_sha256"]}`')
    lines.extend(['', 'Relevance scores use frozen synthetic judgements. The million-product pool includes earlier candidate results; coverage and unjudged IDs are in the report. A measured relevance result requires human review.'])
    if stale:
        lines.extend(['', '**The PR head changed during evaluation. This report belongs to the earlier SHA; rerun the new head.**'])
    return '\n'.join(lines)


def publish_verdict(number, sha, body, passed, stale=False):
    marker = f'<!-- relevance-lab:{sha} -->'
    comments = api(REPO + f'/issues/{number}/comments?limit=100')
    existing = next((comment for comment in comments if marker in comment['body']), None)
    if existing:
        api(REPO + f'/issues/comments/{existing["id"]}', 'PATCH', {'body': body})
    else:
        api(REPO + f'/issues/{number}/comments', 'POST', {'body': body})
    api(REPO + '/statuses/' + sha, 'POST', {'context': 'relevance-lab/evaluation',
        'state': 'error' if stale else ('success' if passed else 'failure'),
        'description': 'Stale PR revision' if stale else ('Checks complete; inspect relevance' if passed else 'Check failed or incomplete'),
        'target_url': CONTROL})


def process(number, baseline_run, release_id='retail-gb-10k-v1', profile='probe'):
    guard()
    triggered = time.monotonic()
    pr = api(REPO + f'/pulls/{number}')
    if not opted_in(pr):
        raise ValueError('The PR must be open and carry the lab-evaluate label.')
    sha = pr['head']['sha']
    baseline_build = build_record(baseline_run)
    candidate_build = successful_run(sha)
    if candidate_build['source_sha'] != sha:
        raise ValueError('Successful build does not match the PR head SHA.')
    controller = local_lifecycle()
    suffix = '1m' if release_id == 'retail-gb-1m-v1' else '10k'
    owner = pr['user']['login']
    baseline = controller.create(f'lab-pr-{number}-base-{baseline_build["source_sha"][:8]}-{suffix}',
                                 baseline_run, owner=owner, release_id=release_id)
    candidate = controller.create(f'lab-pr-{number}-{sha[:10]}-{suffix}',
                                  candidate_build['run'], owner=owner, release_id=release_id)
    if baseline['state'] != 'ready' or candidate['state'] != 'ready':
        raise RuntimeError('PR environments did not become ready.')
    ready_seconds = time.monotonic() - triggered
    started = time.monotonic()
    checks = []
    for label, mode, scope in [('Quick result check', 'result-regression', 'quick'),
                               ('Full result check', 'result-regression', 'full'),
                               ('Frozen relevance', 'relevance', 'full'),
                               ('Gatling probe', 'performance', 'full')]:
        row = compare_once(controller, baseline, candidate, mode, scope, profile)
        checks.append((label, row))
        if row['state'] != 'complete':
            break
    stale = api(REPO + f'/pulls/{number}')['head']['sha'] != sha
    preserve = any(label['name'] == 'lab-preserve-results' for label in pr.get('labels', []))
    passed = all(row['state'] == 'complete' for _, row in checks) and len(checks) == 4
    if preserve:
        passed = passed and len(checks) > 1 and checks[1][1]['verdict'] == 'unchanged'
    if checks and checks[-1][0] == 'Gatling probe':
        passed = passed and checks[-1][1]['verdict'] == 'within-budget'
    seconds = time.monotonic() - started
    body = verdict_comment(pr, sha, baseline, candidate, checks, ready_seconds, seconds, stale)
    publish_verdict(number, sha, body, passed, stale)
    result = {'pr': number, 'head_sha': sha, 'baseline_id': baseline['id'],
              'candidate_id': candidate['id'], 'checks': {name: row['id'] for name, row in checks},
              'passed': passed and not stale, 'stale': stale,
              'trigger_to_first_search_seconds': round(ready_seconds, 3),
              'evaluation_seconds': round(seconds, 3)}
    record('pr-evaluation-' + str(number) + '-' + sha[:12], result)
    return result


def watch(baseline_run, release_id, profile, once=False, interval=30):
    if not once:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as guard_socket:
            guard_socket.bind(('127.0.0.1', 18084))
            guard_socket.listen(1)
            return watch_loop(baseline_run, release_id, profile, once, interval)
    return watch_loop(baseline_run, release_id, profile, once, interval)


def watch_loop(baseline_run, release_id, profile, once, interval):
    while True:
        if (STATE / 'control-drain').exists():
            return
        pulls = api(REPO + '/pulls?state=open&limit=50')
        for pr in pulls:
            if not opted_in(pr):
                continue
            marker = f'<!-- relevance-lab:{pr["head"]["sha"]} -->'
            comments = api(REPO + f'/issues/{pr["number"]}/comments?limit=100')
            if any(marker in comment['body'] for comment in comments):
                continue
            try:
                print(json.dumps(process(pr['number'], baseline_run, release_id, profile)), flush=True)
            except Exception as error:
                print(json.dumps({'pr': pr['number'], 'error': type(error).__name__,
                                  'detail': str(error)[:180]}), flush=True)
        if once:
            return
        time.sleep(interval)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-run', type=int, required=True)
    parser.add_argument('--release', default='retail-gb-10k-v1',
                        choices=('retail-gb-10k-v1', 'retail-gb-1m-v1'))
    parser.add_argument('--profile', default='probe', choices=('probe', 'smoke'))
    parser.add_argument('--pr', type=int)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--once', action='store_true')
    arguments = parser.parse_args()
    if bool(arguments.pr) == arguments.watch:
        parser.error('Select one PR number or --watch.')
    if arguments.watch:
        watch(arguments.baseline_run, arguments.release, arguments.profile, arguments.once)
    else:
        print(json.dumps(process(arguments.pr, arguments.baseline_run,
                                 arguments.release, arguments.profile), indent=2))
