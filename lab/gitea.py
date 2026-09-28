"""Local Gitea API adapter; credentials stay in ignored lab state."""

import base64
import json
import os
import urllib.error
import urllib.request

from common import STATE
from gitea_tls import open_url

BASE = os.environ.get('LAB_GITEA_API_URL', 'http://127.0.0.1:31800/api/v1').rstrip('/')


def api(path, method='GET', body=None, identity='agent'):
    credentials = json.loads((STATE / 'credentials.json').read_text(encoding='utf-8'))
    account = credentials['agent'] if identity == 'agent' else credentials
    auth = base64.b64encode((account['username'] + ':' + account['password']).encode()).decode()
    request = urllib.request.Request(
        BASE + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json'},
    )
    try:
        with open_url(request, timeout=30) as response:
            payload = response.read()
            return json.loads(payload) if payload else None
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'Gitea {method} {path}: {error.code}') from None
