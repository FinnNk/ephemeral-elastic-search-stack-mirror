"""Short-lived local sessions backed by distinct Gitea user accounts."""
import base64
import json
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.cookies import SimpleCookie

GITEA_USER_URL = 'http://127.0.0.1:31800/api/v1/user'
SESSION_SECONDS = 12 * 60 * 60
COOKIE_NAME = 'lab_session'


class GiteaIdentity:
    def verify(self, username, password):
        if not username or not password:
            raise ValueError('Enter your Gitea username and password.')
        credential = base64.b64encode((username + ':' + password).encode()).decode()
        request = urllib.request.Request(GITEA_USER_URL, headers={
            'Authorization': 'Basic ' + credential, 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                profile = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise ValueError('Gitea did not accept those credentials.') from None
            raise RuntimeError('Gitea identity service is unavailable.') from None
        except (OSError, ValueError):
            raise RuntimeError('Gitea identity service is unavailable.') from None
        if not profile.get('login'):
            raise RuntimeError('Gitea returned no user identity.')
        return {'username': profile['login'], 'is_admin': bool(profile.get('is_admin'))}


class Sessions:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.values = {}

    def create(self, identity):
        token = secrets.token_urlsafe(32)
        with self.lock:
            for old_token, old_identity in list(self.values.items()):
                if self.clock() >= old_identity['expires_at']:
                    self.values.pop(old_token, None)
            self.values[token] = {**identity, 'expires_at': self.clock() + SESSION_SECONDS}
        return token

    def get(self, cookie_header):
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header or '')
        except Exception:
            return None
        if COOKIE_NAME not in cookie:
            return None
        token = cookie[COOKIE_NAME].value
        with self.lock:
            identity = self.values.get(token)
            if not identity:
                return None
            if self.clock() >= identity['expires_at']:
                self.values.pop(token, None)
                return None
            return dict(identity)

    def discard(self, cookie_header):
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header or '')
        except Exception:
            return
        if COOKIE_NAME in cookie:
            with self.lock:
                self.values.pop(cookie[COOKIE_NAME].value, None)


def session_cookie(token):
    return f'{COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}'


def expired_cookie():
    return f'{COOKIE_NAME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
