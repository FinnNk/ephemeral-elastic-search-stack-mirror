"""Score two pinned public APIs against the frozen synthetic judgements."""
import hashlib
import json
import sys
from collections import defaultdict

from pathlib import Path

sys.path.insert(0, str(Path('.lab/python-libs').resolve()))
import ir_measures

sys.path.insert(0, 'research/platform-spike')
from common import STATE, guard, record
from compare_search import definition, immutable_blob, response

BASELINE = 'retail-baseline'
CANDIDATE = 'retail-price-rank'
MEASURES = (ir_measures.nDCG @ 10, ir_measures.Judged @ 10, ir_measures.RR(rel=2) @ 10)


def frozen_judgements():
    release = STATE / 'releases/retail-gb-10k-v1'
    manifest = json.loads((release / 'manifest.json').read_text())
    payloads = {}
    for name in ('queries.jsonl', 'judgements.jsonl'):
        payload = (release / name).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == manifest['sha256'][name]
        payloads[name] = [json.loads(line) for line in payload.splitlines()]
    queries = payloads['queries.jsonl']
    judgements = payloads['judgements.jsonl']
    assert len(queries) == manifest['query_count'] == 50
    assert len(judgements) == manifest['judgement_count']
    qids = {row['query_id'] for row in queries}
    assert len(qids) == 50 and {row['query_id'] for row in judgements} == qids
    assert all(1 <= row['grade'] <= 3 for row in judgements)
    return queries, judgements, manifest


def score(judgements, results):
    qrels = [ir_measures.Qrel(row['query_id'], row['product_id'], row['grade']) for row in judgements]
    run = [ir_measures.ScoredDoc(qid, product_id, 10 - rank)
           for qid, ids in results.items() for rank, product_id in enumerate(ids[:10])]
    values = ir_measures.calc_aggregate(MEASURES, qrels, run)
    return {str(metric): round(values[metric], 6) for metric in MEASURES}


def evaluate():
    guard()
    baseline = definition(BASELINE)
    candidate = definition(CANDIDATE)
    assert baseline['dataset_sha256'] == candidate['dataset_sha256']
    assert baseline['index'] == candidate['index']
    assert baseline['engine'] == candidate['engine']
    assert baseline['image'] != candidate['image']
    queries, judgements, manifest = frozen_judgements()
    judged = defaultdict(set)
    for row in judgements:
        judged[row['query_id']].add(row['product_id'])
    results = {BASELINE: {}, CANDIDATE: {}}
    query_rows = []
    for row in queries:
        qid = row['query_id']
        entry = {'query_id': qid, 'query': row['query'], 'judgement_count': len(judged[qid])}
        for name in results:
            answer = response(name, row)
            ids = answer['ids']
            results[name][qid] = ids
            entry[name] = {**answer,
                           'judged_top_10_count': len(set(ids) & judged[qid]),
                           'unjudged_top_10_ids': [pid for pid in ids if pid not in judged[qid]],
                           'metrics': score([j for j in judgements if j['query_id'] == qid], {qid: ids})}
        query_rows.append(entry)
    aggregate = {name: score(judgements, results[name]) for name in results}
    changed_query_ids = [row['query_id'] for row in query_rows
                         if row[BASELINE]['ids'] != row[CANDIDATE]['ids']]
    report = {'kind': 'black-box-graded-relevance-evaluation', 'complete': True,
        'baseline': baseline, 'candidate': candidate,
        'query_sha256': manifest['sha256']['queries.jsonl'],
        'judgement_sha256': manifest['sha256']['judgements.jsonl'],
        'query_count': len(queries), 'judgement_count': len(judgements),
        'evaluation_library': 'ir-measures==0.4.3',
        'interpretation': 'Rules-based positive-only synthetic qrels are incomplete. Unjudged results are unknown, '
                          'although nDCG treats them as zero. Report Judged@10 alongside nDCG; scores are a '
                          'repeatable proxy for this judgement pool, not human or production relevance.',
        'aggregate': aggregate, 'changed_query_ids': changed_query_ids, 'queries': query_rows}
    payload = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    location = immutable_blob('runs', digest + '/retail-relevance-evaluation.json', payload)
    summary = {'report_sha256': digest, 'report_blob': location,
        'query_count': len(queries), 'judgement_count': len(judgements),
        'baseline_fingerprint': baseline['fingerprint'],
        'candidate_fingerprint': candidate['fingerprint'], 'aggregate': aggregate,
        'changed_query_count': len(changed_query_ids)}
    record('retail-relevance-evaluation', summary)
    return summary


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
