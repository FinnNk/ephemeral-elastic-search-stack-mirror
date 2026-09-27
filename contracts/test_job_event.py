"""The finite Job log contract excludes content and credentials."""

from contextlib import redirect_stdout
from io import StringIO
import json
import time
import unittest

from job_event import emit


class JobEventTests(unittest.TestCase):
    def test_only_safe_immutable_fields_are_emitted(self):
        output = StringIO()
        with redirect_stdout(output):
            emit('offline-evaluator', 'evaluation.score', 'complete', time.monotonic(),
                 report_sha256='a' * 64, query='private words',
                 report_blob='runs/private.json',
                 observation_sha256='invalid')
        event = json.loads(output.getvalue())
        self.assertEqual(event['report_sha256'], 'a' * 64)
        self.assertNotIn('query', event)
        self.assertNotIn('report_blob', event)
        self.assertNotIn('observation_sha256', event)
        self.assertGreaterEqual(event['duration_ms'], 0)


if __name__ == '__main__':
    unittest.main()
