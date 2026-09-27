"""Measure no-reindex cloning of the existing frozen million-product index."""
import json
import sys
import time
import urllib.error

sys.path.insert(0, 'research/platform-spike')
from common import guard, record
from data_contract import elastic

SOURCE = 'retail-gb-1m-v1'
TARGET = 'lab-clone-probe-1m'
QUERY = {'query': {'match_all': {}}, 'sort': [{'product_id': 'asc'}], 'size': 10}


def ids(index):
    return [hit['_id'] for hit in elastic('/' + index + '/_search', 'POST', QUERY)['hits']['hits']]


def main():
    guard()
    source = elastic('/' + SOURCE)[SOURCE]
    assert source['settings']['index']['blocks']['write'] == 'true'
    assert elastic('/' + SOURCE + '/_count')['count'] == 1_000_000
    expected_ids = ids(SOURCE)
    try:
        elastic('/' + TARGET)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    else:
        raise ValueError('Clone probe target already exists; refusing to replace it.')
    results = []
    for trial in range(3):
        started = time.monotonic()
        try:
            response = elastic('/' + SOURCE + '/_clone/' + TARGET + '?wait_for_active_shards=1',
                               'POST', {'settings': {'index.number_of_replicas': 0}})
            acknowledged_seconds = round(time.monotonic() - started, 3)
            health = elastic('/_cluster/health/' + TARGET + '?wait_for_status=yellow&timeout=120s')
            if health['timed_out']:
                raise TimeoutError('Clone target shard did not become active.')
            count = elastic('/' + TARGET + '/_count')['count']
            target = elastic('/' + TARGET)[TARGET]
            assert count == 1_000_000 and ids(TARGET) == expected_ids
            assert target['mappings'] == source['mappings']
            assert target['settings']['index']['blocks']['write'] == 'true'
            results.append({'trial': trial + 1, 'acknowledged_seconds': acknowledged_seconds,
                            'ready_seconds': round(time.monotonic() - started, 3),
                            'count': count, 'ordered_sample_equal': True,
                            'acknowledged': response['acknowledged']})
        finally:
            try:
                elastic('/' + TARGET, 'DELETE')
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
    result = {'source': SOURCE, 'target': TARGET, 'method': 'clone', 'trials': results}
    record('million-index-clone', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
