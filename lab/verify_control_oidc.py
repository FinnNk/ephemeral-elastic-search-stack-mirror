"""Exercise real control UI callbacks with disposable administrator and reader identities."""
import json
import secrets
from urllib import parse, request, error

from common import STATE, guard, k
from install_oidc import admin_token, api
from verify_gitea_oidc import browser, load
from verify_oidc import LoginForm

URL = 'https://control.localhost:34443'


def main():
    guard()
    token = admin_token()
    groups = {group['name']: group['id'] for group in api('/admin/realms/relevance-lab/groups', token=token)}
    users = []
    results = {}
    try:
        for role, group in [('administrator', 'lab-admins'), ('reader', 'lab-readers')]:
            name = 'control-' + role + '-' + secrets.token_hex(4)
            password = secrets.token_urlsafe(24)
            api('/admin/realms/relevance-lab/users', 'POST', {'username': name, 'enabled': True,
                'firstName': 'Control', 'lastName': 'Probe', 'email': name + '@lab.invalid', 'emailVerified': True,
                'credentials': [{'type': 'password', 'value': password, 'temporary': False}]}, token)
            user = api('/admin/realms/relevance-lab/users?' + parse.urlencode({'username': name, 'exact': 'true'}), token=token)[0]
            users.append(user['id'])
            api('/admin/realms/relevance-lab/users/' + user['id'] + '/groups/' + groups[group], 'PUT', token=token)
            client = browser()
            url, html = load(client, URL + '/oauth2/start?rd=/')
            form = LoginForm(); form.feed(html)
            if not form.action:
                raise ValueError('Expected identity-provider login form.')
            load(client, form.action, {**form.fields, 'username': name, 'password': password, 'credentialId': ''})
            url, payload = load(client, URL + '/api/me')
            identity = json.loads(payload)
            assert identity['subject'] == user['id'] and identity['username'] == name
            assert identity['is_admin'] == (role == 'administrator')
            _, payload = load(client, URL + '/api/environments')
            assert isinstance(json.loads(payload), list)
            if role == 'reader':
                for method, path in [('POST', '/api/environments'), ('DELETE', '/api/environments/oidc-probe')]:
                    req = request.Request(URL + path, method=method, data=b'{}', headers={
                        'Content-Type': 'application/json', 'X-Lab-Intent': '1'})
                    try:
                        client.open(req, timeout=20)
                    except error.HTTPError as failure:
                        assert failure.code == 403
                    else:
                        raise ValueError('Reader mutation was not denied.')
            results[role] = {'callback': 'passed', 'signed_subject': 'matched', 'read': 'passed'}
        results['reader']['mutations'] = 'forbidden'
        results['anonymous'] = 'redirects_to_sign_in'
        url, _ = load(browser(), URL + '/api/me')
        assert parse.urlparse(url).hostname == 'identity.localhost'
        script = "import urllib.request,urllib.error; r=urllib.request.Request('http://127.0.0.1:18082/api/me',headers={'Host':'control.localhost:34443','X-Forwarded-User':'admin','X-Forwarded-Groups':'lab-admins'});\ntry: urllib.request.urlopen(r); raise AssertionError('Accepted spoof')\nexcept urllib.error.HTTPError as e: assert e.code==401; print('rejected')"
        assert k('exec', 'deployment/lab-control', '-n', 'lab-control', '-c', 'api', '--', 'python', '-c', script).stdout.strip() == 'rejected'
        results['spoofed_headers'] = 'rejected'
        k('exec', 'deployment/lab-control', '-n', 'lab-control', '-c', 'api', '--', 'python', 'lab/control-runtime/smoke.py')
        results['service_credentials'] = 'passed'
        (STATE / 'oidc/control-verification.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(results))
    finally:
        for user in users:
            api('/admin/realms/relevance-lab/users/' + user, 'DELETE', token=token)


if __name__ == '__main__':
    main()
