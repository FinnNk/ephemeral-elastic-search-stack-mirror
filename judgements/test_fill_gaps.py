"""Progressive passes skip labelled pairs and retain source-scoped evidence."""

from pathlib import Path
import json
import tempfile
import unittest

from core import canonical, digest
from fill_gaps import freeze, run
from test_prepare import PrepareTests


class GapPassTests(unittest.TestCase):
    def test_next_pass_skips_accepted_pairs_but_retries_abstentions(self):
        fixture = PrepareTests('test_abstention_then_new_recall_label')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.run_case('p3', 'first', lambda rows: [{'outcome': 'abstain'} for _ in rows])
        observations = fixture.root / 'observations-p3.json'
        output = fixture.root / 'inputs.json'
        result = freeze(observations, fixture.specification, fixture.catalogue,
            fixture.cm, fixture.qm, fixture.source, fixture.sm, [], output)
        self.assertEqual(result['gaps'], 2)
        frozen = json.loads(output.read_bytes())
        previous = fixture.write('pass.json', {'complete': True, 'context': frozen['context'],
            'records': [{'query_id': 'q1', 'product_id': 'p2', 'outcome': 'labelled'},
                        {'query_id': 'q1', 'product_id': 'p3', 'outcome': 'abstain'}]})
        next_output = fixture.root / 'next.json'
        result = freeze(observations, fixture.specification, fixture.catalogue,
            fixture.cm, fixture.qm, fixture.source, fixture.sm, [previous], next_output)
        self.assertEqual(result['gaps'], 1)
        self.assertEqual(json.loads(next_output.read_bytes())['pairs'][0]['product_id'], 'p3')

    def test_unmatched_or_incomplete_protected_audit_blocks_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs = root / 'inputs.json'
            inputs.write_bytes(canonical({'pairs': []}))
            audit = root / 'audit.json'
            audit.write_bytes(canonical({'inputs_sha256': digest(inputs.read_bytes()),
                                         'audit_complete': False}))
            with self.assertRaisesRegex(ValueError, 'complete protected'):
                run(inputs, audit, 'http://example.invalid', {}, root / 'results')
            self.assertFalse((root / 'results').exists())
