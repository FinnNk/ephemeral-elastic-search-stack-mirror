"""Verify source identity checks and real scoring around isolated search captures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import delivery_source_comparison as comparison
import delivery_provider as provider
from variant_gate import canonical, sha
import test_offline


class SourceComparisonTests(unittest.TestCase):
    def test_checkout_preparation_does_not_change_remote_settings(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(provider, 'STATE', Path(directory)), \
                patch.object(provider, 'git') as git, patch.object(provider, 'api') as api:
            path = provider.ensure_checkout(provider.SOURCE)
            self.assertEqual(path, Path(directory) / provider.SOURCE)
            api.assert_not_called()
            self.assertEqual(git.call_args_list[0].args, (provider.SOURCE, 'init', '-b', 'main'))
            self.assertEqual(git.call_args_list[1].args[1:4], ('remote', 'add', 'origin'))
    def test_build_selection_uses_gitea_workflow_path_not_display_title(self):
        runs = [{'id': 108, 'path': 'release.yaml@refs/heads/main',
                 'head_sha': 'a'*40, 'event': 'push', 'status': 'completed', 'conclusion': 'success'},
                {'id': 109, 'path': 'delivery.yaml@refs/heads/main',
                 'head_sha': 'a'*40, 'event': 'push', 'status': 'completed', 'conclusion': 'success'}]
        with patch.object(comparison, 'api', return_value={'workflow_runs': runs}):
            self.assertEqual(comparison.build_for('a'*40, 'push'), 108)
            with self.assertRaises(comparison.BuildPending):
                comparison.build_for('b'*40, 'pull_request')
        runs.append({**runs[0], 'id': 110, 'status': 'running', 'conclusion': None})
        with patch.object(comparison, 'api', return_value={'workflow_runs': runs}):
            with self.assertRaises(comparison.BuildPending):
                comparison.build_for('a'*40, 'push')

    def test_comment_offers_decision_only_when_required(self):
        preview = {'name': 'lab-example', 'expires_at': '2026-10-08'}
        for state in ('pass', 'approved_exception', 'blocked', 'decision_required'):
            with self.subTest(state=state), patch.object(comparison, 'api') as api:
                api.return_value = []
                comparison.comment(31, 'a'*40, 'b'*32, preview, preview,
                                   {'sha256': 'c'*64}, {'state': state})
                body = api.call_args.args[2]['body']
                self.assertIn('**Merge gate: ' + state.replace('_', ' ') + '.**', body)
                self.assertEqual('relevance-decision?operation=' in body, state == 'decision_required')

    def test_moved_baseline_rejected(self):
        pr = {'state': 'open', 'head': {'sha': 'a'*40, 'repo': {'full_name': 'elastic-agent/delivery-source'}},
              'base': {'sha': 'b'*40, 'ref': 'main'}}
        with patch.object(comparison, 'api', return_value=pr):
            comparison.current_pr(1, 'a'*40, 'b'*40)
            with self.assertRaises(ValueError):
                comparison.current_pr(1, 'a'*40, 'c'*40)

    def test_documentation_exemption_does_not_capture(self):
        payload = b':100644 100644 ' + b'a'*40 + b' ' + b'b'*40 + b' M\0README.md\0'
        request = {'pr': 1, 'source_sha': 'b'*40, 'baseline_sha': 'a'*40}
        with patch.object(comparison, 'current_pr'), patch.object(comparison, 'ensure_checkout'), \
                patch.object(comparison, 'git', return_value=payload), \
                patch.object(comparison, 'immutable_blob', side_effect=lambda container, name, data: container+'/'+name), \
                patch.object(comparison, 'status') as status, patch.object(comparison, 'run_variants') as capture:
            result = comparison.compare(request, Mock(), 'operation')
        capture.assert_not_called()
        status.assert_called_once()
        self.assertTrue(result['scope']['documentation_only'])

    def test_standard_and_extra_capture_are_scored_separately(self):
        fixture = test_offline.OfflineContractTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        query = canonical({'query_id': 'q1', 'query': 'lamp', 'country': 'GB', 'currency': 'GBP', 'filters': {}})
        catalogue = json.loads((fixture.root/'catalogue.json').read_bytes())
        query_manifest = {'kind': 'query-suite', 'content': {'sha256': sha(query), 'object': 'queries'}}
        labels = (fixture.root/'judgements.jsonl').read_bytes()
        manifest = json.loads((fixture.root/'judgement-manifest.json').read_bytes())
        manifest['dependencies']['query-suite'] = sha(query)
        manifest['content']['object'] = 'labels'
        raw_manifest = canonical(manifest)
        inputs = {'catalogue': catalogue, 'query_manifest': query_manifest, 'judgement_manifest': manifest,
                  'judgement_manifest_sha256': sha(raw_manifest), 'queries': [json.loads(query)]}
        selection = {'selected': [{'variant': 'ranker-a', 'intent': 'ranking-change'}],
                     'additional_query_sets': [{'name': 'rewrite', 'path': 'evaluation/queries/test.jsonl'}]}
        layout = {'default_variant': 'ranker-a', 'baseline_variant': 'ranker-b'}
        config = {'field_boosts': {'title': 4, 'product_type': 3, 'brand': 2, 'description': 1}}
        def source(path, revision):
            if path == 'gate/selection.json':
                return canonical(selection)
            if path == 'gate/evaluation.json':
                return canonical(layout)
            if path.startswith('configurations/'):
                name = Path(path).stem
                return canonical({'variants': {name: config}})
            return query
        def resolve(run, *args, **kwargs):
            return {'build_run': run, 'fingerprint': str(run)*64, 'fields': {
                'image': 'registry/search@sha256:' + str(run)*64, 'dataset_sha256': 'a'*64,
                'query_manifest_sha256': 'c'*64, 'judgement_manifest_sha256': sha(raw_manifest)}}
        def capture(payload, targets):
            return [{'query_id': 'q1', 'results': {name: {'variant_id': name,
                'configuration_sha256': target['configuration_sha256'], 'ids': ['p1'], 'total': 1}
                for name, target in targets.items()}}], {'worker_count': 8}
        def receipt(run):
            value = {'source_sha': str(run)*40}
            return value, {}, {}, canonical(value)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'evaluation/specs').mkdir(parents=True)
            (root/'evaluation/specs/proxy-v2.json').write_bytes((fixture.root/'specification.json').read_bytes())
            account = Mock()
            account.get_blob_client.return_value.download_blob.return_value.readall.return_value = raw_manifest
            with patch.object(comparison, 'resolve_extra', side_effect=lambda item, *args: {**item, 'resolved_references': {'resolution': {'sha256': 'f'*64, 'blob': 'runs/resolution'}}}), \
                    patch.object(comparison, 'ROOT', root), patch.object(comparison, 'source_bytes', side_effect=source), \
                    patch.object(comparison, 'from_run_bytes', side_effect=receipt), \
                    patch.object(comparison, 'resolve', side_effect=resolve), \
                    patch.object(comparison, 'preview', side_effect=lambda d: {'name': 'lab-fixture-'+str(d['build_run'])}), \
                    patch.object(comparison, 'select', return_value=inputs), \
                    patch.object(comparison, 'retained_bytes', side_effect=lambda m: query if m is query_manifest else labels), \
                    patch.object(comparison, 'service', return_value=account), patch.object(comparison, 'settings', return_value=({}, 'data')), \
                    patch.object(comparison, 'immutable_blob', side_effect=lambda c, n, data: c+'/'+n), \
                    patch.object(comparison, 'run_variants', side_effect=capture) as captures:
                result = comparison.compare({'baseline_run': 1, 'candidate_run': 2}, Mock(), 'operation')
        self.assertEqual(captures.call_count, 2)
        self.assertEqual(result['summary']['metrics']['ranker-a']['nDCG@10'], 1)
        self.assertEqual(result['summary']['combined']['unlabelled_query_count'], 1)
        self.assertEqual(result['summary']['result_similarity']['ranker-a']['jaccard_at_10'], 1)


if __name__ == '__main__':
    unittest.main()
