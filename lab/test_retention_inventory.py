"""The retention check uses independent manifests, not a combined release file."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from generate_example import build
from publish import publish
from retention_inventory import inventory


class RetentionInventoryTests(unittest.TestCase):
    def test_independent_inputs_are_inventoried_without_combined_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            manifests = Path(temporary) / 'manifests'
            build(source)
            publish(source, manifests, 'example-producer', 'example-source')
            self.assertFalse((source / 'manifest.json').exists())
            with patch('retention_inventory.blob_service', return_value=object()), \
                    patch('retention_inventory.blob_status', return_value='present'):
                result = inventory(source, manifests, [], [], None)
            self.assertEqual(result['source_release'], 'example-source')
            self.assertEqual(len(result['entries']), 3)
            self.assertEqual(result['missing'], [])
            self.assertTrue(all(row['local'] == 'present' for row in result['entries']))


if __name__ == '__main__':
    unittest.main()
