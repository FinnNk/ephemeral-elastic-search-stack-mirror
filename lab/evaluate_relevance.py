"""Score two pinned public APIs against the frozen synthetic judgements."""
import hashlib
import json
from collections import defaultdict
import ir_measures

from common import guard, record
from compare_search import definition, immutable_blob, response
from input_selection import select

BASELINE = 'retail-baseline'
CANDIDATE = 'retail-price-rank'
MEASURES = (ir_measures.nDCG @ 10, ir_measures.Judged @ 10, ir_measures.RR(rel=2) @ 10)


def score(judgements, results):
    qrels = [ir_measures.Qrel(row['query_id'], row['product_id'], row['grade']) for row in judgements]
    run = [ir_measures.ScoredDoc(qid, product_id, 10 - rank)
           for qid, ids in results.items() for rank, product_id in enumerate(ids[:10])]
    values = ir_measures.calc_aggregate(MEASURES, qrels, run)
    return {str(metric): round(values[metric], 6) for metric in MEASURES}


def query_ndcg(judgements, results):
    metric = ir_measures.nDCG @ 10
    qrels = [ir_measures.Qrel(row['query_id'], row['product_id'], row['grade']) for row in judgements]
    run = [ir_measures.ScoredDoc(qid, product_id, 10 - rank)
           for qid, ids in results.items() for rank, product_id in enumerate(ids[:10])]
    return {item.query_id: round(item.value, 6)
            for item in ir_measures.iter_calc([metric], qrels, run)}


def evaluate():
    guard()
    baseline = definition(BASELINE)
    candidate = definition(CANDIDATE)
    assert baseline['dataset_sha256'] == candidate['dataset_sha256']
    assert baseline['index'] == candidate['index']
    assert baseline['engine'] == candidate['engine']
    assert baseline['image'] != candidate['image']
    selected = select('retail-gb-10k-v1', baseline['dataset_sha256'], relevance=True)
    queries, judgements = selected['queries'], selected['judgements']
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
        'query_sha256': selected['query_manifest']['content']['sha256'],
        'query_manifest_sha256': selected['query_manifest_sha256'],
        'judgement_sha256': selected['judgement_manifest']['content']['sha256'],
        'judgement_manifest_sha256': selected['judgement_manifest_sha256'],
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
