"""Disposable transport variants; none of these switches enters the reference API."""
import json
import os
import ssl
import time
import urllib.request
from http.server import ThreadingHTTPServer

import httpx
from app import Handler, telemetry


class CachedTLS(Handler):
    def search_index(self, body):
        import base64
        auth = base64.b64encode((os.environ['ES_USER'] + ':' + os.environ['ES_PASSWORD']).encode()).decode()
        headers = {'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth}
        telemetry.inject(headers)
        request = urllib.request.Request(os.environ['ES_URL'] + '/' + os.environ['ES_INDEX'] + '/_search',
                                         data=json.dumps(body).encode(), headers=headers)
        with telemetry.span('search.elasticsearch'):
            started = time.monotonic()
            with urllib.request.urlopen(request, context=self.context, timeout=10) as response:
                result = json.load(response)
            return result, (time.monotonic() - started) * 1000


class PooledES(Handler):
    def search_index(self, body):
        headers = {}
        telemetry.inject(headers)
        with telemetry.span('search.elasticsearch'):
            started = time.monotonic()
            response = self.client.post('/' + os.environ['ES_INDEX'] + '/_search', json=body, headers=headers)
            response.raise_for_status()
            return response.json(), (time.monotonic() - started) * 1000


if __name__ == '__main__':
    telemetry.configure()
    mode = os.environ['EXPERIMENT_TRANSPORT']
    client = None
    if mode == 'original':
        handler = Handler
    elif mode == 'cached-tls':
        handler = CachedTLS
        handler.context = ssl.create_default_context(cafile='/es-ca/tls.crt')
    elif mode in ('pooled-es', 'pooled-both'):
        handler = PooledES
        if mode == 'pooled-both':
            handler.protocol_version = 'HTTP/1.1'
        client = httpx.Client(base_url=os.environ['ES_URL'],
            auth=(os.environ['ES_USER'], os.environ['ES_PASSWORD']),
            verify=ssl.create_default_context(cafile='/es-ca/tls.crt'), timeout=10, trust_env=False,
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=64))
        handler.client = client
    else:
        raise ValueError('Unknown experiment transport.')
    server = ThreadingHTTPServer(('0.0.0.0', 8080), handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if client:
            client.close()
