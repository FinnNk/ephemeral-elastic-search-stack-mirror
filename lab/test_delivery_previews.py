"""PR previews preserve build provenance and cannot become promotion inputs."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import patch

import delivery_runtime as runtime
from delivery_cli import execute, parser


class PreviewBuildTests(unittest.TestCase):
    def setUp(self):
        mapping = {'mappings': {'properties': {'title': {'type': 'text'}}}, 'settings': {}}
        self.recipe = {
            'format': 2, 'engine_version': '9.5.4', 'index_kind': 'shared',
            'product_sha256': 'a' * 64, 'catalogue_manifest_sha256': 'b' * 64,
            'index_definition': mapping,
            'indexer': {'image': 'python@sha256:' + 'c' * 64, 'source_sha256': 'd' * 64},
        }
        self.release = {
            'image': 'registry/search@sha256:' + 'e' * 64,
            'source_sha': 'f' * 40, 'bundle_sha256': '1' * 64,
            'index_contract': {'engine_version': '9.5.4', 'definitions': [mapping],
                               'indexer_image': self.recipe['indexer']['image'],
                               'indexer_source_sha256': 'd' * 64},
        }
        self.receipt = {'event_kind': 'pull_request', 'release_id': '2' * 64}
        fields = {
            'image': self.release['image'], 'source_sha': self.release['source_sha'],
            'bundle_sha256': self.release['bundle_sha256'], 'software_release_id': '2' * 64,
            'index_recipe_sha256': '3' * 64, 'dataset_release': 'esci-gb-v1',
            'dataset_sha256': 'a' * 64, 'catalogue_manifest_sha256': 'b' * 64,
            'query_manifest_sha256': '4' * 64, 'judgement_manifest_sha256': '5' * 64,
            'engine': '9.5.4', 'mapping_sha256': runtime.recipe_digest(mapping),
            'index': 'products-frozen', 'request_context': {'country': 'GB', 'currency': 'GBP'},
        }
        self.deployment = {'fields': fields, 'fingerprint': runtime.fingerprint(fields), 'build_run': 106}

    def dependencies(self, stack):
        files = {'chart/Chart.yaml': b'name: search\n'}
        stack.enter_context(patch.object(runtime, 'load', return_value=(self.release, files)))
        stack.enter_context(patch.object(runtime, 'from_run', return_value=(self.receipt, self.release, files)))
        stack.enter_context(patch.object(runtime, 'load_recipe', return_value=self.recipe))
        stack.enter_context(patch.object(runtime, 'verify_catalogue_manifest'))
        stack.enter_context(patch.object(runtime, 'validate_recipe'))
        stack.enter_context(patch.object(runtime, 'elastic', return_value={'version': {'number': '9.5.4'}}))
        stack.enter_context(patch.object(runtime, 'select_inputs'))
        stack.enter_context(patch.object(runtime, 'shared_index_name', return_value='products-frozen'))

    def test_pr_build_keeps_all_frozen_input_validation(self):
        with ExitStack() as stack:
            self.dependencies(stack)
            recipe, _ = runtime.validate_deployment(self.deployment, merged=False)
            self.assertEqual(recipe, self.recipe)
            self.deployment['fields']['image'] = 'registry/other@sha256:' + '6' * 64
            self.deployment['fingerprint'] = runtime.fingerprint(self.deployment['fields'])
            with self.assertRaisesRegex(ValueError, 'verified source release'):
                runtime.validate_deployment(self.deployment, merged=False)

    def test_pr_build_is_rejected_by_every_promotion_default(self):
        with ExitStack() as stack:
            self.dependencies(stack)
            for action in (lambda: runtime.validate_deployment(self.deployment),
                           lambda: runtime.materialise(self.deployment),
                           lambda: runtime.rendered(self.deployment, 'lab-integration')):
                with self.assertRaisesRegex(ValueError, 'merged-source push'):
                    action()

    def test_other_workflow_events_are_not_preview_builds(self):
        self.receipt['event_kind'] = 'pull_request_target'
        with ExitStack() as stack:
            self.dependencies(stack)
            with self.assertRaisesRegex(ValueError, 'source push or pull-request'):
                runtime.validate_deployment(self.deployment, merged=False)

    def test_merged_source_build_still_validates_for_promotion(self):
        self.receipt['event_kind'] = 'push'
        with ExitStack() as stack:
            self.dependencies(stack)
            recipe, _ = runtime.validate_deployment(self.deployment)
            self.assertEqual(recipe, self.recipe)

    def test_preview_renders_and_materialises_verified_pr_build(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            self.dependencies(stack)
            stack.enter_context(patch.object(runtime, 'STATE', Path(directory)))
            stack.enter_context(patch.object(runtime, 'LOCAL', Path(directory) / 'desired'))
            stack.enter_context(patch.object(runtime, 'checkout', return_value='main'))
            stack.enter_context(patch.object(runtime, 'git', return_value='preview-revision'))
            stack.enter_context(patch.object(runtime, 'k', return_value=SimpleNamespace(returncode=1)))
            stack.enter_context(patch.object(runtime, 'run', return_value=SimpleNamespace(stdout='kind: Deployment\n')))
            index = stack.enter_context(patch.object(runtime, 'ensure_shared_index'))
            stack.enter_context(patch.object(runtime, 'access'))
            application = stack.enter_context(patch.object(runtime, 'application'))
            stack.enter_context(patch.object(runtime, 'verify'))
            result = runtime.preview(self.deployment)
            self.assertEqual(result['source_sha'], self.release['source_sha'])
            self.assertEqual(result['state'], 'ready')
            index.assert_called_once()
            application.assert_called_once()
            manifest = Path(directory) / 'desired/previews' / result['name'] / 'search.yaml'
            self.assertIn(self.release['image'], manifest.read_text(encoding='utf-8'))

    def test_preview_cli_pins_named_variant_configuration(self):
        config = {'default_variant': 'ranker-a', 'variants': {'ranker-a': {
            'field_boosts': {'title': 4, 'product_type': 3, 'brand': 2, 'description': 1}}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'variants.json'
            path.write_text(json.dumps(config), encoding='utf-8')
            args = parser().parse_args(['preview', '--run', '106', '--dataset', 'esci-gb-v1',
                                       '--variant-config', str(path)])
            with patch('delivery_cli.resolve', return_value=self.deployment) as resolve, \
                    patch('delivery_cli.preview', return_value={'state': 'ready'}):
                self.assertEqual(execute(args)['state'], 'ready')
            self.assertFalse(resolve.call_args.kwargs['merged'])
            self.assertEqual(resolve.call_args.kwargs['variant_config'], config)


if __name__ == '__main__':
    unittest.main()
