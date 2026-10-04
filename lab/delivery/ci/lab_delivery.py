"""Submit authenticated lab delivery operations and follow their progress."""
import argparse
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import time
from urllib import error, parse, request

SERVER = 'https://control.localhost:34443'
ISSUER = 'https://identity.localhost:34443/realms/relevance-lab'


class Client:
    """Verify TLS, authenticate with OIDC and refresh tokens during long runs."""

    def __init__(self, server, issuer, ca=None, token_file=None):
        for value in (server, issuer):
            parts = parse.urlsplit(value)
            if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
                raise ValueError('Use HTTPS service addresses without credentials or query parameters.')
        self.server, self.issuer = server.rstrip('/'), issuer.rstrip('/')
        self.context = ssl.create_default_context()
        if ca:
            self.context.load_verify_locations(cafile=ca)
        self.token_file = Path(token_file or Path.home() / '.relevance-lab' / 'delivery-token.json')
        self.tokens = None
        self.expires = 0

    def http(self, url, data=None, headers=None):
        req = request.Request(url, data=data, headers=headers or {})
        with request.urlopen(req, context=self.context, timeout=60) as response:
            return json.load(response)

    def token(self, fields):
        return self.http(self.issuer + '/protocol/openid-connect/token',
                         parse.urlencode(fields).encode(), {'Content-Type': 'application/x-www-form-urlencoded'})

    def save(self, tokens):
        self.tokens = tokens
        self.expires = time.time() + tokens.get('expires_in', 300) - 30
        if not os.environ.get('LAB_DELIVERY_CLIENT_SECRET'):
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            # Create with restrictive permissions before writing on Unix. On Windows
            # the file inherits the user's profile directory permissions.
            fd = os.open(self.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump({'issuer': self.issuer, 'tokens': tokens, 'expires': self.expires}, handle)

    def login(self):
        value = self.http(self.issuer + '/protocol/openid-connect/auth/device',
            parse.urlencode({'client_id': 'lab-delivery-cli', 'scope': 'openid profile email'}).encode(),
            {'Content-Type': 'application/x-www-form-urlencoded'})
        print('Open ' + value['verification_uri'] + ' and enter ' + value['user_code'], flush=True)
        deadline, interval = time.monotonic() + value['expires_in'], value.get('interval', 5)
        while time.monotonic() < deadline:
            time.sleep(interval)
            try:
                self.save(self.token({'client_id': 'lab-delivery-cli',
                    'grant_type': 'urn:ietf:params:oauth:grant-type:device_code', 'device_code': value['device_code']}))
                print('Signed in.')
                return
            except error.HTTPError as failure:
                reason = json.load(failure).get('error')
                if reason == 'slow_down':
                    interval += 5
                elif reason != 'authorization_pending':
                    raise ValueError('Sign-in failed: ' + str(reason)) from None
        raise TimeoutError('Sign-in expired. Run login again.')

    def bearer(self):
        secret = os.environ.get('LAB_DELIVERY_CLIENT_SECRET')
        if self.tokens is None and not secret and self.token_file.exists():
            saved = json.loads(self.token_file.read_text(encoding='utf-8'))
            if saved.get('issuer') == self.issuer:
                self.tokens, self.expires = saved['tokens'], saved['expires']
        if time.time() >= self.expires:
            if secret:
                self.save(self.token({'grant_type': 'client_credentials', 'client_id': 'lab-delivery-actions',
                                      'client_secret': secret}))
            elif self.tokens and self.tokens.get('refresh_token'):
                self.save(self.token({'grant_type': 'refresh_token', 'client_id': 'lab-delivery-cli',
                                      'refresh_token': self.tokens['refresh_token']}))
            else:
                raise ValueError('Sign in first: run this command with login.')
        return self.tokens['access_token']

    def call(self, path, payload=None, key=None):
        headers = {'Authorization': 'Bearer ' + self.bearer(), 'Content-Type': 'application/json',
                   'X-Lab-Intent': '1', 'Accept': 'application/json'}
        if key:
            headers['Idempotency-Key'] = key
        return self.http(self.server + path, json.dumps(payload).encode() if payload is not None else None, headers)

    def submit(self, payload, key=None, wait=True, timeout=3600):
        row = self.call('/api/delivery/operations', payload, key or secrets.token_hex(16))
        print('Progress: ' + row['url'], flush=True)
        if not wait:
            return row
        deadline, previous = time.monotonic() + timeout, None
        while row['state'] in ('queued', 'running'):
            message = row['state'] + ': ' + row['progress']
            if message != previous:
                print(message, flush=True)
                previous = message
            if time.monotonic() >= deadline:
                raise TimeoutError('Operation continues on the server. Follow the progress URL; do not submit it again.')
            time.sleep(2)
            row = self.call('/api/delivery/operations/' + row['id'])
        if row['state'] != 'complete':
            raise ValueError(row.get('error') or 'Operation ' + row['state'])
        return row


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument('--server', default=os.environ.get('LAB_DELIVERY_URL', SERVER))
    root.add_argument('--issuer', default=os.environ.get('LAB_OIDC_ISSUER', ISSUER))
    root.add_argument('--ca', default=os.environ.get('LAB_CA_BUNDLE'))
    commands = root.add_subparsers(dest='command', required=True)
    commands.add_parser('login')
    for name in ('preview', 'compare', 'propose-promotion', 'source-compare', 'gate-check'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--key', help='Stable submission key for retrying this operation')
        cmd.add_argument('--no-wait', action='store_true')
        cmd.add_argument('--dataset', default='esci-gb-v1')
        cmd.add_argument('--recipe')
        if name in ('preview', 'propose-promotion'):
            cmd.add_argument('--run', type=int, required=True)
        if name == 'compare':
            cmd.add_argument('--baseline-run', type=int, required=True)
            cmd.add_argument('--candidate-run', type=int, required=True)
        if name == 'propose-promotion':
            cmd.add_argument('--target', choices=('integration', 'staging', 'production'), required=True)
            cmd.add_argument('--intent', choices=('ranking-change', 'preserve-results'), required=True)
        if name in ('source-compare', 'gate-check'):
            cmd.add_argument('--pr', type=int, required=True)
            cmd.add_argument('--source-sha', required=True)
            if name == 'source-compare':
                cmd.add_argument('--baseline-sha', required=True)
    return root


def main():
    args = parser().parse_args()
    client = Client(args.server, args.issuer, args.ca)
    if args.command == 'login':
        return client.login()
    fields = vars(args)
    payload = {key: value for key, value in fields.items()
               if key not in ('command', 'server', 'issuer', 'ca', 'key', 'no_wait') and value is not None}
    payload['kind'] = {'propose-promotion': 'promotion', 'source-compare': 'compare'}.get(args.command, args.command)
    if args.command == 'gate-check':
        payload.pop('dataset', None)
        payload.pop('recipe', None)
    print(json.dumps(client.submit(payload, args.key, not args.no_wait), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, TimeoutError, error.URLError) as failure:
        # HTTP errors print their status, not token response bodies or credentials.
        print('Delivery command failed: ' + str(failure), file=sys.stderr)
        sys.exit(1)
