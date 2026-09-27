"""Frozen release deployment through Argo CD; no CI process applies search workloads."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
import uuid

sys.path.insert(0, 'research/platform-spike')
sys.path.insert(0, '.lab/python-libs')
from common import HELM, ROOT, STATE, apply, guard, k, run
from data_contract import elastic
from environments import provision_access
from index_recipe import current_recipe, digest as recipe_digest, load as load_recipe, publish as publish_recipe, validate as validate_recipe
from shared_index import ensure_shared_index
from index_candidate import ensure_candidate_index
from delivery_provider import SOURCE, DESIRED, api, endpoint, git
from delivery_release import from_run, load
from delivery.ci.release import canonical, digest
from setup_nexus import image_secret
from compare_search import definition
from lifecycle import wait_correct_search

TARGETS = ('integration', 'staging', 'production')
REPO_URL = 'http://gitea-http.platform.svc.cluster.local:31800/elastic-agent/delivery-state.git'
LOCAL = STATE / DESIRED


@contextmanager
def writer():
    """One host coordinator owns the delivery checkout and evaluation slot at a time."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as lock:
        try:
            lock.bind(('127.0.0.1', 18086))
            lock.listen(1)
        except OSError:
            raise RuntimeError('Another delivery operation is active; retry when it finishes.') from None
        guard()
        yield


def fingerprint(fields):
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def compatible(release, recipe):
    contract = release['index_contract']
    if (recipe['engine_version'] != contract['engine_version'] or
            recipe['index_definition'] not in contract['definitions'] or
            recipe['indexer']['image'] != contract['indexer_image'] or
            recipe['indexer']['source_sha256'] != contract['indexer_source_sha256']):
        raise ValueError('Release is incompatible with the frozen index recipe.')


def resolve(run_id, dataset='retail-gb-10k-v1', recipe_sha=None, merged=True):
    receipt, release, _files = from_run(run_id)
    if merged and receipt['event_kind'] != 'push':
        raise ValueError('Promotion requires a successful merged-source push build.')
    if dataset not in ('retail-gb-10k-v1', 'retail-gb-1m-v1'):
        raise ValueError('Select one of the two frozen synthetic datasets.')
    manifest = json.loads((STATE / 'releases' / dataset / 'manifest.json').read_text())
    recipe = load_recipe(recipe_sha) if recipe_sha else current_recipe(
        dataset, 'shared', manifest, elastic('/')['version']['number'])
    validate_recipe(recipe, dataset, manifest, elastic('/')['version']['number'])
    compatible(release, recipe)
    recipe_sha = recipe_sha or publish_recipe(recipe)
    concrete = dataset if recipe['index_kind'] == 'shared' else 'lab-release-' + recipe_sha[:24] + '-idx'
    fields = {'image': release['image'], 'index': concrete, 'dataset_sha256': recipe['product_sha256'],
              'engine': recipe['engine_version'], 'mapping_sha256': recipe_digest(recipe['index_definition']),
              'index_recipe_sha256': recipe_sha, 'software_release_id': receipt['release_id'],
              'source_sha': release['source_sha'], 'bundle_sha256': release['bundle_sha256'],
              'dataset_release': dataset, 'request_context': {'country': 'GB', 'currency': 'GBP'}}
    return {'fields': fields, 'fingerprint': fingerprint(fields), 'build_run': run_id}


def validate_deployment(deployment):
    fields = deployment['fields']
    if fingerprint(fields) != deployment['fingerprint']:
        raise ValueError('Deployment fingerprint differs.')
    release, files = load(fields['software_release_id'])
    receipt, built, _ = from_run(deployment['build_run'])
    if (receipt['event_kind'] != 'push' or receipt['release_id'] != fields['software_release_id'] or
            release != built or release['image'] != fields['image'] or
            release['source_sha'] != fields['source_sha'] or release['bundle_sha256'] != fields['bundle_sha256']):
        raise ValueError('Deployment differs from its merged-source release.')
    recipe = load_recipe(fields['index_recipe_sha256'])
    manifest = json.loads((STATE / 'releases' / fields['dataset_release'] / 'manifest.json').read_text())
    validate_recipe(recipe, fields['dataset_release'], manifest, elastic('/')['version']['number'])
    compatible(release, recipe)
    if (fields['dataset_sha256'] != recipe['product_sha256'] or fields['engine'] != recipe['engine_version'] or
            fields['mapping_sha256'] != recipe_digest(recipe['index_definition']) or
            fields['request_context'] != {'country': 'GB', 'currency': 'GBP'}):
        raise ValueError('Deployment dataset, schema or request context differs.')
    expected_index = (fields['dataset_release'] if recipe['index_kind'] == 'shared' else
                      'lab-release-' + fields['index_recipe_sha256'][:24] + '-idx')
    if fields['index'] != expected_index:
        raise ValueError('Concrete index differs from the pinned recipe.')
    return recipe, files


def materialise(deployment):
    recipe, _ = validate_deployment(deployment)
    fields = deployment['fields']
    if recipe['index_kind'] == 'shared':
        return ensure_shared_index(fields['dataset_release'], fields['dataset_sha256'], fields['index_recipe_sha256'])
    return ensure_candidate_index('lab-release-' + fields['index_recipe_sha256'][:24],
        fields['dataset_sha256'], release_id=fields['dataset_release'],
        recipe_sha256=fields['index_recipe_sha256'], index_kind=recipe['index_kind'])


def entry(deployment, name):
    return {**deployment['fields'], 'fingerprint': deployment['fingerprint'], 'environment': name}


def rendered(deployment, name):
    _recipe, files = validate_deployment(deployment)
    directory = STATE / 'delivery-render' / deployment['fields']['software_release_id']
    for member, content in files.items():
        path = directory / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    values = entry(deployment, name)
    values_path = directory / 'values.json'
    values_path.write_bytes(canonical(values))
    result = run([HELM, 'template', name, str(directory / 'chart'), '-f', str(values_path)]).stdout
    control_ingress = {
        'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
        'metadata': {'name': 'control-search-ingress', 'namespace': name},
        'spec': {'podSelector': {}, 'policyTypes': ['Ingress'],
                 'ingress': [{'from': [{'namespaceSelector': {'matchLabels': {
                     'kubernetes.io/metadata.name': 'lab-control'}},
                     'podSelector': {'matchLabels': {'app': 'lab-control'}}}],
                     'ports': [{'port': 8080, 'protocol': 'TCP'}]}]}}
    config = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'frozen-definition', 'namespace': name},
              'data': {'definition.json': canonical(values).decode()}}
    return result.rstrip() + '\n---\n' + json.dumps(control_ingress, indent=2) + \
        '\n---\n' + json.dumps(config, indent=2) + '\n'


def checkout():
    if git(DESIRED, 'status', '--porcelain'):
        raise ValueError('Delivery checkout has uncommitted changes.')
    git(DESIRED, 'fetch', 'origin')
    git(DESIRED, 'switch', 'main')
    git(DESIRED, 'merge', '--ff-only', 'origin/main')
    return git(DESIRED, 'rev-parse', 'HEAD')


def read_target(target, revision='HEAD'):
    if target not in TARGETS:
        raise ValueError('Unknown promotion target.')
    return json.loads(git(DESIRED, 'show', revision + ':targets/' + target + '/deployment.json'))


def write_target(target, deployment):
    folder = LOCAL / 'targets' / target
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'deployment.json').write_bytes(canonical(deployment))
    (folder / 'rendered').mkdir(exist_ok=True)
    (folder / 'rendered/search.yaml').write_text(rendered(deployment, 'lab-delivery-' + target),
                                                 encoding='utf-8', newline='\n')


def access(name, deployment):
    indices = [deployment['fields']['index']]
    old = k('get', 'configmap/frozen-definition', '-n', name, '-o', 'json', check=False)
    if not old.returncode:
        previous = json.loads(json.loads(old.stdout)['data']['definition.json'])['index']
        if previous not in indices:
            indices.append(previous)
    provision_access(name, deployment['fields']['index'], read_indices=indices)
    image_secret(name)
    k('delete', 'secret/registry-read', '-n', name, '--ignore-not-found')


def application(name, path, revision='main', expires=None):
    annotations = {'lab/preview-expires-at': expires} if expires else {}
    apply({'apiVersion': 'argoproj.io/v1alpha1', 'kind': 'Application',
        'metadata': {'name': name, 'namespace': 'argocd', 'annotations': annotations,
                     'labels': {'lab/delivery': 'preview' if expires else 'target'},
                     'finalizers': ['resources-finalizer.argocd.argoproj.io']},
        'spec': {'project': 'default', 'source': {'repoURL': REPO_URL, 'path': path, 'targetRevision': revision},
                 'destination': {'server': 'https://kubernetes.default.svc', 'namespace': name},
                 'syncPolicy': {'automated': {'prune': True, 'selfHeal': True}}}})


def verify(name, deployment, revision=None):
    started = time.monotonic()
    k('annotate', 'application/' + name, '-n', 'argocd', 'argocd.argoproj.io/refresh=hard', '--overwrite')
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        app = json.loads(k('get', 'application/' + name, '-n', 'argocd', '-o', 'json').stdout)
        status = app.get('status', {})
        if (status.get('sync', {}).get('status') == 'Synced' and status.get('health', {}).get('status') == 'Healthy' and
                (revision is None or status['sync'].get('revision') == revision)):
            try:
                actual = definition(name)
                if actual['fingerprint'] != deployment['fingerprint']:
                    raise ValueError('Serving definition is not the declared deployment.')
                resource = json.loads(k('get', 'deployment/search', '-n', name, '-o', 'json').stdout)
                observed = resource.get('status', {})
                if (observed.get('observedGeneration', 0) < resource['metadata']['generation'] or
                        observed.get('updatedReplicas') != 1 or observed.get('availableReplicas') != 1):
                    raise ValueError('Deployment has not rolled out.')
                answer = wait_correct_search(name, timeout_seconds=10)
                if answer.get('index') and answer['index'] != deployment['fields']['index']:
                    raise ValueError('API reports a different index.')
                elastic('/_security/role/' + name, 'PUT', {'indices': [{'names': [deployment['fields']['index']],
                         'privileges': ['read', 'view_index_metadata']}]})
                return {'state': 'verified', 'fingerprint': deployment['fingerprint'],
                        'git_revision': status['sync']['revision'], 'environment': name,
                        'verified_at': datetime.now(timezone.utc).isoformat(),
                        'seconds': round(time.monotonic() - started, 3), 'sample_ids': answer['ids'][:10]}
            except (AssertionError, ValueError, TimeoutError):
                pass
        time.sleep(2)
    raise TimeoutError('Argo/API verification did not complete for ' + name)


def preview(deployment):
    name = 'lab-delivery-run-' + str(deployment['build_run']) + '-' + deployment['fields']['index_recipe_sha256'][:8]
    revision = checkout()
    branch = 'preview/' + name + '-' + uuid.uuid4().hex[:8]
    existing = k('get', 'application/' + name, '-n', 'argocd', '-o', 'json', check=False)
    if existing.returncode:
        git(DESIRED, 'switch', '-c', branch)
        folder = LOCAL / 'previews' / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'search.yaml').write_text(rendered(deployment, name), encoding='utf-8', newline='\n')
        git(DESIRED, 'add', 'previews/' + name)
        git(DESIRED, 'commit', '-m', 'Create frozen release preview ' + name)
        revision = git(DESIRED, 'rev-parse', 'HEAD')
        git(DESIRED, 'push', 'origin', branch)
        git(DESIRED, 'switch', 'main')
        materialise(deployment)
        access(name, deployment)
        application(name, 'previews/' + name, revision,
                    (datetime.now(timezone.utc) + timedelta(days=3)).isoformat())
    else:
        revision = json.loads(existing.stdout)['spec']['source']['targetRevision']
        k('annotate', 'application/' + name, '-n', 'argocd',
          'lab/preview-expires-at=' + (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(), '--overwrite')
    verify(name, deployment, revision)
    return {'name': name, 'id': name, 'state': 'ready', 'source_sha': deployment['fields']['source_sha'],
            'release_id': deployment['fields']['dataset_release'], 'fingerprint': deployment['fingerprint']}


def remove_preview(name):
    if not name.startswith('lab-delivery-run-'):
        raise ValueError('Only delivery preview namespaces can be removed by this command.')
    app = k('get', 'application/' + name, '-n', 'argocd', '-o', 'json', check=False)
    if not app.returncode and json.loads(app.stdout)['metadata'].get('labels', {}).get('lab/delivery') != 'preview':
        raise ValueError('Application is not a delivery preview.')
    k('delete', 'application/' + name, '-n', 'argocd', '--ignore-not-found', '--wait=true', '--timeout=120s')
    k('delete', 'namespace/' + name, '--ignore-not-found', '--wait=true', '--timeout=120s')
    for path in ('/_security/user/', '/_security/role/'):
        elastic(path + name, 'DELETE')


def expire_previews():
    apps = json.loads(k('get', 'applications', '-n', 'argocd', '-l', 'lab/delivery=preview', '-o', 'json').stdout)['items']
    for app in apps:
        expiry = app['metadata']['annotations']['lab/preview-expires-at']
        if datetime.now(timezone.utc) >= datetime.fromisoformat(expiry):
            remove_preview(app['metadata']['name'])
