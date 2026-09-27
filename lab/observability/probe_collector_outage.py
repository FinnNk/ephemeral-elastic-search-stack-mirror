"""Show a valid Search API request completes while its OTLP endpoint is absent."""

import http.client
from http.server import ThreadingHTTPServer
import io
import json
import os
import threading
import time
from unittest.mock import patch

os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'] = 'http://127.0.0.1:9'
os.environ.update(ES_USER='reader', ES_PASSWORD='synthetic',
                  ES_URL='https://example.invalid', ES_INDEX='synthetic')

import app  # noqa: E402
from telemetry import telemetry  # noqa: E402

telemetry.configure()
hit = {'_source': {'product_id': 'gb-1', 'title': 'Blue shirt', 'brand': 'Alder',
                   'category': 'clothing', 'price_minor': 2500,
                   'currency': 'GBP', 'available': True}}
elastic = {'hits': {'total': {'value': 1}, 'hits': [hit]}}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
worker = threading.Thread(target=server.serve_forever, daemon=True)
worker.start()
try:
    with patch.object(app.ssl, 'create_default_context', return_value=None), \
            patch.object(app.urllib.request, 'urlopen', return_value=Response(json.dumps(elastic).encode())):
        client = http.client.HTTPConnection('127.0.0.1', server.server_port)
        started = time.monotonic()
        client.request('GET', '/search?q=shirt', headers={'X-Lab-Traffic-Class': 'normal'})
        answer = client.getresponse()
        result = json.load(answer)
        elapsed = time.monotonic() - started
        assert answer.status == 200 and result['ids'] == ['gb-1'] and elapsed < 2, (answer.status, elapsed)
        print(json.dumps({'collector': 'absent', 'status': answer.status,
                          'elapsed_seconds': round(elapsed, 3)}, sort_keys=True), flush=True)
        client.close()
finally:
    server.shutdown()
    server.server_close()
    worker.join(timeout=2)
