"""Guard dashboard actions with the selected release; delivery remains authoritative."""
import hashlib
import json
import re

from release_dashboard import snapshot
from delivery_operations import Operations

ACTIONS = {'integration', 'staging', 'prepare', 'release', 'deploy', 'rollback'}
BUSY = {'queued', 'running', 'accepted'}


def context(data):
    """Bind commands to observed releases and PR heads, excluding refresh timestamps."""
    value = {'selected': data.get('selected'), 'release': data.get('release'),
             'environments': [{k: e.get(k) for k in ('name', 'definition', 'ready', 'active')}
                              for e in data.get('environments', [])],
             'reviews': sorted({(a['pr']['number'], a['pr'].get('head_sha'), a['pr']['state'])
                                for a in data.get('activity', []) if a.get('pr')})}
    # Release choice status changes while an operation runs; only its identity
    # belongs in the execution fence.
    if value['selected']:
        value['selected'] = {k: value['selected'].get(k) for k in ('run', 'source_sha', 'release_id')}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def choices(data, identity):
    """Explain available actions; the worker rechecks the binding before execution."""
    stages = {s['name']: s for s in data.get('stages', [])}
    selected = data.get('selected') or {}
    build = data.get('build') or {}
    admin = identity.get('is_admin') and not identity.get('is_reader') and not identity.get('is_delivery_service')
    unavailable = ('Administrator access is required.' if not admin else
                   'Current release data is unavailable. Refresh before continuing.' if data.get('notices') else
                   'Choose a successful merged-source build.' if not selected or build.get('conclusion') != 'success' else '')
    def current(name, state):
        return stages.get(name, {}).get('state') == state and bool(stages.get(name, {}).get('environment'))
    approved = {a['pr']['number']: a['pr'] for a in data.get('activity', [])
                if a.get('pr', {}).get('state') == 'approved'}
    active = data.get('active_production')
    candidate = stages.get('candidate', {}).get('environment')
    retained = next((e for e in data.get('environments', [])
                     if e.get('slot') and not e.get('active') and e.get('ready')), None)
    reasons = {
        'integration': 'This release is already verified in Integration.' if current('integration', 'verified') else '',
        'staging': '' if current('integration', 'verified') and not current('staging', 'verified') else
                   'Verify this release in Integration first.' if not current('integration', 'verified') else 'This release is already verified in Staging.',
        'prepare': '' if current('staging', 'verified') and not candidate and active and
                   stages['staging']['environment']['definition'].get('fingerprint') != active['definition'].get('fingerprint') else
                   'Prepare from the verified Staging release; active production must differ and no candidate may already be prepared.',
        'release': '' if current('candidate', 'prepared') and active else 'Prepare and deploy this release into the inactive production slot first.',
        'deploy': '' if approved else 'Approve a proposal for this release in Gitea first.',
        'rollback': '' if current('production', 'verified') and retained and retained.get('rollback_verified') and retained['definition'].get('fingerprint') != active['definition'].get('fingerprint') else
                    'Rollback is available for the active release when a different ready release is retained in the other slot.'}
    for name, stage in (('integration', 'integration'), ('staging', 'staging'), ('prepare', 'candidate'), ('release', 'production')):
        review = (stages.get(stage, {}).get('review_operation') or {}).get('pr') or {}
        if review.get('state') in ('awaiting review', 'approved', 'changes requested'):
            reasons[name] = 'A proposal already exists. Review or close it before requesting another.'
    labels = {'integration': 'Check and propose Integration', 'staging': 'Check and propose Staging',
              'prepare': 'Prepare production candidate', 'release': 'Check and request production release',
              'deploy': 'Deploy approved proposal', 'rollback': 'Check and request rollback'}
    busy = any(a.get('state') in BUSY for a in data.get('activity', []))
    return {'context': context(data), 'actions': [{'name': name, 'label': labels[name],
              'enabled': not (unavailable or reasons[name] or busy),
              'reason': unavailable or reasons[name] or ('A release operation is already queued or running.' if busy else '')}
              for name in labels], 'approved_prs': list(approved.values())}


def payload(data, action, intent, number=None):
    """Translate the panel into existing named operations, with no arbitrary arguments."""
    run = data['selected']['run']
    fields = data.get('release') or {}
    if action in ('integration', 'staging'):
        value = {'kind': 'promotion', 'target': action, 'run': run, 'intent': intent}
        for key, source in (('dataset', 'dataset_release'), ('recipe', 'index_recipe_sha256'),
                            ('query_manifest', 'query_manifest_sha256'), ('judgement_manifest', 'judgement_manifest_sha256')):
            if fields.get(source): value[key] = fields[source]
        return value
    if action == 'prepare': return {'kind': 'prepare-production'}
    if action == 'release': return {'kind': 'release-production', 'intent': intent}
    if action == 'deploy': return {'kind': 'merge-reviewed', 'pr': number}
    retained = next(e for e in data['environments'] if e.get('slot') and not e.get('active') and e.get('ready'))
    return {'kind': 'rollback', 'target': 'production',
            'fingerprint': retained['definition']['fingerprint'], 'intent': intent}


def submit(request, identity, key):
    """Deduplicate transport retries and reject stale or ineligible selections."""
    if not identity.get('is_admin') or identity.get('is_reader') or identity.get('is_delivery_service'):
        raise PermissionError('A human lab administrator must request a promotion.')
    if (not isinstance(request, dict) or set(request) - {'run', 'action', 'intent', 'pr', 'context'} or
            type(request.get('run')) is not int or request['run'] < 1 or request.get('action') not in ACTIONS or
            request.get('intent') not in ('ranking-change', 'preserve-results') or
            not re.fullmatch('[0-9a-f]{64}', str(request.get('context', '')))):
        raise ValueError('Choose a release action and refresh its context.')
    if request['action'] == 'deploy' and (type(request.get('pr')) is not int or request['pr'] < 1):
        raise ValueError('Choose an approved proposal.')
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', key or ''):
        raise ValueError('Supply a stable submission key.')
    store = Operations()
    owner = identity.get('issuer', '') + ':' + identity.get('subject', identity['username'])
    identifier = hashlib.sha256((owner + '\n' + key).encode()).hexdigest()[:32]
    previous = store.get(identifier)
    if previous:
        if previous['request'].get('_release_binding', {}).get('request') != request:
            raise ValueError('Submission key already names a different release action.')
        return previous
    data = snapshot(identity, request['run'])
    options = choices(data, identity)
    if options['context'] != request['context']:
        raise ValueError('The release or environment changed. Refresh before continuing.')
    choice = next(a for a in options['actions'] if a['name'] == request['action'])
    if not choice['enabled']: raise ValueError(choice['reason'])
    if request['action'] == 'deploy' and request['pr'] not in {p['number'] for p in options['approved_prs']}:
        raise ValueError('The selected proposal is not approved for this release.')
    binding = {'request': request, 'identity': {k: identity[k] for k in ('username', 'is_admin')}}
    return store.submit(payload(data, request['action'], request['intent'], request.get('pr')),
                        identity, key, release_binding=binding)


def validate_binding(binding):
    """Fail queued work closed if its observed target or approved head has changed."""
    request = binding['request']
    data = snapshot(binding['identity'], request['run'])
    if data.get('notices') or context(data) != request['context']:
        raise ValueError('Release inputs, target or review changed while queued. Refresh and submit again.')
