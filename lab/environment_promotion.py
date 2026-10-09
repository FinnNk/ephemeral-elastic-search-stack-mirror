"""Project exact next-target promotion evidence without authorising deployment."""
import re
import sqlite3
import subprocess

from common import STATE
from delivery_provider import SOURCE, DESIRED, api, endpoint
from release_dashboard import operation_rows, review


def next_target(row):
    """Identify the next release step; ephemeral search builds are not releases."""
    name = row['name']
    if name == 'lab-delivery-integration':
        return 'staging'
    if name == 'lab-delivery-staging' or row.get('slot_role') == 'inactive':
        return 'production'
    if re.fullmatch(r'lab-delivery-run-[1-9][0-9]*-[a-f0-9]{8}', name):
        return 'integration'
    return None


def source_order(candidate, target):
    """Use locally retained Git ancestry; unavailable commits remain unknown."""
    if not all(re.fullmatch('[a-f0-9]{40}', value or '') for value in (candidate, target)):
        return 'unknown'
    if candidate == target:
        return 'same'
    path = STATE / SOURCE
    def ancestry(before, after):
        return subprocess.run(['git', '-c', 'safe.directory=' + str(path).replace('\\', '/'),
            '-C', str(path), 'merge-base', '--is-ancestor', before, after],
            capture_output=True, timeout=5).returncode
    try:
        forward, backward = ancestry(target, candidate), ancestry(candidate, target)
        if forward == 0:
            return 'newer'
        if backward == 0:
            return 'older'
    except (OSError, subprocess.TimeoutExpired):
        pass
    return 'unknown'


def project(row, targets, operations, reviews, main_sha, statuses, order=source_order):
    """Bind readiness to the exact candidate, current target and reviewed PR head."""
    target = next_target(row)
    result = {'target': target, 'state': 'no_evidence', 'tone': '',
              'message': 'No next-target promotion evidence.' if target else 'No forward promotion for this environment.'}
    if not target:
        return result
    active = next((r for r in targets if r['name'] == 'lab-delivery-' + target or
                   target == 'production' and r.get('slot_role') == 'active'), None)
    if not active:
        return {**result, 'message': 'Current target is unavailable.'}
    result['target_build_run'] = active.get('build_run')
    if row.get('fingerprint') == active.get('fingerprint'):
        return {**result, 'state': 'current', 'message': 'This release is already serving in ' + target + '.'}
    matching = []
    for operation in operations:
        proposal = (operation.get('result') or {}).get('proposal') or {}
        deployment = proposal.get('deployment') or {}
        # Preparation is not the final production gate.
        if proposal.get('kind') in ('promotion', 'rollback') and proposal.get('target') == target and \
                deployment.get('fingerprint') == row.get('fingerprint') and \
                deployment.get('fields') == {k: v for k, v in (row.get('definition') or {}).items()
                                            if k not in ('fingerprint', 'environment')}:
            matching.append(operation)
    if not matching:
        return result
    operation = max(matching, key=lambda r: r['updated_at'])
    proposal = operation['result']['proposal']
    number = operation['result'].get('pr')
    result.update(operation_url='/api/delivery/operations/' + operation['id'], pr=number)
    validation = (operation['result'].get('validation') or {}).get('passed')
    if operation['state'] != 'complete' or validation is not True:
        return {**result, 'state': 'closed', 'tone': 'bad', 'message': 'Promotion checks failed or are incomplete.'}
    if proposal.get('expected_target') != active.get('fingerprint') or proposal.get('base_revision') != main_sha:
        return {**result, 'state': 'closed', 'tone': 'bad', 'message': 'Target or desired state changed; fresh checks are required.'}
    pr = reviews.get(number) or {}
    if not pr or pr.get('state') == 'unknown':
        return {**result, 'message': 'Current approval is unavailable.'}
    if pr.get('state') != 'approved':
        return {**result, 'state': 'closed', 'tone': 'bad', 'message': 'Promotion is awaiting review or approval.'}
    if pr.get('head_sha') != operation['result'].get('head_sha'):
        return {**result, 'state': 'closed', 'tone': 'bad', 'message': 'Proposal changed; fresh promotion evidence is required.'}
    if statuses.get(number) != 'success':
        return {**result, 'state': 'closed', 'tone': 'bad', 'message': 'Current PR validation is not passing.'}
    relation = order(row.get('source_sha'), active.get('source_sha'))
    return {**result, 'state': 'promotable', 'order': relation,
            'tone': 'good' if relation == 'newer' else 'warn' if relation == 'older' else '',
            'message': 'Promotable · ' + {'newer': 'newer than target', 'older': 'older than target',
                'same': 'same source commit', 'unknown': 'source order unknown'}[relation]}


def decorate(rows, identity):
    """Collect bounded read-only evidence once for the environment list."""
    try:
        operations = operation_rows(identity)
    except (OSError, ValueError, KeyError, sqlite3.Error):
        return [{**r, 'promotion': {'target': next_target(r), 'state': 'no_evidence', 'tone': '',
                                  'message': 'Promotion history is unavailable.'}} for r in rows]
    reviews, statuses = {}, {}
    main_sha = None
    candidates = {(r.get('fingerprint'), next_target(r)) for r in rows if next_target(r)}
    numbers = {(r.get('result') or {}).get('pr') for r in operations
               if (r.get('result') or {}).get('proposal', {}).get('kind') in ('promotion', 'rollback') and
               (((r.get('result') or {}).get('proposal', {}).get('deployment') or {}).get('fingerprint'),
                (r.get('result') or {}).get('proposal', {}).get('target')) in candidates}
    try:
        main_sha = api(endpoint(DESIRED, '/branches/main'))['commit']['id']
        for number in sorted(numbers - {None})[-20:]:
            reviews[number] = review(number)
            values = api(endpoint(DESIRED, '/commits/' + reviews[number]['head_sha'] + '/statuses'))
            checks = [s for s in values if s.get('context') == 'delivery/validation']
            statuses[number] = max(checks, key=lambda s: s.get('id', 0))['status'] if checks else None
    except (RuntimeError, OSError, KeyError, ValueError):
        main_sha = None
    if main_sha is None:
        return [{**r, 'promotion': {'target': next_target(r), 'state': 'no_evidence', 'tone': '',
                                  'message': 'Promotion evidence is unavailable.'}} for r in rows]
    return [{**r, 'promotion': project(r, rows, operations, reviews, main_sha, statuses)} for r in rows]
