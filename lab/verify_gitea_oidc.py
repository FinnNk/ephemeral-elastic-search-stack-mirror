"""Verify native Gitea account linking with disposable identities."""
from html.parser import HTMLParser
import http.cookiejar
import json
import secrets
import ssl
from urllib import request, parse

from common import STATE, guard
from gitea import api as gitea
from install_oidc import admin_token, api as oidc
from verify_oidc import LoginForm

BASE = 'https://gitea.localhost:34443'


class Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None
    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'form':
            self.current = {'action': attrs.get('action', ''), 'fields': {}, 'names': []}
            self.forms.append(self.current)
        if self.current is not None and tag == 'input' and attrs.get('name'):
            self.current['names'].append(attrs['name'])
            if attrs.get('type') == 'hidden':
                self.current['fields'][attrs['name']] = attrs.get('value', '')
    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


def browser():
    return request.build_opener(request.HTTPSHandler(context=ssl.create_default_context(
        cafile=str(STATE / 'https-ingress/root.pem'))), request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def load(client, url, fields=None):
    with client.open(request.Request(url, data=None if fields is None else parse.urlencode(fields).encode()), timeout=30) as r:
        return r.geturl(), r.read().decode()


def provider_login(client, username, password):
    url, html = load(client, BASE + '/user/oauth2/lab-identity')
    form = LoginForm(); form.feed(html)
    if not form.action:
        raise ValueError('Expected Keycloak login form.')
    return load(client, form.action, {**form.fields, 'username': username, 'password': password, 'credentialId': ''})


def main():
    guard()
    token = admin_token()
    name = 'oidc-link-probe-' + secrets.token_hex(4)
    local_password, provider_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    user = gitea('/admin/users', 'POST', {'username': name, 'email': name + '@lab.invalid',
        'password': local_password, 'must_change_password': False, 'send_notify': False}, identity='bootstrap')
    provider = None
    try:
        oidc('/admin/realms/relevance-lab/users', 'POST', {'username': name, 'enabled': True,
            'firstName': 'OIDC', 'lastName': 'Probe', 'email': name + '@lab.invalid', 'emailVerified': True,
            'credentials': [{'type': 'password', 'value': provider_password, 'temporary': False}]}, token)
        provider = oidc('/admin/realms/relevance-lab/users?' + parse.urlencode({'username': name, 'exact': 'true'}), token=token)[0]
        client = browser()
        url, html = provider_login(client, name, provider_password)
        forms = Forms(); forms.feed(html)
        print(json.dumps({'after_provider_path': parse.urlparse(url).path,
            'forms': [{'action': parse.urlparse(f['action']).path, 'names': f['names']} for f in forms.forms]}))
        password_forms = [f for f in forms.forms if 'password' in f['names']]
        if not password_forms:
            raise ValueError('Expected explicit existing-account password proof.')
        form = password_forms[0]
        fields = {**form['fields'], 'user_name': name, 'password': local_password}
        bad_url, bad_html = load(client, parse.urljoin(url, form['action']), {**fields, 'password': secrets.token_urlsafe(24)})
        if parse.urlparse(bad_url).path != '/user/link_account_signin':
            raise ValueError('Wrong existing-account password was not rejected.')
        form_retry = Forms(); form_retry.feed(bad_html)
        retry = next(f for f in form_retry.forms if 'password' in f['names'])
        url, html = load(client, parse.urljoin(bad_url, retry['action']), {**retry['fields'], 'user_name': name, 'password': local_password})
        url, html = load(client, BASE + '/user/settings/account')
        if parse.urlparse(url).path == '/user/login':
            raise ValueError('Account linking did not establish a Gitea session.')
        fresh = browser()
        url, html = provider_login(fresh, name, provider_password)
        url, html = load(fresh, BASE + '/user/settings/account')
        if parse.urlparse(url).path == '/user/login':
            raise ValueError('Repeated OIDC login failed.')
        after = gitea('/users/' + name)
        assert after['id'] == user['id'] and after['login'] == name
        receipt = {'explicit_account_linking': True, 'repeat_oidc_sign_in': True,
            'account_id_preserved': True, 'wrong_existing_password_rejected': True, 'automatic_registration': False, 'roles_remapped': False}
        (STATE / 'oidc/gitea-verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps(receipt))
    finally:
        gitea('/admin/users/' + name, 'DELETE', identity='bootstrap')
        if provider:
            oidc('/admin/realms/relevance-lab/users/' + provider['id'], 'DELETE', token=token)


if __name__ == '__main__':
    main()
