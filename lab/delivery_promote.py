"""Protected desired-state PRs, exact-input gates and deployment verification."""
from datetime import datetime, timezone
import json
import time
import uuid

from common import STATE, apply, k
from gitea import api
from delivery_provider import DESIRED, endpoint, git, pull_request, merge_demo
from delivery_runtime import (LOCAL, TARGETS, REPO_URL, access, application, checkout, entry,
                              materialise, read_target, rendered, validate_deployment, verify, write_target)
from delivery_gates import deployment_inputs, retain, validate_evidence
from delivery.ci.release import canonical
from compare_search import definition
from operation_telemetry import operation

STATUS = 'delivery/validation'
RECORDS = STATE / 'delivery'


def save_verification(target, deployment, value):
    value = {**value, 'deployment': deployment}
    reference = retain(value, 'deployment-verification.json')
    record = {**value, 'report': reference}
    folder = RECORDS / 'verified' / target
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (deployment['fingerprint'] + '.json')).write_bytes(canonical(record))
    (RECORDS / (target + '.json')).write_bytes(canonical(record))
    return record


@operation('delivery.verify', deadline_seconds=120)
def verify_target(target, deployment=None, revision=None):
    deployment = deployment or read_target(target)
    value = verify('lab-delivery-' + target, deployment, revision)
    return save_verification(target, deployment, value)


def verified(target, deployment):
    path = RECORDS / (target + '.json')
    if not path.exists():
        raise ValueError('Source target has no deployment verification.')
    value = json.loads(path.read_text())
    if value['state'] != 'verified' or value['deployment'] != deployment:
        raise ValueError('Source target verification is stale.')
    if definition('lab-delivery-' + target)['fingerprint'] != deployment['fingerprint']:
        raise ValueError('Source target is not serving its verified release.')
    return value


def protect():
    c = json.loads((STATE / 'credentials.json').read_text())
    reviewer = c['username']
    api(endpoint(DESIRED, '/collaborators/' + reviewer), 'PUT', {'permission': 'write'})
    rule = {'rule_name': 'main', 'enable_push': False, 'enable_force_push': False,
            'required_approvals': 1, 'dismiss_stale_approvals': True,
            'block_on_rejected_reviews': True, 'block_on_outdated_branch': True,
            'block_admin_merge_override': True, 'enable_status_check': True,
            'status_check_contexts': [STATUS], 'enable_approvals_whitelist': True,
            'approvals_whitelist_username': ['finnnk', reviewer]}
    rules = api(endpoint(DESIRED, '/branch_protections'))
    exists = any(row['rule_name'] == 'main' for row in rules)
    api(endpoint(DESIRED, '/branch_protections' + ('/main' if exists else '')),
        'PATCH' if exists else 'POST', rule)


def bootstrap(deployment):
    """Seed an empty fixture repository; resume setup only for the same baseline."""
    existing = api(endpoint(DESIRED))
    validate_deployment(deployment)
    if not existing['empty']:
        revision = checkout()
        if any(read_target(target) != deployment for target in TARGETS):
            raise ValueError('Desired-state repository has changed; use promotion PRs.')
    materialise(deployment)
    if existing['empty']:
        for target in TARGETS:
            write_target(target, deployment)
        (LOCAL / 'README.md').write_text('# Search delivery targets\n\nPromotion requires a validated PR and review. Production is simulated in this local cluster.\n', encoding='utf-8')
        git(DESIRED, 'add', '.')
        git(DESIRED, 'commit', '-m', 'Seed known frozen baseline for three delivery targets')
        git(DESIRED, 'push', '-u', 'origin', 'main')
        revision = git(DESIRED, 'rev-parse', 'HEAD')
    c = json.loads((STATE / 'credentials.json').read_text())
    apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'delivery-state-repo',
        'namespace': 'argocd', 'labels': {'argocd.argoproj.io/secret-type': 'repository'}},
        'stringData': {'type': 'git', 'url': REPO_URL, 'username': 'elastic-agent',
                       'password': c['delivery_read_token']}})
    protect()
    records = {}
    for target in TARGETS:
        name = 'lab-delivery-' + target
        access(name, deployment)
        application(name, 'targets/' + target + '/rendered')
        records[target] = verify_target(target, deployment, revision)
    return records


def propose(target, deployment, evidence, intent='preserve-results', rollback=False):
    base = checkout()
    current = read_target(target)
    if deployment['fingerprint'] == current['fingerprint']:
        raise ValueError('Target already declares this deployment.')
    validate_deployment(deployment)
    validate_evidence(evidence, current['fingerprint'], deployment['fingerprint'], intent,
                      deployment_inputs(deployment))
    source = None if target == 'integration' or rollback else TARGETS[TARGETS.index(target) - 1]
    if source:
        upstream = read_target(source)
        if upstream != deployment:
            raise ValueError('Promotion must reuse the preceding target deployment unchanged.')
        verified(source, upstream)
    if rollback:
        path = RECORDS / 'verified' / target / (deployment['fingerprint'] + '.json')
        if not path.exists() or json.loads(path.read_text())['deployment'] != deployment:
            raise ValueError('Rollback requires a retained, previously verified deployment for this target.')
    materialise(deployment)
    # Grant only old/new frozen indices before Argo can roll between the two versions.
    access('lab-delivery-' + target, deployment)
    proposal = {'format': 1, 'target': target, 'kind': 'rollback' if rollback else 'promotion',
                'base_revision': base, 'expected_target': current['fingerprint'],
                'source_target': source, 'deployment': deployment, 'evidence': evidence, 'intent': intent}
    identifier = target + '-' + uuid.uuid4().hex[:10]
    branch = 'promote/' + identifier
    git(DESIRED, 'switch', '-c', branch)
    history = LOCAL / 'history' / target
    history.mkdir(parents=True, exist_ok=True)
    previous = history / (current['fingerprint'] + '.json')
    if previous.exists() and json.loads(previous.read_text()) != current:
        raise ValueError('Retained deployment history differs.')
    previous.write_bytes(canonical(current))
    write_target(target, deployment)
    folder = LOCAL / 'proposals'
    folder.mkdir(exist_ok=True)
    (folder / (identifier + '.json')).write_bytes(canonical(proposal))
    git(DESIRED, 'add', '.')
    git(DESIRED, 'commit', '-m', proposal['kind'].capitalize() + ' to ' + target)
    git(DESIRED, 'push', 'origin', branch)
    body = ('## ' + proposal['kind'].capitalize() + ' to ' + target + '\n\n'
        'Release `' + deployment['fields']['software_release_id'] + '`; source `' + deployment['fields']['source_sha'] + '`.\n\n'
        'Baseline `' + current['fingerprint'] + '` → candidate `' + deployment['fingerprint'] + '`.\n\n'
        'Intent: **' + intent + '**. Evidence SHA-256 `' + evidence['sha256'] + '` in `' + evidence['blob'] + '`.\n\n'
        'Review the deployment, full result check, frozen relevance coverage and Gatling report. '
        'Synthetic relevance is a measurement, not automatic quality approval. '
        'The production target is a local simulation. Approval and deployment verification are separate.\n')
    pr = pull_request(DESIRED, branch, proposal['kind'].capitalize() + ': ' + target + ' release ' +
                      deployment['fields']['software_release_id'][:12], body)
    git(DESIRED, 'switch', 'main')
    validation = validate_pr(pr['number'])
    return {'pr': pr['number'], 'url': pr['html_url'], 'head_sha': pr['head']['sha'],
            'proposal': proposal, 'validation': validation}


def inspect_pr(number):
    pr = api(endpoint(DESIRED, '/pulls/' + str(number)))
    if pr['state'] != 'open' or pr['base']['ref'] != 'main':
        raise ValueError('Promotion must be an open PR to main.')
    git(DESIRED, 'fetch', 'origin', 'main', pr['head']['ref'])
    head = pr['head']['sha']
    base = git(DESIRED, 'rev-parse', 'origin/main')
    changed = git(DESIRED, 'diff', '--name-only', base + '...' + head).splitlines()
    proposals = [name for name in changed if name.startswith('proposals/') and name.endswith('.json')]
    if len(proposals) != 1:
        raise ValueError('A promotion PR must contain exactly one proposal.')
    proposal = json.loads(git(DESIRED, 'show', head + ':' + proposals[0]))
    target = proposal['target']
    if target not in TARGETS or proposal['base_revision'] != base:
        raise ValueError('Desired-state main changed; recreate the proposal against the current target.')
    current = read_target(target, base)
    deployment = proposal['deployment']
    if proposal['expected_target'] != current['fingerprint']:
        raise ValueError('Target baseline changed after evaluation.')
    expected_paths = {proposals[0], 'targets/' + target + '/deployment.json',
                      'targets/' + target + '/rendered/search.yaml'}
    history_path = 'history/' + target + '/' + current['fingerprint'] + '.json'
    if not expected_paths.issubset(changed) or set(changed) - expected_paths - {history_path}:
        raise ValueError('Promotion PR changes files outside its declared deployment.')
    if json.loads(git(DESIRED, 'show', head + ':' + history_path)) != current:
        raise ValueError('Prior deployment history differs.')
    if json.loads(git(DESIRED, 'show', head + ':targets/' + target + '/deployment.json')) != deployment:
        raise ValueError('Proposed deployment differs from the PR files.')
    if git(DESIRED, 'show', head + ':targets/' + target + '/rendered/search.yaml') != rendered(deployment, 'lab-delivery-' + target).strip():
        raise ValueError('Rendered workloads differ from the pinned release and deployment.')
    validate_evidence(proposal['evidence'], current['fingerprint'], deployment['fingerprint'],
                      proposal['intent'], deployment_inputs(deployment))
    if proposal['kind'] == 'rollback':
        record = RECORDS / 'verified' / target / (deployment['fingerprint'] + '.json')
        if not record.exists() or json.loads(record.read_text())['deployment'] != deployment:
            raise ValueError('Rollback deployment was not previously verified here.')
        if proposal['source_target'] is not None:
            raise ValueError('Rollback does not inherit a preceding stage.')
    elif proposal['kind'] == 'promotion':
        source = None if target == 'integration' else TARGETS[TARGETS.index(target) - 1]
        if proposal['source_target'] != source:
            raise ValueError('Promotion skips a required stage.')
        if source:
            if read_target(source, base) != deployment:
                raise ValueError('Source stage changed or has a different deployment.')
            verified(source, deployment)
    else:
        raise ValueError('Unknown promotion kind.')
    if api(endpoint(DESIRED, '/pulls/' + str(number)))['head']['sha'] != head:
        raise ValueError('PR head changed during validation.')
    return pr, proposal


@operation('delivery.validate_pr')
def validate_pr(number):
    pr = api(endpoint(DESIRED, '/pulls/' + str(number)))
    try:
        checked, proposal = inspect_pr(number)
        if checked['head']['sha'] != pr['head']['sha']:
            raise ValueError('PR head changed before validation finished.')
        result = {'passed': True, 'detail': 'Exact release, evidence and target verified; review required'}
    except Exception as error:
        result = {'passed': False, 'detail': str(error)[:130]}
    api(endpoint(DESIRED, '/statuses/' + pr['head']['sha']), 'POST', {
        'context': STATUS, 'state': 'success' if result['passed'] else 'failure',
        'description': result['detail'][:140], 'target_url': pr['html_url']})
    return {**result, 'head_sha': pr['head']['sha'], 'pr': number}


def approved_head(reviews, head_sha):
    return any(review.get('state') == 'APPROVED' and
               review.get('commit_id') == head_sha and
               review.get('user', {}).get('login') not in (None, 'elastic-agent')
               for review in reviews)


def merge_reviewed(number, approval_kind='separate reviewer'):
    """Merge a validated fixture PR only after a distinct reviewer approved its exact head."""
    checked = validate_pr(number)
    if not checked['passed']:
        raise ValueError(checked['detail'])
    pr, proposal = inspect_pr(number)
    reviews = api(endpoint(DESIRED, '/pulls/' + str(number) + '/reviews'))
    if not approved_head(reviews, pr['head']['sha']):
        raise ValueError('A separate reviewer must approve the exact PR head.')
    # Recheck immediately before merge; strict branch protection also blocks a moved main.
    inspect_pr(number)
    started = time.monotonic()
    merged = merge_demo(DESIRED, number, pr['head']['sha'])
    checkout()
    result = verify_target(proposal['target'], proposal['deployment'], merged['merge_commit_sha'])
    result['merge_to_verified_seconds'] = round(time.monotonic() - started, 3)
    result['pr'] = number
    result['approval_kind'] = approval_kind
    reference = retain(result, 'promotion-completion.json')
    api(endpoint(DESIRED, '/issues/' + str(number) + '/comments'), 'POST', {'body':
        'Argo CD and the public API verified the declared deployment in ' + str(result['merge_to_verified_seconds']) +
        ' s after merge. Verification SHA-256 `' + reference['sha256'] + '`. Artifact digests were reused without rebuilding.'})
    return result


def demonstrate_merge(number):
    """Host-only fixture shortcut: approve as lab-admin, then merge the reviewed head."""
    checked = validate_pr(number)
    if not checked['passed']:
        raise ValueError(checked['detail'])
    pr, _proposal = inspect_pr(number)
    api(endpoint(DESIRED, '/pulls/' + str(number) + '/reviews'), 'POST', {
        'event': 'APPROVED', 'commit_id': pr['head']['sha'],
        'body': 'Automated lab demonstration approval by the simulated reviewer. This is not human acceptance of relevance quality or a project implementation PR.'}, identity='admin')
    return merge_reviewed(number, 'automated demonstration by separate lab administrator')


@operation('delivery.watch_once')
def watch_once():
    checkout()
    results = []
    for pr in api(endpoint(DESIRED, '/pulls?state=open&limit=100')):
        if pr['head']['ref'].startswith('promote/'):
            results.append(validate_pr(pr['number']))
    for target in TARGETS:
        deployment = read_target(target)
        previous = RECORDS / (target + '.json')
        if (not previous.exists() or json.loads(previous.read_text())['deployment'] != deployment or
                json.loads(previous.read_text()).get('state') != 'verified'):
            access('lab-delivery-' + target, deployment)
            try:
                result = verify_target(target, deployment)
            except Exception as error:
                result = {'state': 'deployment-failed', 'target': target, 'error': str(error)[:180],
                          'deployment': deployment, 'at': datetime.now(timezone.utc).isoformat()}
                (RECORDS / (target + '.json')).write_bytes(canonical(result))
            results.append(result)
    return results
