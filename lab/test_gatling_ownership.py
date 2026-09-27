"""Delivery load Jobs must survive control comparison orphan clean-up."""
import unittest
from unittest.mock import patch
from pathlib import Path

import run_gatling_job


class GatlingOwnershipContract(unittest.TestCase):
    def test_orphan_cleanup_only_selects_control_jobs(self):
        class EmptyStore:
            def __init__(self, _path):
                pass

            def all_comparisons(self):
                return []

        with patch('run_gatling_job.IN_CLUSTER', True), \
             patch('lifecycle.Store', EmptyStore), \
             patch('run_gatling_job.k') as kubectl:
            self.assertTrue(run_gatling_job.cleanup_orphans())
        selector = 'app.kubernetes.io/managed-by=lab-control-gatling'
        self.assertEqual(run_gatling_job.OWNED_LABEL['app.kubernetes.io/managed-by'],
                         'lab-control-gatling')
        self.assertNotEqual(run_gatling_job.DELIVERY_LABEL['app.kubernetes.io/managed-by'],
                            run_gatling_job.OWNED_LABEL['app.kubernetes.io/managed-by'])
        self.assertEqual(len(kubectl.call_args_list), 4)
        self.assertTrue(all(selector in call.args for call in kubectl.call_args_list))

    def test_local_copy_target_allows_state_outside_checkout(self):
        root = Path('D:/lab/worktrees/experiment')
        target = Path('D:/lab/gatling-jobs/run/report')
        self.assertEqual(run_gatling_job.local_copy_target(target, root, False),
                         '../../gatling-jobs/run/report')
        self.assertEqual(run_gatling_job.local_copy_target(target, root, True), str(target))


if __name__ == '__main__':
    unittest.main()
