"""Finite, bounded-memory indexing worker with a verified frozen Blob source."""
import base64
import gzip
import hashlib
import json
import os
import ssl
import tempfile
import time
import urllib.error
import urllib.request

BATCH_SIZE = 1000


def download_verified(url, expected_sha256, destination):
    digest = hashlib.sha256()
    count = 0
    with urllib.request.urlopen(url, timeout=120) as response, open(destination, 'wb') as output:
        for block in iter(lambda: response.read(1024 * 1024), b''):
            output.write(block)
            digest.update(block)
            count += len(block)
    if digest.hexdigest() != expected_sha256:
        raise ValueError('Frozen dataset Blob SHA-256 differs.')
    return count


def product_lines(path, compression):
    opener = gzip.open if compression == 'gzip' else open
    with opener(path, 'rt', encoding='utf-8') as source:
        for line in source:
            product = json.loads(line)
            yield json.dumps({'index': {'_id': product['product_id']}}, separators=(',', ':'))
            yield line.rstrip('\n')


def bulk_request(index, lines, auth, context):
    payload = ('\n'.join(lines) + '\n').encode()
    request = urllib.request.Request(
        'https://shared-es-http.platform.svc:9200/' + index + '/_bulk', data=payload,
        headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/x-ndjson'})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, context=context, timeout=120) as response:
                result = json.load(response)
            if result.get('errors'):
                first = next(item['index'].get('error') for item in result['items']
                             if item['index']['status'] >= 300)
                raise RuntimeError('Bulk item failed: ' + json.dumps(first)[:300])
            return result.get('took', 0)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 503) or attempt == 4:
                raise
            time.sleep(2 ** attempt)


def index_file(path, compression, index, user, password):
    if compression not in ('none', 'gzip'):
        raise ValueError('Unsupported dataset compression.')
    auth = base64.b64encode((user + ':' + password).encode()).decode()
    context = ssl.create_default_context(cafile='/es-ca/tls.crt')
    lines = []
    indexed = batches = elastic_ms = 0
    for line in product_lines(path, compression):
        lines.append(line)
        if len(lines) == BATCH_SIZE * 2:
            elastic_ms += bulk_request(index, lines, auth, context)
            indexed += len(lines) // 2
            batches += 1
            lines.clear()
    if lines:
        elastic_ms += bulk_request(index, lines, auth, context)
        indexed += len(lines) // 2
        batches += 1
    request = urllib.request.Request(
        'https://shared-es-http.platform.svc:9200/' + index + '/_refresh',
        data=b'', method='POST', headers={'Authorization': 'Basic ' + auth})
    with urllib.request.urlopen(request, context=context, timeout=120):
        pass
    return {'indexed': indexed, 'bulk_batches': batches, 'elasticsearch_bulk_ms': elastic_ms}


def main():
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as temporary:
        path = os.path.join(temporary, 'products')
        downloaded = download_verified(os.environ['DATASET_URL'], os.environ['DATASET_SHA256'], path)
        result = index_file(path, os.environ.get('DATASET_COMPRESSION', 'none'),
                            os.environ['ES_INDEX'], os.environ['ES_USER'], os.environ['ES_PASSWORD'])
    result.update({'dataset_sha256': os.environ['DATASET_SHA256'], 'downloaded_bytes': downloaded,
                   'elapsed_seconds': round(time.monotonic() - started, 3)})
    print(json.dumps(result))


if __name__ == '__main__':
    main()
