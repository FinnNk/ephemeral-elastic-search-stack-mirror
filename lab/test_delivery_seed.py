"""Check that a fresh source repository can select its seeded ranking configuration."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import setup_delivery


class DeliverySeedTests(unittest.TestCase):
    def test_fresh_seed_has_complete_gate_inputs(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(setup_delivery, 'api', return_value={'empty': True}), \
                patch.object(setup_delivery, 'git'):
            root = Path(directory)
            setup_delivery.seed_source(root)
            self.assertEqual((root / 'VERSION').read_text().strip(), '1.0.0')
            self.assertTrue((root / 'ci/versioning.py').exists())
            selection = json.loads((root / 'gate/selection.json').read_text())
            layout = json.loads((root / 'gate/evaluation.json').read_text())
            self.assertEqual(selection['kind'], 'variant-gate-selection')
            self.assertEqual(selection['schema_version'], 1)
            selected = selection['selected'][0]
            self.assertEqual(selected['intent'], 'preserve-results')
            self.assertEqual(selected['variant'], layout['default_variant'])
            configuration = json.loads((root / 'configurations' / (selected['variant'] + '.json')).read_text())
            self.assertIn(selected['variant'], configuration['variants'])

    def test_existing_repository_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(setup_delivery, 'api', return_value={'empty': False}), \
                patch.object(setup_delivery, 'git') as git:
            root = Path(directory)
            selection = root / 'gate/selection.json'
            selection.parent.mkdir()
            selection.write_text('human selection')
            setup_delivery.seed_source(root)
            self.assertEqual(selection.read_text(), 'human selection')
            git.assert_not_called()


if __name__ == '__main__':
    unittest.main()
