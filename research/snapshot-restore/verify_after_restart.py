"""Verify that the isolated snapshot PVC survives an Elasticsearch Pod restart."""
import gzip
import heapq
import json
import sys
import time

sys.path.insert(0, 'research/snapshot-restore')
sys.path.insert(0, 'research/platform-spike')
from common import STATE, guard, record
from probe_fs import Client, REPOSITORY, frozen_ids, port_forward, wait_cluster


def main():
    guard()
    wait_cluster()
    process, log = port_forward()
    try:
        client = Client()
        client.call('/_snapshot/' + REPOSITORY, 'PUT',
                    {'type': 'fs', 'settings': {'location': '/mnt/snapshots/lab'}})
        source = 'lab-fs-source-1m'
        target = 'lab-fs-restart-restored-1m'
        snapshot = client.call('/_snapshot/' + REPOSITORY + '/frozen-1m')
        if snapshot['snapshots'][0]['state'] != 'SUCCESS':
            raise ValueError('Frozen million-product snapshot is unavailable after restart.')
        started = time.monotonic()
        client.call('/_snapshot/' + REPOSITORY + '/frozen-1m/_restore?wait_for_completion=true',
                    'POST', {'indices': source, 'include_global_state': False,
                             'include_aliases': False, 'rename_pattern': source,
                             'rename_replacement': target})
        restore_api_seconds = round(time.monotonic() - started, 3)
        health = client.call('/_cluster/health/' + target + '?wait_for_status=yellow&timeout=120s')
        if health['timed_out']:
            raise TimeoutError('Restored shard did not become active after restart.')
        definition = client.call('/' + target)[target]
        count = client.call('/' + target + '/_count')['count']
        actual = frozen_ids(client, target)
        ready_seconds = round(time.monotonic() - started, 3)
        product_path = STATE / 'releases/retail-gb-1m-v1/products.jsonl.gz'
        with gzip.open(product_path, 'rt', encoding='utf-8') as source_file:
            expected = heapq.nsmallest(10, (json.loads(line)['product_id'] for line in source_file))
        if count != 1_000_000 or actual != expected:
            raise ValueError('Restored million-product index differs after Pod restart.')
        if definition['settings']['index'].get('blocks', {}).get('write') != 'true':
            raise ValueError('Restored million-product index lost its write block.')
        result = {'snapshot': 'frozen-1m', 'count': count,
                  'recipe_sha256': definition['mappings']['_meta']['index_recipe_sha256'],
                  'ordered_sample_equal': True, 'write_block': True,
                  'restore_api_seconds': restore_api_seconds,
                  'ready_seconds': ready_seconds,
                  'full_verification_seconds': round(time.monotonic() - started, 3)}
        record('fs-snapshot-after-restart', result)
        print(json.dumps(result, indent=2))
        client.call('/' + target, 'DELETE')
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


if __name__ == '__main__':
    main()
