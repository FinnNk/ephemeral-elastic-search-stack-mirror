"""Git decision integrity, human review and post-merge recovery."""
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import Mock, patch

import relevance_decisions as decisions
from delivery_operations import Operations
import test_variant_gate as fixtures
from test_variant_gate import SOURCE, STAMP, EVIDENCE_KEY, APPROVAL_KEY
from variant_gate import attest, canonical, sha


class DecisionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        state = patch.object(decisions, 'STATE', Path(directory.name))
        state.start()
        self.addCleanup(state.stop)
        self.fixture = fixtures.VariantGateTests()
        self.fixture.setUp()
        self.fixture.report['source_context'] = {'pr': 3, 'source_sha': SOURCE, 'baseline_sha': 'b'*40}
        self.fixture.report['frozen_inputs'] = {'build_receipt': {'blob': 'runs/build.json',
                                                               'sha256': sha(self.fixture.build)}}
        self.request = {'kind': 'request-exception', 'pr': 3, 'source_sha': SOURCE,
                        'variant': 'ranker-a', 'reason': 'Accept the measured loss for a security fix.'}
        self.report = canonical(self.fixture.report)
        self.evidence = attest(self.report, SOURCE, self.fixture.build, EVIDENCE_KEY, STAMP)
        self.keys = patch.object(decisions, 'operator_key', side_effect=lambda name:
            EVIDENCE_KEY if 'EVIDENCE' in name else APPROVAL_KEY)
        self.keys.start()
        self.addCleanup(self.keys.stop)

    def frozen(self):
        blob = Mock()
        blob.get_blob_client.return_value.download_blob.return_value.readall.return_value = self.fixture.build
        def nexus(path, **kwargs):
            return self.report if path.endswith('report.json') else canonical(self.evidence)
        with patch.object(decisions, 'nexus_request', side_effect=nexus), \
                patch.object(decisions, 'service', return_value=blob), \
                patch.object(decisions, 'source_bytes', return_value=canonical(self.fixture.selection)), \
                patch.object(decisions, 'current_pr'):
            return decisions.frozen(self.request)

    def record(self):
        bindings, *inputs = self.frozen()
        decision = {'kind': 'relevance-decision', 'schema_version': 1, **bindings,
                    'variant': 'ranker-a', 'reason': self.request['reason'], 'reviewer': 'finnnk',
                    'requested_by': {'issuer': 'fixture', 'subject': 'human'}, 'requested_at': STAMP}
        payload = canonical(decision)
        path = 'decisions/relevance/' + sha(payload) + '.json'
        pr = {'number': 7, 'state': 'open', 'merged': False, 'base': {'ref': 'main', 'sha': 'b'*40},
              'head': {'ref': decisions.PREFIX + sha(payload)[:16], 'sha': 'c'*40},
              'user': {'login': 'elastic-agent'}}
        return pr, path, payload, decision, *inputs

    def test_bound_evidence_preserves_measured_loss(self):
        value = self.frozen()[0]
        self.assertEqual(value['measured']['delta'], -0.02)
        self.assertEqual(value['report_sha256'], sha(self.report))
        self.assertEqual(value['build_receipt_sha256'], sha(self.fixture.build))

    def test_request_creates_a_single_git_record_without_changing_main(self):
        repo = decisions.STATE / 'delivery-state'
        repo.mkdir()
        remote = decisions.STATE / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(remote)], capture_output=True, check=True)
        subprocess.run(['git', 'init', '-b', 'main', str(repo)], capture_output=True, check=True)
        def git(_repo, *args, raw=False):
            result = subprocess.run(['git', '-C', str(repo), '-c', 'user.name=elastic-agent',
                '-c', 'user.email=agent@fixture.invalid', *args], capture_output=True, check=True)
            return result.stdout if raw else result.stdout.decode().strip()
        git('delivery-state', 'remote', 'add', 'origin', str(remote))
        (repo/'README.md').write_text('Fixture desired state', encoding='utf-8')
        git('delivery-state', 'add', '.')
        git('delivery-state', 'commit', '-m', 'Initial fixture')
        base = git('delivery-state', 'rev-parse', 'HEAD')
        git('delivery-state', 'push', '-u', 'origin', 'main')
        def pull(_repo, branch, title, body):
            head = git('delivery-state', 'rev-parse', branch)
            return {'number': 7, 'head': {'sha': head}}
        with patch.object(decisions, 'checkout'), patch.object(decisions, 'git', side_effect=git), \
                patch.object(decisions, 'pull_request', side_effect=pull), \
                patch.object(decisions, 'frozen', return_value=self.frozen()):
            result = decisions.request_decision(self.request,
                {'username': 'finnnk', 'is_admin': True, 'issuer': 'fixture', 'subject': 'human'})
        self.assertEqual(git('delivery-state', 'rev-parse', 'HEAD'), base)
        changed = git('delivery-state', 'diff', '--name-only', base, result['head_sha']).splitlines()
        self.assertEqual(len(changed), 1)
        self.assertTrue(changed[0].startswith('decisions/relevance/'))
        payload = git('delivery-state', 'show', result['head_sha']+':'+changed[0], raw=True)
        self.assertEqual(payload, canonical(result['decision']))
        self.assertEqual(result['decision']['reviewer'], 'finnnk')

    def test_blocked_variant_cannot_be_accepted(self):
        self.fixture.report['delta_from_baseline']['ranker-a']['nDCG@10'] = -0.2
        self.fixture.report['metrics']['ranker-a']['nDCG@10'] = 0.5
        self.report = canonical(self.fixture.report)
        self.evidence = attest(self.report, SOURCE, self.fixture.build, EVIDENCE_KEY, STAMP)
        with self.assertRaisesRegex(ValueError, 'bounded exception'):
            self.frozen()

    def test_machine_cannot_request_human_decision(self):
        for identity in ({'username': 'actions', 'is_admin': True, 'is_delivery_service': True},
                         {'username': 'reader', 'is_admin': False}):
            with self.assertRaisesRegex(ValueError, 'human'), patch.object(decisions, 'frozen') as frozen:
                decisions.request_decision(self.request, identity)
            frozen.assert_not_called()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'human'):
                Operations(Path(folder)/'ops.db').submit(self.request,
                    {'username': 'actions', 'is_delivery_service': True, 'is_admin': False}, 'request')

    def test_human_merged_decisions_are_queued_once(self):
        pr = {'number': 7, 'head': {'ref': decisions.PREFIX+'fixture'}, 'merged': True}
        store = Operations(decisions.STATE/'operations.db')
        with patch.object(decisions, 'api', side_effect=lambda path: [pr] if 'state=closed' in path else []), \
                patch('delivery_operations.Operations', return_value=store):
            first = decisions.watch_decisions()[0]
            second = decisions.watch_decisions()[0]
        self.assertEqual(first['operation'], second['operation'])
        self.assertEqual(store.next()['request'], {'kind': 'merge-exception', 'pr': 7})
        self.assertIsNone(store.next())

    def test_receipts_for_two_variants_use_distinct_immutable_paths(self):
        with patch('nexus.publish') as publish:
            for variant, digest in (('ranker-a', 'c'*64), ('ranker-c', 'd'*64)):
                decisions.publish_approval({'source_sha': SOURCE, 'variant': variant,
                    'decision': {'file_sha256': digest}})
        paths = [call.args[0] for call in publish.call_args_list]
        self.assertIn('variant-gates/'+SOURCE+'/approvals/ranker-a.json', paths)
        self.assertIn('variant-gates/'+SOURCE+'/approvals/ranker-c.json', paths)

    def test_only_one_exact_decision_file_is_allowed(self):
        pr, path, payload, decision, *inputs = self.record()
        def git(*args, **kwargs):
            if args[1] == 'diff':
                return 'A\t' + path
            if args[1] == 'show':
                return payload
            return 'b'*40
        with patch.object(decisions, 'api', return_value=pr), patch.object(decisions, 'git', side_effect=git), \
                patch.object(decisions, 'frozen', return_value=({key: decision[key] for key in self.frozen()[0]}, *inputs)):
            self.assertEqual(decisions.inspect(7)[2], payload)
        for changes in ('A\t'+path+'\nM\ttargets/production/deployment.json', 'M\t'+path):
            with patch.object(decisions, 'api', return_value=pr), \
                    patch.object(decisions, 'git', side_effect=lambda *args, **kwargs:
                        changes if args[1]=='diff' else 'b'*40), self.assertRaisesRegex(ValueError, 'exactly one'):
                decisions.inspect(7)

    def test_latest_exact_named_review_is_required(self):
        pr, _, _, decision, *_ = self.record()
        review = {'id': 10, 'user': {'login': 'finnnk'}, 'state': 'APPROVED', 'commit_id': 'c'*40,
                  'submitted_at': STAMP, 'dismissed': False}
        for permission, reviews, passed in (
                ('owner', [review], True), ('admin', [review], True), ('write', [review], False),
                ('admin', [review, {**review, 'id': 11, 'state': 'REQUEST_CHANGES'}], False),
                ('admin', [{**review, 'commit_id': 'd'*40}], False),
                ('admin', [{**review, 'dismissed': True}], False),
                ('admin', [{**review, 'user': {'login': 'someone-else'}}], False)):
            with self.subTest(permission=permission, reviews=reviews), patch.object(decisions, 'api',
                    side_effect=[{'permission': permission}, reviews]):
                if passed:
                    self.assertEqual(decisions.approved_review(pr, decision)['id'], 10)
                else:
                    with self.assertRaises(ValueError):
                        decisions.approved_review(pr, decision)

    def test_stale_policy_or_metrics_reject_record(self):
        pr, path, payload, decision, *inputs = self.record()
        bindings = {key: decision[key] for key in self.frozen()[0]}
        for field in ('report_sha256', 'policy_sha256', 'selection_sha256', 'baseline_sha', 'build_receipt_sha256'):
            with self.subTest(field=field), patch.object(decisions, 'api', return_value=pr), \
                    patch.object(decisions, 'git', side_effect=lambda *args, **kwargs:
                        'A\t'+path if args[1]=='diff' else payload if args[1]=='show' else 'b'*40), \
                    patch.object(decisions, 'frozen', return_value=({**bindings, field: 'changed'}, *inputs)), \
                    self.assertRaisesRegex(ValueError, 'no longer matches'):
                decisions.inspect(7)

    def test_resume_after_merge_issues_git_bound_receipt_without_remerging(self):
        record = list(self.record())
        record[0] = {**record[0], 'merged': True, 'state': 'closed', 'merge_commit_sha': 'd'*40}
        review = {'id': 10, 'submitted_at': STAMP}
        with patch.object(decisions, 'checkout'), patch.object(decisions, 'inspect', return_value=record), \
                patch.object(decisions, 'approved_review', return_value=review), \
                patch.object(decisions, 'git', return_value=record[2]), patch.object(decisions, 'frozen'), \
                patch.object(decisions, 'publish_approval') as publish, \
                patch.object(decisions, 'recheck', return_value={'gate': {'state': 'approved_exception'}}), \
                patch.object(decisions, 'merge_demo') as merge:
            result = decisions.complete(7, lambda _: None, 'fixture')
        merge.assert_not_called()
        receipt = publish.call_args.args[0]
        self.assertEqual(receipt['decision']['merge_sha'], 'd'*40)
        self.assertEqual(receipt['reviewer'], 'finnnk')
        self.assertEqual(receipt['report_sha256'], sha(self.report))
        self.assertEqual(result['gate']['state'], 'approved_exception')

    def test_wrong_merged_bytes_prevent_signing(self):
        record = list(self.record())
        record[0] = {**record[0], 'merged': True, 'merge_commit_sha': 'd'*40}
        with patch.object(decisions, 'checkout'), patch.object(decisions, 'inspect', return_value=record), \
                patch.object(decisions, 'approved_review', return_value={'id': 1}), \
                patch.object(decisions, 'git', return_value=b'changed'), patch.object(decisions, 'publish_approval') as publish:
            with self.assertRaisesRegex(ValueError, 'Merged decision bytes'):
                decisions.complete(7, lambda _: None, 'fixture')
        publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
