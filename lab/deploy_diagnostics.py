"""Build two diagnostic API variants in Gitea and deploy over the frozen index."""
import json
import shutil
import subprocess
import sys

sys.path.insert(0, 'research/platform-spike')
from common import ROOT, STATE, guard, record
from environments import REPO, define, git, provision_access, publish
from gitea import api
from measure import search
from deploy_baseline import successful_run
from deploy_candidate import wait_healthy

SOURCE = STATE / 'search-source'
DIAGNOSTIC_BRANCH = 'retail-diagnostics'
REWRITE_BRANCH = 'retail-diagnostics-trainers'


def source(branch, base, message, title, body):
    assert not git('status', '--porcelain', cwd=SOURCE)
    git('switch', base, cwd=SOURCE)
    if not git('branch', '--list', branch, cwd=SOURCE):
        git('switch', '-c', branch, cwd=SOURCE)
        if branch == DIAGNOSTIC_BRANCH:
            for name in ('app.py', 'test_app.py'):
                shutil.copy2(ROOT / 'lab/search-app' / name, SOURCE / name)
        else:
            patch = STATE / 'retail-diagnostic-trainers.patch'
            patch.write_bytes((ROOT / 'lab/diagnostic-candidate/trainers.patch').read_text(encoding='utf-8').encode())
            git('apply', '--unidiff-zero', '--check', str(patch), cwd=SOURCE)
            git('apply', '--unidiff-zero', str(patch), cwd=SOURCE)
            shutil.copy2(ROOT / 'lab/diagnostic-candidate/test_rewrite.py', SOURCE / 'test_rewrite.py')
        result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-p', 'test_*.py', '-v'],
                                cwd=SOURCE, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        git('add', 'app.py', 'test_app.py', cwd=SOURCE)
        if branch == REWRITE_BRANCH:
            git('add', 'test_rewrite.py', cwd=SOURCE)
        git('commit', '-m', message, cwd=SOURCE)
        git('push', '--set-upstream', 'origin', branch, cwd=SOURCE)
    else:
        git('switch', branch, cwd=SOURCE)
        assert not git('status', '--porcelain', cwd=SOURCE)
    sha = git('rev-parse', 'HEAD', cwd=SOURCE)
    pulls = api('/repos/elastic-agent/search-spike/pulls?state=open')
    matching = [pr for pr in pulls if pr['head']['ref'] == branch]
    pr = matching[0] if matching else api('/repos/elastic-agent/search-spike/pulls', 'POST', {
        'base': base, 'head': branch, 'title': title, 'body': body})
    assert pr['head']['sha'] == sha
    return sha, pr['html_url']


def deploy(name, sha, source_pr, baseline):
    build = successful_run(sha)
    provision_access(name, baseline['index'])
    definition = define(name, build['image'], baseline['index'], baseline['dataset_sha256'])
    if git('status', '--porcelain'):
        publish('Deploy ' + name)
    wait_healthy(name)
    return {'name': name, 'source_sha': sha, 'source_pr': source_pr,
            'build_run': build['run'], 'image': build['image'],
            'fingerprint': definition['fingerprint']}


def main():
    guard()
    assert not git('status', '--porcelain')
    baseline = json.loads((REPO / 'environments/retail-baseline.json').read_text())
    baseline_source = json.loads((STATE / 'evidence/retail-deployment.json').read_text())['source_sha']
    assert not git('status', '--porcelain', cwd=SOURCE)
    git('switch', 'main', cwd=SOURCE)
    assert git('rev-parse', 'HEAD', cwd=SOURCE) == baseline_source
    diagnostic_sha, diagnostic_pr = source(
        DIAGNOSTIC_BRANCH, 'main', 'Capture correlated API search diagnostics',
        'Add opt-in diagnostic records without changing search results',
        'Adds a versioned, correlation-ID-linked record of query understanding and Elasticsearch retrieval. Normal responses and ranking remain stable.')
    rewrite_sha, rewrite_pr = source(
        REWRITE_BRANCH, DIAGNOSTIC_BRANCH, 'Name the trainers query rewrite',
        'Show the trainers rewrite in API-stage diagnostics',
        'Builds on the diagnostic source branch. The public API rewrites trainers to running shoes over the same frozen index.')
    first = deploy('retail-diagnostics', diagnostic_sha, diagnostic_pr, baseline)
    second = deploy('retail-diagnostics-trainers', rewrite_sha, rewrite_pr, baseline)
    original = search('retail-baseline', 'trainers')
    rewritten = search('retail-diagnostics-trainers', 'trainers')
    assert original is not None and rewritten is not None
    assert original['ids'] == [] and len(rewritten['ids']) >= 10
    evidence = {'baseline_fingerprint': baseline['fingerprint'], 'shared_index': baseline['index'],
                'dataset_sha256': baseline['dataset_sha256'], 'diagnostic': first, 'rewrite': second}
    record('retail-diagnostics-deployment', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
