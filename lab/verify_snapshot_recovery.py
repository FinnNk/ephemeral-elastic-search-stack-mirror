"""Build, snapshot and repeatedly restore one million synthetic products."""
import gzip
import heapq
import json
import os
import sys

sys.path.insert(0, 'research/platform-spike')
from common import STATE, guard, record
from data_contract import elastic
from index_candidate import _existing, ensure_candidate_index, index_name, mapping_contract, remove_candidate_index
from index_recipe import current_recipe, publish
from index_recovery import sample_ids


RELEASE = 'retail-gb-1m-v1'
KIND = 'title-keyword-v1'
SOURCE = 'lab-snapshot-source-1m'
TARGET = 'lab-snapshot-restore-1m'
REPOSITORY = 'lab-s3'


def expected_ids(path):
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        return heapq.nsmallest(10, (json.loads(line)['product_id'] for line in source))


def main():
    guard()
    if os.environ.get('LAB_SNAPSHOT_REPOSITORY') != REPOSITORY:
        raise ValueError('Set LAB_SNAPSHOT_REPOSITORY=lab-s3 before the recovery check.')
    for name in (SOURCE, TARGET):
        if _existing(index_name(name)):
            raise ValueError('Disposable verification index already exists: ' + index_name(name))
    data = STATE / 'releases' / RELEASE
    manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
    recipe = current_recipe(RELEASE, KIND, manifest, elastic('/')['version']['number'],
                            mapping_contract(RELEASE, KIND)[0])
    recipe_sha = publish(recipe)
    product_sha = manifest['sha256']['products.jsonl.gz']
    expected = expected_ids(data / 'products.jsonl.gz')
    trials = []
    source_created = False
    try:
        built = ensure_candidate_index(SOURCE, product_sha, RELEASE, recipe_sha, KIND)
        source_created = True
        if built['materialisation'] != 'rebuild' or sample_ids(index_name(SOURCE)) != expected:
            raise ValueError('Initial frozen build did not match the product release.')
        remove_candidate_index(SOURCE)
        source_created = False
        for number in range(3):
            try:
                restored = ensure_candidate_index(TARGET, product_sha, RELEASE, recipe_sha, KIND)
                if restored['materialisation'] != 'snapshot' or sample_ids(index_name(TARGET)) != expected:
                    raise ValueError('Restored index did not match the frozen product release.')
                trials.append({'trial': number + 1, 'seconds': restored['build_seconds'],
                               'count': restored['count'], 'path': restored['materialisation']})
            finally:
                remove_candidate_index(TARGET)
    finally:
        if source_created:
            remove_candidate_index(SOURCE)
    result = {'repository': REPOSITORY, 'release': RELEASE, 'recipe_sha256': recipe_sha,
              'source_build_seconds': built['build_seconds'], 'source_count': built['count'],
              'source_deleted_before_restore': True, 'ordered_sample': expected, 'restore_trials': trials}
    record('million-s3-restore', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
