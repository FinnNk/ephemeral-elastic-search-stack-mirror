"""Informational paired inference over request groups; never a gate input."""
import hashlib
import json
from pathlib import Path
import math

import numpy as np
import scipy
from scipy.stats import bootstrap, permutation_test

SEED = 20261006
RESAMPLES = 9999


def request_group(row):
    """Keep repeats and case variants together without conflating filtered requests."""
    return json.dumps({**{k: row[k] for k in ('country', 'currency')},
                       'query': row['query'].casefold(), 'filters': row.get('filters', {})},
                      sort_keys=True, separators=(',', ':'))


def analyse(per_case, requests, baseline, variants, eligible_ids):
    """Test the query-weighted mean difference, resampling whole request groups."""
    comparisons = {}
    tests = []
    for variant in sorted(variants):
        if variant == baseline:
            continue
        comparisons[variant] = {}
        names = sorted(set(per_case.get(baseline, {})) | set(per_case.get(variant, {})))
        for metric in names:
            if not metric.startswith('nDCG@'):
                continue
            groups = {}
            paired = 0
            for qid, row in sorted(requests.items()):
                a = per_case.get(baseline, {}).get(metric, {}).get(qid)
                b = per_case.get(variant, {}).get(metric, {}).get(qid)
                if qid not in eligible_ids or a is None or b is None or not math.isfinite(a + b):
                    continue
                groups.setdefault(request_group(row), []).append(b - a)
                paired += 1
            result = {'paired_queries': paired, 'excluded_queries': len(requests) - paired,
                      'request_groups': len(groups), 'mean_difference': None,
                      'confidence_interval_95': None, 'p_value': None,
                      'adjusted_p_value': None, 'significant': None}
            comparisons[variant][metric] = result
            if paired:
                result['mean_difference'] = sum(sum(v) for v in groups.values()) / paired
            if len(groups) < 2:
                result['unavailable_reason'] = ('No paired finite scores with positive reference gain.' if not paired else
                                                'Fewer than two independently resampled request groups.')
                continue
            sums = np.array([sum(v) for _, v in sorted(groups.items())])
            counts = np.array([len(v) for _, v in sorted(groups.items())])
            if np.all(sums == 0):
                result['permutation_mode'] = 'zero request-group differences'
                p, interval = 1.0, [0.0, 0.0]
            else:
                result['permutation_mode'] = 'exact' if len(groups) <= 13 else 'Monte Carlo'
                test = permutation_test((sums,), lambda x, axis: np.sum(x, axis=axis) / paired,
                    permutation_type='samples', vectorized=True, alternative='two-sided',
                    n_resamples=RESAMPLES, batch=128, rng=np.random.default_rng(SEED))
                ci = bootstrap((sums, counts),
                    lambda x, n, axis: np.sum(x, axis=axis) / np.sum(n, axis=axis),
                    paired=True, vectorized=True, method='percentile', confidence_level=.95,
                    n_resamples=RESAMPLES, batch=128, rng=np.random.default_rng(SEED))
                p = float(test.pvalue)
                interval = [float(ci.confidence_interval.low), float(ci.confidence_interval.high)]
            result.update(p_value=p, confidence_interval_95=interval)
            tests.append(result)
    # Holm controls the family-wise error rate without requiring independent tests.
    running = 0.0
    for rank, result in enumerate(sorted(tests, key=lambda r: r['p_value'])):
        running = max(running, min(1.0, (len(tests) - rank) * result['p_value']))
        result['adjusted_p_value'] = running
        result['significant'] = running < .05
    return {'informational_only': True, 'alpha': .05,
            'method': 'two-sided paired permutation of request groups',
            'confidence_interval_method': 'paired request-group percentile bootstrap',
            'grouping': 'casefolded query, country, currency and filters',
            'weighting': 'equal weight per eligible query case; groups resampled together',
            'adjustment': 'Holm across variants and nDCG cut-offs within this report',
            'tested_comparisons': len(tests), 'resamples': RESAMPLES, 'seed': SEED,
            'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scipy_version': scipy.__version__, 'numpy_version': np.__version__,
            'comparisons': comparisons}
