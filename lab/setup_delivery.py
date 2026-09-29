"""Seed isolated delivery demo repositories and a repository-scoped Actions runner."""
import json
import shutil
import secrets
from common import ROOT, STATE, apply, guard, k
from gitea import api
from delivery_provider import SOURCE, DESIRED, endpoint, ensure_repo, git
from load_release import BASELINE_MAPPING, INDEXER_IMAGE
from load_million_release import MAPPING as MILLION_MAPPING
from nexus import REGISTRY, credentials
from delivery.ci.release import canonical, digest
from keyvault import floci_forward, vault_request


def configure_ci():
    value = json.loads((STATE / 'credentials.json').read_text())
    if 'delivery_read_token' not in value:
        value['delivery_read_token'] = api('/users/elastic-agent/tokens', 'POST',
            {'name': 'delivery-source-read', 'scopes': ['read:repository']})['sha1']
        (STATE / 'credentials.json').write_text(json.dumps(value), encoding='utf-8')
    publisher = credentials()['publisher']
    for name, data in {'SOURCE_USER': 'elastic-agent', 'SOURCE_TOKEN': value['delivery_read_token'],
                       'NEXUS_USER': publisher['username'], 'NEXUS_PASSWORD': publisher['password']}.items():
        api(endpoint(SOURCE, '/actions/secrets/' + name), 'PUT', {'data': data})
    existing = {row['name'] for row in api(endpoint(SOURCE, '/actions/variables'))}
    for name, data in {'SOURCE_BASE_URL': 'https://gitea-internal.lab-ingress.svc.cluster.local',
                       'RELEASE_REGISTRY': REGISTRY,
                       'RELEASE_ARTIFACT_URL': 'http://nexus.platform.svc.cluster.local:8081/repository/lab-releases',
                       'LAB_VARIANT_POLICY_SHA256': digest((ROOT / 'lab/delivery/policies/variant-merge-v1.json').read_bytes()),
                       'LAB_VARIANT_GATE_CODE_SHA256': digest((ROOT / 'lab/variant_gate.py').read_bytes())}.items():
        api(endpoint(SOURCE, '/actions/variables/' + name), 'PUT' if name in existing else 'POST', {'value': data})
    with floci_forward() as base:
        for name in ('LAB_VARIANT_EVIDENCE_KEY', 'LAB_VARIANT_APPROVAL_KEY'):
            remote = 'lab-variant-gate-' + name.lower().replace('_', '-')
            record = vault_request(base, remote)
            if record is None:
                vault_request(base, remote, 'PUT', secrets.token_urlsafe(48))
                record = vault_request(base, remote)
            api(endpoint(SOURCE, '/actions/secrets/' + name), 'PUT', {'data': record['value']})
    token = api(endpoint(SOURCE, '/actions/runners/registration-token'), 'POST')['token']
    apply({'apiVersion': 'v1', 'kind': 'Secret',
           'metadata': {'name': 'delivery-registration', 'namespace': 'platform'},
           'stringData': {'token': token}})
    from https_ingress import certificate
    _, _, ca_path = certificate()
    apply({'apiVersion': 'v1', 'kind': 'ConfigMap',
           'metadata': {'name': 'delivery-runner-ca', 'namespace': 'platform'},
           'data': {'root.pem': ca_path.read_text(encoding='utf-8')}})
    runner = (ROOT / 'lab/delivery/bootstrap/runner.yaml').read_text(encoding='utf-8')
    path = STATE / 'delivery-runner.yaml'
    path.write_text(runner, encoding='utf-8', newline='\n')
    k('apply', '-f', str(path))
    k('-n', 'platform', 'rollout', 'status', 'deployment/delivery-runner', '--timeout=120s')


def seed_source(path):
    if not api(endpoint(SOURCE))['empty']:
        print('Source already seeded; publish further changes through a branch and PR.')
        return
    for name in ('app.py', 'telemetry.py', 'variants.py', 'requirements.lock',
                 'index.html', 'test_app.py', 'Dockerfile'):
        target = path / 'app' / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((ROOT / 'lab/search-app' / name).read_bytes().replace(b'\r\n', b'\n'))
    dockerfile = path / 'app/Dockerfile'
    dockerfile.write_text(dockerfile.read_text().replace('python:3.13.7-alpine3.22', INDEXER_IMAGE),
                          encoding='utf-8', newline='\n')
    shutil.copytree(ROOT / 'lab/delivery/ci', path / 'ci', ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
    shutil.copyfile(ROOT / 'lab/variant_gate.py', path / 'ci/variant_gate.py')
    shutil.copytree(ROOT / 'lab/delivery/bootstrap/chart', path / 'chart', dirs_exist_ok=True)
    chart = path / 'chart/templates/environment.yaml'
    chart.write_text(chart.read_text().replace('name: registry-read', 'name: nexus-read'),
                     encoding='utf-8', newline='\n')
    (path / '.github/workflows').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'lab/delivery/workflows/release.yaml', path / '.github/workflows/release.yaml')
    (path / 'contracts').mkdir(exist_ok=True)
    (path / 'gate').mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'lab/delivery/policies/variant-merge-v1.json',
                    path / 'gate/policy.json')
    worker = (ROOT / 'lab/index_job.py').read_text(encoding='utf-8').encode()
    contract = {'engine_version': '9.5.4', 'definitions': [BASELINE_MAPPING, MILLION_MAPPING],
                'indexer_image': INDEXER_IMAGE, 'indexer_source_sha256': digest(worker)}
    (path / 'contracts/index.json').write_bytes(canonical(contract))
    (path / 'contracts/indexer.py').write_bytes(worker)
    (path / '.gitignore').write_text('__pycache__/\n.docker-ci/\nimage-metadata.json\n', encoding='utf-8')
    (path / 'README.md').write_text('# Search delivery demonstration\n\nSynthetic search API; immutable Nexus releases. This is a fixture repository for the lab reference CI/CD.\n', encoding='utf-8')
    git(SOURCE, 'add', '.')
    git(SOURCE, 'commit', '-m', 'Seed portable search release workflow')
    git(SOURCE, 'push', '-u', 'origin', 'main')


def main():
    guard()
    source = ensure_repo(SOURCE, actions=True)
    ensure_repo(DESIRED)
    configure_ci()
    seed_source(source)
    print('Delivery repositories and portable workflow ready. Source SHA: ' + git(SOURCE, 'rev-parse', 'HEAD'))


if __name__ == '__main__':
    main()
