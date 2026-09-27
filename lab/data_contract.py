"""Elasticsearch access for the local lab cluster."""

import base64
import json
import os
import ssl
import urllib.request

from common import k


def elastic(path, method='GET', body=None, user='elastic', password=None,
            raw=False, cluster='shared', port=19200):
    if password is None:
        secret = json.loads(k('get', 'secret', cluster + '-es-elastic-user',
                              '-n', 'platform', '-o', 'json').stdout)
        password = base64.b64decode(secret['data']['elastic']).decode()
    certificate = json.loads(k('get', 'secret', cluster + '-es-http-certs-public',
                               '-n', 'platform', '-o', 'json').stdout)
    context = ssl.create_default_context(
        cadata=base64.b64decode(certificate['data']['tls.crt']).decode())
    context.check_hostname = False
    payload = body.encode() if raw else (None if body is None else json.dumps(body).encode())
    endpoint = (os.environ.get('LAB_ELASTICSEARCH_URL') if cluster == 'shared' else None) or \
        f'https://127.0.0.1:{port}'
    auth = base64.b64encode((user + ':' + password).encode()).decode()
    request = urllib.request.Request(endpoint.rstrip('/') + path, method=method, data=payload,
        headers={'Content-Type': 'application/x-ndjson' if raw else 'application/json',
                 'Authorization': 'Basic ' + auth})
    with urllib.request.urlopen(request, context=context, timeout=60) as response:
        return json.load(response)
