"""Summarise retained captures without dropping failed or slower observations."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import statistics


def median(rows, key):
    return statistics.median(row[key] for row in rows)


def analyse(directory):
    rows = [json.loads(line) for line in (directory / 'ledger.jsonl').read_bytes().splitlines()]
    groups = defaultdict(list)
    reference = {}
    changed = defaultdict(int)
    for row in rows:
        raw = (directory / (row['run_id'] + '.json.gz')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['raw_sha256']:
            raise ValueError('Retained raw record differs: ' + row['run_id'])
        capture = json.loads(gzip.decompress(raw))
        if row['request_count'] != row['expected_requests']:
            raise ValueError('Incomplete request count: ' + row['run_id'])
        key = (row['query_count'], row['variant_count'])
        baseline = reference.setdefault(key, capture['observations'])
        if len(baseline) != len(capture['observations']):
            raise ValueError('Observation count differs.')
        changed[row['run_id']] = sum(first != second for first, second in zip(baseline, capture['observations']))
        stage = row['label'].rsplit('-', 1)[0] if row['label'].rsplit('-', 1)[-1].isdigit() else row['label']
        spec = row['specification']
        groups[(stage, row['transport'], spec['strategy'], spec['client'], spec['limit'], row['variant_count'])].append(row)
    summaries = [{'stage': key[0], 'transport': key[1], 'strategy': key[2], 'client': key[3],
                  'limit': key[4], 'variant_count': key[5], 'runs': len(values),
                  'capture_median_seconds': median(values, 'capture_seconds'),
                  'capture_worst_seconds': max(row['capture_seconds'] for row in values),
                  'end_to_end_median_seconds': median(values, 'end_to_end_seconds'),
                  'errors': sum(row['errors'] for row in values), 'retries': sum(row['retries'] for row in values)}
                 for key, values in groups.items()]
    blocks = defaultdict(dict)
    for row in rows:
        if row['label'].startswith('confirmation-'):
            blocks[row['label']][row['transport']] = row
    comparisons = []
    for simpler, candidate in [('original', 'pooled-es'), ('pooled-es', 'pooled-both'), ('original', 'pooled-both')]:
        complete = [block for block in blocks.values() if simpler in block and candidate in block]
        a, b = [block[simpler] for block in complete], [block[candidate] for block in complete]
        if not a:
            continue
        capture_gain = 1 - median(b, 'capture_seconds') / median(a, 'capture_seconds')
        e2e_gain = 1 - median(b, 'end_to_end_seconds') / median(a, 'end_to_end_seconds')
        improving = sum(block[candidate]['capture_seconds'] < block[simpler]['capture_seconds'] and
                        block[candidate]['end_to_end_seconds'] < block[simpler]['end_to_end_seconds'] for block in complete)
        healthy = all(row['errors'] == row['retries'] == 0 and not changed[row['run_id']] for row in b)
        comparisons.append({'simpler': simpler, 'candidate': candidate, 'pairs': len(complete),
            'capture_reduction': capture_gain, 'end_to_end_reduction': e2e_gain, 'improving_pairs': improving,
            'qualifies': len(complete) == 6 and capture_gain >= .15 and e2e_gain >= .10 and improving >= 4 and healthy,
            'paired_capture_ratios': [block[candidate]['capture_seconds'] / block[simpler]['capture_seconds'] for block in complete],
            'paired_end_to_end_ratios': [block[candidate]['end_to_end_seconds'] / block[simpler]['end_to_end_seconds'] for block in complete]})
    selected = 'original'
    if comparisons and comparisons[0]['qualifies']:
        selected = 'pooled-both' if comparisons[1]['qualifies'] else 'pooled-es'
    return {'selected_transport': selected, 'kind': 'evaluation-throughput-analysis', 'runs': len(rows), 'groups': summaries,
            'confirmation': comparisons, 'changed_queries_per_run': dict(changed),
            'semantic_hashes': sorted({row['semantic_sha256'] for row in rows}),
            'limits': 'Local finite captures; six pairs are not a p95, cloud or inference-capacity claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyse(args.directory)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['confirmation'], indent=2))
