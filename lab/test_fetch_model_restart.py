"""A restarted KServe initialiser accepts only the same pinned model bytes."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'judgements'))
from fetch_model import fetch, tree_digest


class ModelFetchRestartTests(unittest.TestCase):
    def test_same_model_volume_is_reused_but_changed_bytes_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            (destination / 'MLmodel').write_text('synthetic model')
            digest = tree_digest(destination)
            identity = {'name': 'synthetic-esci-judge', 'version': '1',
                        'artifact_sha256': digest}
            (destination / '.model-identity.json').write_text(json.dumps(identity))
            uri = 'mlflow-registry://synthetic-esci-judge/1?sha256=' + digest
            self.assertEqual(fetch(uri, destination)['artifact_sha256'], digest)
            (destination / 'MLmodel').write_text('changed model')
            with self.assertRaisesRegex(ValueError, 'differ from the pinned'):
                fetch(uri, destination)

    def test_partial_and_unpinned_model_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            (destination / 'MLmodel').write_text('partial')
            digest = tree_digest(destination)
            with self.assertRaisesRegex(ValueError, 'Existing model bytes'):
                fetch('mlflow-registry://judge/1?sha256=' + digest, destination)
            with self.assertRaisesRegex(ValueError, 'pinned SHA-256'):
                fetch('mlflow-registry://judge/1', destination)


if __name__ == '__main__':
    unittest.main()
