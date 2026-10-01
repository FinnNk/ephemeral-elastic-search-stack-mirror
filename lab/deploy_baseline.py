"""Build the lab API in Gitea and reconcile the frozen baseline through Argo CD."""
import json
import shutil
import time
from pathlib import Path

from common import ROOT, STATE, guard, k, record
from environments import build_record, define, git, provision_access, publish
from gitea import api

SOURCE = STATE / 'search-source'
APP = ROOT / 'lab/search-app'


def source_commit():
    assert (SOURCE / '.git').exists(), 'Run the platform research bootstrap first'
    assert not git('status', '--porcelain', cwd=SOURCE), 'Local search source has changes'
    git('switch', 'main', cwd=SOURCE)
    for name in ('app.py', 'telemetry.py', 'variants.py', 'search_filters.py', 'index.html',
                 'demo.py', 'test_app.py', 'test_demo.py', 'test_filters.py', 'requirements.lock', 'Dockerfile'):
        shutil.copy2(APP / name, SOURCE / name)
    shutil.copy2(APP / '.gitea/workflows/build.yaml', SOURCE / '.gitea/workflows/build.yaml')
    if git('status', '--porcelain', cwd=SOURCE):
        git('add', '.', cwd=SOURCE)
        git('commit', '-m', 'Build runnable UK retail search API', cwd=SOURCE)
        git('push', 'origin', 'main', cwd=SOURCE)
    return git('rev-parse', 'HEAD', cwd=SOURCE)


def successful_run(sha):
    deadline = time.monotonic() + 360
    while time.monotonic() < deadline:
        runs = api('/repos/elastic-agent/search-spike/actions/runs?limit=30')['workflow_runs']
        matching = [run for run in runs if run['head_sha'] == sha]
        if matching:
            run = matching[0]
            if run['status'] == 'completed':
                assert run['conclusion'] == 'success', f'Gitea build {run["id"]} failed'
                return build_record(run['id'])
        time.sleep(3)
    raise TimeoutError('Gitea did not complete the source build within six minutes')


def main():
    guard()
    assert (STATE / 'evidence/retail-release.json').exists(), 'Run lab/load_release.py first'
    assert not git('status', '--porcelain'), 'Local environment state has changes'
    sha = source_commit()
    build = successful_run(sha)
    manifest = json.loads((STATE / 'releases/retail-gb-10k-v1/manifest.json').read_text())
    name = 'retail-baseline'
    provision_access(name, 'retail-gb-10k-v1')
    definition = define(name, build['image'], 'retail-gb-10k-v1', manifest['sha256']['products.jsonl'])
    if git('status', '--porcelain'):
        publish('Deploy frozen UK retail baseline')
    k('wait', '--for=jsonpath={.status.health.status}=Healthy', 'application/' + name,
      '-n', 'argocd', '--timeout=180s')
    record('retail-deployment', {'build_run': build['run'], 'source_sha': sha,
        'image': build['image'], 'environment': name, 'fingerprint': definition['fingerprint'],
        'argo_health': 'Healthy'})
    print(json.dumps({'environment': name, 'source_sha': sha, 'image': build['image'],
        'fingerprint': definition['fingerprint'], 'argo_health': 'Healthy'}, indent=2))


if __name__ == '__main__':
    main()
