"""Named query suites never advertise unavailable or incompatible curated labels."""
import unittest
from unittest.mock import patch
from azure.core.exceptions import ResourceNotFoundError
import query_suites


class QuerySuitesTests(unittest.TestCase):
    def test_unpublished_alternatives_leave_standard_choices(self):
        with patch.object(query_suites, 'fetch_manifest', side_effect=ResourceNotFoundError()):
            rows = query_suites.choices()
        self.assertEqual(len(rows), len(query_suites.DEFAULTS))
        self.assertTrue(all(row['id'].endswith('-standard') for row in rows))

    def test_curated_choices_require_matching_judgements(self):
        def manifest(kind, sha):
            if kind == 'judgement-set':
                return {'dependencies': {'catalogue': 'catalogue', 'query-suite': 'queries'}}
            return {'content': {'sha256': 'catalogue' if kind == 'catalogue' else 'queries'}}
        with patch.object(query_suites, 'fetch_manifest', side_effect=manifest):
            rows = query_suites.choices()
        self.assertEqual(len(rows), len(query_suites.DEFAULTS) + 2)
        with patch.object(query_suites, 'fetch_manifest', return_value={
                'content': {'sha256': 'x'}, 'dependencies': {}}):
            with self.assertRaisesRegex(ValueError, 'incompatible'):
                query_suites.choices()
