import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, 'lab')
from promotion_policy import validate


class PromotionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 27, 14, tzinfo=timezone.utc)
        self.policy = json.loads(Path('lab/delivery/policies/observation-evidence-v1.json').read_text())
        self.expected = {key: chr(ord('a') + index) * 64 for index, key in enumerate((
            'baseline_fingerprint', 'candidate_fingerprint', 'catalogue_sha256',
            'query_suite_sha256', 'observation_sha256', 'judgement_sha256',
            'judgement_manifest_sha256', 'specification_sha256', 'evaluator_sha256'))}
        self.report = {'kind': 'offline-evaluation-report', 'schema_version': 1,
                       'complete': True, 'query_count': 50, **self.expected,
                       'observation_captured_at': (self.now - timedelta(hours=1)).isoformat(),
                       'evaluated_at': self.now.isoformat(),
                       'metrics': {'baseline': {'nDCG@10': .1, 'Judged@10': .2},
                                   'candidate': {'nDCG@10': .2, 'Judged@10': .2}},
                       'coverage': {'baseline': {'fraction': .2},
                                    'candidate': {'fraction': .2}}}

    def check(self):
        return validate(json.dumps(self.report).encode(), json.dumps(self.policy).encode(),
                        self.expected, now=self.now)

    def test_exact_report_passes_but_still_requires_review(self):
        self.assertTrue(self.check()['review_required'])

    def test_other_query_suite_cannot_authorise_proposal(self):
        self.report['query_suite_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'another exact input'):
            self.check()

    def test_stale_capture_fails_even_with_fresh_scoring(self):
        self.report['observation_captured_at'] = (self.now - timedelta(hours=73)).isoformat()
        with self.assertRaisesRegex(ValueError, 'capture evidence'):
            self.check()


if __name__ == '__main__':
    unittest.main()
