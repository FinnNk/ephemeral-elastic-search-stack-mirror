import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import setup_relevance_gate as setup


class RelevanceProtectionTests(unittest.TestCase):
    def test_new_lab_source_requires_checks_without_author_approval(self):
        with patch.object(setup, 'git', side_effect=self.deployed_file), \
                patch.object(setup, 'api', side_effect=[[], None]) as api:
            setup.install()
        rule = api.call_args.args[2]
        self.assertEqual(rule['required_approvals'], 0)
        self.assertFalse(rule['enable_push'])
        self.assertEqual(len(rule['status_check_contexts']), 3)
        self.assertIn('relevance-lab/merge-gate', rule['status_check_contexts'])

    def deployed_file(self, repository, *args):
        if args[0] == 'fetch':
            return ''
        source_path = args[1].split(':', 1)[1]
        mapping = {'.github/workflows/relevance.yaml': 'lab/delivery/workflows/relevance.yaml',
                   '.github/workflows/release.yaml': 'lab/delivery/workflows/release.yaml',
                   '.github/workflows/delivery.yaml': 'lab/delivery/workflows/delivery.yaml',
                   'gate/evaluation.json': 'lab/delivery/bootstrap/gate/evaluation.json',
                   'ci/variant_gate.py': 'lab/variant_gate.py',
                   'gate/policy.json': 'lab/delivery/policies/variant-merge-v1.json'}
        path = mapping.get(source_path, 'lab/delivery/' + source_path)
        return (setup.ROOT / path).read_text(encoding='utf-8').strip()

    def test_unaccepted_source_does_not_change_protection(self):
        with patch.object(setup, 'git', return_value='wrong source'), patch.object(setup, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'Merge the accepted gate implementation'):
                setup.install()
            api.assert_not_called()

    def test_existing_review_and_check_requirements_are_preserved(self):
        current = {'rule_name': 'main', 'required_approvals': 2,
                   'status_check_contexts': ['Additional check'], 'require_signed_commits': True}
        with patch.object(setup, 'git', side_effect=self.deployed_file), \
             patch.object(setup, 'api', side_effect=[[current], None]) as api:
            setup.install()
        _, method, rule = api.call_args.args
        self.assertEqual(method, 'PATCH')
        self.assertEqual(rule['required_approvals'], 2)
        self.assertTrue(rule['require_signed_commits'])
        self.assertEqual(len(rule['status_check_contexts']), 4)
        self.assertIn('Additional check', rule['status_check_contexts'])
        self.assertTrue(rule['block_admin_merge_override'])
        self.assertFalse(rule['enable_push'])

    def test_unaccepted_policy_does_not_change_protection(self):
        def deployed(repository, *args):
            if args[0] == 'show' and args[1].endswith(':gate/policy.json'):
                return 'different gate policy'
            return self.deployed_file(repository, *args)

        with patch.object(setup, 'git', side_effect=deployed), patch.object(setup, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'gate/policy.json'):
                setup.install()
            api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
