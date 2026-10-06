"""Production requires the full pinned load test, including after PR creation."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import unittest
from unittest.mock import patch

from delivery_load_policy import PROFILE, RECIPE, validate
from delivery_gates import validate_evidence
from delivery_cli import execute, parser
from delivery_promote import propose, inspect_pr
from run_gatling_job import workload_parts


def performance():
    recipe_sha = hashlib.sha256(RECIPE.read_bytes()).hexdigest()
    phases = {}
    for phase in json.loads(RECIPE.read_bytes())['profiles'][PROFILE]:
        phases[phase['name']] = {'requests': phase['seconds'] * phase['rate'],
            'planned_seconds': phase['seconds'], 'offered_rps': phase['rate'],
            'p95_ms': 100, 'p99_ms': 200, 'failed': 0, 'failed_percent': 0}
    run = {'fingerprint': 'B', 'profile': PROFILE, 'recipe_sha256': recipe_sha,
           'complete': True, 'valid': True, 'arrival': {'valid': True},
           'duration_seconds': 1260, 'phases': phases}
    return {'kind': 'paired-api-performance', 'profile': PROFILE,
            'recipe_sha256': recipe_sha, 'valid': True, 'same_workload': True,
            'warmup_ready': True, 'verdict': 'within-budget',
            'measured_phases': {'normal': {}, 'peak': {}},
            'baseline': run, 'candidate': {**deepcopy(run), 'fingerprint': 'C'}}


class ProductionLoadTests(unittest.TestCase):
    def test_full_valid_pair_passes(self):
        validate(performance())

    def test_probe_smoke_and_changed_recipe_fail(self):
        for field, value in [('profile', 'probe'), ('profile', 'smoke'),
                             ('recipe_sha256', 'a' * 64)]:
            report = performance()
            report[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate(report)

    def test_short_peak_incomplete_arrivals_and_budget_misses_fail(self):
        for side in ('baseline', 'candidate'):
            for field, value in [('planned_seconds', 30), ('requests', 100),
                                 ('offered_rps', 2), ('p95_ms', 401),
                                 ('p99_ms', 801), ('failed_percent', 1.0)]:
                report = performance()
                report[side]['phases']['peak'][field] = value
                with self.subTest(side=side, field=field), self.assertRaises(ValueError):
                    validate(report)
            report = performance()
            report[side]['arrival']['valid'] = False
            with self.assertRaises(ValueError):
                validate(report)

    def test_production_evidence_rechecked_but_earlier_targets_accept_probe(self):
        evidence = {'baseline': 'B', 'candidate': 'C', 'intent': 'ranking-change',
                    'completed_at': datetime.now(timezone.utc).isoformat(),
                    'reports': {mode: {'mode': mode} for mode in
                                ('result-regression', 'relevance', 'performance')}}
        probe = {**performance(), 'profile': 'probe'}
        def read(ref):
            return probe if ref.get('mode') == 'performance' else evidence
        with patch('delivery_gates.read', side_effect=read), patch('delivery_gates.check_report'):
            validate_evidence({}, 'B', 'C', 'ranking-change', target='staging')
            with self.assertRaisesRegex(ValueError, 'Production requires'):
                validate_evidence({}, 'B', 'C', 'ranking-change', target='production')

    def test_production_probe_rejected_before_work(self):
        args = parser().parse_args(['evaluate-target', 'production', '--run', '108', '--profile', 'probe'])
        with patch('delivery_cli.checkout') as checkout, self.assertRaisesRegex(ValueError, 'Production requires'):
            execute(args)
        checkout.assert_not_called()

    def test_proposal_passes_target_to_gate_before_side_effects(self):
        with patch('delivery_promote.checkout'), \
             patch('delivery_promote.read_target', return_value={'fingerprint': 'B'}), \
             patch('delivery_promote.validate_deployment'), \
             patch('delivery_promote.deployment_inputs', return_value={}), \
             patch('delivery_promote.validate_evidence', side_effect=ValueError('blocked')) as gate, \
             patch('delivery_promote.materialise') as materialise:
            with self.assertRaisesRegex(ValueError, 'blocked'):
                propose('production', {'fingerprint': 'C'}, {}, 'ranking-change')
        self.assertEqual(gate.call_args.kwargs, {'target': 'production'})
        materialise.assert_not_called()

    def test_pr_validation_rechecks_production_policy(self):
        deployment = {'fingerprint': 'C'}
        previous = {'fingerprint': 'B'}
        proposal = {'kind': 'promotion', 'target': 'production', 'base_revision': 'base',
                    'expected_target': 'B', 'deployment': deployment,
                    'evidence': {}, 'intent': 'ranking-change'}
        slots = {'active': 'blue', 'slots': {'blue': previous, 'green': deployment}}
        proposal.update(previous_slots=slots, slots={**slots, 'active': 'green'})
        paths = ['targets/production/slots.json', 'proposals/p.json', 'targets/production/deployment.json',
                 'targets/production/rendered/search.yaml', 'history/production/B.json']
        def git(_repo, *args):
            if args[0] == 'rev-parse':
                return 'base'
            if args[0] == 'diff':
                return '\n'.join(paths)
            if args[0] == 'show':
                path = args[1].split(':')[1]
                return 'manifest' if path.endswith('.yaml') else json.dumps(
                    proposal if path.startswith('proposals/') else
                    previous if path.startswith('history/') else deployment)
        pr = {'state': 'open', 'base': {'ref': 'main'}, 'head': {'sha': 'head', 'ref': 'branch'}}
        with patch('delivery_promote.api', return_value=pr), patch('delivery_promote.git', side_effect=git), \
             patch('delivery_promote.read_target', return_value=previous), \
             patch('delivery_promote.rendered', return_value='manifest'), \
             patch('delivery_promote.deployment_inputs', return_value={}), \
             patch('production_release.state', return_value=slots), patch('production_release.live', return_value=slots), \
             patch('production_release.validate_files'), patch('production_release.validate_final'), \
             patch('delivery_gates.read', return_value={}), \
             patch('delivery_promote.validate_evidence', side_effect=ValueError('load rejected')) as gate:
            with self.assertRaisesRegex(ValueError, 'load rejected'):
                inspect_pr(15)
        self.assertEqual(gate.call_args.kwargs, {'target': 'production'})

    def test_large_unicode_workload_preserves_bytes_in_bounded_maps(self):
        payload = ('query,£\n' * 200000).encode()
        parts, command = workload_parts({'peak.csv': payload}, 'workload')
        restored = b''.join(base64.b64decode(next(iter(p['binaryData'].values()))) for p in parts)
        self.assertEqual(restored, payload)
        self.assertTrue(all(len(json.dumps(p).encode()) < 800000 for p in parts))
        self.assertIn(' > /workload/peak.csv', command)


if __name__ == '__main__':
    unittest.main()
