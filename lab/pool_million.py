"""Freeze symmetric synthetic assessments of both million-scale result pools."""
import bisect
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import STATE, record
from compare_search import immutable_blob
from data_contract import BlobServiceClient, DEMO_KEY
from release_million import RELEASE, category_ranges, product_at

DATA = STATE / 'releases' / RELEASE
POOL = DATA / 'judgements-pool-v2.jsonl'
MANIFEST = DATA / 'judgement-pool-v2-manifest.json'


def grade_result(plan, product):
    if plan['kind'] == 'zero' or product['category'] != plan['category']:
        return 0
    if product['product_type'] != plan['product_type']:
        return 1
    if plan['kind'] == 'type' or product[plan['kind']] == plan['value']:
        return 3
    return 2


def downloaded_report(reference):
    path = reference['report_blob']
    container, name = path.split('/', 1)
    account = BlobServiceClient(account_url='http://127.0.0.1:14577/devstoreaccount1', credential=DEMO_KEY)
    payload = account.get_blob_client(container, name).download_blob().readall()
    if hashlib.sha256(payload).hexdigest() != reference['report_sha256']:
        raise ValueError('Source comparison report hash differs.')
    report = json.loads(payload)
    if not report['complete'] or report['query_count'] != 1000:
        raise ValueError('Source comparison must cover all 1,000 queries.')
    return report


def generate():
    state = json.loads((STATE / 'million-control-state.json').read_text(encoding='utf-8'))
    refs = [state['comparisons'][name + '-result-regression'] for name in ('api', 'index')]
    reports = [downloaded_report(ref) for ref in refs]
    plans = {row['query_id']: row for row in
             (json.loads(line) for line in (DATA / 'queries.jsonl').read_text(encoding='utf-8').splitlines())}
    ranges = category_ranges(1_000_000)
    ends = [row['start'] + row['count'] for row in ranges]
    pooled = {qid: set() for qid in plans}
    for report in reports:
        if {row['query_id'] for row in report['queries']} != set(plans):
            raise ValueError('Source comparison query IDs differ from the frozen release.')
        for row in report['queries']:
            for side in ('baseline', 'candidate'):
                pooled[row['query_id']].update(row[side]['ids'])
    original = {}
    for line in (DATA / 'judgements.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        original.setdefault(row['query_id'], []).append(row)
        pooled[row['query_id']].add(row['product_id'])
    original_grades = {(qid, row['product_id']): row['grade']
                       for qid, originals in original.items() for row in originals}
    rows = []
    for qid, plan in plans.items():
        for product_id in sorted(pooled[qid]):
            number = int(product_id.removeprefix('gb-'))
            category = ranges[bisect.bisect_right(ends, number)]
            product = product_at(category, number - category['start'])
            grade = original_grades.get((qid, product_id), grade_result(plan, product))
            rows.append({'query_id': qid, 'product_id': product_id, 'grade': grade,
                         'assessment': ('I', 'C', 'S', 'E')[grade]})
    labelled = {(row['query_id'], row['product_id']): row['grade'] for row in rows}
    if len(labelled) != len(rows) or len({row['query_id'] for row in rows}) != len(plans):
        raise ValueError('Pool IDs or query coverage differ.')
    if any(labelled[(qid, row['product_id'])] != row['grade']
           for qid, originals in original.items() for row in originals):
        raise ValueError('Original frozen grades were not retained.')
    if any((qid, product_id) not in labelled for qid, ids in pooled.items() for product_id in ids):
        raise ValueError('A pooled result ID is unjudged.')
    payload = ''.join(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n'
                      for row in rows).encode()
    digest = hashlib.sha256(payload).hexdigest()
    if POOL.exists() and POOL.read_bytes() != payload:
        raise ValueError('Frozen pooled assessment bytes differ.')
    if not POOL.exists():
        POOL.write_bytes(payload)
    release = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
    manifest = {'kind': 'symmetric synthetic result-pool assessments', 'schema_version': 2,
                'release': RELEASE, 'query_sha256': release['sha256']['queries.jsonl'],
                'original_judgement_sha256': release['sha256']['judgements.jsonl'],
                'source_report_sha256': [ref['report_sha256'] for ref in refs],
                'sha256': digest, 'count': len(rows),
                'query_count': len(plans),
                'pool_coverage': 'Original twenty-per-query assessments plus top ten from baseline and both candidate types',
                'grading': 'Retain original frozen grades; apply deterministic rules only to newly pooled result IDs',
                'limitation': 'Rule-based assessments selected after seeing these three result lists; future lists may contain unjudged products.'}
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    if MANIFEST.exists() and MANIFEST.read_bytes() != manifest_bytes:
        raise ValueError('Frozen pooled assessment manifest differs.')
    if not MANIFEST.exists():
        MANIFEST.write_bytes(manifest_bytes)
    location = immutable_blob('datasets', RELEASE + '/judgement-pools/v2/judgements.jsonl', payload)
    manifest_location = immutable_blob('datasets', RELEASE + '/judgement-pools/v2/manifest.json', manifest_bytes)
    evidence = {**manifest, 'blob': location, 'manifest_blob': manifest_location}
    record('million-judgement-pool', evidence)
    return evidence


if __name__ == '__main__':
    print(json.dumps(generate(), indent=2))
