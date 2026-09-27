"""Check the SLO arithmetic on bounded synthetic search events.

This fixture analyser is not a telemetry-loss or duplicate-delivery detector.
The dashboard must use unsampled counters and display collection coverage.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


def utc(value):
    moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if moment.utcoffset() is None:
        raise ValueError('Search event time needs a UTC offset.')
    return moment.astimezone(timezone.utc)


def analyse(events, policy, now=None, coverage_complete=False):
    if policy.get('kind') != 'search-slo-policy' or policy.get('schema_version') != 1:
        raise ValueError('Unsupported search SLO policy.')
    now = now or datetime.now(timezone.utc)
    window = timedelta(days=policy['window_days'])
    if not 0 < window.days <= 30:
        raise ValueError('Invalid SLO window.')
    selected = []
    for event in events:
        if event.get('event') != 'search.completed' or \
                event.get('traffic_class') != policy['traffic_class']:
            continue
        moment = utc(event['observed_at'])
        if moment > now:
            raise ValueError('Search event is in the future.')
        if moment < now - window:
            continue
        selected.append(event)
    result = {'policy': policy['kind'], 'window_days': window.days,
              'traffic_class': policy['traffic_class'], 'eligible': len(selected),
              'coverage': 'complete' if coverage_complete else 'unverified',
              'low_sample_count': len(selected) < policy['minimum_sample_count'],
              'objectives': {}}
    for objective in policy['objectives']:
        target = objective['target']
        if not 0 < target < 1:
            raise ValueError('SLO target must be between zero and one.')
        field = objective['good_field']
        values = [event.get(field) for event in selected]
        if any(type(value) is not bool for value in values):
            raise ValueError('Search event lacks an explicit good/bad classification.')
        eligible = len(values)
        good = sum(values)
        bad = eligible - good
        allowance = eligible * (1 - target)
        result['objectives'][objective['id']] = {
            'target': target, 'good': good, 'bad': bad,
            'observed_sli': good / eligible if eligible else None,
            'allowed_bad': allowance if eligible else None,
            'remaining_budget': allowance - bad if eligible else None,
            'budget_consumed': bad / allowance if allowance else None,
            'status': ('no-data' if not eligible else
                       'unverified' if not coverage_complete else
                       'met' if good / eligible >= target else 'breached')}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=Path, required=True)
    parser.add_argument('--policy', type=Path, default=Path(__file__).parent / 'policies/search-slo-v1.json')
    parser.add_argument('--coverage-complete', action='store_true',
                        help='Only for a verified complete synthetic fixture window')
    args = parser.parse_args()
    events = [json.loads(line) for line in args.events.read_text(encoding='utf-8').splitlines()]
    print(json.dumps(analyse(events, json.loads(args.policy.read_bytes()),
                             coverage_complete=args.coverage_complete), indent=2))


if __name__ == '__main__':
    main()
