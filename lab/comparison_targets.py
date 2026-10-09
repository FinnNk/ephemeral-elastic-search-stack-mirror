"""Ready delivery targets and immutable identities for exploratory comparisons."""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from common import STATE, k
from search_target import coordinates, api_url

ID = re.compile(r'delivery:(lab-delivery-(?:integration|staging|production-(?:blue|green)|run-[1-9][0-9]*-[a-f0-9]{8})):([a-f0-9]{64})\Z')


def snapshot(identifier):
    """Read retained target metadata so historical reports survive later releases."""
    if not ID.fullmatch(identifier):
        return None
    path = STATE / 'comparison-targets' / (hashlib.sha256(identifier.encode()).hexdigest() + '.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def available():
    """Discover healthy deployed releases; never create lifecycle or lease records."""
    from compare_search import definition
    rows = []
    active_obj = k('get', 'configmap/frozen-definition', '-n', 'lab-delivery-production', '-o', 'json', check=False)
    active = json.loads(active_obj.stdout).get('data', {}).get('active-slot') if not active_obj.returncode else None
    apps = k('get', 'applications', '-n', 'argocd', '-o', 'json')
    now = datetime.now(timezone.utc)
    previews = {}
    for app in json.loads(apps.stdout)['items']:
        name = app['metadata']['name']
        if not re.fullmatch(r'lab-delivery-run-[1-9][0-9]*-[a-f0-9]{8}', name):
            continue
        expiry = app['metadata'].get('annotations', {}).get('lab/preview-expires-at')
        if not expiry or datetime.fromisoformat(expiry.replace('Z', '+00:00')) <= now:
            continue
        previews[name] = expiry
    for name in ('lab-delivery-integration', 'lab-delivery-staging',
                 'lab-delivery-production-blue', 'lab-delivery-production-green', *previews):
        namespace, service = coordinates(name)
        try:
            value = definition(name)
            ready = json.loads(k('get', 'deployment/' + service, '-n', namespace, '-o', 'json').stdout)
            status = ready.get('status', {})
            replicas = ready.get('spec', {}).get('replicas', 1)
            if (replicas < 1 or status.get('observedGeneration', 0) < ready['metadata']['generation']
                    or any(status.get(key, 0) < replicas for key in ('availableReplicas', 'readyReplicas', 'updatedReplicas'))):
                continue
        except (AssertionError, KeyError, ValueError, RuntimeError):
            continue
        colour = name.rsplit('-', 1)[1] if service != 'search' else None
        role = ('active' if colour == active else 'inactive') if colour else None
        title = 'Production ' + colour + ' — ' + role if colour else name.removeprefix('lab-delivery-').title()
        if name in previews:
            title = 'Preview — ' + name.removeprefix('lab-delivery-')
        # A verification receipt may supply the build number; the observed
        # definition remains the authority for the release identity.
        build = int(name.split('-')[3]) if name in previews else None
        folder = STATE / 'delivery'
        for path in folder.glob('verified/*/*.json'):
            receipt = json.loads(path.read_text(encoding='utf-8'))
            deployment = receipt.get('deployment', {})
            if deployment.get('fingerprint') == value['fingerprint']:
                build = deployment.get('build_run')
                break
        now = datetime.now(timezone.utc).isoformat()
        identifier = 'delivery:' + name + ':' + value['fingerprint']
        row = {'id': identifier, 'name': name, 'owner': 'lab', 'shared': True,
               'managed_by': 'delivery', 'state': 'ready', 'label': title + (' — build ' + str(build) if build else ''),
               'build_run': build, 'source_sha': value['source_sha'], 'image': value['image'],
               'software_version': value.get('software_version'),
               'dataset_sha256': value['dataset_sha256'], 'fingerprint': value['fingerprint'],
               'release_id': value['dataset_release'], 'index_name': value['index'], 'index_kind': 'shared',
               'index_recipe_sha256': value['index_recipe_sha256'], 'created_at': now,
               'api_url': api_url(name), 'definition': value, 'slot_role': role,
               'expires_at': previews.get(name), 'browser_url': None}
        path = STATE / 'comparison-targets' / (hashlib.sha256(identifier.encode()).hexdigest() + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
            temporary.write_text(json.dumps(row, sort_keys=True), encoding='utf-8')
            temporary.replace(path)
        rows.append(row)
    return rows


def lookup(store, identifier, *, current=False):
    """Resolve only server-discovered targets, rejecting changed or unready releases."""
    if not identifier.startswith('delivery:'):
        return store.get(identifier)
    if current:
        row = next((r for r in available() if r['id'] == identifier), None)
        if row is None:
            raise ValueError('Delivery release changed or is not ready. Refresh and select it again.')
        return row
    return snapshot(identifier)
