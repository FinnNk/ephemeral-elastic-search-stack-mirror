"""Create a named local administrator in Gitea and Argo CD for lab review."""
import base64
import http.client
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from common import KUBE, ROOT, STATE, guard, k
from gitea import api

sys.path.insert(0, str(STATE / 'python-libs'))
import bcrypt

USERNAME = 'finnnk'
CREDS = STATE / 'user-credentials.json'
ARGO_URL = 'http://127.0.0.1:31801'
GITEA_URL = 'http://127.0.0.1:31800'


def user_credentials():
    if CREDS.exists():
        data = json.loads(CREDS.read_text(encoding='utf-8'))
        assert data['username'] == USERNAME
        return data
    email = subprocess.check_output(
        ['git', '-c', 'safe.directory=' + str(ROOT).replace('\\', '/'), 'config', 'user.email'],
        cwd=ROOT, text=True, encoding='utf-8'
    ).strip()
    assert '@' in email
    data = {
        'username': USERNAME,
        'email': email,
        'gitea_password': secrets.token_urlsafe(32),
        'argocd_password': secrets.token_urlsafe(32),
    }
    CREDS.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return data


def gitea_user(data):
    try:
        existing = api('/users/' + USERNAME, identity='admin')
    except RuntimeError as error:
        if '404' not in str(error):
            raise
        existing = None
    if existing is None:
        api('/admin/users', 'POST', {
            'username': USERNAME,
            'email': data['email'],
            'full_name': 'Finn Newick',
            'password': data['gitea_password'],
            'must_change_password': False,
            'send_notify': False,
            'restricted': False,
        }, identity='admin')
    admin = api('/admin/users/' + USERNAME, 'PATCH', {
        'admin': True,
        'active': True,
        'prohibit_login': False,
        'restricted': False,
        'source_id': 0,
        'login_name': USERNAME,
    }, identity='admin')
    assert admin['is_admin'] and admin['login'] == USERNAME
    for name in ['ephemeral-elastic-search-stack', 'search-spike', 'environment-state']:
        path = '/repos/elastic-agent/' + name + '/collaborators/' + USERNAME
        api(path, 'PUT', {'permission': 'admin'})
        permission = api(path + '/permission')
        assert permission['permission'] in ('admin', 'owner'), (name, permission['permission'])
    auth = base64.b64encode((USERNAME + ':' + data['gitea_password']).encode()).decode()
    req = urllib.request.Request(GITEA_URL + '/api/v1/user', headers={'Authorization': 'Basic ' + auth})
    with urllib.request.urlopen(req, timeout=10) as response:
        signed_in = json.load(response)
    assert signed_in['login'] == USERNAME and signed_in['is_admin']
    print('Named Gitea site administrator and repository administrator verified.', flush=True)


def argocd_user(data):
    current_cm = json.loads(k('get', 'configmap/argocd-cm', '-n', 'argocd', '-o', 'json').stdout)
    current_params = json.loads(k('get', 'configmap/argocd-cmd-params-cm', '-n', 'argocd', '-o', 'json').stdout)
    needs_restart = (current_cm.get('data', {}).get('accounts.' + USERNAME) != 'login'
                     or current_params.get('data', {}).get('server.insecure') != 'true')
    k('patch', 'configmap/argocd-cm', '-n', 'argocd', '--type=merge', '-p',
      json.dumps({'data': {'accounts.' + USERNAME: 'login'}}))
    k('patch', 'configmap/argocd-rbac-cm', '-n', 'argocd', '--type=merge', '-p',
      json.dumps({'data': {'policy.csv': 'g, ' + USERNAME + ', role:admin\n'}}))
    current = json.loads(k('get', 'secret/argocd-secret', '-n', 'argocd', '-o', 'json').stdout)
    if 'accounts.' + USERNAME + '.password' not in current['data']:
        hashed = bcrypt.hashpw(data['argocd_password'].encode(), bcrypt.gensalt(rounds=12)).decode()
        secret_data = {
            'accounts.' + USERNAME + '.password': base64.b64encode(hashed.encode()).decode(),
            'accounts.' + USERNAME + '.passwordMtime': base64.b64encode(
                datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ').encode()
            ).decode(),
        }
        k('patch', 'secret/argocd-secret', '-n', 'argocd', '--type=merge', '-p', json.dumps({'data': secret_data}))
    k('patch', 'configmap/argocd-cmd-params-cm', '-n', 'argocd', '--type=merge', '-p',
      json.dumps({'data': {'server.insecure': 'true'}}))
    if needs_restart:
        k('rollout', 'restart', 'deployment/argocd-server', '-n', 'argocd')
        k('rollout', 'status', 'deployment/argocd-server', '-n', 'argocd', '--timeout=120s')


def port_forward():
    try:
        with urllib.request.urlopen(ARGO_URL, timeout=2) as response:
            if response.status == 200:
                return
    except (OSError, http.client.HTTPException):
        pass
    log = open(STATE / 'argocd-forward.log', 'a', encoding='utf-8')
    process = subprocess.Popen(
        KUBE + ['-n', 'argocd', 'port-forward', 'svc/argocd-server', '31801:80', '--address', '127.0.0.1'],
        stdout=log, stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
    (STATE / 'argocd-forward.pid').write_text(str(process.pid), encoding='utf-8')
    for _ in range(30):
        try:
            with urllib.request.urlopen(ARGO_URL, timeout=2) as response:
                assert response.status == 200
                return
        except (OSError, http.client.HTTPException):
            time.sleep(1)
    raise TimeoutError('Argo CD port forward did not become ready')


def verify_argocd(data):
    req = urllib.request.Request(
        ARGO_URL + '/api/v1/session',
        data=json.dumps({'username': USERNAME, 'password': data['argocd_password']}).encode(),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            token = json.load(response)['token']
    except urllib.error.HTTPError as error:
        if error.code == 401:
            print('Existing Argo CD password was preserved; sign in with the password you set in Argo CD.', flush=True)
            return
        raise
    req = urllib.request.Request(ARGO_URL + '/api/v1/applications', headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=10) as response:
        names = {item['metadata']['name'] for item in json.load(response).get('items', [])}
    assert {'spike-baseline', 'spike-candidate-retained'} <= names, names
    print('Named Argo CD administrator login and both search applications verified.', flush=True)


if __name__ == '__main__':
    guard()
    credentials = user_credentials()
    gitea_user(credentials)
    argocd_user(credentials)
    port_forward()
    verify_argocd(credentials)
    print('Gitea:', GITEA_URL + '/user/login', flush=True)
    print('Argo CD:', ARGO_URL, flush=True)
    print('Local credentials:', CREDS, flush=True)
