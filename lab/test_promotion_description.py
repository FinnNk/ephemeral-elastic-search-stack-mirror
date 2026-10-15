import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from delivery.ci.release import canonical, digest
from delivery_json import write_json
from promotion_description import description


class HumanReview(unittest.TestCase):
    def test_git_formatting_preserves_semantic_identity(self):
        value = {'format': 1, 'fields': {'version': '1.2.3', 'name': 'Catalogue — GB'},
                 'evidence': {'sha256': 'a' * 64, 'blob': 'runs/example'}}
        before = digest(canonical(value))
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'proposal.json'
            write_json(path, value)
            content = path.read_bytes()
            self.assertTrue(content.endswith(b'\n'))
            self.assertNotIn(b'\r', content)
            self.assertIn(b'\n  "fields": {\n', content)
            self.assertEqual(digest(canonical(json.loads(content))), before)

    def test_review_leads_with_names_and_retains_hashes_in_details(self):
        fields = {'source_sha': 's' * 40, 'software_release_id': 'r' * 64,
                  'software_version': '1.2.3+build.184.1', 'dataset_release': 'esci-gb-v1',
                  'engine': '9.5.4', 'variant_config_json': json.dumps({'variants': {
                      'ranker-a': {'field_boosts': {'title': 4, 'brand': 2}}}})}
        report = {'baseline_build_run': 158, 'baseline_variant': 'default',
                  'baseline_pin': {'settings': {'field_boosts': {'title': 3}}},
                  'checks': [{'variant': 'ranker-a', 'intent': 'ranking-change', 'state': 'pass'}]}
        text = description('integration', {'build_run': 184, 'fingerprint': 'new', 'fields': fields},
                           {'build_run': 158, 'fingerprint': 'old'},
                           {'sha256': 'a' * 64, 'blob': 'runs/hash/evidence.json'}, report)
        lead, details = text.split('<details>')
        self.assertIn('Promote build 184 to Integration', lead)
        self.assertIn('1.2.3+build.184.1', lead)
        self.assertIn('1.2.3+build.184.1 · ' + 's' * 12, lead)
        self.assertIn('title 4', lead)
        self.assertNotIn('s' * 40, lead)
        self.assertIn('s' * 40, details)
        self.assertIn('Version not recorded', lead)
        self.assertIn('Deploy approved proposal', lead)
