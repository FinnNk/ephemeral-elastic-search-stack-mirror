"""Build a Gitea PR candidate and pin it beside the frozen retail baseline."""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import ROOT, STATE, guard, k, record
from environments import REPO, define, git, provision_access, publish
from gitea import api
from measure import search
from deploy_baseline import successful_run

SOURCE = STATE / 'search-source'
BRANCH = 'retail-trainers'
NAME = 'retail-candidate'


def candidate_source():
    assert not git('status', '--porcelain', cwd=SOURCE), 'Search source has local changes'
    git('switch', 'main', cwd=SOURCE)
    baseline = json.loads((STATE / 'evidence/retail-deployment.json').read_text())
    assert git('rev-parse', 'HEAD', cwd=SOURCE) == baseline['source_sha'], 'Baseline source moved'
    if not git('branch', '--list', BRANCH, cwd=SOURCE):
        git('switch', '-c', BRANCH, cwd=SOURCE)
        # Git on Windows checks out the project patch with CRLF. git apply needs LF.
        patch = STATE / 'retail-trainers.patch'
        patch.write_bytes((ROOT / 'lab/candidate/trainers.patch').read_text(encoding='utf-8').encode())
        git('apply', '--unidiff-zero', '--check', str(patch), cwd=SOURCE)
        git('apply', '--unidiff-zero', str(patch), cwd=SOURCE)
        result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-p', 'test_*.py', '-v'], cwd=SOURCE,
                                text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        git('add', 'app.py', 'test_app.py', cwd=SOURCE)
        git('commit', '-m', 'Understand trainers as running shoes', cwd=SOURCE)
        git('push', '--set-upstream', 'origin', BRANCH, cwd=SOURCE)
    else:
        git('switch', BRANCH, cwd=SOURCE)
        assert not git('status', '--porcelain', cwd=SOURCE)
    sha = git('rev-parse', 'HEAD', cwd=SOURCE)
    pulls = api('/repos/elastic-agent/search-spike/pulls?state=open')
    matching = [pr for pr in pulls if pr['head']['ref'] == BRANCH]
    if matching:
        pr = matching[0]
    else:
        pr = api('/repos/elastic-agent/search-spike/pulls', 'POST', {
            'base': 'main', 'head': BRANCH,
            'title': 'Compare trainers query understanding with the retail baseline',
            'body': 'Synthetic candidate: the API expands trainers to running shoes. The frozen retail catalogue and shared Elasticsearch index are unchanged.',
        })
    assert pr['head']['sha'] == sha
    return sha, pr['html_url']


def wait_healthy(name):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = k('get', 'application/' + name, '-n', 'argocd', '-o', 'json', check=False)
        if result.returncode == 0:
            status = json.loads(result.stdout).get('status', {})
            if status.get('sync', {}).get('status') == 'Synced' and status.get('health', {}).get('status') == 'Healthy':
                return
        time.sleep(2)
    raise TimeoutError(f'Argo CD did not make {name} Synced/Healthy')


def main():
    guard()
    assert not git('status', '--porcelain'), 'Environment state has local changes'
    baseline = json.loads((REPO / 'environments/retail-baseline.json').read_text())
    assert baseline['index'] == 'retail-gb-10k-v1'
    sha, pr_url = candidate_source()
    build = successful_run(sha)
    provision_access(NAME, baseline['index'])
    candidate = define(NAME, build['image'], baseline['index'], baseline['dataset_sha256'])
    assert candidate['dataset_sha256'] == baseline['dataset_sha256']
    if git('status', '--porcelain'):
        publish('Deploy trainers query candidate')
    wait_healthy(NAME)
    before = search('retail-baseline', 'trainers')
    after = search(NAME, 'trainers')
    assert before is not None and after is not None
    assert before['ids'] == [] and len(after['ids']) >= 10, (before['ids'], after['ids'])
    evidence = {'source_pr': pr_url, 'source_sha': sha, 'build_run': build['run'],
        'baseline_fingerprint': baseline['fingerprint'], 'candidate_fingerprint': candidate['fingerprint'],
        'candidate_image': build['image'], 'shared_index': baseline['index'],
        'dataset_sha256': baseline['dataset_sha256'], 'argo_health': 'Healthy',
        'trainers_baseline_count': before['total'], 'trainers_candidate_count': after['total']}
    record('retail-candidate', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
