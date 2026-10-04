"""Preserve delivery exclusivity and never repeat a completed merge."""
import json
import socket
import unittest
from unittest.mock import patch

import delivery_promote as promote
from delivery_runtime import writer


class DeliveryFeedbackTests(unittest.TestCase):
    def test_busy_wait_is_bounded_and_does_not_enter(self):
        with socket.socket() as lock:
            lock.bind(('127.0.0.1', 18086))
            with self.assertRaisesRegex(RuntimeError, 'wait expired'):
                with writer(timeout=0):
                    self.fail('Entered another operation slot')

    def test_merged_promotion_only_verifies_matching_target(self):
        deployment = {'fingerprint': 'frozen'}
        pr = {'merged': True, 'base': {'ref': 'main'},
              'head': {'sha': 'a' * 40, 'ref': 'promote/staging-example'}}
        proposal = {'target': 'staging', 'deployment': deployment}
        def git(repo, *args):
            if args[0] == 'show':
                return json.dumps(proposal if ':proposals/' in args[1] else deployment)
            return ''
        with patch.object(promote, 'api', return_value=pr), \
                patch.object(promote, 'checkout'), patch.object(promote, 'git', side_effect=git), \
                patch.object(promote, 'read_target', return_value=deployment), \
                patch.object(promote, 'verify_target', return_value={'state': 'verified'}) as verify, \
                patch.object(promote, 'merge_demo') as merge:
            self.assertEqual(promote.merge_reviewed(15)['merge_state'], 'already-merged')
            verify.assert_called_once_with('staging', deployment)
            merge.assert_not_called()

    def test_target_advanced_never_reapplies_old_deployment(self):
        pr = {'merged': True, 'base': {'ref': 'main'},
              'head': {'sha': 'a' * 40, 'ref': 'promote/staging-example'}}
        proposal = {'target': 'staging', 'deployment': {'fingerprint': 'older'}}
        with patch.object(promote, 'api', return_value=pr), patch.object(promote, 'checkout'), \
                patch.object(promote, 'git', side_effect=['', json.dumps(proposal), json.dumps(proposal['deployment'])]), \
                patch.object(promote, 'read_target', return_value={'fingerprint': 'newer'}), \
                patch.object(promote, 'verify_target') as verify, patch.object(promote, 'merge_demo') as merge:
            self.assertEqual(promote.merge_reviewed(15)['state'], 'already-merged')
            verify.assert_not_called()
            merge.assert_not_called()


if __name__ == '__main__':
    unittest.main()
