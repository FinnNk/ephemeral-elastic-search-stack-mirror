"""Rebuild an old index after its mapping source has changed, then compare schemas."""
import copy
import json
import time
from unittest.mock import patch

from common import STATE, guard, record
from data_contract import elastic
from index_candidate import KIND, _existing, ensure_candidate_index, index_name, mapping_contract, remove_candidate_index
from index_recipe import current_recipe, publish


def main():
    guard()
    release = 'retail-gb-10k-v1'
    manifest = json.loads((STATE / 'releases' / release / 'manifest.json').read_text(encoding='utf-8'))
    product_sha = manifest['sha256']['products.jsonl']
    engine = elastic('/')['version']['number']
    old = current_recipe(release, KIND, manifest, engine, mapping_contract(release)[0])
    old_sha = publish(old)
    changed = copy.deepcopy(old)
    changed['index_definition']['mappings']['properties']['title'] = {'type': 'text'}
    new_sha = publish(changed)
    names = ('lab-recipe-old', 'lab-recipe-new')
    for name in names:
        if _existing(index_name(name)):
            raise ValueError('A verification index name already exists; refusing to replace it.')
    try:
        started = time.monotonic()
        first = ensure_candidate_index(names[0], product_sha, release, old_sha)
        first_seconds = round(time.monotonic() - started, 3)
        sample_query = {'query': {'match_all': {}}, 'sort': [{'product_id': 'asc'}], 'size': 10}
        first_ids = [hit['_id'] for hit in elastic('/' + index_name(names[0]) + '/_search', 'POST',
                                                  sample_query)['hits']['hits']]
        remove_candidate_index(names[0])
        # Historical restoration must read the stored definition, never the current mapping file.
        with patch('index_candidate.mapping_contract', side_effect=AssertionError('Current mapping was read')):
            started = time.monotonic()
            restored = ensure_candidate_index(names[0], product_sha, release, old_sha)
            restore_seconds = round(time.monotonic() - started, 3)
        newer = ensure_candidate_index(names[1], product_sha, release, new_sha)
        old_mapping = elastic('/' + index_name(names[0]))[index_name(names[0])]['mappings']
        new_mapping = elastic('/' + index_name(names[1]))[index_name(names[1])]['mappings']
        assert old_mapping['properties']['title'] == {'type': 'keyword'}
        assert new_mapping['properties']['title'] == {'type': 'text'}
        assert old_mapping['_meta']['index_recipe_sha256'] == old_sha
        assert new_mapping['_meta']['index_recipe_sha256'] == new_sha
        assert first['count'] == restored['count'] == newer['count'] == manifest['count']
        restored_ids = [hit['_id'] for hit in elastic('/' + index_name(names[0]) + '/_search', 'POST',
                                                     sample_query)['hits']['hits']]
        assert len(first_ids) == 10 and restored_ids == first_ids
        title_query = {'query': {'match': {'title': 'running shoes'}}, 'size': 10}
        old_hits = elastic('/' + index_name(names[0]) + '/_search', 'POST', title_query)['hits']['total']['value']
        new_hits = elastic('/' + index_name(names[1]) + '/_search', 'POST', title_query)['hits']['total']['value']
        assert old_hits != new_hits
        result = {'old_recipe_sha256': old_sha, 'new_recipe_sha256': new_sha,
                  'old_mapping_title': 'keyword', 'new_mapping_title': 'text',
                  'products_per_index': manifest['count'], 'first_build_seconds': first_seconds,
                  'historical_rebuild_seconds': restore_seconds,
                  'historical_recipe_loaded_without_current_mapping': True,
                  'old_top_10_reproduced': True, 'old_title_hits': old_hits, 'new_title_hits': new_hits}
        record('historical-index-rebuild', result)
        print(json.dumps(result, indent=2))
    finally:
        for name in names:
            remove_candidate_index(name)


if __name__ == '__main__':
    main()
