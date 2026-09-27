"""Publish the frozen million-product release and build its shared index."""
import json
import time
import urllib.error

from common import STATE, guard, record
from data_contract import elastic
from load_release import index_job, publish_blobs
from release_million import RELEASE, build

INDEX = RELEASE
DATA = STATE / 'releases' / RELEASE
MAPPING = {'settings': {'number_of_shards': 1, 'number_of_replicas': 0,
                        'refresh_interval': '30s'},
           'mappings': {'dynamic': 'strict', 'properties': {
               'product_id': {'type': 'keyword'}, 'sku': {'type': 'keyword'},
               'title': {'type': 'text'}, 'description': {'type': 'text'},
               'bullets': {'type': 'text'}, 'attrs': {'type': 'object', 'enabled': False},
               'category_path': {'type': 'keyword'}, 'brand': {'type': 'text'},
               'product_type': {'type': 'text'}, 'category': {'type': 'keyword'},
               'colour': {'type': 'keyword'}, 'material': {'type': 'keyword'},
               'country': {'type': 'keyword'}, 'currency': {'type': 'keyword'},
               'price_minor': {'type': 'integer'}, 'available': {'type': 'boolean'},
               'popularity': {'type': 'float'}, 'rating': {'type': 'float'},
               'review_count': {'type': 'integer'},
           }}}


def existing_index():
    try:
        return elastic('/' + INDEX)[INDEX]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def main():
    guard()
    manifest = build(DATA)
    assert manifest['count'] == 1_000_000 and manifest['query_count'] == 1_000
    started = time.monotonic()
    blob_path = publish_blobs(manifest, DATA)
    published_seconds = round(time.monotonic() - started, 3)
    existing = existing_index()
    if existing:
        if existing['mappings'] != MAPPING['mappings']:
            raise ValueError('Existing million-product index mapping differs.')
        created = False
        job = None
    else:
        created = True
        elastic('/' + INDEX, 'PUT', MAPPING)
        try:
            job = index_job(blob_path, manifest['sha256']['products.jsonl.gz'],
                            index=INDEX, role='retail-million-indexer',
                            expected_count=1_000_000, compression='gzip', deadline_seconds=1500)
            elastic('/' + INDEX + '/_settings', 'PUT', {'index.blocks.write': True})
        except Exception:
            elastic('/' + INDEX, 'DELETE')
            raise
    info = elastic('/' + INDEX + '/_settings')[INDEX]['settings']['index']
    count = elastic('/' + INDEX + '/_count')['count']
    if count != 1_000_000 or info.get('blocks', {}).get('write') != 'true':
        raise ValueError('Million-product index count or write block differs.')
    store = elastic('/' + INDEX + '/_stats/store')['indices'][INDEX]['total']['store']['size_in_bytes']
    evidence = {'release': RELEASE, 'index': INDEX, 'count': count,
                'query_count': manifest['query_count'], 'judgement_count': manifest['judgement_count'],
                'products_sha256': manifest['sha256']['products.jsonl.gz'],
                'compressed_bytes': manifest['bytes']['products.jsonl.gz'],
                'index_store_bytes': store, 'frozen': True, 'created': created,
                'publish_seconds': published_seconds, 'index_job': job,
                'total_seconds': round(time.monotonic() - started, 3)}
    record('million-release', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
