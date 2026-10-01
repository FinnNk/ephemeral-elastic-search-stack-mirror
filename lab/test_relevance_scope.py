from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent / 'delivery/ci'))
sys.path.insert(0, str(Path(__file__).parent))
from relevance_scope import classify
from relevance_gate import decide


def record(path, status='M', old='100644', new='100644'):
    return f':{old} {new} {"a" * 40} {"b" * 40} {status}\0{path}\0'.encode()


class RelevanceScopeTests(unittest.TestCase):
    def test_two_allowed_documents_do_not_fetch_evidence(self):
        evaluate = Mock(side_effect=AssertionError('Must not fetch evidence.'))
        result = decide(record('README.md') + record('gate/README.md'), 'a' * 40, 'b' * 40, evaluate)
        self.assertEqual(result['state'], 'evaluation_not_required')
        evaluate.assert_not_called()

    def test_mixed_code_and_documentation_needs_evaluation(self):
        evaluate = Mock(return_value={'state': 'blocked'})
        self.assertEqual(decide(record('README.md') + record('app/app.py'),
                                'a' * 40, 'b' * 40, evaluate)['state'], 'blocked')
        evaluate.assert_called_once()

    def test_sensitive_and_unrecognised_files_are_not_exempt(self):
        for path in ('app/requirements.lock', 'chart/values.yaml', 'contracts/index.json',
                     '.github/workflows/relevance.yaml', 'ci/relevance_scope.py',
                     'gate/policy.json', 'gate/selection.json', 'docs/README.md', 'README.md.bak'):
            with self.subTest(path=path):
                self.assertFalse(classify(record(path))['documentation_only'])

    def test_missing_evidence_preserves_evaluation_required_reason(self):
        result = decide(record('ci/relevance_scope.py'), 'a' * 40, 'b' * 40,
                        Mock(side_effect=ValueError('Missing report.')))
        self.assertEqual(result['state'], 'invalid')
        self.assertFalse(result['scope']['documentation_only'])
        self.assertEqual(result['reason'], 'Missing report.')

    def test_readme_symlink_or_executable_is_not_exempt(self):
        for mode in ('120000', '100755', '160000'):
            self.assertFalse(classify(record('README.md', new=mode))['documentation_only'])

    def test_deleted_code_renamed_to_readme_is_not_exempt(self):
        payload = record('app/app.py', 'D', new='000000') + record('README.md', 'A', old='000000')
        self.assertFalse(classify(payload)['documentation_only'])

    def test_empty_or_malformed_diff_cannot_get_exemption(self):
        self.assertFalse(classify(b'')['documentation_only'])
        for payload in (record('README.md')[:-1], b'README.md\0',
                        record('README.md').replace(b' M\0', b' R100\0')):
            with self.assertRaises(ValueError):
                classify(payload)

    def test_actual_git_diff_compares_pr_changes_from_merge_base(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.check_output(['git', '-C', directory,
                    '-c', 'user.name=fixture', '-c', 'user.email=fixture@lab.invalid', *args])
            git('init', '-b', 'main')
            path = Path(directory)
            (path / 'README.md').write_text('original', encoding='utf-8')
            git('add', '.'); git('commit', '-m', 'base')
            git('checkout', '-b', 'docs')
            (path / 'README.md').write_text('updated', encoding='utf-8')
            git('add', '.'); git('commit', '-m', 'docs')
            git('checkout', 'main')
            (path / 'app.py').write_text('target-only change', encoding='utf-8')
            git('add', '.'); git('commit', '-m', 'target update')
            diff = git('diff', '--raw', '--no-abbrev', '--no-renames', '-z', 'main...docs')
            self.assertEqual(classify(diff)['files'], ['README.md'])
            self.assertTrue(classify(diff)['documentation_only'])


if __name__ == '__main__':
    unittest.main()
