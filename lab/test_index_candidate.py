import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, 'research/platform-spike')
from common import STATE
from index_candidate import ensure_candidate_index


class CandidateIndexRecovery(unittest.TestCase):
    def test_failed_finite_job_removes_partial_index(self):
        digest = json.loads((STATE / 'releases/retail-gb-10k-v1/manifest.json').read_text())['sha256']['products.jsonl']
        with patch('index_candidate._existing', return_value=None), \
             patch('index_candidate.publish_blobs', return_value='retail-gb-10k-v1/products.jsonl'), \
             patch('index_candidate.index_job', side_effect=RuntimeError('job failed')), \
             patch('index_candidate.elastic') as es:
            with self.assertRaisesRegex(RuntimeError, 'job failed'):
                ensure_candidate_index('lab-failed', digest)
            es.assert_any_call('/lab-failed-idx', 'DELETE')


if __name__ == '__main__':
    unittest.main()
