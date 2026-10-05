"""Protect destination history when configuring native mirrors."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import github_mirror as mirror


class MirrorSetup(unittest.TestCase):
    def test_populated_destination_is_rejected_before_creating_mirror(self):
        with patch.object(mirror, 'guard'), patch.object(mirror, 'api', return_value=[]) as api, \
                patch.object(mirror, 'git', return_value=SimpleNamespace(stdout='abc refs/heads/main\n')) as git:
            with self.assertRaisesRegex(ValueError, 'not empty'):
                mirror.add('delivery-source', 'https://github.com/FinnNk/new-mirror.git', 1, 2)
            api.assert_called_once_with('/repos/elastic-agent/delivery-source/push_mirrors')
            self.assertEqual(git.call_count, 1)

    def test_empty_destination_uses_native_sync_and_scoped_helper(self):
        target = 'https://github.com/FinnNk/new-mirror.git'
        with patch.object(mirror, 'guard'), patch.object(mirror, 'api', side_effect=[[], {'remote_name': 'mirror'}, None]) as api, \
                patch.object(mirror, 'git', return_value=SimpleNamespace(stdout='')) as git:
            self.assertEqual(mirror.add('delivery-source', target, 1, 2)['remote_name'], 'mirror')
            self.assertTrue(api.call_args_list[1].args[2]['sync_on_commit'])
            self.assertEqual(api.call_args_list[2].args, ('/repos/elastic-agent/delivery-source/push_mirrors-sync', 'POST'))
            self.assertIn('credential.' + target + '.helper', git.call_args_list[1].args)

    def test_repeat_setup_leaves_existing_mirror_unchanged(self):
        row = {'remote_address': 'https://github.com/FinnNk/new-mirror.git', 'remote_name': 'mirror'}
        with patch.object(mirror, 'guard'), patch.object(mirror, 'api', return_value=[row]) as api, \
                patch.object(mirror, 'git') as git:
            self.assertEqual(mirror.add('delivery-source', row['remote_address'], 1, 2), row)
            self.assertEqual(api.call_count, 1)
            git.assert_not_called()

    def test_credentials_and_paths_cannot_be_injected(self):
        for target in ['https://secret@github.com/FinnNk/repo.git', 'https://elsewhere.example/repo.git', 'ssh://git@github.com/x/y']:
            with self.assertRaises(ValueError):
                mirror.destination(target)
        with self.assertRaises(ValueError):
            mirror.repository('../repo')
        with self.assertRaises(ValueError):
            mirror.helper(0, 1)


if __name__ == '__main__':
    unittest.main()
