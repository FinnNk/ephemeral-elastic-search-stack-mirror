"""Exact source pins, one dispatch, protected receipts and preview-only deployment."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import preview_build as builds
from delivery_operations import Operations, execute_next, validate
from delivery_release import validate_receipt
from delivery.ci.versioning import build_version

SOURCE, WORKFLOW, IDENTIFIER = 'a' * 40, 'b' * 40, 'c' * 32
HUMAN = {'username': 'reviewer', 'is_admin': True, 'is_reader': False,
         'issuer': 'issuer', 'subject': 'reviewer'}


def run(**changes):
    return {'id': 250, 'run_attempt': 1, 'head_sha': WORKFLOW,
            'display_title': 'Preview ' + SOURCE + ' ' + IDENTIFIER,
            'path': 'build-preview.yaml@refs/heads/main', 'event': 'workflow_dispatch',
            'status': 'completed', 'conclusion': 'success', **changes}


def receipt():
    return {'source_sha': SOURCE, 'workflow_source_sha': WORKFLOW,
            'preview_request_id': IDENTIFIER, 'event_kind': 'workflow_dispatch',
            'source_repository': 'elastic-agent/delivery-source', 'image': 'image@sha256:' + 'd' * 64,
            'run_id': '250', 'run_attempt': '1', 'version': '1.2.3-preview.250.1'}


def release():
    return {'source_sha': SOURCE, 'source_repository': 'elastic-agent/delivery-source',
            'image': receipt()['image'], 'version': '1.2.3-preview.250.1', 'declared_version': '1.2.3'}


class PreviewBuildTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.state = Path(self.folder.name)
        self.addCleanup(patch.stopall)
        patch.object(builds, 'STATE', self.state).start()
        self.request = {'kind': 'build-preview', 'source_ref': 'feature/search',
                        '_preview_source_sha': SOURCE, '_preview_workflow_sha': WORKFLOW}

    def provider(self, rows=None):
        def api(path, method='GET', body=None):
            if '/actions/runs?' in path:
                return {'workflow_runs': rows or []}
            if path.endswith('/branches/main'):
                return {'commit': {'id': WORKFLOW}}
            if path.endswith('/dispatches'):
                return None
            raise AssertionError(path)
        return Mock(side_effect=api)

    def test_resolves_branch_once_before_queue_and_does_not_follow_it_later(self):
        store = Operations(self.state / 'ops.sqlite3')
        with patch.object(builds, 'prepare', return_value={
                '_preview_source_sha': SOURCE, '_preview_workflow_sha': WORKFLOW}) as prepare:
            first = store.submit({'kind': 'build-preview', 'source_ref': 'feature/search'}, HUMAN, 'stable')
            prepare.return_value['_preview_source_sha'] = 'd' * 40
            again = store.submit({'kind': 'build-preview', 'source_ref': 'feature/search'}, HUMAN, 'stable')
        prepare.assert_called_once()
        self.assertEqual(again['request']['_preview_source_sha'], SOURCE)
        self.assertEqual(first['id'], again['id'])
        self.assertTrue(again['submission_reused'])

    def test_rejects_machine_reader_and_non_administrator(self):
        store = Operations(self.state / 'ops.sqlite3')
        for identity in ({**HUMAN, 'is_delivery_service': True},
                         {**HUMAN, 'is_reader': True}, {**HUMAN, 'is_admin': False}):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                store.submit({'kind': 'build-preview', 'source_ref': 'main'}, identity, 'denied')

    def test_rejects_revision_expressions_urls_and_private_payload_fields(self):
        for ref in ('main~1', '-main', '../main', 'https://host/repo', 'a..b', 'branch.lock',
                    'a//b', 'main:app', '', 'x' * 201, 'name with spaces'):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                validate({'kind': 'build-preview', 'source_ref': ref})
        with self.assertRaises(ValueError):
            validate(self.request)
        for ref in ('feature/search', SOURCE, SOURCE.upper(), 'release-1.2.3'):
            validate({'kind': 'build-preview', 'source_ref': ref})

    def test_full_sha_resolves_in_fixed_repository(self):
        with patch.object(builds, 'api', side_effect=[{'sha': SOURCE},
                 {'commit': {'id': WORKFLOW}}, {'type': 'file'}]) as api:
            self.assertEqual(builds.prepare(SOURCE.upper()), {
                '_preview_source_sha': SOURCE, '_preview_workflow_sha': WORKFLOW})
        self.assertIn('/delivery-source/git/commits/' + SOURCE, api.call_args_list[0].args[0])
        self.assertIn('?ref=' + WORKFLOW, api.call_args_list[-1].args[0])

    def test_dispatch_is_not_repeated_while_waiting(self):
        api = self.provider()
        with patch.object(builds, 'api', api):
            first = builds.advance(self.request, IDENTIFIER, Mock())
            second = builds.advance(self.request, IDENTIFIER, Mock())
        self.assertTrue(first['waiting'] and second['waiting'])
        mutations = [c for c in api.call_args_list if len(c.args) > 1 and c.args[1] == 'POST']
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0].args[2], {'ref': 'main', 'inputs': {
            'source_sha': SOURCE, 'request_id': IDENTIFIER}})

    def test_unknown_dispatch_outcome_retains_intent_and_never_blindly_retries(self):
        normal = self.provider()
        def api(path, method='GET', body=None):
            if method == 'POST':
                raise TimeoutError('private transport detail')
            return normal(path, method, body)
        with patch.object(builds, 'api', side_effect=api) as remote:
            with self.assertRaises(builds.PreviewBuildError) as failure:
                builds.advance(self.request, IDENTIFIER, Mock())
            self.assertNotIn('private transport', str(failure.exception))
            self.assertTrue(builds.advance(self.request, IDENTIFIER, Mock())['waiting'])
        self.assertEqual(sum(len(c.args) > 1 and c.args[1] == 'POST' for c in remote.call_args_list), 1)

    def test_main_movement_is_detected_before_dispatch(self):
        api = self.provider()
        def changed(path, method='GET', body=None):
            if path.endswith('/branches/main'):
                return {'commit': {'id': 'e' * 40}}
            return api(path, method, body)
        with patch.object(builds, 'api', side_effect=changed), self.assertRaises(builds.PreviewBuildError):
            builds.advance(self.request, IDENTIFIER, Mock())
        self.assertFalse((self.state / 'preview-builds' / (IDENTIFIER + '.json')).exists())

    def test_failed_build_keeps_build_link_and_does_not_create_environment(self):
        with patch.object(builds, 'api', self.provider([run(conclusion='failure')])), \
                patch('delivery_runtime.preview') as preview:
            with self.assertRaises(builds.PreviewBuildError) as failure:
                builds.advance(self.request, IDENTIFIER, Mock())
        self.assertTrue(failure.exception.preview_result['build_url'].endswith('/runs/250'))
        preview.assert_not_called()

    def test_invalid_build_evidence_keeps_build_link(self):
        with patch.object(builds, 'api', self.provider([run()])), \
                patch('delivery_release.from_run', side_effect=ValueError('private validation detail')), \
                patch('delivery_runtime.preview') as preview:
            with self.assertRaises(builds.PreviewBuildError) as failure:
                builds.advance(self.request, IDENTIFIER, Mock())
        self.assertTrue(failure.exception.preview_result['build_url'].endswith('/runs/250'))
        self.assertNotIn('private validation detail', str(failure.exception))
        preview.assert_not_called()

    def test_success_uses_requested_variant_config_and_cannot_resolve_as_merged(self):
        config = {'default_variant': 'ranker-a', 'variants': {'ranker-a': {'field_boosts': {'title': 4}}}}
        with patch.object(builds, 'api', self.provider([run()])), \
                patch('delivery_release.from_run', return_value=(receipt(), release(), {})), \
                patch('delivery_variant_selection.source_selection', return_value={'configuration': config}), \
                patch('delivery_runtime.resolve', return_value={'frozen': True}) as resolve, \
                patch('delivery_runtime.preview', return_value={'name': 'lab-delivery-run-250-abcdef01',
                    'expires_at': '2026-10-19T00:00:00Z'}) as preview:
            result = builds.advance(self.request, IDENTIFIER, Mock())
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(result['version'], '1.2.3-preview.250.1')
        resolve.assert_called_once_with(250, 'esci-gb-v1', None, merged=False, variant_config=config)
        self.assertIn('lab-delivery-run-250', result['browser_url'])
        preview.assert_called_once()
        with patch('delivery_runtime.from_run', return_value=(receipt(), release(), {})), \
                self.assertRaisesRegex(ValueError, 'merged-source'):
            from delivery_runtime import resolve as real_resolve
            real_resolve(250)

    def test_worker_yields_while_building_and_keeps_result(self):
        store = Operations(self.state / 'ops.sqlite3')
        with patch.object(builds, 'prepare', return_value={
                '_preview_source_sha': SOURCE, '_preview_workflow_sha': WORKFLOW}):
            operation = store.submit({'kind': 'build-preview', 'source_ref': 'main'}, HUMAN, 'queued')
        with patch('delivery_operations.Operations', return_value=store), \
                patch.object(builds, 'advance', return_value={
                    'waiting': True, 'progress': 'Build 250 is running', 'build_run': 250}):
            result = execute_next()
        self.assertEqual(result['id'], operation['id'])
        self.assertEqual(result['state'], 'queued')
        self.assertEqual(result['result']['build_run'], 250)

    def test_receipt_binds_candidate_workflow_run_request_and_version(self):
        validate_receipt(run(), receipt(), release())
        for changed in (run(path='other.yaml@refs/heads/main'), run(head_sha='e' * 40),
                        run(display_title='Preview ' + 'e' * 40 + ' ' + IDENTIFIER),
                        run(display_title='Preview ' + SOURCE + ' ' + 'e' * 32)):
            with self.subTest(run=changed), self.assertRaises(ValueError):
                validate_receipt(changed, receipt(), release())
        self.assertEqual(build_version('1.2.3', 'workflow_dispatch', 250, 1), '1.2.3-preview.250.1')


if __name__ == '__main__':
    unittest.main()
