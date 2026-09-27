import os
import unittest
import urllib.error
from unittest.mock import patch

from index_recovery import clone_from_live, restore_snapshot, save_snapshot, snapshot_name, verify


SHA = 'a' * 64
RECIPE = {'release_id': 'retail-gb-10k-v1', 'product_sha256': 'b' * 64,
          'engine_version': '9.5.4', 'document_count': 2,
          'index_definition': {'settings': {'number_of_shards': 1, 'number_of_replicas': 0},
                               'mappings': {'properties': {'product_id': {'type': 'keyword'}}}}}
META = {'index_recipe_sha256': SHA, 'product_sha256': 'b' * 64,
        'engine_version': '9.5.4', 'ordered_sample': ['p1', 'p2']}


class FakeElastic:
    def __init__(self):
        self.indices = {'source-idx': True}
        self.calls = []
        self.snapshot = {'state': 'SUCCESS', 'indices': ['source-idx'], 'metadata': dict(META)}

    def __call__(self, path, method='GET', body=None):
        self.calls.append((path, method, body))
        if path == '/_cat/indices?format=json&h=index':
            return [{'index': name} for name in self.indices]
        if path.startswith('/_snapshot/'):
            if path.endswith('/_verify'):
                return {'nodes': {'node-1': {}}}
            if path.endswith('/_restore?wait_for_completion=true'):
                self.indices['target-idx'] = True
                return {'snapshot': {'shards': {'successful': 1}}}
            if method == 'PUT':
                self.snapshot = {'state': 'SUCCESS', 'indices': [body['indices']],
                                 'metadata': body['metadata']}
                return {'snapshot': {'state': 'SUCCESS'}}
            return {'snapshots': [self.snapshot]}
        if path.startswith('/_cluster/health/'):
            return {'timed_out': False}
        if '/_clone/' in path:
            self.indices['target-idx'] = True
            return {'acknowledged': True}
        name = path.strip('/').split('/')[0]
        if method == 'DELETE':
            self.indices.pop(name, None)
            return {'acknowledged': True}
        if name not in self.indices:
            raise urllib.error.HTTPError(path, 404, 'missing', None, None)
        if path.endswith('/_count'):
            return {'count': 2}
        if path.endswith('/_search'):
            return {'hits': {'hits': [{'_id': 'p1'}, {'_id': 'p2'}]}}
        return {name: {'mappings': {'_meta': {'index_recipe_sha256': SHA},
                                   **RECIPE['index_definition']['mappings']},
                       'settings': {'index': {'number_of_shards': '1', 'number_of_replicas': '0',
                                              'blocks': {'write': 'true'}}}}}


class RecoveryContract(unittest.TestCase):
    def setUp(self):
        self.es = FakeElastic()
        self.patcher = patch('index_recovery.elastic', self.es)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_clone_requires_exact_live_recipe_and_verifies_target(self):
        result = clone_from_live('target-idx', RECIPE, SHA)
        self.assertEqual(result['source'], 'clone')
        self.assertEqual(result['source_index'], 'source-idx')
        self.assertIn('target-idx', self.es.indices)

    def test_restore_uses_matching_snapshot_and_separate_name(self):
        with patch.dict(os.environ, {'LAB_SNAPSHOT_REPOSITORY': 'lab-fs'}):
            result = restore_snapshot('target-idx', RECIPE, SHA)
        self.assertEqual(result['source'], 'snapshot')
        call = next(body for path, method, body in self.es.calls if path.endswith('/_restore?wait_for_completion=true'))
        self.assertEqual(call['rename_replacement'], 'target-idx')
        self.assertFalse(call['include_global_state'])
        self.assertFalse(call['include_aliases'])

    def test_metadata_mismatch_never_starts_restore(self):
        self.es.snapshot['metadata']['product_sha256'] = 'wrong'
        with patch.dict(os.environ, {'LAB_SNAPSHOT_REPOSITORY': 'lab-fs'}):
            with self.assertRaisesRegex(ValueError, 'metadata differs'):
                restore_snapshot('target-idx', RECIPE, SHA)
        self.assertFalse(any(path.endswith('/_restore?wait_for_completion=true') for path, _, _ in self.es.calls))

    def test_wrong_ordered_sample_removes_restored_target(self):
        self.es.snapshot['metadata']['ordered_sample'] = ['other', 'ids']
        with patch.dict(os.environ, {'LAB_SNAPSHOT_REPOSITORY': 'lab-fs'}):
            with self.assertRaisesRegex(ValueError, 'ordered sample differs'):
                restore_snapshot('target-idx', RECIPE, SHA)
        self.assertNotIn('target-idx', self.es.indices)

    def test_saved_snapshot_pins_recipe_and_is_reused(self):
        with patch.dict(os.environ, {'LAB_SNAPSHOT_REPOSITORY': 'lab-fs'}):
            self.assertEqual(save_snapshot('source-idx', RECIPE, SHA), snapshot_name(SHA))
        self.assertFalse(any(method == 'PUT' for _, method, _ in self.es.calls))

    def test_index_with_wrong_mapping_fails_verification(self):
        other = {**RECIPE, 'index_definition': {'settings': RECIPE['index_definition']['settings'],
                                                'mappings': {'properties': {'title': {'type': 'text'}}}}}
        with self.assertRaisesRegex(ValueError, 'recipe or mapping'):
            verify('source-idx', other, SHA)


if __name__ == '__main__':
    unittest.main()
