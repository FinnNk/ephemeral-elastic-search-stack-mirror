"""Read-only release projection. Reading this module never acquires the writer lock."""
import json
import sqlite3
from datetime import datetime, timezone

from common import STATE, k
from delivery_provider import SOURCE, DESIRED, api, endpoint

GITEA = 'https://gitea.localhost:34443/elastic-agent/'
TARGETS = ('integration', 'staging', 'production')


def operation_rows(identity):
    """Read a bounded history without creating a database or exposing identities."""
    path = STATE / 'delivery-operations.sqlite3'
    if not path.exists():
        return []
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    db.row_factory = sqlite3.Row
    try:
        # Apply the same visibility as the operation API before using any results.
        predicate, args = ('1=1', ()) if identity.get('is_admin') or identity.get('is_reader') else ('owner=?', (identity['username'],))
        rows = db.execute('SELECT id,request,state,progress,result,error,created_at,updated_at '
                          'FROM operations WHERE ' + predicate + ' ORDER BY updated_at DESC LIMIT 300', args)
        return [{**dict(r), 'request': json.loads(r['request']),
                 'result': json.loads(r['result']) if r['result'] else {}} for r in rows]
    finally:
        db.close()


def records():
    """Load immutable verification history; broken records are reported by the caller."""
    return [{**json.loads(p.read_text(encoding='utf-8')), 'target': p.parent.name}
            for p in sorted((STATE / 'delivery/verified').glob('*/*.json'))]


def observed():
    """Read definitions, rollout and GitOps status using Kubernetes GETs only."""
    environments, notices = {}, []
    for target in TARGETS:
        ns = 'lab-delivery-' + target
        result = k('get', 'configmaps,deployments,services', '-n', ns, '-o', 'json', check=False)
        if result.returncode:
            notices.append('Could not read ' + target + '. Its current deployment is unknown.')
            continue
        items = {(r['kind'], r['metadata']['name']): r for r in json.loads(result.stdout)['items']}
        route = items.get(('ConfigMap', 'frozen-definition'), {}).get('data', {})
        for name, service in ((target, 'search'),) if target != 'production' else (
                ('production-blue', 'search-blue'), ('production-green', 'search-green')):
            colour = name.removeprefix('production-') if target == 'production' else None
            cm = 'frozen-definition-' + colour if colour else 'frozen-definition'
            raw = items.get(('ConfigMap', cm), {}).get('data', {}).get('definition.json')
            if not raw:
                continue
            definition = json.loads(raw)
            deployment = items.get(('Deployment', service), {})
            status = deployment.get('status', {})
            spec = deployment.get('spec', {})
            replicas = spec.get('replicas', 1)
            containers = spec.get('template', {}).get('spec', {}).get('containers', [])
            matching = any(c.get('image') == definition.get('image') and
                any(e.get('name') == 'ES_INDEX' and e.get('value') == definition.get('index')
                    for e in c.get('env', [])) for c in containers)
            ready = bool(matching and replicas > 0 and
                status.get('observedGeneration', 0) >= deployment.get('metadata', {}).get('generation', 1) and
                all(status.get(key, 0) >= replicas for key in ('readyReplicas', 'updatedReplicas', 'availableReplicas')))
            active = bool(colour and route.get('active-slot') == colour and
                items.get(('Service', 'search'), {}).get('spec', {}).get('selector', {}).get('release-slot') == colour)
            environments[name] = {'name': name, 'definition': definition, 'ready': ready,
                'active': active, 'slot': colour, 'ready_replicas': status.get('readyReplicas', 0),
                'replicas': replicas, 'url': 'https://' + ns + '.preview.relevance.test:34443/' if not colour or active else
                    'https://' + ns + '-' + colour + '.preview.relevance.test:34443/'}
    apps = k('get', 'applications', '-n', 'argocd', '-o', 'json', check=False)
    if apps.returncode:
        notices.append('GitOps status is unavailable.')
    else:
        for app in json.loads(apps.stdout)['items']:
            name = app['metadata']['name'].removeprefix('lab-delivery-')
            for row in environments.values():
                if row['name'] == name or name == 'production' and row['slot']:
                    status = app.get('status', {})
                    row['sync'] = status.get('sync', {}).get('status', 'Unknown')
                    row['health'] = status.get('health', {}).get('status', 'Unknown')
                    row['git_revision'] = status.get('sync', {}).get('revision')
    return environments, notices


def review(number):
    """Summarise current-head approval without interpreting it as deployment."""
    pr = api(endpoint(DESIRED, '/pulls/' + str(number)))
    head = pr['head']['sha']
    if pr.get('merged'):
        state = 'merged'
    elif pr.get('state') != 'open':
        state = 'closed'
    else:
        latest, all_reviews = {}, []
        for page in range(1, 11):
            rows = api(endpoint(DESIRED, f'/pulls/{number}/reviews?limit=50&page={page}'))
            all_reviews.extend(rows)
            if len(rows) < 50:
                break
        else:
            raise ValueError('Review history exceeds the dashboard limit.')
        for r in sorted(all_reviews, key=lambda r:r['id']):
            if not r.get('dismissed') and r.get('commit_id') == head and r.get('state') in ('APPROVED', 'REQUEST_CHANGES'):
                latest[r['user']['login']] = r['state']
        state = 'changes requested' if 'REQUEST_CHANGES' in latest.values() else 'approved' if 'APPROVED' in latest.values() else 'awaiting review'
    return {'number': number, 'state': state, 'head_sha': head,
            'url': GITEA + DESIRED + '/pulls/' + str(number)}


def candidate(proposal):
    """Preparation records contain the active deployment and a separate candidate."""
    return proposal.get('candidate') if proposal.get('kind') == 'prepare-production' else proposal.get('deployment')


def duration(start, end):
    try:
        return max(0, round((datetime.fromisoformat(end.replace('Z', '+00:00')) -
                            datetime.fromisoformat(start.replace('Z', '+00:00'))).total_seconds(), 1))
    except (AttributeError, ValueError, TypeError):
        return None


def project(run, rows, receipts, environments, reviews, builds, notices):
    """Join stages by exact build and deployment identity, never by the newest success."""
    now = datetime.now(timezone.utc).isoformat()
    proposals = {r['result']['pr']: r['result']['proposal'] for r in rows
                 if r['result'].get('pr') and r['result'].get('proposal')}
    deployments = [r['deployment'] for r in receipts if r.get('state') == 'verified']
    deployments += [candidate(p) for p in proposals.values() if candidate(p)]
    choices = {d['build_run']: {'run': d['build_run'], 'source_sha': d['fields']['source_sha'],
        'release_id': d['fields']['software_release_id']} for d in deployments}
    for build in builds:
        choices.setdefault(build['id'], {'run': build['id'], 'source_sha': build['head_sha'], 'release_id': None})
    choices = sorted(choices.values(), key=lambda r: r['run'], reverse=True)
    for choice in choices:
        deployed = [e for e in environments.values() if any(
            d['build_run'] == choice['run'] and d['fingerprint'] == e['definition'].get('fingerprint') and
            d['fields'] == {k:v for k,v in e['definition'].items() if k not in ('fingerprint','environment')}
            for d in deployments)]
        build = next((b for b in builds if b['id'] == choice['run']), {})
        choice['state'] = ('active production' if any(e['active'] and e['ready'] for e in deployed) else
            'rollout incomplete' if any(not e['ready'] for e in deployed) else
            'candidate ready' if any(e['slot'] and not e['active'] for e in deployed) else
            'staging' if any(e['name'] == 'staging' for e in deployed) else
            'integration' if any(e['name'] == 'integration' for e in deployed) else
            'build failed' if build.get('conclusion') == 'failure' else
            'built' if build.get('conclusion') == 'success' else
            'building' if build and build.get('status') != 'completed' else 'recorded')
        choice['environments'] = [e['name'] for e in deployed]
        choice['created_at'] = build.get('created_at')
    selected = next((r for r in choices if r['run'] == run), None) if run else next(iter(choices), None)
    if run and not selected:
        raise ValueError('Choose a listed merged-source build.')
    run = selected['run'] if selected else None
    details = [d for d in deployments if d['build_run'] == run]
    # A build may have several deployment definitions (for example, a changed
    # query suite). Follow one exact definition, anchored at the furthest live
    # stage, rather than joining unrelated successful fingerprints together.
    anchors = sorted(environments.values(), key=lambda e:
        4 if e['active'] else 3 if e['slot'] else 2 if e['name']=='staging' else 1, reverse=True)
    anchor = next((d for e in anchors for d in details if d['fingerprint'] == e['definition'].get('fingerprint') and
        d['fields'] == {k:v for k,v in e['definition'].items() if k not in ('fingerprint','environment')}),
        details[-1] if details else None)
    def matches(d):
        return bool(d and anchor and d.get('build_run') == run and
                    d.get('fingerprint') == anchor['fingerprint'] and d.get('fields') == anchor['fields'])
    def operation_deployment(row):
        result = row['result']
        p = result.get('proposal') or proposals.get(row['request'].get('pr'), {})
        return candidate(p) or result.get('deployment')
    activity = []
    for r in rows:
        d = operation_deployment(r)
        bound = matches(d) if d else r['request'].get('run') == run and run is not None
        if not bound:
            continue
        url = '/api/delivery/operations/' + r['id']
        activity.append({'id': r['id'], 'kind': r['request']['kind'], 'state': r['state'],
            'target': (r['result'].get('proposal') or proposals.get(r['request'].get('pr'), {})).get('target', r['request'].get('target')),
            'progress': r['progress'], 'error': r['error'], 'created_at': r['created_at'],
            'updated_at': r['updated_at'], 'duration_seconds': duration(r['created_at'], now if r['state'] in ('running','queued','accepted') else r['updated_at']),
            'url': url, 'report_url': url + '/report' if r['result'].get('report') else None,
            'evidence': r['result'].get('report'),
            'pr': reviews.get(r['result'].get('pr') or r['request'].get('pr')),
            'intent': r['request'].get('intent') or r['result'].get('proposal', {}).get('intent')})
    stages = []
    for name, title in (('integration','Integration'), ('staging','Staging'),
                        ('candidate','Production candidate'), ('production','Active production')):
        target = 'production' if name == 'candidate' else name
        history = sorted([r for r in receipts if r.get('state') == 'verified' and
                          r['target'] == target and matches(r.get('deployment'))], key=lambda r: r.get('verified_at', ''))
        current = next((r for r in environments.values() if
            (r['name'] == name or name == 'production' and r['active'] or name == 'candidate' and r['slot'] and not r['active']) and
            any(matches(d) and d['fingerprint'] == r['definition'].get('fingerprint') and
                d['fields'] == {k:v for k,v in r['definition'].items() if k not in ('fingerprint','environment')} for d in details)), None)
        related = [r for r in activity if r['target'] == target and
                   ((r['kind'] == 'prepare-production' or (proposals.get((r.get('pr') or {}).get('number'), {}).get('kind') == 'prepare-production')) == (name == 'candidate'))]
        latest = next(iter(related), None)
        receipt = next((r for r in reversed(history) if current and r['deployment']['fingerprint'] == current['definition']['fingerprint']), None)
        state, message = 'pending', 'No matching deployment recorded.'
        if current:
            state = 'prepared' if name == 'candidate' and current['ready'] else 'verified' if current['ready'] and receipt else 'observed' if current['ready'] else 'deploying'
            message = 'Serving this release.' if name == 'production' and current['ready'] else 'Inactive slot is ready; production remains unchanged.' if name == 'candidate' and current['ready'] else 'Deployment is ready.' if current['ready'] else 'Waiting for the rollout.'
        elif history and name != 'candidate':
            state = 'previously verified'
            available = any(r['name']==name or name=='production' and r['active'] for r in environments.values())
            message = 'Verified earlier; another release is now deployed.' if available else 'Verified earlier; current deployment is unavailable.'
        if latest and (not current or state == 'deploying'):
            if latest['state'] in ('failed','interrupted','running','queued','accepted'):
                state, message = latest['state'], latest['error'] or latest['progress']
            elif latest.get('pr') and latest['pr']['state'] != 'merged':
                state, message = latest['pr']['state'], 'Review the proposal and retained checks in Gitea.'
            elif latest.get('pr') and latest['pr']['state'] == 'merged' and not current:
                state, message = 'merged', 'Proposal merged; matching current rollout is not yet observed.'
        stages.append({'name': name, 'title': title, 'state': state, 'message': message,
                       'environment': current, 'verification': {k: receipt.get(k) for k in ('verified_at','seconds','git_revision')} if receipt else None,
                       'operation': latest, 'review_operation': next((r for r in related if r.get('pr')), None),
                       'check_operation': next((r for r in related
                           if r['kind'] in ('promotion','release-production','rollback') and r.get('evidence')), None)})
    active = next((r for r in environments.values() if r['active']), None)
    # Unbound production requests are shown separately. Never infer their release
    # from whatever happens to be in the inactive slot at read time.
    unbound = [{'kind':r['request']['kind'], 'state':r['state'], 'progress':r['progress'],
                'error':r['error'], 'updated_at':r['updated_at'], 'url':'/api/delivery/operations/'+r['id']}
               for r in rows if r['request']['kind'] == 'release-production' and not operation_deployment(r)][:5]
    build = next((r for r in builds if r['id'] == run), None)
    return {'updated_at': now, 'releases': choices, 'selected': selected,
        'build': {'state':build.get('conclusion') or build.get('status'), 'url':GITEA+SOURCE+'/actions/runs/'+str(run),
                  'duration_seconds':duration(build.get('created_at'), build.get('updated_at'))} if build else None,
        'release': anchor['fields'] if anchor else None, 'fingerprint':anchor['fingerprint'] if anchor else None, 'stages': stages,
        'active_production': active, 'environments': list(environments.values()),
        'activity': activity[:30], 'unbound_operations': unbound,
        'notices': notices, 'limits': 'Latest 50 source runs and 300 visible operations; retained deployment verification history.'}


def snapshot(identity, run=None):
    """Collect a read-only snapshot. Unavailable providers leave explicit unknowns."""
    if run is not None and (type(run) is not int or run < 1):
        raise ValueError('Build run must be a positive integer.')
    notices, builds, reviews = [], [], {}
    rows = operation_rows(identity)
    try:
        receipts = records()
    except (OSError, ValueError, KeyError):
        receipts = []
        notices.append('Verification history could not be read.')
    try:
        builds = [r for r in api(endpoint(SOURCE, '/actions/runs?limit=50'))['workflow_runs']
                  if r.get('event') == 'push' and r.get('path') == 'release.yaml@refs/heads/main']
    except (RuntimeError, OSError, KeyError, ValueError):
        notices.append('Source build status is unavailable.')
    environments, warnings = observed()
    notices += warnings
    # Only fetch reviews for the selected release, keeping refresh work bounded.
    first = project(run, rows, receipts, environments, {}, builds, notices)
    # Derive reviews through bound operation IDs; no cross-owner operation leaks.
    numbers = set()
    ids = {a['id'] for a in first['activity']}
    numbers |= {r['result'].get('pr') or r['request'].get('pr') for r in rows if r['id'] in ids}
    for number in sorted(numbers - {None}):
        try:
            reviews[number] = review(number)
        except (RuntimeError, OSError, ValueError, KeyError):
            reviews[number] = {'number':number,'state':'unknown','url':GITEA+DESIRED+'/pulls/'+str(number)}
            notices.append('Review status is unavailable for PR #' + str(number) + '.')
    result = project(run, rows, receipts, environments, reviews, builds, notices)
    result['source'] = source_merge(result.get('selected'), rows, notices)
    check_results(result['stages'], notices)
    return result


def source_merge(selected, rows, notices):
    """Show the source PR and its recorded gate at merge, preserving the PR head."""
    if not selected:
        return None
    try:
        pulls = api(endpoint(SOURCE, '/pulls?state=closed&limit=50&sort=recentupdate'))
        pr = next((p for p in pulls if p.get('merged') and p.get('merge_commit_sha') == selected['source_sha']), None)
        if not pr:
            return {'state':'unknown', 'message':'Source PR is outside the recent window or this was a direct main push.'}
        gate_rows = [r for r in rows if r['result'].get('gate') and
            r['result'].get('source_sha') == pr['head']['sha'] and
            (r['result'].get('source_pr') == pr['number'] or r['request'].get('pr') == pr['number']) and
            r['updated_at'] <= pr.get('merged_at', '').replace('Z', '+00:00')]
        gate = gate_rows[0] if gate_rows else None
        return {'state':'merged', 'number':pr['number'], 'title':pr['title'],
            'url':GITEA+SOURCE+'/pulls/'+str(pr['number']), 'merged_at':pr.get('merged_at'),
            'head_sha':pr['head']['sha'], 'gate':gate['result']['gate'] if gate else None,
            'gate_url':'/api/delivery/operations/'+gate['id'] if gate else None,
            'message':'Recorded source gate before merge.' if gate else 'No visible frozen gate record for the PR head at merge.'}
    except (RuntimeError, OSError, ValueError, KeyError):
        notices.append('Source merge details are unavailable.')
        return {'state':'unknown', 'message':'Source merge details could not be read.'}


def check_results(stages, notices):
    """Read saved check verdicts; this does not validate or rerun a promotion gate."""
    from delivery_gates import read
    for stage in stages:
        operation = stage.get('check_operation') or {}
        reference = operation.get('evidence')
        stage['checks'] = []
        if not reference:
            continue
        try:
            report = read(reference)
            for name, child in report.get('reports', {}).items():
                check = read(child)
                stage['checks'].append({'name':name, 'verdict':check.get('verdict','unknown'),
                    'profile':check.get('profile'), 'url':operation['report_url']+'/'+name})
            if report.get('production_final'):
                stage['checks'].append({'name':'production-final', 'verdict':'review evidence',
                    'url':operation['report_url']+'/production-final'})
        except Exception:
            # Blob providers have their own transport exception types. A read
            # failure must not turn unavailable evidence into a passing gate.
            notices.append('Saved check results could not be read for ' + stage['title'] + '.')
