import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, 'research/platform-spike')
from common import STATE
from index_candidate import KIND, ensure_candidate_index, mapping_contract
from index_recipe import current_recipe, digest


class CandidateIndexRecovery(unittest.TestCase):
    def test_exact_clone_short_circuits_bulk_build(self):
        manifest = json.loads((STATE / 'releases/retail-gb-10k-v1/manifest.json').read_text())
        recipe = current_recipe('retail-gb-10k-v1', KIND, manifest, '9.5.4', mapping_contract()[0])
        with patch('index_candidate.load_recipe', return_value=recipe), \
             patch('index_candidate._existing', return_value=None), \
             patch('index_candidate.clone_from_live', return_value={'source': 'clone', 'seconds': 1.2}), \
             patch('index_candidate.restore_snapshot') as restored, \
             patch('index_candidate.save_snapshot'), \
             patch('index_candidate.index_job') as job, \
             patch('index_candidate.elastic', return_value={'version': {'number': '9.5.4'}}):
            built = ensure_candidate_index('lab-cloned', manifest['sha256']['products.jsonl'],
                                           recipe_sha256=digest(recipe))
        self.assertEqual(built['materialisation'], 'clone')
        self.assertEqual(built['build_seconds'], 1.2)
        restored.assert_not_called()
        job.assert_not_called()

    def test_failed_recovery_uses_the_same_recipe_for_rebuild(self):
        manifest = json.loads((STATE / 'releases/retail-gb-10k-v1/manifest.json').read_text())
        recipe = current_recipe('retail-gb-10k-v1', KIND, manifest, '9.5.4', mapping_contract()[0])
        with patch('index_candidate.load_recipe', return_value=recipe), \
             patch('index_candidate._existing', return_value=None), \
             patch('index_candidate.clone_from_live', side_effect=RuntimeError('clone failed')), \
             patch('index_candidate.restore_snapshot', side_effect=ValueError('snapshot mismatch')), \
             patch('index_candidate.publish_blobs', return_value='retail-gb-10k-v1/products.jsonl'), \
             patch('index_candidate.index_job') as job, \
             patch('index_candidate.save_snapshot'), \
             patch('index_candidate._frozen_count', return_value=(True, 10000)), \
             patch('index_candidate.elastic', side_effect=lambda path, *args: \
                   {'version': {'number': '9.5.4'}} if path == '/' else None):
            built = ensure_candidate_index('lab-rebuilt', manifest['sha256']['products.jsonl'],
                                           recipe_sha256=digest(recipe))
        self.assertEqual(built['materialisation'], 'rebuild')
        self.assertEqual(len(built['recovery_errors']), 2)
        self.assertIn('snapshot mismatch', built['recovery_errors'][1])
        self.assertEqual(job.call_args.kwargs['worker_source'], recipe['indexer']['source'])

    def test_failed_finite_job_removes_partial_index(self):
        digest = json.loads((STATE / 'releases/retail-gb-10k-v1/manifest.json').read_text())['sha256']['products.jsonl']
        with patch('index_candidate._existing', return_value=None), \
             patch('index_candidate.clone_from_live', return_value=None), \
             patch('index_candidate.restore_snapshot', return_value=None), \
             patch('index_candidate.publish_blobs', return_value='retail-gb-10k-v1/products.jsonl'), \
             patch('index_candidate.index_job', side_effect=RuntimeError('job failed')), \
             patch('index_candidate.elastic') as es:
            with self.assertRaisesRegex(RuntimeError, 'job failed'):
                ensure_candidate_index('lab-failed', digest)
            es.assert_any_call('/lab-failed-idx', 'DELETE')

    def test_pinned_recipe_builds_without_reading_evolved_mapping_file(self):
        manifest = json.loads((STATE / 'releases/retail-gb-10k-v1/manifest.json').read_text())
        recipe = current_recipe('retail-gb-10k-v1', KIND, manifest, '9.5.4', mapping_contract()[0])
        recipe_sha = digest(recipe)
        with patch('index_candidate.load_recipe', return_value=recipe), \
             patch('index_candidate.clone_from_live', return_value=None), \
             patch('index_candidate.restore_snapshot', return_value=None), \
             patch('index_candidate.save_snapshot', return_value=None), \
             patch('index_candidate.mapping_contract', side_effect=AssertionError('current mapping read')), \
             patch('index_candidate._existing', return_value=None), \
             patch('index_candidate.publish_blobs', return_value='retail-gb-10k-v1/products.jsonl'), \
             patch('index_candidate.index_job'), \
             patch('index_candidate._frozen_count', return_value=(True, 10000)), \
             patch('index_candidate.elastic', side_effect=lambda path, *args: \
                   {'version': {'number': '9.5.4'}} if path == '/' else None) as es:
            built = ensure_candidate_index('lab-pinned', manifest['sha256']['products.jsonl'],
                                           recipe_sha256=recipe_sha)
        self.assertEqual(built['mapping_sha256'], digest(recipe['index_definition']))
        definition = next(call.args[2] for call in es.call_args_list if call.args[:2] == ('/lab-pinned-idx', 'PUT'))
        self.assertEqual(definition['mappings']['_meta']['index_recipe_sha256'], recipe_sha)


if __name__ == '__main__':
    unittest.main()
