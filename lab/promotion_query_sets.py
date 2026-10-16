"""Frozen extra suites for promotion; the standard suite cannot be replaced."""
import json
import sys
from datetime import datetime, timezone
from copy import deepcopy

from common import ROOT
from input_selection import DEFAULTS
sys.path[:0] = [str(ROOT / 'evaluation'), str(ROOT / 'lab/search-app')]
from query_sets import freeze, score_extra, combine, canonical, sha


def standard_inputs(deployment, selected):
    """Reject a replacement primary suite before creating evaluation workloads."""
    from primary_query_sets import configuration
    group = configuration(deployment['fields']['dataset_release'])
    expected = DEFAULTS[deployment['fields']['dataset_release']]['query-suite']
    if (not isinstance(selected, dict) or selected.get('query_manifest_sha256') != expected or
            selected.get('judgement_manifest_sha256') != group[0]['judgement_manifest_sha256']):
        raise ValueError('Promotion always requires the catalogue\'s frozen standard query suite. '
                         'Declare custom queries as additional_query_sets instead of replacing it.')


def frozen_sets(selection, deployment=None):
    from delivery_source_comparison import source_bytes
    from primary_query_sets import frozen_sets as mandatory_sets
    primary = mandatory_sets(deployment['fields']['dataset_release'], deployment['fields']['dataset_sha256']) if deployment else []
    if selection.get('_release_plan'):
        from release_check_plans import frozen_additional
        return [*primary, *frozen_additional(selection['_release_plan'])]
    return [*primary, *freeze({'additional_query_sets': selection.get('additional_query_sets', [])},
                  lambda path: source_bytes(path, selection['source_sha']))]


def policy():
    return json.loads((ROOT / 'lab/delivery/policies/variant-merge-v1.json').read_text(encoding='utf-8'))


def outcome(report, required, intent):
    """Apply the trusted required-set limits; report-only measurements never block."""
    result = {'state': 'blocked', 'required': required, 'used_for_gate': required}
    def measured(value):
        if required:
            return value
        return {**value, 'state': 'report_only', 'assessment': value['state'],
                'available': report.get('complete') is True}
    try:
        from variant_gate import require_gate_judgements, number
        limits = policy()
        if report.get('complete') is not True or report.get('relevance_available') is not True:
            raise ValueError(report.get('relevance_unavailable_reason') or 'Required query set has incomplete capture or no usable relevance scores.')
        if required:
            require_gate_judgements(report)
        metric = limits['metric']
        coverage = min(number(report['coverage'][v]['fraction'], 'Judged coverage')
                       for v in ('baseline', 'candidate'))
        delta = round(number(report['metrics']['candidate'][metric], 'Candidate score') -
                      number(report['metrics']['baseline'][metric], 'Baseline score'), 6)
        count = report['query_count']
        changed = report['result_changes']['candidate']['changed_queries']
        if type(count) is not int or count < 1 or type(changed) is not int or not 0 <= changed <= count:
            raise ValueError('Required query set has invalid result-change counts.')
        fraction = changed / count
        budgets = limits['changed_query_fraction'][intent]
        if coverage < limits['minimum_judged_fraction'] or delta < limits['exception_min_delta'] or fraction > budgets['exception']:
            state = 'blocked'
        elif delta >= limits['pass_min_delta'] and fraction <= budgets['pass']:
            state = 'pass'
        else:
            state = 'decision_required'
        reasons = []
        if coverage < limits['minimum_judged_fraction']:
            reasons.append(f'Judged coverage {coverage:.1%} is below {limits["minimum_judged_fraction"]:.1%}.')
        if delta < limits['pass_min_delta']:
            reasons.append(f'{metric} change {delta:+.4f} is below {limits["pass_min_delta"]:+.4f}.')
        if fraction > budgets['pass']:
            reasons.append(f'Changed-query fraction {fraction:.1%} exceeds {budgets["pass"]:.1%}.')
        return measured({**result, 'state': state, 'delta': delta, 'judged_fraction': coverage,
                'changed_query_fraction': fraction, 'reason': ' '.join(reasons) or 'Within the comparison limits.'})
    except (ValueError, KeyError, TypeError) as error:
        return measured({**result, 'state': 'blocked' if required else 'incomplete', 'reason': str(error)})


def pins(baseline, candidate, runtime):
    return {side: {'image': deployment['fields']['image'],
                   'environment_fingerprint': deployment['fingerprint'],
                   'configuration_sha256': runtime[side]['configuration_sha256']}
            for side, deployment in (('baseline', baseline), ('candidate', candidate))}


def standard_report(report, variant_pins, inputs):
    """Adapt the unchanged standard measurements to the suite display contract."""
    count = report['query_count']
    changes = len(report['changed_query_ids'])
    per_case = {side: {'nDCG@10': {row['query_id']: row[side]['ndcg_at_10']
                for row in report['queries']}} for side in ('baseline', 'candidate')}
    positives = {row['query_id'] for row in inputs['judgements'] if row['grade'] > 0}
    return {'kind': 'variant-evaluation-report', 'schema_version': 1, 'complete': report['complete'],
        'baseline_variant': 'baseline', 'default_variant': 'candidate', 'variants': variant_pins,
        'query_count': count, 'relevance_available': True, 'metrics': report['metrics'],
        'coverage': report['judgement_coverage'], 'judgement_coverage': report['judgement_coverage'],
        'catalogue_sha256': report['baseline']['dataset_sha256'],
        'query_suite_sha256': report['suite_sha256'], 'per_case': per_case,
        'ndcg_eligible_query_ids': sorted(positives), 'ndcg_significance': report.get('ndcg_significance'),
        'result_changes': {'baseline': {'changed_queries': 0, 'fraction': 0},
                           'candidate': {'changed_queries': changes, 'fraction': changes/count}},
        'result_similarity': {'baseline': {'rbo_at_10_p_0_9': 1, 'jaccard_at_10': 1},
                             'candidate': {k: report['result_similarity'].get(k) for k in
                                           ('rbo_at_10_p_0_9', 'jaccard_at_10')}},
        'delta_from_baseline': {'candidate': {'nDCG@10': round(
            report['metrics']['candidate']['nDCG@10'] - report['metrics']['baseline']['nDCG@10'], 6)}}}


def combined_report(reports, requests):
    """Combine case-weighted metrics only when every set completed; never a gate."""
    if any(not report.get('complete') for report in reports.values()):
        return {'available': False, 'used_for_gate': False,
                'unavailable_reason': 'A query set did not complete; no combined average is reported.'}
    copies = deepcopy(reports)
    common = set.intersection(*(set(r['metrics']['baseline']) for r in copies.values()
                                 if r.get('relevance_available', True)))
    for report in copies.values():
        if report.get('relevance_available', True):
            report['metrics'] = {v: {k: m[k] for k in common} for v, m in report['metrics'].items()}
    try:
        result = combine(copies, requests)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return {'available': False, 'used_for_gate': False,
                'unavailable_reason': 'The suites do not have compatible finite metrics for a combined view.'}
    # Coverage is a pooled result count, not a mean of suite percentages.
    result['coverage'] = {}
    for side in ('baseline', 'candidate'):
        judged = sum(r.get('coverage', {}).get(side, {}).get('judged', 0) for r in reports.values())
        returned = sum(r.get('coverage', {}).get(side, {}).get('returned', 0) for r in reports.values())
        result['coverage'][side] = {'judged': judged, 'returned': returned,
                                   'fraction': judged/returned if returned else None}
    return {**result, 'available': True, 'baseline_variant': 'baseline', 'variants': reports['standard']['variants']}


def evaluate(reference, baseline, candidate, selection, frozen, intent):
    """Capture extras once per variant, resolve once per suite and freeze all results."""
    from delivery_gates import read, retain
    from delivery_source_comparison import retain_input
    from evaluation_job import run_variants, capture_scope
    from additional_judgements import resolve_extra
    from compare_search import definition
    from input_selection import select

    parent = read(reference)
    relevance = read(parent['reports']['relevance'])
    inputs = select(candidate['fields']['dataset_release'], candidate['fields']['dataset_sha256'],
                    parent['selected_inputs']['query_manifest_sha256'],
                    parent['selected_inputs']['judgement_manifest_sha256'], relevance=True)
    runtime = parent['variant_runtime']
    variant_pins = pins(baseline, candidate, runtime)
    reports = {'standard': standard_report(relevance, variant_pins, inputs)}
    metadata = {'standard': {'required': True, 'query_manifest_sha256': parent['selected_inputs']['query_manifest_sha256'],
                              'query_sha256': reports['standard']['query_suite_sha256']}}
    gates = {'standard': {'state': 'pass', 'required': True, 'used_for_gate': True}}
    requests = {'standard': inputs['queries']}
    targets = {side: {'environment': environment, 'selection': 'default',
                      'variant_id': runtime[side]['variant'],
                      'configuration_sha256': runtime[side]['configuration_sha256']}
               for side, environment in zip(('baseline', 'candidate'), parent['previews'])}
    specification = (ROOT / 'evaluation/specs/proxy-v2.json').read_bytes()
    for item in frozen:
        name = item['name']; requests[name] = item['queries']
        metadata[name] = {k: item[k] for k in ('name', 'path', 'required', 'query_sha256')}
        metadata[name].update(source_judgement_sha256=item['judgement_sha256'], group=item.get('group','change-specific'))
        for key in ('query_manifest_sha256','judgement_manifest_sha256'):
            if key in item: metadata[name][key]=item[key]
        if item.get('judgements'): metadata[name]['judgements'] = item['judgements']
        print('Checking ' + ('standard query set ' if item.get('group') == 'mandatory' else 'additional query set ') + name + (' (required)' if item['required'] else ' (report only)'), flush=True)
        stage = 'API capture'
        try:
            for side, deployment in (('baseline', baseline), ('candidate', candidate)):
                if definition(targets[side]['environment'])['fingerprint'] != deployment['fingerprint']:
                    raise ValueError('A preview changed before additional capture.')
            with capture_scope(name):
                rows, execution = run_variants(item['query_bytes'], targets)
            if any('error' in row for row in rows): raise ValueError('Additional capture has failed requests.')
            observations = {'kind': 'search-variant-observation-set', 'schema_version': 1,
                'default_variant': 'candidate', 'baseline_variant': 'baseline', 'variants': variant_pins,
                'variant_set_sha256': sha(canonical({'variants': variant_pins,
                    'default_variant': 'candidate', 'baseline_variant': 'baseline'})),
                'catalogue_sha256': candidate['fields']['dataset_sha256'], 'query_suite_sha256': item['query_sha256'],
                'request_adapter': 'search-api-variant-v1', 'execution': execution, 'errors': [], 'captured_depth': 10,
                'captured_at': datetime.now(timezone.utc).isoformat(), 'observations': [
                    {'query_id': row['query_id'], 'request': {k: request.get(k, {} if k=='filters' else None)
                        for k in ('query', 'country', 'currency', 'filters')}, 'results': row['results']}
                    for row, request in zip(rows, item['queries'])]}
            for side, deployment in (('baseline', baseline), ('candidate', candidate)):
                if definition(targets[side]['environment'])['fingerprint'] != deployment['fingerprint']:
                    raise ValueError('A preview changed during additional capture.')
            stage = 'Judgement resolution'
            if item.get('group') == 'mandatory':
                from primary_query_sets import retain_labels
                resolved = retain_labels(item, retain_input)
            else:
                resolved = resolve_extra(item, observations, specification, inputs['catalogue'], retain_input)
            from operation_telemetry import evaluation_progress
            evaluation_progress('Scoring frozen results',suite=name)
            stage = 'Scoring'
            reports[name] = score_extra(resolved, observations, specification, canonical(inputs['catalogue']))
            metadata[name]['judgement_sha256'] = resolved['judgement_sha256']
            metadata[name]['frozen_inputs'] = {'observations': retain_input(canonical(observations), 'observations.json'),
                                             **resolved['resolved_references']}
        except Exception as error:
            reports[name] = {'kind': 'variant-evaluation-report', 'complete': False,
                'variants': variant_pins, 'baseline_variant': 'baseline', 'query_count': len(item['queries']),
                'error': type(error).__name__, 'relevance_unavailable_reason': stage + ' did not complete (' + type(error).__name__ + ').'}
        gates[name] = outcome(reports[name], item['required'], intent)
    summary = {'kind': 'promotion-query-set-report', 'format': 1,
        'baseline': baseline['fingerprint'], 'candidate': candidate['fingerprint'],
        'source_sha': selection['source_sha'], 'intent': intent,
        'policy_sha256': sha(canonical(policy())),
        'standard_inputs': parent['selected_inputs'], 'query_sets': reports, 'query_set_metadata': metadata,
        'gate_outcomes': gates, 'combined': combined_report(reports, requests),
        'state': 'pass' if all(g['state']=='pass' for g in gates.values() if g['required']) else 'failed'}
    from primary_query_sets import annotate
    annotate(summary, candidate['fields']['dataset_release'])
    summary_ref = retain(summary, 'promotion-query-sets.json')
    return retain({**parent, 'query_sets_report': summary_ref}, 'delivery-evidence.json')


def validate(reference, baseline, candidate, selection, frozen, intent):
    """Recheck exact source suites and each required outcome when proposing/merging."""
    from delivery_gates import read
    parent = read(reference)
    ref = parent.get('query_sets_report')
    from primary_query_sets import configuration
    configured = configuration(candidate['fields']['dataset_release'])
    if not frozen:
        if ref: raise ValueError('Delivery evidence contains undeclared additional query sets.')
        return
    if not ref: raise ValueError('Delivery evidence is missing the source-declared additional query sets.')
    value = read(ref)
    if value.get('primary_query_sets') != configured or value.get('primary_query_manifest_sha256') != configured[0]['query_manifest_sha256']:
        raise ValueError('Promotion evidence omitted or changed mandatory query sets.')
    expected = {'standard', *(item['name'] for item in frozen)}
    if (value.get('kind') != 'promotion-query-set-report' or value.get('baseline') != baseline['fingerprint'] or
        value.get('candidate') != candidate['fingerprint'] or value.get('source_sha') != selection['source_sha'] or
        value.get('intent') != intent or value.get('policy_sha256') != sha(canonical(policy())) or value.get('standard_inputs') != parent['selected_inputs'] or
        set(value.get('query_sets', {})) != expected or set(value.get('query_set_metadata', {})) != expected or
        set(value.get('gate_outcomes', {})) != expected):
        raise ValueError('Additional promotion query sets differ from their source or deployment context.')
    meta = value['query_set_metadata']['standard']
    if meta.get('required') is not True or meta.get('query_manifest_sha256') != DEFAULTS[candidate['fields']['dataset_release']]['query-suite']:
        raise ValueError('The mandatory standard comparison is missing or replaced.')
    standard = value['query_sets']['standard']
    if standard.get('complete') is not True or value['gate_outcomes']['standard'] != {'state':'pass','required':True,'used_for_gate':True}:
        raise ValueError('The mandatory standard comparison has not passed.')
    expected_pins = pins(baseline, candidate, parent['variant_runtime'])
    from input_selection import select
    relevance = read(parent['reports']['relevance'])
    inputs = select(candidate['fields']['dataset_release'], candidate['fields']['dataset_sha256'],
                    parent['selected_inputs']['query_manifest_sha256'],
                    parent['selected_inputs']['judgement_manifest_sha256'], relevance=True)
    if standard != standard_report(relevance, expected_pins, inputs) or meta.get('query_sha256') != standard['query_suite_sha256']:
        raise ValueError('The standard suite differs from its retained mandatory comparison.')
    for item in frozen:
        name = item['name']; report = value['query_sets'][name]; meta = value['query_set_metadata'][name]
        if any(meta.get(k) != item.get(k) for k in ('name','path','required','judgements','query_sha256','query_manifest_sha256','judgement_manifest_sha256')) or meta.get('source_judgement_sha256') != item['judgement_sha256']:
            raise ValueError('Additional query bytes, reference labels or required settings changed.')
        if report.get('variants') != expected_pins or report.get('baseline_variant') != 'baseline':
            raise ValueError('An additional query set used different runtime configurations.')
        if report.get('complete') and (report.get('query_suite_sha256') != item['query_sha256'] or
                report.get('catalogue_sha256') != candidate['fields']['dataset_sha256']):
            raise ValueError('An additional report belongs to different queries or catalogue.')
        expected_outcome = outcome(report, item['required'], intent)
        if value['gate_outcomes'][name] != expected_outcome:
            raise ValueError('An additional query-set outcome differs from the measured result.')
        if item['required'] and expected_outcome['state'] != 'pass':
            raise ValueError('Required query set ' + name + ' has outcome ' + expected_outcome['state'] + '.')
    if value.get('state') != 'pass':
        raise ValueError('Required promotion query sets have not all passed.')
