"""Read pinned Gatling 3.15.1 HTML statistics and validate scheduled arrivals."""
import csv
import hashlib
import html
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def report_rows(report_directory):
    page = (Path(report_directory) / 'index.html').read_text(encoding='utf-8')
    rows = {}
    for match in re.finditer(r'<tr id="req_[^"]+"[^>]*>(.*?)</tr>', page, re.S):
        fragment = match.group(1)
        label = re.search(r'class="ellipsed-name">([^<]+)', fragment)
        if not label:
            continue
        name = html.unescape(label.group(1))
        cells = {int(number): value.strip() for number, value in
                 re.findall(r'<td class="value [^"]* col-(\d+)">([^<]*)</td>', fragment)}
        if not all(number in cells for number in (2, 3, 4, 5, 6, 10, 11)):
            raise ValueError('Gatling statistics row lacks expected columns.')
        rows[name] = {'requests': int(cells[2]), 'ok': int(cells[3]), 'failed': int(cells[4]),
                      'failed_percent': float(cells[5]), 'gatling_reported_rps_over_whole_run': float(cells[6]),
                      'p95_ms': int(cells[10]), 'p99_ms': int(cells[11])}
    if not rows:
        raise ValueError('No request statistics found in Gatling report.')
    return rows


def validate_arrivals(workload, arrivals):
    workload = Path(workload)
    manifest = json.loads((workload / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected_hash in manifest['files'].items():
        if hashlib.sha256((workload / name).read_bytes()).hexdigest() != expected_hash:
            raise ValueError('Compiled workload file differs: ' + name)
    expected = Counter()
    for phase in manifest['phase_counts']:
        with (workload / (phase + '.csv')).open(newline='', encoding='utf-8') as handle:
            for row in csv.DictReader(handle):
                expected[(phase, row['query_id'], row['planned_ms'])] += 1
    actual = Counter()
    offsets = []
    with Path(arrivals).open(newline='', encoding='utf-8') as handle:
        for row in csv.reader(handle):
            if len(row) != 4:
                raise ValueError('Actual arrival row is incomplete.')
            epoch, phase, query_id, planned = row
            actual[(phase, query_id, planned)] += 1
            offsets.append(int(epoch) - int(planned))
    complete = actual == expected
    centre = statistics.median(offsets) if offsets else 0
    drift = [abs(offset - centre) for offset in offsets]
    return {'planned_count': sum(expected.values()), 'actual_count': sum(actual.values()),
            'complete': complete, 'arrival_drift_p95_ms': percentile(drift, .95),
            'arrival_drift_max_ms': max(drift) if drift else None,
            'valid': complete and percentile(drift, .95) is not None and percentile(drift, .95) <= 500}


def summarise(report_directory, workload, arrivals):
    manifest = json.loads((Path(workload) / 'manifest.json').read_text(encoding='utf-8'))
    phases = report_rows(report_directory)
    seconds = Counter()
    with (Path(workload) / 'schedule.csv').open(newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            seconds[row['phase']] += 1
    for name, metrics in phases.items():
        if seconds[name]:
            metrics['offered_rps'] = round(manifest['phase_counts'][name] / seconds[name], 3)
            metrics['planned_seconds'] = seconds[name]
    arrival = validate_arrivals(workload, arrivals)
    complete = all(phases.get(name, {}).get('requests') == expected
                   for name, expected in manifest['phase_counts'].items())
    return {'profile': manifest['profile'], 'workload_sha256': manifest['workload_sha256'],
            'source_sha256': manifest['source_sha256'], 'recipe_sha256': manifest['recipe_sha256'],
            'duration_seconds': manifest['duration_seconds'], 'phases': phases,
            'arrival': arrival, 'complete': complete,
            'valid': complete and arrival['valid']}
