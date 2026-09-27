"""Gitea-specific repository, run and PR adapter for the local delivery reference."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, 'research/platform-spike')
from common import STATE
from gitea import api

SOURCE = 'delivery-source'
DESIRED = 'delivery-state'
OWNER = 'elastic-agent'


def endpoint(repo, suffix=''):
    if repo not in (SOURCE, DESIRED):
        raise ValueError('Delivery adapter is limited to the two demonstration repositories.')
    return '/repos/' + OWNER + '/' + repo + suffix


def git(repo, *args):
    path = STATE / repo
    user = json.loads((STATE / 'credentials.json').read_text())['agent']
    auth = base64.b64encode((user['username'] + ':' + user['password']).encode()).decode()
    env = os.environ.copy()
    env.update({'GIT_CONFIG_COUNT': '2', 'GIT_CONFIG_KEY_0': 'http.extraHeader',
                'GIT_CONFIG_VALUE_0': 'Authorization: Basic ' + auth,
                'GIT_CONFIG_KEY_1': 'credential.helper', 'GIT_CONFIG_VALUE_1': ''})
    result = subprocess.run(['git', '-c', 'safe.directory=' + str(path).replace('\\', '/'),
        '-c', 'user.name=elastic-agent', '-c', 'user.email=elastic-agent@lab.invalid',
        '-C', str(path), *args], env=env, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stderr.replace(auth, '[redacted]')[-1600:])
    return result.stdout.strip()


def ensure_repo(repo, actions=False):
    existing = api('/user/repos?limit=100')
    if not any(row['name'] == repo for row in existing):
        api('/user/repos', 'POST', {'name': repo, 'private': True,
                                   'default_branch': 'main', 'auto_init': False})
    api(endpoint(repo), 'PATCH', {'has_actions': actions, 'allow_merge_commits': True})
    api(endpoint(repo, '/collaborators/finnnk'), 'PUT', {'permission': 'admin'})
    path = STATE / repo
    if not (path / '.git').exists():
        path.mkdir(exist_ok=True)
        git(repo, 'init', '-b', 'main')
        git(repo, 'remote', 'add', 'origin', 'http://127.0.0.1:31800/' + OWNER + '/' + repo + '.git')
    return path


def pull_request(repo, branch, title, body):
    pulls = api(endpoint(repo, '/pulls?state=open&limit=100'))
    existing = next((row for row in pulls if row['head']['ref'] == branch), None)
    return existing or api(endpoint(repo, '/pulls'), 'POST',
        {'head': branch, 'base': 'main', 'title': title, 'body': body})


def runs(sha):
    return [row for row in api(endpoint(SOURCE, '/actions/runs?limit=50'))['workflow_runs']
            if row['head_sha'] == sha]


def wait_run(sha, timeout=900, event=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matching = [row for row in runs(sha) if event is None or row['event'] == event]
        if matching:
            run = max(matching, key=lambda row: row['id'])
            if run['status'] == 'completed':
                return run
        time.sleep(3)
    raise TimeoutError('No completed delivery CI run for ' + sha)


def merge_demo(repo, number, sha):
    """Merge a fixture PR only. Project implementation repositories are excluded."""
    pr = api(endpoint(repo, '/pulls/' + str(number)))
    if pr['head']['sha'] != sha:
        raise ValueError('Demo PR head changed before merge.')
    api(endpoint(repo, '/pulls/' + str(number) + '/merge'), 'POST',
        {'Do': 'merge', 'head_commit_id': sha, 'delete_branch_after_merge': False})
    return api(endpoint(repo, '/pulls/' + str(number)))
