import unittest
from unittest.mock import patch

import release_names as names
from gitea import GiteaHTTPError


class ReleaseNames(unittest.TestCase):
    def setUp(self):
        names._changelog.cache_clear()
        self.addCleanup(names._changelog.cache_clear)

    def test_label_identifies_version_build_and_exact_commit(self):
        text = names.label({'build_run': 207, 'fields': {
            'software_version': '1.2.3+build.207.1', 'source_sha': 'a'*40}})
        self.assertEqual(text, '1.2.3+build.207.1 · ' + 'a'*12 + ' · build 207')

    def test_changelog_is_source_pinned_and_missing_file_is_optional(self):
        with patch.object(names, 'api', return_value={'type': 'file'}) as call:
            self.assertIn('/commit/'+'a'*40+'/CHANGELOG.md', names.changelog('a'*40))
            self.assertEqual(names.changelog('a'*40), names.changelog('a'*40))
            call.assert_called_once()
        with patch.object(names, 'api', side_effect=GiteaHTTPError('GET', '/file', 404)):
            self.assertIsNone(names.changelog('b'*40))

    def test_transient_failure_does_not_permanently_hide_release_notes(self):
        with patch.object(names, 'api', side_effect=[OSError('unavailable'), {'type': 'file'}]):
            self.assertIsNone(names.changelog('a'*40))
            self.assertIsNotNone(names.changelog('a'*40))
