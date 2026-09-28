"""Join retained Gatling arrivals, readiness probes and SigNoz counter increases.

This adapter deliberately leaves the seven-day source verification false unless
the complete seven-day independent ledger is available. It never turns a short
load run into a seven-day green verdict.
"""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen

from window import assess


HERE = Path(__file__).resolve().parent
POLICY = HERE / 'policies/search-slo-v1.json'
METRICS = {'eligible': 'lab.search.eligible',
           'success_good': 'lab.search.success_good',
           'responsive_good': 'lab.search.responsive_good'}
STEP = timedelta(minutes=1)


def minute(moment):
    return moment.replace(second=0, microsecond=0)


def read_arrivals(path):
    counts = Counter()
    with Path(path).open(newline='', encoding='utf-8') as handle:
        for row in csv.reader(handle):
            if len(row) != 4:
                raise ValueError('Gatling arrival record is incomplete.')
            epoch_ms, phase, _query_id, _planned_ms = row
            if phase == 'normal':
                counts[minute(datetime.fromtimestamp(int(epoch_ms) / 1000, timezone.utc))] += 1
    if not counts:
        raise ValueError('No normal-phase Gatling arrivals.')
    return counts


def read_probes(paths):
    grouped = defaultdict(list)
    seen = set()
    for path in paths:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['observed_at'] in seen:
                continue
            seen.add(row['observed_at'])
            at = datetime.fromisoformat(row['observed_at'].replace('Z', '+00:00'))
            grouped[minute(at.astimezone(timezone.utc))].append(row)
    return grouped


def counter_points(url, token, start, end, tier):
    if not tier or any(character not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for character in tier):
        raise ValueError('Deployment tier must be a bounded lab identifier.')
    queries = []
    for name, metric in METRICS.items():
        queries.append({'type': 'builder_query', 'spec': {
            'name': name, 'signal': 'metrics', 'stepInterval': 60,
            'aggregations': [{'metricName': metric, 'timeAggregation': 'increase',
                              'spaceAggregation': 'sum'}],
            'filter': {'expression': "lab.traffic_class = 'normal' AND "
                       + "deployment.environment.name = '" + tier + "'"},
            'disabled': False}})
    body = {'start': int(start.timestamp() * 1000),
            'end': int(end.timestamp() * 1000),
            'requestType': 'time_series', 'compositeQuery': {'queries': queries}}
    request = Request(url.rstrip('/') + '/api/v5/query_range', method='POST',
                      headers={'Authorization': 'Bearer ' + token,
                               'Content-Type': 'application/json'},
                      data=json.dumps(body).encode())
    with urlopen(request, timeout=30) as response:
        value = json.load(response)
    if value.get('status') != 'success':
        raise RuntimeError('SigNoz counter query did not succeed.')
    output = {name: {} for name in METRICS}
    for result in value['data']['data']['results']:
        name = result['queryName']
        if name not in output:
            continue
        for aggregation in result.get('aggregations') or []:
            for series in aggregation.get('series') or []:
                for point in series.get('values') or []:
                    at = datetime.fromtimestamp(point['timestamp'] / 1000, timezone.utc)
                    amount = point['value']
                    if not math.isfinite(amount) or amount < 0 or abs(amount - round(amount)) > 1e-6:
                        raise ValueError('Counter increase is not an exact non-negative request count.')
                    output[name][minute(at)] = output[name].get(minute(at), 0) + round(amount)
    return output


def assemble(arrivals, probes, counters, policy):
    first, last = min(arrivals), max(arrivals)
    end = last + STEP
    start = end - timedelta(days=policy['window_days'])
    buckets = []
    run_mismatches = []
    for at, expected in sorted(arrivals.items()):
        samples = probes.get(at, [])
        healthy = len(samples) >= 5 and all(row.get('collector_ok') is True for row in samples)
        observed = {name: counters[name].get(at) for name in METRICS}
        if any(value is None for value in observed.values()):
            healthy = False
            observed = {name: 0 if value is None else value for name, value in observed.items()}
        if observed['eligible'] != expected:
            run_mismatches.append(at.isoformat())
        buckets.append({'start': at.isoformat(), 'collector_ok': healthy,
                        'expected_requests': expected, **observed})
    document = {'window_start': start.isoformat(), 'window_end': end.isoformat(),
                'interval_seconds': 60, 'source_verified': False, 'buckets': buckets}
    verdict = assess(document, policy)
    total_matched = sum(row['eligible'] for row in buckets) == sum(arrivals.values())
    all_healthy = all(row['collector_ok'] for row in buckets)
    verdict['run_segment'] = {'first': first.isoformat(), 'last': last.isoformat(),
                              'expected_requests': sum(arrivals.values()),
                              'observed_eligible': sum(row['eligible'] for row in buckets),
                              'healthy_arrival_minutes': sum(row['collector_ok'] for row in buckets),
                              'arrival_minutes': len(buckets),
                              'counter_mismatch_minutes': run_mismatches,
                              'status': ('matched-exact' if total_matched and all_healthy and
                                         not run_mismatches else
                                         'matched-total-only' if total_matched and all_healthy else
                                         'unverified')}
    return document, verdict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arrivals', type=Path, required=True)
    parser.add_argument('--gatling-summary', type=Path, required=True)
    parser.add_argument('--probes', type=Path, required=True, action='append',
                        help='Repeat for consecutive or overlapping probe files.')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tier', default='reference-probe')
    parser.add_argument('--signoz-url', default='http://127.0.0.1:18090')
    args = parser.parse_args()
    token = os.environ.get('SIGNOZ_ACCESS_TOKEN')
    if not token:
        raise SystemExit('Set a short-lived SIGNOZ_ACCESS_TOKEN outside Git.')
    summary = json.loads(args.gatling_summary.read_bytes())
    if summary.get('label') != 'on' or summary.get('arrival', {}).get('complete') is not True:
        raise ValueError('Use a complete telemetry-enabled Gatling arrival ledger.')
    arrivals = read_arrivals(args.arrivals)
    if sum(arrivals.values()) != summary['requests']:
        raise ValueError('Retained normal arrivals differ from Gatling request total.')
    probes = read_probes(args.probes)
    first, last = min(arrivals), max(arrivals)
    counters = counter_points(args.signoz_url, token, first - STEP, last + 2 * STEP,
                              args.tier)
    document, verdict = assemble(arrivals, probes, counters, json.loads(POLICY.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'source': {'gatling_summary': str(args.gatling_summary),
                                                  'arrivals': str(args.arrivals),
                                                  'probes': [str(path) for path in args.probes]},
                                       'window': document, 'assessment': verdict}, indent=2) + '\n',
                           encoding='utf-8')
    print(json.dumps({'coverage': verdict['coverage'], 'run_segment': verdict['run_segment'],
                      'seven_day_eligible_lower_bound': verdict['eligible']}, indent=2))


if __name__ == '__main__':
    main()
