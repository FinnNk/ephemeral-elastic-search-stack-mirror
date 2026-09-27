import json
import unittest
from unittest.mock import patch

from common import STATE
from index_recipe import current_recipe
from shared_index import ensure_shared_index


class HistoricalSharedIndex(unittest.TestCase):
    def test_different_existing_schema_is_never_replaced(self):
        manifest = json.loads((STATE / 'releases/retail-gb-10k-v1/manifest.json').read_text())
        recipe = current_recipe('retail-gb-10k-v1', 'shared', manifest, '9.5.4')
        existing = {'retail-gb-10k-v1': {'mappings': {'properties': {'title': {'type': 'keyword'}}},
                                       'settings': {'index': {'number_of_shards': '1',
                                                              'number_of_replicas': '0'}}}}
        with patch('shared_index.load_recipe', return_value=recipe), \
             patch('shared_index.elastic', side_effect=lambda path, *args: \
                   {'version': {'number': '9.5.4'}} if path == '/' else existing) as es:
            with self.assertRaisesRegex(ValueError, 'different historical mapping'):
                ensure_shared_index('retail-gb-10k-v1', manifest['sha256']['products.jsonl'], 'a' * 64)
        self.assertNotIn('DELETE', [call.args[1] for call in es.call_args_list if len(call.args) > 1])


if __name__ == '__main__':
    unittest.main()
