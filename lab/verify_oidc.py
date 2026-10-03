"""Verify real OIDC callbacks and permissions with disposable named users."""
from html.parser import HTMLParser
import http.cookiejar
import json
import secrets
import ssl
from urllib import request, parse, error

from common import STATE, k
from install_oidc import api, admin_token, ISSUER, STATE_DIR


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}
        self.inside = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form' and attrs.get('id') == 'kc-form-login':
            self.action = attrs['action']
            self.inside = True
        if self.inside and tag == 'input' and attrs.get('type') == 'hidden' and attrs.get('name'):
            self.fields[attrs['name']] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.inside = False


def login(start, name, password):
    cookies = http.cookiejar.CookieJar()
    context = ssl.create_default_context(cafile=str(STATE / 'https-ingress/root.pem'))
    browser = request.build_opener(request.HTTPSHandler(context=context), request.HTTPCookieProcessor(cookies))
    with browser.open(start, timeout=30) as response:
        form = LoginForm()
        form.feed(response.read().decode())
    if not form.action:
        raise ValueError('OIDC redirect did not reach a Keycloak login form.')
    fields = {**form.fields, 'username': name, 'password': password, 'credentialId': ''}
    with browser.open(request.Request(form.action, data=parse.urlencode(fields).encode()), timeout=30) as response:
        response.read()
        if parse.urlparse(response.geturl()).hostname == 'identity.localhost':
            raise ValueError('Login did not complete the application callback.')
    return browser


def check(browser, url, expected, body=None):
    req = request.Request(url, data=None if body is None else json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json'})
    try:
        with browser.open(req, timeout=30) as response:
            code = response.status
            result = response.read()
    except error.HTTPError as exc:
        code, result = exc.code, exc.read()
    if code != expected:
        raise ValueError('Unexpected HTTP status at ' + parse.urlparse(url).path + ': ' + str(code) + ' ' + result[:120].decode(errors='replace'))
    return json.loads(result) if result else None


def main():
    token = admin_token()
    groups = {g['name']: g['id'] for g in api('/admin/realms/relevance-lab/groups', token=token)}
    users = []
    clients = []
    file = STATE_DIR / 'wrong-audience-kubeconfig.json'
    results = {'issuer': ISSUER, 'scope': 'disposable users, real authorization-code callbacks and live permissions', 'checks': {}}
    try:
        for suffix, group in [('admin', 'lab-admins'), ('reader', 'lab-readers'), ('unassigned', None)]:
            name = 'oidc-probe-' + suffix + '-' + secrets.token_hex(3)
            password = secrets.token_urlsafe(24)
            api('/admin/realms/relevance-lab/users', 'POST', {'username': name, 'enabled': True,
                'firstName': 'OIDC', 'lastName': 'Probe', 'email': name + '@lab.invalid', 'emailVerified': True,
                'credentials': [{'type': 'password', 'value': password, 'temporary': False}]}, token)
            user = api('/admin/realms/relevance-lab/users?' + parse.urlencode({'username': name, 'exact': 'true'}), token=token)[0]
            users.append(user['id'])
            if group:
                api('/admin/realms/relevance-lab/users/' + user['id'] + '/groups/' + groups[group], 'PUT', token=token)
            headlamp = login('https://headlamp.localhost:34443/oidc?cluster=relevance-lab', name, password)
            namespaces = check(headlamp, 'https://headlamp.localhost:34443/clusters/relevance-lab/api/v1/namespaces', 200 if group else 403)
            if group:
                assert namespaces['kind'] == 'NamespaceList'
            check(headlamp, 'https://headlamp.localhost:34443/clusters/relevance-lab/api/v1/namespaces/default/secrets', 200 if suffix == 'admin' else 403)
            access = check(headlamp, 'https://headlamp.localhost:34443/clusters/relevance-lab/apis/authorization.k8s.io/v1/selfsubjectaccessreviews', 201,
                {'apiVersion': 'authorization.k8s.io/v1', 'kind': 'SelfSubjectAccessReview',
                 'spec': {'resourceAttributes': {'namespace': 'default', 'verb': 'create', 'resource': 'configmaps'}}})
            assert access['status']['allowed'] == (suffix == 'admin')
            argo = login('https://argocd.localhost:34443/auth/login?return_url=https%3A%2F%2Fargocd.localhost%3A34443%2F', name, password)
            identity = check(argo, 'https://argocd.localhost:34443/api/v1/session/userinfo', 200)
            assert identity['loggedIn']
            assert group in identity['groups'] if group else not identity.get('groups')
            applications = check(argo, 'https://argocd.localhost:34443/api/v1/applications', 200)
            if not group:
                assert not applications.get('items')
            permission = check(argo, 'https://argocd.localhost:34443/api/v1/account/can-i/applications/sync/default%2Foidc-permission-probe', 200)
            assert permission['value'] == ('yes' if suffix == 'admin' else 'no'), permission
            results['checks'][suffix] = {'headlamp_callback': True, 'namespace_listing_allowed': bool(group),
                'secrets_read_allowed': suffix == 'admin', 'configmap_create_allowed': suffix == 'admin',
                'argocd_callback': True, 'argocd_group': group, 'argocd_sync_allowed': suffix == 'admin'}
        client_id = 'oidc-wrong-audience-' + secrets.token_hex(3)
        api('/admin/realms/relevance-lab/clients', 'POST', {'clientId': client_id, 'protocol': 'openid-connect',
            'publicClient': True, 'directAccessGrantsEnabled': True, 'standardFlowEnabled': False}, token)
        client = api('/admin/realms/relevance-lab/clients?' + parse.urlencode({'clientId': client_id}), token=token)[0]
        clients.append(client['id'])
        wrong = api('/realms/relevance-lab/protocol/openid-connect/token', 'POST',
            form={'grant_type': 'password', 'client_id': client_id, 'username': name, 'password': password, 'scope': 'openid'})['id_token']
        base = json.loads(k('config', 'view', '--raw', '-o', 'json').stdout)
        config = {'apiVersion': 'v1', 'kind': 'Config', 'clusters': base['clusters'],
                  'users': [{'name': 'probe', 'user': {'token': wrong}}],
                  'contexts': [{'name': 'probe', 'context': {'cluster': base['contexts'][0]['context']['cluster'], 'user': 'probe'}}],
                  'current-context': 'probe'}
        file.write_text(json.dumps(config), encoding='utf-8')
        from common import run
        rejected = run(['kubectl', '--kubeconfig', str(file), 'get', 'namespaces'], check=False)
        assert rejected.returncode != 0 and ('Unauthorized' in rejected.stderr or 'logged in' in rejected.stderr)
        file.unlink()
        results['checks']['wrong_audience_rejected'] = True
        results['checks']['discovery_https'] = api('/realms/relevance-lab/.well-known/openid-configuration')['issuer'] == ISSUER
    finally:
        file.unlink(missing_ok=True)
        for user in users:
            api('/admin/realms/relevance-lab/users/' + user, 'DELETE', token=token)
        for client in clients:
            api('/admin/realms/relevance-lab/clients/' + client, 'DELETE', token=token)
    (STATE_DIR / 'verification.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
