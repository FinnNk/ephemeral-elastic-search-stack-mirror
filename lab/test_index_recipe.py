import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, 'research/platform-spike')
from common import STATE
from index_candidate import KIND, mapping_contract
from index_recipe import catalogue_recipe, current_recipe, digest, validate
from environments import define


class FrozenRecipeContract(unittest.TestCase):
    def test_catalogue_recipe_ignores_query_and_judgement_revision(self):
        manifest = json.loads((STATE / 'releases/retail-gb-10k-v1/manifest.json').read_text())
        product_hash = manifest['sha256']['products.jsonl']
        catalogue = {'kind': 'catalogue', 'schema_version': 1,
                     'content': {'sha256': product_hash,
                                 'object': 'catalogue/' + product_hash + '/products.jsonl',
                                 'format': 'jsonl', 'compression': 'none'},
                     'record_count': manifest['count']}
        recipe = catalogue_recipe('retail-gb-10k-v1', KIND, catalogue,
                                  '9.5.4', mapping_contract()[0])
        self.assertEqual(recipe['format'], 2)
        self.assertNotIn('release_manifest_sha256', recipe)
        changed_evaluation_inputs = copy.deepcopy(manifest)
        changed_evaluation_inputs['sha256']['queries.jsonl'] = 'a' * 64
        changed_evaluation_inputs['sha256']['judgements.jsonl'] = 'b' * 64
        validate(recipe, 'retail-gb-10k-v1', changed_evaluation_inputs, '9.5.4', catalogue)
        altered_catalogue = copy.deepcopy(catalogue)
        altered_catalogue['record_count'] += 1
        with self.assertRaisesRegex(ValueError, 'Catalogue artifact differs'):
            validate(recipe, catalogue_manifest=altered_catalogue)

    def test_recipe_change_changes_environment_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory, patch('environments.REPO', Path(directory)):
            first = define('lab-recipe-fingerprint', 'registry/image@sha256:' + 'a' * 64,
                           'retail-gb-10k-v1', 'b' * 64, 'c' * 64, 'd' * 64)
            second = define('lab-recipe-fingerprint', 'registry/image@sha256:' + 'a' * 64,
                            'retail-gb-10k-v1', 'b' * 64, 'c' * 64, 'e' * 64)
        self.assertNotEqual(first['fingerprint'], second['fingerprint'])

    def test_rejects_changed_release_engine_and_worker(self):
        manifest = json.loads((STATE / 'releases/retail-gb-10k-v1/manifest.json').read_text())
        recipe = current_recipe('retail-gb-10k-v1', KIND, manifest, '9.5.4', mapping_contract()[0])
        self.assertEqual(len(digest(recipe)), 64)
        validate(recipe, 'retail-gb-10k-v1', manifest, '9.5.4')
        with self.assertRaisesRegex(ValueError, 'different Elasticsearch version'):
            validate(recipe, 'retail-gb-10k-v1', manifest, '9.5.3')
        altered = copy.deepcopy(manifest)
        altered['count'] += 1
        with self.assertRaisesRegex(ValueError, 'release differs'):
            validate(recipe, 'retail-gb-10k-v1', altered, '9.5.4')
        altered = copy.deepcopy(recipe)
        altered['indexer']['source'] += '\n# changed'
        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            validate(altered)


if __name__ == '__main__':
    unittest.main()
