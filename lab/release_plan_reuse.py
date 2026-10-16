"""Carry reviewed choices forward without carrying approval across destinations."""
from copy import deepcopy


def defaults(suggestion):
    """Suggest retiring unlabelled copies only when the same queries gain labels."""
    suites = suggestion['suites']
    decisions = []
    for item in suites:
        replacement = next((other for other in reversed(suites) if other['id'] != item['id'] and
            other.get('name') == item.get('name') and other.get('query_sha256') == item.get('query_sha256') and
            other.get('judgements')), None)
        retire = not item['required'] and not item.get('judgements') and replacement
        decisions.append({'id': item['id'],
            'disposition': 'required' if item['required'] else 'retired' if retire else 'report_only',
            'reason': 'Superseded by the labelled version of the same queries: ' + replacement['id'] + '.' if retire else ''})
    return {'variants': deepcopy(suggestion['variants']), 'suites': decisions,
            'additional_query_sets': [], 'reason': ''}


def recommend(suggestion):
    """Reuse choices only for the exact release in the immediately preceding stage."""
    import release_check_plans as plans
    pin = suggestion['binding']
    preceding = {'staging': 'integration', 'production': 'staging'}.get(pin['target'])
    if not preceding:
        return {'recommended_edits': defaults(suggestion)}
    for pr in sorted(plans.pulls(), key=lambda p: p['number'], reverse=True):
        if not pr.get('merged'):
            continue
        checked, path, payload, plan = plans.inspect(pr['number'])
        old = plan['suggestion']['binding']
        if (old['target'] != preceding or old['candidate'] != pin['candidate'] or
                old['primary_query_sets'] != pin['primary_query_sets'] or
                old['policy_sha256'] != pin['policy_sha256']):
            continue
        if plans.content(path, 'main') != payload or plans.content(path, pr['merge_commit_sha']) != payload:
            continue
        plans.approval(checked, plan)
        previous = {d['id']: d for d in plan['edits']['suites']}
        current = {v['variant'] for v in suggestion['variants']}
        if current != {v['variant'] for v in plan['edits']['variants']}:
            continue
        edits = {'variants': deepcopy(plan['edits']['variants']),
                 'suites': [deepcopy(previous.get(s['id'], {
                     'id': s['id'], 'disposition': 'required' if s['required'] else 'report_only', 'reason': ''}))
                     for s in suggestion['suites']],
                 'additional_query_sets': deepcopy(plan['edits'].get('additional_query_sets', [])),
                 'reason': f'Carry forward reviewed {preceding} plan PR #{pr["number"]} for the same release. '
                           'Review the current destination baseline and any destination-specific requirements. '
                           + plan['edits']['reason']}
        # A new required source declaration cannot be weakened by an older choice.
        for item, decision in zip(suggestion['suites'], edits['suites']):
            if item['required'] and decision['disposition'] != 'required':
                decision.update(disposition='required', reason='')
        try:
            plans.build_plan(suggestion, edits, plan['reviewer'])
        except ValueError:
            continue
        return {'recommended_edits': edits, 'carried_from': {
            'pr': pr['number'], 'target': preceding,
            'url': 'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/' + str(pr['number'])}}
    return {'recommended_edits': defaults(suggestion)}


def queue_checks(record, identity, store):
    """One durable child request per recorded plan; ordinary retries reuse it."""
    pin = record['plan']['suggestion']['binding']
    if pin['target'] == 'production':
        payload = {'kind': 'release-production', 'run': record['run']}
    else:
        payload = {'kind': 'promotion', 'run': record['run'], 'target': pin['target']}
        for field, argument in (('dataset_release', 'dataset'), ('index_recipe_sha256', 'recipe'),
                                ('query_manifest_sha256', 'query_manifest'), ('judgement_manifest_sha256', 'judgement_manifest')):
            if pin['candidate']['fields'].get(field):
                payload[argument] = pin['candidate']['fields'][field]
    child = store.submit(payload, identity, 'plan-checks-' + record['id'], check_plan_id=record['id'])
    return {'id': child['id'], 'url': child['url'], 'state': child['state']}
