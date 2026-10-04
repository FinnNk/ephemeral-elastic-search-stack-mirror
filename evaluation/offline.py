"""Score one frozen public-API observation set across named variants."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lab/search-app'))
from search_filters import validate_filters

import ir_measures
from result_similarity import summarise

SCHEMA = 1
METRICS = {'nDCG@5': ir_measures.nDCG @ 5,
           'nDCG@10': ir_measures.nDCG @ 10,
           'Judged@10': ir_measures.Judged @ 10,
           'RR@10:rel=2': ir_measures.RR(rel=2) @ 10}


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_bytes().splitlines()]


def source_identity():
    return sha(Path(__file__).read_bytes())


def validate_observations(value):
    if value.get('kind') != 'search-variant-observation-set' or value.get('schema_version') != SCHEMA:
        raise ValueError('Unsupported observation contract.')
    variants = value.get('variants')
    if not isinstance(variants, dict) or len(variants) < 2 or any(
            not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', name)
            or not isinstance(pin, dict)
            or not re.fullmatch(r'[0-9a-f]{64}', str(pin.get('environment_fingerprint', '')))
            or not re.fullmatch(r'[0-9a-f]{64}', str(pin.get('configuration_sha256', '')))
            or not re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}', str(pin.get('image', '')))
            for name, pin in variants.items()):
        raise ValueError('At least two named, pinned variants are required.')
    if value.get('default_variant') not in variants or value.get('baseline_variant') not in variants:
        raise ValueError('Default and baseline must name variants in the frozen set.')
    depth = value.get('captured_depth')
    if type(depth) is not int or depth < 1:
        raise ValueError('Observation depth is invalid.')
    if value.get('errors') != [] or value.get('request_adapter') != 'search-api-variant-v1':
        raise ValueError('Observation execution is incomplete or uses another request adapter.')
    if value.get('captured_at') is not None:
        moment = datetime.fromisoformat(value['captured_at'].replace('Z', '+00:00'))
        if moment.utcoffset() is None:
            raise ValueError('Observation capture time must include a UTC offset.')
    ids = set()
    for row in value.get('observations', []):
        qid = row.get('query_id')
        if not isinstance(qid, str) or qid in ids:
            raise ValueError('Observation IDs are missing or duplicated.')
        ids.add(qid)
        request = row.get('request', {})
        if not all(isinstance(request.get(key), str) and request[key]
                   for key in ('query', 'country', 'currency')) or \
                not isinstance(request.get('filters'), dict):
            raise ValueError('Observation does not retain the original request.')
        validate_filters(request['filters'])
        answers = row.get('results')
        if not isinstance(answers, dict) or set(answers) != set(variants):
            raise ValueError('Observation does not cover every frozen variant.')
        for variant, answer in answers.items():
            result_ids = answer.get('ids')
            if not isinstance(result_ids, list) or len(result_ids) > depth or \
                    len(set(result_ids)) != len(result_ids) or \
                    type(answer.get('total')) is not int or answer['total'] < len(result_ids) or \
                    answer.get('variant_id') != variant or \
                    answer.get('configuration_sha256') != variants[variant]['configuration_sha256']:
                raise ValueError('Observation result list is invalid.')
    if not ids:
        raise ValueError('Observation set is empty.')
    return value


def evaluate(observation_path, judgement_path, specification_path,
             catalogue_manifest_path, query_manifest_path, judgement_manifest_path,
             evaluated_at=None):
    observation_bytes = Path(observation_path).read_bytes()
    observations = validate_observations(json.loads(observation_bytes))
    evaluated_at = evaluated_at or datetime.now(timezone.utc).isoformat()
    if datetime.fromisoformat(evaluated_at.replace('Z', '+00:00')).utcoffset() is None:
        raise ValueError('Evaluation time must include a UTC offset.')
    catalogue = json.loads(Path(catalogue_manifest_path).read_bytes())
    queries = json.loads(Path(query_manifest_path).read_bytes())
    if observations['catalogue_sha256'] != catalogue['content']['sha256'] or \
            observations['query_suite_sha256'] != queries['content']['sha256']:
        raise ValueError('Observations belong to another catalogue or query suite.')
    judgement_bytes = Path(judgement_path).read_bytes()
    judgement_manifest_bytes = Path(judgement_manifest_path).read_bytes()
    judgement_manifest = json.loads(judgement_manifest_bytes)
    if judgement_manifest.get('kind') != 'judgement-set' or \
            judgement_manifest.get('schema_version') != SCHEMA or \
            judgement_manifest.get('content', {}).get('sha256') != sha(judgement_bytes) or \
            judgement_manifest.get('dependencies') != {
                'catalogue': catalogue['content']['sha256'],
                'query-suite': queries['content']['sha256']}:
        raise ValueError('Judgement set is incompatible with retained observations.')
    specification_bytes = Path(specification_path).read_bytes()
    specification = json.loads(specification_bytes)
    if specification.get('kind') != 'evaluation-specification' or \
            specification.get('schema_version') != SCHEMA:
        raise ValueError('Unsupported evaluation specification.')
    names = specification.get('metrics')
    if not isinstance(names, list) or not names or len(set(names)) != len(names) or \
            any(name not in METRICS for name in names):
        raise ValueError('Unsupported or duplicated metric definition.')
    if specification.get('unjudged_policy') != 'unknown; metric library treats missing qrels as zero' or \
            specification.get('aggregation') != 'macro':
        raise ValueError('Judgement or aggregation policy is not explicit.')
    if any(int(name.split('@')[1].split(':')[0]) > observations['captured_depth']
           for name in names):
        raise ValueError('Metric cut-off exceeds captured result depth.')
    selected = [METRICS[name] for name in names]
    rows = [json.loads(line) for line in judgement_bytes.splitlines()]
    if judgement_manifest.get('record_count') != len(rows):
        raise ValueError('Judgement manifest record count differs.')
    observed_ids = {row['query_id'] for row in observations['observations']}
    judgements = {}
    sources = {}
    for row in rows:
        key = (row['query_id'], row['product_id'])
        if key in judgements:
            raise ValueError('Duplicate judgement in the selected set.')
        if row['query_id'] not in observed_ids:
            continue
        if type(row.get('grade')) is not int or row['grade'] not in range(4):
            raise ValueError('Judgement grade must be 0, 1, 2 or 3.')
        judgements[key] = row['grade']
        provenance = row.get('provenance', {'kind': 'published',
                                           'source_id': judgement_manifest['content']['sha256']})
        eligible = row.get('gate_eligible', True)
        if not isinstance(provenance, dict) or type(eligible) is not bool:
            raise ValueError('Selected judgement provenance or eligibility is invalid.')
        identity = sha(canonical({'provenance': provenance, 'gate_eligible': eligible}))
        source = sources.setdefault(identity, {'provenance': provenance,
                                                'gate_eligible': eligible, 'count': 0})
        source['count'] += 1
    qrels = [ir_measures.Qrel(qid, pid, grade)
             for (qid, pid), grade in judgements.items()]
    results = {}
    coverage = {}
    per_case = {}
    for variant in observations['variants']:
        run = [ir_measures.ScoredDoc(row['query_id'], pid, len(row['results'][variant]['ids']) - rank)
               for row in observations['observations']
               for rank, pid in enumerate(row['results'][variant]['ids'])]
        aggregate = ir_measures.calc_aggregate(selected, qrels, run)
        results[variant] = {name: round(aggregate[METRICS[name]], 6) for name in names}
        judged = sum((row['query_id'], pid) in judgements
                     for row in observations['observations'] for pid in row['results'][variant]['ids'])
        returned = sum(len(row['results'][variant]['ids']) for row in observations['observations'])
        coverage[variant] = {'judged': judged, 'returned': returned,
                          'fraction': round(judged / returned, 6) if returned else None}
        values = {name: {} for name in names}
        for item in ir_measures.iter_calc(selected, qrels, run):
            name = next(name for name in names if METRICS[name] == item.measure)
            values[name][item.query_id] = round(item.value, 6)
        per_case[variant] = values
    baseline = observations['baseline_variant']
    deltas = {variant: {name: round(score - results[baseline][name], 6)
                        for name, score in scores.items()}
              for variant, scores in results.items() if variant != baseline}
    result_changes = {}
    for variant in results:
        changed = sum(row['results'][variant]['ids'] != row['results'][baseline]['ids'] or
                      row['results'][variant]['total'] != row['results'][baseline]['total']
                      for row in observations['observations'])
        result_changes[variant] = {'changed_queries': changed,
                                   'fraction': round(changed / len(observed_ids), 6)}
    return {'kind': 'variant-evaluation-report', 'schema_version': SCHEMA,
            'complete': True, 'query_count': len(observed_ids),
            'judgement_selection': judgement_manifest.get('producer', {}).get('selection', 'gate'),
            'judgement_rubric': judgement_manifest.get('producer', {}).get('rubric'),
            'judgement_sources': [sources[identity] for identity in sorted(sources)],
            'unqualified_judgements': sum(source['count'] for source in sources.values()
                                         if not source['gate_eligible']),
            'default_variant': observations['default_variant'],
            'baseline_variant': baseline, 'variants': observations['variants'],
            'variant_set_sha256': observations.get('variant_set_sha256'),
            'catalogue_sha256': observations['catalogue_sha256'],
            'query_suite_sha256': observations['query_suite_sha256'],
            'observation_sha256': sha(observation_bytes),
            'observation_captured_at': observations.get('captured_at'),
            'evaluated_at': evaluated_at,
            'judgement_sha256': sha(judgement_bytes),
            'judgement_manifest_sha256': sha(judgement_manifest_bytes),
            'specification_sha256': sha(specification_bytes),
            'evaluator_sha256': source_identity(),
            'metrics': results, 'delta_from_baseline': deltas,
            'result_changes': result_changes,
            'result_similarity': summarise(observations, baseline),
            'coverage': coverage, 'per_case': per_case,
            'unjudged_policy': specification['unjudged_policy']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations', required=True, type=Path)
    parser.add_argument('--judgements', required=True, type=Path)
    parser.add_argument('--specification', required=True, type=Path)
    parser.add_argument('--catalogue-manifest', required=True, type=Path)
    parser.add_argument('--query-manifest', required=True, type=Path)
    parser.add_argument('--judgement-manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--evaluated-at', help='Fixed UTC evaluation time for a repeatable fixture run')
    args = parser.parse_args()
    result = evaluate(args.observations, args.judgements, args.specification,
                      args.catalogue_manifest, args.query_manifest, args.judgement_manifest,
                      args.evaluated_at)
    payload = canonical(result)
    if args.output.exists() and args.output.read_bytes() != payload:
        raise ValueError('Existing evaluation report differs.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists():
        args.output.write_bytes(payload)
    print(json.dumps({'report_sha256': sha(payload), 'complete': result['complete'],
                      'query_count': result['query_count'], 'metrics': result['metrics'],
                      'result_similarity': {name: {key: value for key, value in scores.items()
                                                   if key != 'per_query'}
                                            for name, scores in result['result_similarity'].items()}}))


if __name__ == '__main__':
    main()
