"""Reviewed blue–green production releases on one frozen catalogue."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid
import sys

import yaml
from common import ROOT, STATE, k
from delivery_provider import DESIRED, endpoint, git, pull_request
from delivery.ci.release import canonical
from operation_telemetry import operation
from delivery_runtime import LOCAL, entry, rendered, read_target, checkout

NAMESPACE = 'lab-delivery-production'
PATH = 'targets/production/slots.json'
CATALOGUE_FIELDS = ('index', 'dataset_sha256', 'catalogue_manifest_sha256',
                    'mapping_sha256', 'index_recipe_sha256', 'engine', 'request_context')


def same_catalogue(first, second):
    if any(first['fields'].get(key) != second['fields'].get(key) for key in CATALOGUE_FIELDS):
        raise ValueError('Blue and green require the same concrete frozen index and catalogue.')


def state(revision='HEAD'):
    value = json.loads(git(DESIRED, 'show', revision + ':' + PATH))
    validate_state(value)
    return value


def validate_state(value):
    if (value.get('kind') != 'production-slots' or value.get('schema_version') != 1 or
            value.get('active') not in ('blue', 'green') or
            not isinstance(value.get('slots'), dict) or
            set(value['slots']) - {'blue', 'green'} or value['active'] not in value['slots']):
        raise ValueError('Invalid production slot state.')
    from delivery_runtime import fingerprint
    for deployment in value['slots'].values():
        if fingerprint(deployment['fields']) != deployment['fingerprint']:
            raise ValueError('Production slot fingerprint differs.')
        same_catalogue(value['slots'][value['active']], deployment)
    return value


def initial(deployment):
    return {'kind': 'production-slots', 'schema_version': 1,
            'active': 'blue', 'slots': {'blue': deployment}}


def inactive(value):
    return 'green' if value['active'] == 'blue' else 'blue'


def documents(value, render=rendered):
    """Render both exact release bundles and select only the active slot."""
    validate_state(value)
    shared, slots = {}, []
    for colour, deployment in sorted(value['slots'].items()):
        for doc in yaml.safe_load_all(render(deployment, NAMESPACE)):
            if doc is None:
                continue
            doc = deepcopy(doc)
            kind = doc['kind']
            if kind == 'Deployment':
                doc['metadata']['name'] = 'search-' + colour
                doc['spec']['selector']['matchLabels']['release-slot'] = colour
                doc['spec']['template']['metadata']['labels']['release-slot'] = colour
                slots.append(doc)
            elif kind == 'Service' and doc['metadata']['name'] == 'search':
                doc['metadata']['name'] = 'search-' + colour
                doc['spec']['selector']['release-slot'] = colour
                slots.append(doc)
            elif kind == 'ConfigMap' and doc['metadata']['name'] == 'frozen-definition':
                doc['metadata']['name'] += '-' + colour
                slots.append(doc)
            else:
                key = (kind, doc['metadata']['name'])
                if key in shared and shared[key] != doc:
                    raise ValueError('Release bundles disagree on shared production resources.')
                shared[key] = doc
    active = value['active']
    stable = deepcopy(next(d for d in slots if d['kind'] == 'Service' and
                           d['metadata']['name'] == 'search-' + active))
    stable['metadata']['name'] = 'search'
    stable['metadata'].setdefault('annotations', {})['argocd.argoproj.io/sync-wave'] = '1'
    definition = {'apiVersion': 'v1', 'kind': 'ConfigMap',
        'metadata': {'name': 'frozen-definition', 'namespace': NAMESPACE,
                     'annotations': {'argocd.argoproj.io/sync-wave': '1'}},
        'data': {'definition.json': canonical(entry(value['slots'][active], NAMESPACE)).decode(),
                 'active-slot': active}}
    return [*shared.values(), *slots, stable, definition]


def render_state(value):
    return yaml.safe_dump_all(documents(value), sort_keys=False)


def write(value):
    validate_state(value)
    folder = LOCAL / 'targets/production'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'rendered').mkdir(exist_ok=True)
    (folder / 'slots.json').write_bytes(canonical(value))
    (folder / 'deployment.json').write_bytes(canonical(value['slots'][value['active']]))
    (folder / 'rendered/search.yaml').write_text(render_state(value), encoding='utf-8', newline='\n')


def frozen_catalogue(deployment):
    """A real Elasticsearch write block represents paused catalogue updates."""
    from data_contract import elastic
    index = deployment['fields']['index']
    settings = elastic('/' + index + '/_settings')
    if settings.get(index, {}).get('settings', {}).get('index', {}).get('blocks', {}).get('write') not in ('true', True):
        raise ValueError('Pause catalogue updates: the production index must have a write block.')


def live(value):
    """Check declared images, rollout and stable routing without trusting a preview."""
    validate_state(value)
    frozen_catalogue(value['slots'][value['active']])
    service = json.loads(k('get', 'service/search', '-n', NAMESPACE, '-o', 'json').stdout)
    if service['spec']['selector'] != {'app': 'search', 'release-slot': value['active']}:
        raise ValueError('Production service does not select its declared active slot.')
    slices = json.loads(k('get', 'endpointslices', '-n', NAMESPACE, '-l',
        'kubernetes.io/service-name=search', '-o', 'json').stdout)
    pods = [endpoint.get('targetRef', {}).get('name', '')
        for item in slices.get('items', []) for endpoint in item.get('endpoints', [])
        if endpoint.get('conditions', {}).get('ready') is True]
    if not pods or any(not pod.startswith('search-' + value['active'] + '-') for pod in pods):
        raise ValueError('Production route has not reached the declared active slot.')
    for colour, deployment in value['slots'].items():
        obj = json.loads(k('get', 'deployment/search-' + colour, '-n', NAMESPACE, '-o', 'json').stdout)
        status = obj.get('status', {})
        if (status.get('observedGeneration', 0) < obj['metadata']['generation'] or
                status.get('updatedReplicas') != 1 or status.get('availableReplicas') != 1):
            raise ValueError('Production slot has not rolled out: ' + colour)
        container = obj['spec']['template']['spec']['containers'][0]
        if container['image'] != deployment['fields']['image'] or next(
                e['value'] for e in container['env'] if e['name'] == 'ES_INDEX') != deployment['fields']['index']:
            raise ValueError('Production slot serves a different image or index.')
        config = json.loads(k('get', 'configmap/frozen-definition-' + colour, '-n', NAMESPACE, '-o', 'json').stdout)
        if json.loads(config['data']['definition.json']) != entry(deployment, NAMESPACE):
            raise ValueError('Production slot definition differs.')
    return value


@operation('delivery.production_prepare')
def prepare():
    """Propose a candidate beside the active release, without moving the route."""
    from delivery_promote import verified, validate_pr
    from delivery_runtime import materialise, access
    base = checkout()
    current, candidate = read_target('production'), read_target('staging')
    verified('production', current)
    verified('staging', candidate)
    same_catalogue(current, candidate)
    frozen_catalogue(current)
    # Initial setup seeds slots directly. An existing lab is explicitly adopted
    # once by this reviewed preparation; no old-data conversion is used at runtime.
    exists = git(DESIRED, 'ls-tree', '--name-only', base, PATH)
    before = state(base) if exists else initial(current)
    if candidate['fingerprint'] == current['fingerprint']:
        raise ValueError('Staging already matches active production; prepare a different merged release.')
    after = deepcopy(before)
    after['slots'][inactive(before)] = candidate
    materialise(candidate)
    access(NAMESPACE, candidate)
    identifier = 'production-prepare-' + uuid.uuid4().hex[:10]
    proposal = {'format': 1, 'kind': 'prepare-production', 'target': 'production',
        'base_revision': base, 'expected_target': current['fingerprint'],
        'source_target': 'staging', 'deployment': current, 'slots': after,
        'previous_slots': before, 'candidate': candidate}
    git(DESIRED, 'switch', '-c', 'promote/' + identifier)
    write(after)
    folder = LOCAL / 'proposals'; folder.mkdir(exist_ok=True)
    (folder / (identifier + '.json')).write_bytes(canonical(proposal))
    git(DESIRED, 'add', '.')
    git(DESIRED, 'commit', '-m', 'Prepare inactive production API')
    git(DESIRED, 'push', 'origin', 'promote/' + identifier)
    pr = pull_request(DESIRED, 'promote/' + identifier, 'Prepare production candidate',
        'Deploy the verified staging release beside active production. The production URL stays on **' +
        before['active'] + '**. Both APIs use the same read-only catalogue. Review and approve this PR, '
        'then use **Deploy approved PR** in the [production release UI](https://control.localhost:34443/production-release).')
    git(DESIRED, 'switch', 'main')
    return {'pr': pr['number'], 'url': pr['html_url'], 'proposal': proposal,
            'validation': validate_pr(pr['number'])}


def inspect_preparation(pr, proposal, base, head, changed, proposal_path):
    from delivery_runtime import validate_deployment
    from delivery_promote import verified
    before = state(base) if git(DESIRED, 'ls-tree', '--name-only', base, PATH) else initial(read_target('production', base))
    after = validate_state(proposal['slots'])
    candidate = proposal['candidate']
    expected = deepcopy(before); expected['slots'][inactive(before)] = candidate
    if proposal['previous_slots'] != before or after != expected or proposal['deployment'] != before['slots'][before['active']]:
        raise ValueError('Preparation must leave the active release and route unchanged.')
    if read_target('staging', base) != candidate:
        raise ValueError('Staging changed after candidate preparation.')
    validate_deployment(candidate)
    verified('staging', candidate)
    frozen_catalogue(candidate)
    validate_files(head, after, changed, {proposal_path})
    return pr, proposal


def validate_files(head, value, changed, extra):
    allowed = {PATH, 'targets/production/deployment.json', 'targets/production/rendered/search.yaml', *extra}
    if set(changed) - allowed or not {PATH, 'targets/production/rendered/search.yaml'} <= set(changed):
        raise ValueError('Production PR changes files outside its declared slots.')
    for path, expected in ((PATH, value), ('targets/production/deployment.json', value['slots'][value['active']])):
        if json.loads(git(DESIRED, 'show', head + ':' + path)) != expected:
            raise ValueError('Production PR state differs from its proposal.')
    if git(DESIRED, 'show', head + ':targets/production/rendered/search.yaml') != render_state(value).strip():
        raise ValueError('Production workloads differ from their exact release bundles.')


def retain_bytes(payload, filename):
    from compare_search import immutable_blob
    sha = hashlib.sha256(payload).hexdigest()
    return {'sha256': sha, 'blob': immutable_blob('runs', sha + '/' + filename, payload)}


@operation('delivery.production_final')
def final_check(progress=lambda message: None):
    """Capture active production and its prepared candidate, then freeze shared labels."""
    from delivery_gates import retain
    from input_selection import select
    from search_probe import search
    from evaluation_job import run_variants
    from additional_judgements import resolve_extra
    sys.path[:0] = [str(ROOT / 'evaluation'), str(ROOT / 'lab/search-app')]
    from query_sets import score_extra, sha
    checkout()
    before = live(state())
    colour = inactive(before)
    if colour not in before['slots']:
        raise ValueError('Prepare and deploy the candidate before the final check.')
    first, second = before['slots'][before['active']], before['slots'][colour]
    inputs = select(second['fields']['dataset_release'], second['fields']['dataset_sha256'],
                    second['fields']['query_manifest_sha256'], second['fields']['judgement_manifest_sha256'], relevance=True)
    # Fixture for yesterday's recent-query selection. It is intentionally labelled
    # simulated traffic and pins the exact suite; no real traffic is claimed.
    queries = inputs['queries'][:1000]
    payload = b''.join(canonical(row) + b'\n' for row in queries)
    labels = [r for r in inputs['judgements'] if r['query_id'] in {q['query_id'] for q in queries}]
    label_bytes = b''.join(canonical(row) + b'\n' for row in labels)
    item = {'name': 'recent-production', 'required': False, 'queries': queries,
        'query_bytes': payload, 'query_sha256': sha(payload), 'judgements_rows': labels,
        'judgement_bytes': label_bytes, 'judgement_sha256': sha(label_bytes)}
    pins, targets = {}, {}
    for name, deployment, service in (('active', first, 'search'), ('candidate', second, 'search-' + colour)):
        answer = search(NAMESPACE, queries[0]['query'], service=service)
        if not answer:
            raise ValueError('Production API preflight failed.')
        pins[name] = {'image': deployment['fields']['image'], 'environment_fingerprint': deployment['fingerprint'],
                      'configuration_sha256': answer['configuration_sha256'], 'api_variant_id': answer['variant_id']}
        targets[name] = {'environment': NAMESPACE, 'service': service, 'selection': 'default',
                         'variant_id': answer['variant_id'], 'configuration_sha256': answer['configuration_sha256']}
    progress('Comparing the active production API with the prepared candidate')
    rows, execution = run_variants(payload, targets)
    if any('error' in row for row in rows):
        raise ValueError('Final capture is incomplete; inspect coordinator logs.')
    by_id = {q['query_id']: q for q in queries}
    observations = {'kind': 'search-variant-observation-set', 'schema_version': 1,
        'default_variant': 'active', 'baseline_variant': 'active', 'variants': pins,
        'variant_set_sha256': sha(canonical(pins)), 'captured_depth': 10,
        'catalogue_sha256': second['fields']['dataset_sha256'], 'query_suite_sha256': sha(payload),
        'captured_at': datetime.now(timezone.utc).isoformat(), 'request_adapter': 'search-api-variant-v1',
        'execution': execution, 'errors': [], 'observations': [{'query_id': r['query_id'],
        'request': {k: by_id[r['query_id']].get(k, {} if k == 'filters' else None)
                    for k in ('query','country','currency','filters')}, 'results': r['results']} for r in rows]}
    spec = (ROOT / 'evaluation/specs/proxy-v2.json').read_bytes()
    progress('Resolving gaps and freezing one judgement set for both production APIs')
    resolved = resolve_extra(item, observations, spec, inputs['catalogue'], retain_bytes)
    report = score_extra(resolved, observations, spec, canonical(inputs['catalogue']))
    if live(state()) != before:
        raise ValueError('Production slots changed during the final check.')
    report.update(production_slots_sha256=sha(canonical(before)),
        production_baseline=first['fingerprint'], production_candidate=second['fingerprint'],
        completed_at=datetime.now(timezone.utc).isoformat(),
        recent_query_source='simulated recent traffic: pinned ESCI query fixture',
        frozen_inputs={'queries': retain_bytes(payload, 'recent-queries.jsonl'),
            'observations': retain_bytes(canonical(observations), 'observations.json'),
            'judgements': resolved['resolved_references']['judgements'],
            'resolution': resolved['resolved_references']['resolution'],
            'specification': retain_bytes(spec, 'specification.json')})
    # The existing delivery gates still decide eligibility. This final check is
    # additional human-reviewed evidence, not a new unqualified quality threshold.
    report['release_review'] = 'Review relevance, result changes and coverage before activation.'
    return retain(report, 'production-final-comparison.json')


def validate_final(reference, value):
    from delivery_gates import read
    report = read(reference)
    active, other = value['active'], inactive(value)
    moment = datetime.fromisoformat(report['completed_at'])
    now = datetime.now(timezone.utc)
    if (not report.get('complete') or report['production_slots_sha256'] != hashlib.sha256(canonical(value)).hexdigest()
            or report['production_baseline'] != value['slots'][active]['fingerprint']
            or report['production_candidate'] != value['slots'][other]['fingerprint']
            or moment > now or now - moment > timedelta(days=3)):
        raise ValueError('Final production evidence is stale or belongs to other slots.')
    frozen_catalogue(value['slots'][active])
    return report


@operation('delivery.production_release')
def release(intent, progress=lambda message: None):
    from delivery_gates import evaluate, read, retain
    from delivery_promote import propose, verified
    checkout()
    value = live(state())
    if inactive(value) not in value['slots']:
        raise ValueError('Prepare and deploy an inactive production candidate first.')
    first, candidate = value['slots'][value['active']], value['slots'][inactive(value)]
    if candidate != read_target('staging'):
        raise ValueError('Prepared candidate no longer matches verified staging.')
    verified('staging', candidate)
    progress('Running the required production normal and peak Gatling gate')
    evidence = evaluate(first, candidate, intent, 'production-load')
    final = final_check(progress)
    updated = {**read(evidence), 'production_final': final}
    evidence = retain(updated, 'delivery-evidence.json')
    progress('Creating the reviewed production route switch')
    result = propose('production', candidate, evidence, intent)
    return {**result, 'report': evidence, 'final_report': final}


def view():
    """Read observed release state without touching the coordinator Git checkout."""
    obj = k('get','configmap/frozen-definition','-n',NAMESPACE,'-o','json',check=False)
    if obj.returncode:
        return {'state': 'unavailable'}
    data = json.loads(obj.stdout)['data']; definition = json.loads(data['definition.json'])
    active = data.get('active-slot')
    slots = {}
    for colour in ('blue','green'):
        obj = k('get','configmap/frozen-definition-'+colour,'-n',NAMESPACE,'-o','json',check=False)
        if not obj.returncode:
            slots[colour] = json.loads(json.loads(obj.stdout)['data']['definition.json'])
    other = next((v for colour, v in slots.items() if colour != active), None)
    rollback = bool(other and (STATE / 'delivery/verified/production' / (other['fingerprint'] + '.json')).exists())
    return {'state': 'ready' if active else 'not-prepared', 'active': active, 'can_rollback': rollback,
            'production': definition, 'slots': slots,
            'browser_url': 'https://' + NAMESPACE + '.preview.relevance.test:34443/'}
