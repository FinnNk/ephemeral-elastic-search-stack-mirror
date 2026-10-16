import unittest

from compare_gatling import compare
from aggregate_smoke import baseline_spread


def run(target, *, valid=True, workload='frozen', normal_p95=100, warmup_p95=1000):
    return {'profile': 'probe', 'workload_sha256': workload, 'source_sha256': 'source',
            'recipe_sha256': 'recipe', 'valid': valid, 'runner_image': 'pinned',
            'fingerprint': target, 'phases': {
                'warmup': {'p95_ms': warmup_p95, 'p99_ms': warmup_p95, 'failed': 0, 'failed_percent': 0,
                           'offered_rps': 2, 'requests': 10},
                'normal': {'p95_ms': normal_p95, 'p99_ms': normal_p95, 'failed_percent': 0,
                           'offered_rps': 2, 'requests': 20}}}


class GatlingComparisonContract(unittest.TestCase):
    def test_normal_p95_budget_applies_to_both_sides_at_300_ms(self):
        for side in ('baseline', 'candidate'):
            for latency, verdict in ((254, 'within-budget'), (300, 'within-budget'),
                                     (301, 'budget-missed')):
                with self.subTest(side=side, latency=latency):
                    runs = {name: run(name) for name in ('baseline', 'candidate')}
                    runs[side]['phases']['normal']['p95_ms'] = latency
                    runs[side]['phases']['normal']['p99_ms'] = max(latency, 100)
                    report = compare(runs['baseline'], runs['candidate'])
                    self.assertEqual(report['verdict'], verdict)
                    self.assertEqual(report['measured_phases']['normal']['budget']['p95_ms'], 300)

    def test_other_normal_limits_remain_enforced(self):
        for metric, value in (('p99_ms', 501), ('failed_percent', 1.0)):
            with self.subTest(metric=metric):
                candidate = run('candidate')
                candidate['phases']['normal'][metric] = value
                self.assertEqual(compare(run('baseline'), candidate)['verdict'], 'budget-missed')

    def test_baseline_stability_uses_spread_over_median(self):
        self.assertEqual(baseline_spread([100, 105, 110]), 9.524)
        self.assertGreater(baseline_spread([100, 105, 120]), 10)

    def test_warmup_does_not_fail_measured_budget(self):
        report = compare(run('baseline'), run('candidate'))
        self.assertTrue(report['valid'])
        self.assertEqual(report['verdict'], 'within-budget')
        self.assertNotIn('warmup', report['measured_phases'])

    def test_different_or_invalid_workload_cannot_pass(self):
        self.assertEqual(compare(run('baseline'), run('candidate', workload='other'))['verdict'], 'invalid')
        self.assertEqual(compare(run('baseline'), run('candidate', valid=False))['verdict'], 'invalid')
        self.assertEqual(compare(run('baseline'), run('candidate', normal_p95=600))['verdict'], 'budget-missed')
        candidate = run('candidate')
        candidate['phases']['warmup']['failed'] = 1
        self.assertEqual(compare(run('baseline'), candidate)['verdict'], 'invalid')


if __name__ == '__main__':
    unittest.main()
