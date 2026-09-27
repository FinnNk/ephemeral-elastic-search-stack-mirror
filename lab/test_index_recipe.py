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
from index_recipe import current_recipe, digest, validate
from environments import define


class FrozenRecipeContract(unittest.TestCase):
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
