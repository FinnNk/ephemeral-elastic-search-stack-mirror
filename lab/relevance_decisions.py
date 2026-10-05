"""Human-reviewed relevance decisions in Git, bound to frozen source evidence."""
import json
from datetime import datetime, timezone
import re

from common import ROOT, STATE
from blob_config import service
from delivery_provider import DESIRED, api, endpoint, git, pull_request, merge_demo
from delivery_runtime import checkout
from delivery_source_comparison import current_pr, source_bytes, recheck
from nexus import request as nexus_request
from variant_gate import approve, canonical, check, sha
from variant_gate_issue import operator_key

PREFIX = 'codex/relevance-decision-'


def frozen(request):
    """Revalidate the current source and signed evidence without any exceptions."""
    revision = request['source_sha']
    base = '/repository/lab-releases/variant-gates/' + revision + '/'
    report = nexus_request(base + 'report.json', identity='reader')
    context = json.loads(report)['source_context']
    if context['source_sha'] != revision or context['pr'] != request['pr']:
        raise ValueError('Decision evidence belongs to another source PR.')
    current_pr(request['pr'], revision, context['baseline_sha'])
    reference = json.loads(report)['frozen_inputs']['build_receipt']
    container, name = reference['blob'].split('/', 1)
    build = service().get_blob_client(container, name).download_blob().readall()
    if sha(build) != reference['sha256']:
        raise ValueError('Frozen build receipt differs.')
    policy = (ROOT / 'lab/delivery/policies/variant-merge-v1.json').read_bytes()
    selection = source_bytes('gate/selection.json', revision)
    verdict = check(report, policy, selection,
        json.loads(nexus_request(base + 'attestation.json', identity='reader')), [],
        operator_key('LAB_VARIANT_EVIDENCE_KEY'), operator_key('LAB_VARIANT_APPROVAL_KEY'),
        sha(policy), revision, build, 'elastic-agent/delivery-source')
    matches = [item for item in verdict['variants'] if item['variant'] == request['variant']]
    if len(matches) != 1 or matches[0]['state'] != 'decision_required':
        raise ValueError('The selected variant has no bounded exception to approve.')
    bindings = {key: verdict[key] for key in ('report_sha256', 'policy_sha256', 'selection_sha256')}
    bindings.update(source_pr=request['pr'], source_sha=revision, baseline_sha=context['baseline_sha'],
                    source_repository='elastic-agent/delivery-source', build_receipt_sha256=sha(build),
                    measured=matches[0], limits={key: json.loads(policy)[key] for key in (
                        'metric', 'minimum_judged_fraction', 'pass_min_delta', 'exception_min_delta',
                        'changed_query_fraction', 'low_coverage_exception', 'max_age_hours')})
    return bindings, report, policy, selection


def request_decision(request, identity):
    """Create one decision PR on behalf of an authenticated human administrator."""
    if not identity.get('is_admin') or identity.get('is_delivery_service'):
        raise ValueError('A human lab administrator must request an exception.')
    if len(request['reason'].strip()) < 20:
        raise ValueError('Explain why this measured regression is acceptable.')
    bindings, *_ = frozen(request)
    decision = {'kind': 'relevance-decision', 'schema_version': 1, **bindings,
        'variant': request['variant'], 'reason': request['reason'].strip(),
        'reviewer': identity['username'], 'requested_by': {
            'issuer': identity.get('issuer'), 'subject': identity.get('subject')},
        'requested_at': datetime.now(timezone.utc).isoformat()}
    payload = canonical(decision)
    identifier = sha(payload)
    path = 'decisions/relevance/' + identifier + '.json'
    branch = PREFIX + identifier[:16]
    checkout()
    git(DESIRED, 'switch', '-c', branch)
    try:
        destination = STATE / DESIRED / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        git(DESIRED, 'add', path)
        git(DESIRED, 'commit', '-m', 'Record relevance decision for ' + request['variant'])
        git(DESIRED, 'push', 'origin', 'HEAD')
    finally:
        git(DESIRED, 'switch', 'main')
    pr = pull_request(DESIRED, branch, 'Accept relevance regression: ' + request['variant'],
        'Review the measured results and reason in `' + path + '`.\n\n'
        'The named reviewer must approve this exact PR head. Merging records the decision; '
        'it does not deploy a release. Run **Lab delivery → merge-exception** with this PR number '
        'to merge the approved decision and recheck the source gate.\n\nSource PR: ' +
        'https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/' + str(request['pr']))
    return {'pr': pr['number'], 'url': 'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/' +
            str(pr['number']), 'decision': decision, 'head_sha': pr['head']['sha']}


def inspect(number):
    """Reject decision PRs that change anything except their single immutable record."""
    pr = api(endpoint(DESIRED, '/pulls/' + str(number)))
    if pr['base']['ref'] != 'main' or not pr['head']['ref'].startswith(PREFIX):
        raise ValueError('Choose a relevance decision PR to main.')
    if pr['state'] != 'open' and not pr.get('merged'):
        raise ValueError('Decision PR was closed without merging.')
    # Compare against the recorded base, not a main that has advanced since review.
    git(DESIRED, 'fetch', 'origin')
    base = git(DESIRED, 'merge-base', pr['base']['sha'], pr['head']['sha'])
    changes = git(DESIRED, 'diff', '--name-status', base, pr['head']['sha']).splitlines()
    if len(changes) != 1 or not re.fullmatch(r'A\tdecisions/relevance/[0-9a-f]{64}\.json', changes[0]):
        raise ValueError('A decision PR must add exactly one decision file.')
    path = changes[0].split('\t')[1]
    payload = git(DESIRED, 'show', pr['head']['sha'] + ':' + path, raw=True)
    decision = json.loads(payload)
    if (decision.get('kind') != 'relevance-decision' or decision.get('schema_version') != 1 or
            path != 'decisions/relevance/' + sha(payload) + '.json' or
            pr['head']['ref'] != PREFIX + sha(payload)[:16] or len(decision.get('reason', '').strip()) < 20):
        raise ValueError('Decision identity or reason differs.')
    bindings, report, policy, selection = frozen({'pr': decision['source_pr'],
        'source_sha': decision['source_sha'], 'variant': decision['variant']})
    if any(decision.get(key) != value for key, value in bindings.items()):
        raise ValueError('Decision no longer matches the source, policy or measured evidence.')
    return pr, path, payload, decision, report, policy, selection


def approved_review(pr, decision):
    """Require the named administrator's latest submitted review of the exact head."""
    username = decision['reviewer']
    permission = api(endpoint(DESIRED, '/collaborators/' + username + '/permission'))
    if permission.get('permission') not in ('admin', 'owner') or username == pr['user']['login']:
        raise ValueError('The named separate reviewer must administer delivery-state.')
    reviews = api(endpoint(DESIRED, '/pulls/' + str(pr['number']) + '/reviews'))
    submitted = [item for item in reviews if item['user']['login'] == username and
                 item.get('state') != 'PENDING']
    latest = max(submitted, key=lambda item: item['id'], default={})
    if latest.get('state') != 'APPROVED' or latest.get('dismissed') or latest.get('commit_id') != pr['head']['sha']:
        raise ValueError('The named reviewer must approve the exact decision PR head.')
    return latest


def complete(number, progress, operation_id):
    """Merge a reviewed decision, or resume receipt issuance after its merge."""
    checkout()
    pr, path, payload, decision, report, policy, selection = inspect(number)
    review = approved_review(pr, decision)
    if not pr.get('merged'):
        progress('Merging the approved relevance decision')
        # Revalidate immediately before the protected merge.
        current = inspect(number)[0]
        if current['head']['sha'] != pr['head']['sha']:
            raise ValueError('Decision head changed before merge.')
        approved_review(current, decision)
        pr = merge_demo(DESIRED, number, pr['head']['sha'])
    checkout()
    merge_sha = pr['merge_commit_sha']
    if not merge_sha or git(DESIRED, 'show', merge_sha + ':' + path, raw=True) != payload or \
            git(DESIRED, 'show', 'origin/main:' + path, raw=True) != payload:
        raise ValueError('Merged decision bytes differ from the approved record.')
    # A moved source or baseline after merge must never receive an exception.
    frozen({'pr': decision['source_pr'], 'source_sha': decision['source_sha'], 'variant': decision['variant']})
    reference = {'repository': 'elastic-agent/delivery-state', 'pr': number, 'path': path,
        'file_sha256': sha(payload), 'head_sha': pr['head']['sha'], 'merge_sha': merge_sha,
        'review_id': review['id']}
    receipt = approve(report, policy, selection, decision['source_sha'], decision['variant'],
        decision['reviewer'], decision['reason'], operator_key('LAB_VARIANT_APPROVAL_KEY'),
        review['submitted_at'], reference)
    progress('Publishing the Git-bound receipt and rechecking the source gate')
    publish_approval(receipt)
    result = recheck({'pr': decision['source_pr'], 'source_sha': decision['source_sha']}, progress, operation_id)
    result = {**result, 'decision': reference, 'url':
        'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/' + str(number)}
    marker = STATE / 'delivery' / 'relevance-decisions' / (str(number) + '.json')
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_bytes(canonical(result))
    return result


def publish_approval(receipt):
    """Retain one immutable receipt per source variant; retries compare exact bytes."""
    from nexus import publish
    revision = receipt['source_sha']
    publish('variant-gates/' + revision + '/decisions/' + receipt['decision']['file_sha256'] + '.json',
            canonical(receipt))
    publish('variant-gates/' + revision + '/approvals/' + receipt['variant'] + '.json', canonical(receipt))


def watch_decisions():
    """Validate open decisions and queue human-merged decisions once for processing."""
    from delivery_operations import Operations
    results = []
    for state in ('open', 'closed'):
        page = 1
        while True:
            pulls = api(endpoint(DESIRED, f'/pulls?state={state}&limit=100&page={page}'))
            for pr in pulls:
                if not pr['head']['ref'].startswith(PREFIX):
                    continue
                if state == 'open':
                    try:
                        inspect(pr['number'])
                        status, detail = 'success', 'Exact frozen decision verified; human review required'
                    except (ValueError, KeyError) as error:
                        status, detail = 'failure', str(error)[:140]
                    api(endpoint(DESIRED, '/statuses/' + pr['head']['sha']), 'POST', {
                        'context': 'delivery/validation', 'state': status, 'description': detail})
                    results.append({'pr': pr['number'], 'validation': status})
                elif pr.get('merged'):
                    marker = STATE / 'delivery' / 'relevance-decisions' / (str(pr['number']) + '.json')
                    if marker.exists():
                        continue
                    row = Operations().submit({'kind': 'merge-exception', 'pr': pr['number']},
                        {'username': 'delivery-coordinator', 'subject': 'delivery-coordinator',
                         'issuer': 'lab-internal', 'is_admin': False, 'is_delivery_service': True},
                        'merged-decision-' + str(pr['number']))
                    results.append({'pr': pr['number'], 'operation': row['id'], 'state': row['state']})
            if len(pulls) < 100:
                break
            page += 1
    return results
