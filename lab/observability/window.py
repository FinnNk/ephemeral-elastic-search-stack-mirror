"""Assess seven-day search SLO buckets against an independent request ledger.

Input buckets are SigNoz counter increases, not trace samples. Each bucket also
contains the number of requests attempted by the load driver and a collector
probe outcome. `source_verified` means those two independent sources were
checked for the full window. An absent or mismatched interval is unknown.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


FIELDS = ('expected_requests', 'eligible', 'success_good', 'responsive_good')


def moment(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() is None:
        raise ValueError('Window and bucket times need a UTC offset.')
    return parsed.astimezone(timezone.utc)


def count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + ' must be a non-negative integer.')
    return value


def assess(document, policy):
    if policy.get('kind') != 'search-slo-policy' or policy.get('schema_version') != 1:
        raise ValueError('Unsupported search SLO policy.')
    start, end = moment(document['window_start']), moment(document['window_end'])
    if end - start != timedelta(days=policy['window_days']):
        raise ValueError('Window must match the policy duration exactly.')
    seconds = count(document['interval_seconds'], 'interval_seconds')
    if not seconds or (end - start).total_seconds() % seconds:
        raise ValueError('Interval must divide the policy window.')
    positions = {}
    for bucket in document['buckets']:
        at = moment(bucket['start'])
        if at < start or at >= end or (at - start).total_seconds() % seconds:
            raise ValueError('Bucket lies outside the aligned window.')
        if at in positions:
            raise ValueError('Duplicate bucket start.')
        positions[at] = bucket
    totals = dict.fromkeys(FIELDS, 0)
    gaps = []
    mismatches = []
    interval_count = int((end - start).total_seconds() / seconds)
    for index in range(interval_count):
        at = start + timedelta(seconds=index * seconds)
        bucket = positions.get(at)
        if bucket is None or bucket.get('collector_ok') is not True:
            gaps.append(at.isoformat())
            continue
        values = {name: count(bucket[name], name) for name in FIELDS}
        if (values['eligible'] != values['expected_requests'] or
                values['success_good'] > values['eligible'] or
                values['responsive_good'] > values['success_good']):
            mismatches.append(at.isoformat())
            continue
        for name, value in values.items():
            totals[name] += value
    complete = bool(document.get('source_verified') is True and not gaps and not mismatches)
    enough = totals['eligible'] >= policy['minimum_sample_count']
    result = {
        'policy': policy['kind'], 'window_start': start.isoformat(),
        'window_end': end.isoformat(), 'interval_seconds': seconds,
        'expected_intervals': interval_count, 'observed_intervals': len(positions),
        'gap_count': len(gaps), 'mismatch_count': len(mismatches),
        'first_gaps': gaps[:5], 'first_mismatches': mismatches[:5],
        'coverage': 'complete' if complete else 'unverified',
        'source_verified': document.get('source_verified') is True,
        'low_sample_count': not enough, 'eligible': totals['eligible'],
        'expected_requests': totals['expected_requests'], 'objectives': {},
    }
    for objective in policy['objectives']:
        target = objective['target']
        if not 0 < target < 1:
            raise ValueError('SLO target must be between zero and one.')
        good = totals[objective['good_field']]
        bad = totals['eligible'] - good
        allowance = totals['eligible'] * (1 - target)
        result['objectives'][objective['id']] = {
            'target': target, 'good': good, 'bad': bad,
            'observed_sli': good / totals['eligible'] if totals['eligible'] else None,
            'allowed_bad': allowance if totals['eligible'] else None,
            'remaining_budget': allowance - bad if totals['eligible'] else None,
            'budget_consumed': bad / allowance if allowance else None,
            'status': ('no-data' if not totals['eligible'] else
                       'unverified' if not complete or not enough else
                       'met' if good / totals['eligible'] >= target else 'breached'),
        }
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--buckets', required=True, type=Path)
    parser.add_argument('--policy', type=Path, default=Path(__file__).parent /
                        'policies/search-slo-v1.json')
    args = parser.parse_args()
    print(json.dumps(assess(json.loads(args.buckets.read_bytes()),
                            json.loads(args.policy.read_bytes())), indent=2))
