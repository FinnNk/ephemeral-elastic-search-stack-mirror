"""Measure a regular filesystem snapshot restore on an isolated ECK cluster."""
import argparse
import base64
import gzip
import hashlib
import json
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
sys.path.insert(0, 'lab')
from common import KUBE, STATE, guard, k, record
from index_recipe import current_recipe, publish

CLUSTER = 'lab-fs-probe'
PORT = 19202
REPOSITORY = 'lab-fs-repo'
QUERY = {'query': {'match_all': {}}, 'sort': [{'product_id': 'asc'}], 'size': 10}


class Client:
    def __init__(self):
        password = json.loads(k('get', 'secret', CLUSTER + '-es-elastic-user', '-n', 'platform',
                                '-o', 'json').stdout)['data']['elastic']
        cert = json.loads(k('get', 'secret', CLUSTER + '-es-http-certs-public', '-n', 'platform',
                            '-o', 'json').stdout)['data']['tls.crt']
        self.context = ssl.create_default_context(cadata=base64.b64decode(cert).decode())
        self.context.check_hostname = False
        self.auth = 'Basic ' + base64.b64encode(b'elastic:' + base64.b64decode(password)).decode()

    def call(self, path, method='GET', body=None, raw=False):
        data = None if body is None else (body if raw else json.dumps(body).encode())
        request = urllib.request.Request('https://127.0.0.1:' + str(PORT) + path, data=data,
            method=method, headers={'Authorization': self.auth,
                'Content-Type': 'application/x-ndjson' if raw else 'application/json'})
        try:
            with urllib.request.urlopen(request, context=self.context, timeout=300) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Elasticsearch {method} {path}: {error.code} '
                               + error.read().decode()[:1200]) from None


def wait_cluster():
    for _ in range(240):
        obj = json.loads(k('get', 'elasticsearch/' + CLUSTER, '-n', 'platform', '-o', 'json').stdout)
        if obj.get('status', {}).get('health') == 'green':
            return
        time.sleep(2)
    raise TimeoutError('Isolated ECK cluster did not become green.')


def port_forward():
    log = (STATE / 'snapshot-fs-forward.log').open('a', encoding='utf-8')
    process = subprocess.Popen(KUBE + ['-n', 'platform', 'port-forward',
        'svc/' + CLUSTER + '-es-http', str(PORT) + ':9200', '--address', '127.0.0.1'],
        stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    for _ in range(40):
        if process.poll() is not None:
            raise RuntimeError('Snapshot probe port forward stopped.')
        try:
            with socket.create_connection(('127.0.0.1', PORT), timeout=1):
                return process, log
        except OSError:
            time.sleep(0.5)
    process.terminate()
    raise TimeoutError('Snapshot probe port forward did not open.')


def frozen_ids(client, index):
    return [hit['_id'] for hit in client.call('/' + index + '/_search', 'POST', QUERY)['hits']['hits']]


def load_release(client, release_id):
    data_dir = STATE / 'releases' / release_id
    manifest = json.loads((data_dir / 'manifest.json').read_text(encoding='utf-8'))
    product_name = 'products.jsonl.gz' if manifest.get('compression') == 'gzip' else 'products.jsonl'
    product_path = data_dir / product_name
    digest = hashlib.sha256()
    with product_path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != manifest['sha256'][product_name]:
        raise ValueError('Frozen product object hash differs.')
    from load_release import BASELINE_MAPPING
    from load_million_release import MAPPING as MILLION_MAPPING
    definition = MILLION_MAPPING if manifest['count'] >= 1_000_000 else BASELINE_MAPPING
    recipe = current_recipe(release_id, 'shared', manifest, client.call('/')['version']['number'], definition)
    recipe_sha = publish(recipe)
    index = 'lab-fs-source-' + ('1m' if manifest['count'] >= 1_000_000 else '10k')
    created = json.loads(json.dumps(definition))
    created['mappings']['_meta'] = {'index_recipe_sha256': recipe_sha}
    try:
        existing = client.call('/' + index)[index]
    except RuntimeError as error:
        if ': 404 ' not in str(error):
            raise
        existing = None
    if existing:
        if existing['mappings'] != created['mappings']:
            raise ValueError('Disposable probe index has another mapping; refusing to replace it.')
        count = client.call('/' + index + '/_count')['count']
        frozen = existing['settings']['index'].get('blocks', {}).get('write') == 'true'
        if count == manifest['count'] and frozen:
            return {'index': index, 'recipe_sha256': recipe_sha, 'count': count,
                    'build_seconds': None, 'ordered_sample': frozen_ids(client, index)}
        client.call('/' + index, 'DELETE')
    started = time.monotonic()
    client.call('/' + index, 'PUT', created)
    opener = gzip.open if product_name.endswith('.gz') else open
    lines, total = [], 0
    with opener(product_path, 'rt', encoding='utf-8') as source:
        for line in source:
            product = json.loads(line)
            lines.extend([json.dumps({'index': {'_id': product['product_id']}}), line.rstrip('\n')])
            if len(lines) == 2000:
                result = client.call('/' + index + '/_bulk', 'POST', ('\n'.join(lines) + '\n').encode(), raw=True)
                if result['errors']:
                    raise ValueError('Elasticsearch bulk request failed.')
                total += len(lines) // 2
                lines.clear()
    if lines:
        result = client.call('/' + index + '/_bulk', 'POST', ('\n'.join(lines) + '\n').encode(), raw=True)
        if result['errors']:
            raise ValueError('Elasticsearch bulk request failed.')
        total += len(lines) // 2
    client.call('/' + index + '/_refresh', 'POST')
    client.call('/' + index + '/_settings', 'PUT', {'index.blocks.write': True})
    if total != manifest['count'] or client.call('/' + index + '/_count')['count'] != total:
        raise ValueError('Probe index document count differs.')
    return {'index': index, 'recipe_sha256': recipe_sha, 'count': total,
            'build_seconds': round(time.monotonic() - started, 3),
            'ordered_sample': frozen_ids(client, index)}


def measure_restore(client, source, snapshot_name, trials):
    target = source['index'].replace('source', 'restored')
    client.call('/' + source['index'], 'DELETE')
    samples = []
    for number in range(trials):
        started = time.monotonic()
        response = client.call('/_snapshot/' + REPOSITORY + '/' + snapshot_name +
            '/_restore?wait_for_completion=true', 'POST', {
                'indices': source['index'], 'include_global_state': False,
                'include_aliases': False, 'rename_pattern': source['index'],
                'rename_replacement': target})
        restore_seconds = round(time.monotonic() - started, 3)
        health = client.call('/_cluster/health/' + target + '?wait_for_status=yellow&timeout=120s')
        if health['timed_out']:
            raise TimeoutError('Restored shard did not become active.')
        count = client.call('/' + target + '/_count')['count']
        definition = client.call('/' + target)[target]
        if count != source['count'] or frozen_ids(client, target) != source['ordered_sample']:
            raise ValueError('Snapshot restore differed from the source index.')
        if definition['mappings']['_meta']['index_recipe_sha256'] != source['recipe_sha256']:
            raise ValueError('Restored recipe marker differs.')
        frozen = definition['settings']['index'].get('blocks', {}).get('write') == 'true'
        samples.append({'trial': number + 1, 'restore_api_seconds': restore_seconds,
                        'ready_seconds': round(time.monotonic() - started, 3),
                        'count': count, 'write_block': frozen,
                        'successful_shards': response['snapshot']['shards']['successful']})
        client.call('/' + target, 'DELETE')
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', choices=['retail-gb-10k-v1', 'retail-gb-1m-v1'], required=True)
    parser.add_argument('--trials', type=int, default=3)
    args = parser.parse_args()
    guard()
    wait_cluster()
    process, log = port_forward()
    try:
        client = Client()
        repo = client.call('/_snapshot/' + REPOSITORY, 'PUT',
                           {'type': 'fs', 'settings': {'location': '/mnt/snapshots/lab'}})
        verification = client.call('/_snapshot/' + REPOSITORY + '/_verify', 'POST')
        source = load_release(client, args.release)
        name = 'frozen-' + ('1m' if source['count'] >= 1_000_000 else '10k')
        started = time.monotonic()
        snapshot = client.call('/_snapshot/' + REPOSITORY + '/' + name +
            '?wait_for_completion=true', 'PUT', {'indices': source['index'],
                                                'include_global_state': False})
        snapshot_seconds = round(time.monotonic() - started, 3)
        if snapshot['snapshot']['state'] != 'SUCCESS':
            raise ValueError('Snapshot did not complete.')
        samples = measure_restore(client, source, name, args.trials)
        result = {'repository': 'fs', 'cluster': CLUSTER, 'engine': client.call('/')['version']['number'],
                  'release': args.release, 'recipe_sha256': source['recipe_sha256'],
                  'count': source['count'], 'repository_acknowledged': repo['acknowledged'],
                  'repository_verified_nodes': len(verification['nodes']),
                  'build_seconds': source['build_seconds'], 'snapshot_seconds': snapshot_seconds,
                  'restore_trials': samples}
        record('fs-snapshot-' + ('1m' if source['count'] >= 1_000_000 else '10k'), result)
        print(json.dumps(result, indent=2))
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


if __name__ == '__main__':
    main()
