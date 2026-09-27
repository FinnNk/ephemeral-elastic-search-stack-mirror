"""Build and deploy a deliberately different API ranking over the frozen index."""
import json
import subprocess
import sys

from common import ROOT, STATE, guard, record
from environments import REPO, define, git, provision_access, publish
from gitea import api
from search_probe import search
from deploy_baseline import successful_run
from deploy_candidate import wait_healthy

SOURCE = STATE / 'search-source'
BRANCH = 'retail-price-rank'
NAME = 'retail-price-rank'


def candidate_source():
    assert not git('status', '--porcelain', cwd=SOURCE), 'Search source has local changes'
    git('switch', 'main', cwd=SOURCE)
    baseline = json.loads((STATE / 'evidence/retail-deployment.json').read_text())
    assert git('rev-parse', 'HEAD', cwd=SOURCE) == baseline['source_sha']
    if not git('branch', '--list', BRANCH, cwd=SOURCE):
        git('switch', '-c', BRANCH, cwd=SOURCE)
        patch = STATE / 'retail-price-rank.patch'
        patch.write_bytes((ROOT / 'lab/rank-candidate/price-rank.patch').read_text(encoding='utf-8').encode())
        git('apply', '--unidiff-zero', '--check', str(patch), cwd=SOURCE)
        git('apply', '--unidiff-zero', str(patch), cwd=SOURCE)
        result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-p', 'test_*.py', '-v'],
                                cwd=SOURCE, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        git('add', 'app.py', 'test_app.py', cwd=SOURCE)
        git('commit', '-m', 'Compare price order with baseline relevance', cwd=SOURCE)
        git('push', '--set-upstream', 'origin', BRANCH, cwd=SOURCE)
    else:
        git('switch', BRANCH, cwd=SOURCE)
        assert not git('status', '--porcelain', cwd=SOURCE)
    sha = git('rev-parse', 'HEAD', cwd=SOURCE)
    pulls = api('/repos/elastic-agent/search-spike/pulls?state=open')
    matching = [pr for pr in pulls if pr['head']['ref'] == BRANCH]
    pr = matching[0] if matching else api('/repos/elastic-agent/search-spike/pulls', 'POST', {
        'base': 'main', 'head': BRANCH,
        'title': 'Compare price ranking with the frozen retail baseline',
        'body': 'Synthetic ranking experiment: order matching products by price. The frozen catalogue and shared Elasticsearch index are unchanged.',
    })
    assert pr['head']['sha'] == sha
    return sha, pr['html_url']


def main():
    guard()
    assert not git('status', '--porcelain'), 'Environment state has local changes'
    baseline = json.loads((REPO / 'environments/retail-baseline.json').read_text())
    sha, pr_url = candidate_source()
    build = successful_run(sha)
    provision_access(NAME, baseline['index'])
    candidate = define(NAME, build['image'], baseline['index'], baseline['dataset_sha256'])
    if git('status', '--porcelain'):
        publish('Deploy price ranking candidate')
    wait_healthy(NAME)
    before = search('retail-baseline', 'cotton shirt')
    after = search(NAME, 'cotton shirt')
    assert before and after and before['ids'][:10] != after['ids'][:10]
    evidence = {'source_pr': pr_url, 'source_sha': sha, 'build_run': build['run'],
        'baseline_fingerprint': baseline['fingerprint'], 'candidate_fingerprint': candidate['fingerprint'],
        'candidate_image': build['image'], 'shared_index': baseline['index'],
        'dataset_sha256': baseline['dataset_sha256'], 'argo_health': 'Healthy',
        'sample_query': 'cotton shirt', 'sample_top_10_changed': True}
    record('retail-price-rank', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
