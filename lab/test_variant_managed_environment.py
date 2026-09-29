"""Frozen environment fingerprints include runtime variant and registry choices."""

import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import environments


class ManagedVariantEnvironmentTests(unittest.TestCase):
    def test_configuration_is_canonical_and_changes_the_fingerprint(self):
        configuration = {'variants': {
            'ranker-b': {'field_boosts': {'title': 2}},
            'ranker-a': {'field_boosts': {'title': 4}}},
            'default_variant': 'ranker-a'}
        with tempfile.TemporaryDirectory() as directory, patch.object(
                environments, 'REPO', Path(directory)):
            first = environments.define('lab-variant-test', 'nexus.localhost:18185/search-api@sha256:' +
                'a' * 64, 'retail-gb-1m-v1', 'b' * 64,
                variant_config=configuration, image_pull_secret='nexus-read')
            decoded = json.loads(base64.b64decode(first['variant_config_b64']))
            self.assertEqual(decoded, configuration)
            self.assertEqual(first['image_pull_secret'], 'nexus-read')
            changed = {**configuration, 'default_variant': 'ranker-b'}
            second = environments.define('lab-variant-test', first['image'],
                first['index'], first['dataset_sha256'],
                variant_config=changed, image_pull_secret='nexus-read')
            self.assertNotEqual(first['fingerprint'], second['fingerprint'])

    def test_missing_default_and_unknown_secret_fail(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
                environments, 'REPO', Path(directory)):
            with self.assertRaisesRegex(ValueError, 'named default'):
                environments.define('lab-variant-test', 'image', 'index', 'a' * 64,
                    variant_config={'variants': {'a': {}}})
            with self.assertRaisesRegex(ValueError, 'registry identity'):
                environments.define('lab-variant-test', 'image', 'index', 'a' * 64,
                    image_pull_secret='unexpected')


if __name__ == '__main__':
    unittest.main()
