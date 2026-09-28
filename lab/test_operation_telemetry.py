import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import operation_telemetry
from operation_telemetry import GOOD_TERMINAL_STATES, correlation, operation


class OperationTelemetryContract(unittest.TestCase):
    def test_job_correlation_is_optional(self):
        self.assertEqual(correlation(baseline_fingerprint='a' * 64), {})

    def test_only_terminal_success_states_are_good(self):
        self.assertEqual(GOOD_TERMINAL_STATES,
                         {'complete', 'ready', 'deleted', 'verified'})
        for state in ('requested', 'provisioning', 'running', 'incomplete', 'failed'):
            self.assertNotIn(state, GOOD_TERMINAL_STATES)

    def test_incomplete_result_spends_deadline_budget(self):
        class Counter:
            def __init__(self):
                self.values = []

            def add(self, value, _attributes):
                self.values.append(value)

            def record(self, value, _attributes):
                self.values.append(value)

        eligible, good, deadline_good, duration = Counter(), Counter(), Counter(), Counter()
        with patch.object(operation_telemetry, '_eligible', eligible), \
                patch.object(operation_telemetry, '_good', good), \
                patch.object(operation_telemetry, '_deadline_good', deadline_good), \
                patch.object(operation_telemetry, '_duration', duration), \
                redirect_stdout(io.StringIO()):
            @operation('environment.delete', deadline_seconds=300)
            def remove():
                return {'state': 'incomplete'}

            self.assertEqual(remove(), {'state': 'incomplete'})
        self.assertEqual(eligible.values, [1])
        self.assertEqual(good.values, [0])
        self.assertEqual(deadline_good.values, [0])
        self.assertEqual(len(duration.values), 1)

    def test_result_and_correlation_without_payload(self):
        @operation('comparison.evaluate')
        def evaluate():
            return {'id': 'comparison-1', 'state': 'complete',
                    'report_sha256': 'a' * 64, 'query': 'synthetic private phrase'}

        output = io.StringIO()
        with redirect_stdout(output):
            result = evaluate()
        self.assertEqual(result['query'], 'synthetic private phrase')
        event = json.loads(output.getvalue())
        self.assertEqual(event['id'], 'comparison-1')
        self.assertEqual(event['report_sha256'], 'a' * 64)
        self.assertNotIn('query', event)

    def test_operation_log_retains_deployment_identity(self):
        @operation('delivery.verify')
        def verify():
            return {'state': 'verified', 'fingerprint': 'a' * 64}

        output = io.StringIO()
        with patch.dict(os.environ, {'LAB_RELEASE_SHA': 'sha256:' + 'b' * 64,
                                      'LAB_DEPLOYMENT_TIER': 'lab-control'}), \
                redirect_stdout(output):
            verify()
        event = json.loads(output.getvalue())
        self.assertEqual(event['service_version'], 'sha256:' + 'b' * 64)
        self.assertEqual(event['deployment_tier'], 'lab-control')
        self.assertEqual(event['fingerprint'], 'a' * 64)

    def test_exception_type_without_message(self):
        @operation('environment.create')
        def create():
            raise RuntimeError('secret-value')

        output = io.StringIO()
        with redirect_stdout(output), self.assertRaisesRegex(RuntimeError, 'secret-value'):
            create()
        event = json.loads(output.getvalue())
        self.assertEqual(event['state'], 'failed')
        self.assertEqual(event['error_kind'], 'RuntimeError')
        self.assertNotIn('secret-value', output.getvalue())


if __name__ == '__main__':
    unittest.main()
