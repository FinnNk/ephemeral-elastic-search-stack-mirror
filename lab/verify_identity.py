"""Exercise distinct Gitea owners and administrator cleanup through the local API."""
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, 'research/platform-spike')
from common import STATE, record

BASE = 'http://localhost:18082/api'


def client(username, password):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    body = json.dumps({'username': username, 'password': password}).encode()
    request = urllib.request.Request(BASE + '/login', data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-Lab-Intent': '1'})
    with opener.open(request, timeout=15) as response:
        payload = response.read()
        assert password.encode() not in payload and b'lab_session' not in payload
        assert 'HttpOnly' in response.headers['Set-Cookie']
        assert 'SameSite=Strict' in response.headers['Set-Cookie']
        identity = json.loads(payload)
    return opener, identity


def call(opener, path, method='GET', body=None):
    payload = None if body is None else json.dumps(body).encode()
    headers = {'X-Lab-Intent': '1'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(BASE + path, data=payload, method=method, headers=headers)
    with opener.open(request, timeout=240) as response:
        return json.load(response)


def denied(opener, path, method='GET', body=None):
    try:
        call(opener, path, method, body)
    except urllib.error.HTTPError as error:
        return error.code == 403
    return False


def main():
    credentials = json.loads((STATE / 'credentials.json').read_text())
    run = json.loads((STATE / 'evidence/retail-deployment.json').read_text())['build_run']
    agent, agent_identity = client(credentials['agent']['username'], credentials['agent']['password'])
    admin, admin_identity = client(credentials['username'], credentials['password'])
    assert not agent_identity['is_admin'] and admin_identity['is_admin']
    created = []
    try:
        first = call(agent, '/environments', 'POST', {'name': 'lab-agent-identity', 'build_run': run})
        created.append(first)
        second = call(admin, '/environments', 'POST', {'name': 'lab-admin-identity', 'build_run': run})
        created.append(second)
        assert first['state'] == second['state'] == 'ready'
        assert first['owner'] == agent_identity['username'] and second['owner'] == admin_identity['username']
        assert denied(agent, '/environments/' + second['id'])
        assert denied(agent, '/environments/' + second['id'], 'DELETE', {})
        assert call(admin, '/environments/' + first['id'])['owner'] == agent_identity['username']
        result = {'agent_username': agent_identity['username'], 'admin_username': admin_identity['username'],
                  'agent_admin': False, 'admin_admin': True, 'distinct_owners': True,
                  'cross_owner_read_denied': True, 'cross_owner_delete_denied': True,
                  'cookie_httponly_samesite': True, 'credentials_absent_from_login_body': True}
    finally:
        states = []
        for row in reversed(created):
            states.append(call(admin, '/environments/' + row['id'], 'DELETE', {})['state'])
    assert states == ['deleted', 'deleted']
    result['final_states'] = states
    record('identity-walkthrough', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
