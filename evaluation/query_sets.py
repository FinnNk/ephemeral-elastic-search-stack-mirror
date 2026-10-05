"""Freeze source-controlled query sets and report their results independently."""
import hashlib
import json
import math
from pathlib import PurePosixPath
import re
from pathlib import Path
import tempfile

from search_filters import validate_filters
from result_similarity import summarise
from ndcg_significance import analyse


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def source_path(value):
    """Accept bounded evaluation paths; never read arbitrary repository files."""
    if not isinstance(value, str) or '\\' in value:
        raise ValueError('Query-set paths must be repository-relative evaluation paths.')
    path = PurePosixPath(value)
    if (path.is_absolute() or '..' in path.parts or not value.startswith('evaluation/')
            or path.suffix != '.jsonl' or str(path) != value):
        raise ValueError('Query-set paths must be repository-relative evaluation JSONL paths.')
    return value


def declarations(selection):
    """Validate optional suites; the frozen standard suite is always required."""
    extra = selection.get('additional_query_sets', [])
    if not isinstance(extra, list) or len(extra) > 8:
        raise ValueError('Select at most eight additional query sets.')
    names = {'standard'}
    for item in extra:
        if (not isinstance(item, dict) or set(item) - {'name', 'path', 'required', 'judgements'}
                or not {'name', 'path'} <= set(item)
                or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', str(item.get('name', '')))
                or item['name'] in names or type(item.get('required', False)) is not bool):
            raise ValueError('Additional query sets need distinct names and explicit valid settings.')
        names.add(item['name'])
        source_path(item['path'])
        if 'judgements' in item:
            source_path(item['judgements'])
        if item.get('required') and not item.get('judgements'):
            raise ValueError('A required additional set needs a matching judgement file.')
    return extra


def freeze(selection, read_source):
    """Read original bytes from the caller's exact source revision, preserving hashes."""
    frozen = []
    for item in declarations(selection):
        payload = read_source(item['path'])
        if len(payload) > 700_000:
            raise ValueError('Additional query set exceeds the capture payload limit.')
        rows = [json.loads(line) for line in payload.splitlines()]
        ids = set()
        for row in rows:
            if (not isinstance(row, dict) or not all(isinstance(row.get(key), str) and row[key]
                    for key in ('query_id', 'query', 'country', 'currency'))
                    or row['query_id'] in ids or len(row['query']) > 150
                    or (row['country'], row['currency']) != ('GB', 'GBP')):
                raise ValueError('Query-set rows need distinct IDs and valid GB/GBP requests.')
            ids.add(row['query_id'])
            validate_filters(row.get('filters', {}))
        if not rows:
            raise ValueError('Additional query set is empty.')
        label_bytes = read_source(item['judgements']) if item.get('judgements') else b''
        labels = [json.loads(line) for line in label_bytes.splitlines()]
        pairs = set()
        for label in labels:
            if (label.get('query_id') not in ids or not isinstance(label.get('product_id'), str)
                    or not label['product_id'] or type(label.get('grade')) is not int
                    or label['grade'] not in range(4)
                    or (label['query_id'], label['product_id']) in pairs):
                raise ValueError('Additional labels need unique query/product pairs and ESCI grades.')
            # Source-controlled labels are authored reference judgements. Model
            # predictions belong behind the judgement API with their provenance.
            if label.get('provenance', {}).get('kind') == 'model':
                raise ValueError('Model predictions cannot be supplied as source reference labels.')
            pairs.add((label['query_id'], label['product_id']))
        frozen.append({**item, 'required': item.get('required', False),
                       'query_bytes': payload, 'query_sha256': sha(payload), 'queries': rows,
                       'judgement_bytes': label_bytes, 'judgement_sha256': sha(label_bytes),
                       'judgements_rows': labels})
    return frozen


def combine(reports, requests_by_suite):
    """Combine equally weighted query cases, disclosing repeats and absent labels."""
    variants = reports['standard']['variants']
    metrics = {}
    similarities = {}
    labelled_cases = sum(r.get('relevance_query_count', r['query_count']) for r in reports.values() if r.get('relevance_available', True))
    total = sum(r['query_count'] for r in reports.values())
    for variant in variants:
        names = reports['standard']['metrics'][variant]
        metrics[variant] = {metric: round(sum(
            report['metrics'][variant][metric] * report.get('relevance_query_count', report['query_count'])
            for report in reports.values() if report.get('relevance_available', True)) / labelled_cases, 6)
            if labelled_cases else None for metric in names}
        similarities[variant] = {metric: round(sum(
            report['result_similarity'][variant][metric] * report['query_count']
            for report in reports.values()) / total, 6)
            for metric in ('rbo_at_10_p_0_9', 'jaccard_at_10')}
    seen, repeats = set(), 0
    for rows in requests_by_suite.values():
        for row in rows:
            identity = canonical({key: row.get(key, {} if key == 'filters' else None)
                                  for key in ('query', 'country', 'currency', 'filters')})
            repeats += identity in seen
            seen.add(identity)
    if any(not math.isfinite(v) for scores in similarities.values() for v in scores.values()):
        raise ValueError('Combined similarity is not finite.')
    per_case = {v: {} for v in variants}
    requests, eligible = {}, set()
    for suite, report in reports.items():
        for row in requests_by_suite[suite]:
            requests[suite + ':' + row['query_id']] = row
        eligible.update(suite + ':' + qid for qid in report.get('ndcg_eligible_query_ids', []))
        for variant, scores in report.get('per_case', {}).items():
            for metric, cases in scores.items():
                per_case[variant].setdefault(metric, {}).update(
                    {suite + ':' + qid: score for qid, score in cases.items()})
    significance = analyse(per_case, requests, reports['standard']['baseline_variant'], variants, eligible)
    return {'ndcg_significance': significance, 'weighting': 'equal weight per query case; repeated requests counted in each suite',
            'query_count': total, 'relevance_query_count': labelled_cases,
            'unlabelled_query_count': total - labelled_cases,
            'repeated_request_count': repeats, 'metrics': metrics,
            'result_similarity': similarities, 'used_for_gate': False}


def assemble(standard, extra_reports, frozen, standard_queries, selection):
    """Keep standard gate metrics at the top and retain every named suite separately."""
    reports = {'standard': standard, **extra_reports}
    if set(extra_reports) != {item['name'] for item in frozen}:
        raise ValueError('Not every additional query set was evaluated.')
    metadata = {'standard': {'required': True, 'query_sha256': standard['query_suite_sha256']}}
    for item in frozen:
        metadata[item['name']] = {key: value for key, value in item.items()
                                  if key in ('name', 'path', 'required', 'judgements',
                                             'query_sha256', 'judgement_sha256')}
    requests = {'standard': standard_queries, **{item['name']: item['queries'] for item in frozen}}
    return {**standard, 'query_sets': reports, 'query_set_metadata': metadata,
            'additional_query_sets_selection_sha256': sha(canonical(declarations(selection))),
            'combined': combine(reports, requests),
            'complete': all(report['complete'] for report in reports.values())}


def score_extra(item, observations, specification_bytes, catalogue_manifest_bytes):
    """Score a fresh extra capture; absent reference labels stay explicitly unknown."""
    from offline import evaluate, validate_observations
    validate_observations(observations)
    if observations['query_suite_sha256'] != item['query_sha256'] or \
            {row['query_id'] for row in observations['observations']} != {
                row['query_id'] for row in item['queries']}:
        raise ValueError('Additional capture differs from its frozen query set.')
    variants = observations['variants']
    baseline = observations['baseline_variant']
    changes = {variant: {
        'changed_queries': sum(row['results'][variant]['ids'] != row['results'][baseline]['ids'] or
                               row['results'][variant]['total'] != row['results'][baseline]['total']
                               for row in observations['observations'])}
        for variant in variants}
    for value in changes.values():
        value['fraction'] = round(value['changed_queries'] / len(item['queries']), 6)
    labelled = {(row['query_id'], row['product_id']) for row in item['judgements_rows']}
    positive_queries = {row['query_id'] for row in item['judgements_rows'] if row['grade'] > 0}
    resolution = item.get('judgement_resolution')
    coverage = {}
    for name in variants:
        returned = [(row['query_id'], pid) for row in observations['observations']
                    for pid in row['results'][name]['ids']]
        judged = sum(pair in labelled for pair in returned)
        coverage[name] = {'judged': judged, 'returned': len(returned),
                          'fraction': round(judged / len(returned), 6) if returned else None}
    reason = None
    if not any(c['returned'] for c in coverage.values()):
        reason = 'No products were returned by any variant.'
    elif not item['judgements_rows']:
        reason = ('No judgements were supplied or requested.' if resolution is None else
                  'No usable labels: all resolution outcomes were abstentions, errors or ineligible predictions.')
    elif not positive_queries:
        reason = 'No positive relevance labels: nDCG has no non-zero ideal gain.'
    if reason:
        metric_names = [name for name in json.loads(specification_bytes)['metrics'] if name.startswith('nDCG@')]
        significance = analyse({v: {name: {} for name in metric_names} for v in variants},
            {r['query_id']: r for r in item['queries']}, baseline, variants, set())
        return {'kind': 'variant-evaluation-report', 'schema_version': 1, 'complete': True,
                'variants': variants, 'default_variant': observations['default_variant'],
                'baseline_variant': baseline, 'query_count': len(item['queries']),
                'catalogue_sha256': observations['catalogue_sha256'],
                'query_suite_sha256': item['query_sha256'], 'observation_sha256': sha(canonical(observations)),
                'relevance_available': False, 'metrics': None, 'ndcg_significance': significance,
                'delta_from_baseline': {v: {'nDCG@5': None, 'nDCG@10': None} for v in variants if v != baseline},
                'relevance_unavailable_reason': reason, 'relevance_query_count': 0,
                'unlabelled_query_count': len(item['queries']),
                'judgement_resolution': resolution, 'execution': observations.get('execution'),
                'coverage': coverage, 'result_changes': changes,
                'result_similarity': summarise(observations, baseline)}
    manifest = {'kind': 'judgement-set', 'schema_version': 1,
                'record_count': len(item['judgements_rows']),
                'content': {'sha256': item['judgement_sha256']},
                'dependencies': {'catalogue': observations['catalogue_sha256'],
                                 'query-suite': item['query_sha256']},
                'producer': {'selection': item.get('judgement_selection', 'gate'), 'rubric': 'esci-v1'}}
    # Exclude cases without positive references from quality averages; disclose
    # their coverage separately instead of making unknown quality look like zero.
    scored_observations = {**observations, 'observations': [r for r in observations['observations']
                                                          if r['query_id'] in positive_queries]}
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        contents = {'observations': canonical(scored_observations), 'judgements': item['judgement_bytes'],
                    'specification': specification_bytes, 'catalogue': catalogue_manifest_bytes,
                    'queries': canonical({'kind': 'query-suite', 'content': {'sha256': item['query_sha256']}}),
                    'manifest': canonical(manifest)}
        for name, payload in contents.items():
            (folder / name).write_bytes(payload)
        result = evaluate(*(folder / name for name in (
            'observations', 'judgements', 'specification', 'catalogue', 'queries', 'manifest')))
    result['coverage'] = coverage
    result['ndcg_significance'] = analyse(result['per_case'],
        {r['query_id']: r for r in item['queries']}, baseline, variants, positive_queries)
    return {**result, 'query_count': len(item['queries']), 'relevance_query_count': len(positive_queries),
            'unlabelled_query_count': len(item['queries']) - len(positive_queries),
            'observation_sha256': sha(canonical(observations)), 'result_changes': changes,
            'result_similarity': summarise(observations, baseline),
            'judgement_resolution': resolution, 'relevance_available': True}
