"""Local Nexus API and immutable release storage. Credentials never enter Git."""
import base64
import hashlib
import json
import os
import urllib.error
import urllib.request

from common import STATE

BASE = os.environ.get('LAB_NEXUS_API_URL', 'http://127.0.0.1:18183').rstrip('/')
REGISTRY = 'nexus.localhost:18185'
CREDENTIALS = STATE / 'nexus.json'


def credentials():
    return json.loads(CREDENTIALS.read_text(encoding='utf-8'))


def request(path, method='GET', body=None, identity='agent', content_type='application/json'):
    user = credentials()[identity] if isinstance(identity, str) else identity
    headers = {'Content-Type': content_type}
    if user:
        headers['Authorization'] = 'Basic ' + base64.b64encode(
            (user['username'] + ':' + user['password']).encode()).decode()
    if body is not None and not isinstance(body, bytes):
        body = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, method=method, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def api(path, method='GET', body=None, identity='agent'):
    value = request('/service/rest/v1' + path, method, body, identity)
    return json.loads(value) if value else None


def publish(path, content, identity='publisher'):
    """Retry an identical upload; never replace different bytes at an existing path."""
    if not path or any(part in ('', '.', '..') for part in path.split('/')):
        raise ValueError('Artifact path must be a relative path without traversal.')
    url = '/repository/lab-releases/' + path
    try:
        existing = request(url, identity=identity)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    else:
        if existing != content:
            raise ValueError('Immutable artifact already exists with different bytes.')
        return hashlib.sha256(content).hexdigest()
    try:
        request(url, 'PUT', content, identity, 'application/octet-stream')
    except urllib.error.HTTPError as error:
        # Another publisher may have won the race. Compare its bytes before accepting.
        if error.code not in (400, 409) or request(url, identity=identity) != content:
            raise
    if request(url, identity=identity) != content:
        raise ValueError('Nexus read-back differs from the published artifact.')
    return hashlib.sha256(content).hexdigest()
