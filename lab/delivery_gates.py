"""Frozen public-API evidence gates; provider approvals are a separate step."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from blob_config import service
from compare_search import definition, immutable_blob
from control_comparison import evaluate_pair
from performance_pair import evaluate_performance_pair
from delivery.ci.release import canonical, digest
from delivery_runtime import preview
from promotion_policy import validate as validate_offline_policy
from input_selection import DEFAULTS
from delivery_load_policy import validate as validate_production_load
from search_probe import search


class EvidenceFailure(ValueError):
    """A rejected gate with retained evidence available for human inspection."""
    def __init__(self, detail, reference):
        super().__init__(detail)
        self.reference = reference


def performance_failure(report):
    if not report.get('valid') or not report.get('same_workload') or not report.get('warmup_ready'):
        return 'Performance execution is incomplete or invalid; inspect workload and warm-up evidence.'
    misses = []
    for phase, measured in report.get('measured_phases', {}).items():
        if phase.startswith('stress-'):
            continue
        for side in ('baseline', 'candidate'):
            for metric, limit in measured.get('budget', {}).items():
                value = measured[side].get(metric)
                if value is not None and (value >= limit if metric == 'failed_percent' else value > limit):
                    misses.append(f'{side} {phase} {metric}: {value} (limit {limit})')
    return 'Performance budget missed: ' + '; '.join(misses) if misses else 'Performance check failed or is incomplete.'


def deployment_inputs(deployment):
    fields = deployment['fields']
    defaults = DEFAULTS[fields['dataset_release']]
    return {'catalogue_manifest_sha256': fields.get('catalogue_manifest_sha256'),
            'query_manifest_sha256': fields.get('query_manifest_sha256') or defaults['query-suite'],
            'judgement_manifest_sha256': fields.get('judgement_manifest_sha256') or defaults['judgement-set']}


def retain(value, filename):
    payload = canonical(value)
    sha = digest(payload)
    return {'sha256': sha, 'blob': immutable_blob('runs', sha + '/' + filename, payload)}


def read(reference):
    container, name = reference['blob'].split('/', 1)
    if container != 'runs' or name.split('/')[0] != reference['sha256']:
        raise ValueError('Report reference is not addressed by its hash.')
    payload = service().get_blob_client(container, name).download_blob().readall()
    if digest(payload) != reference['sha256']:
        raise ValueError('Retained report bytes differ from their hash.')
    return json.loads(payload)


def read_offline(reference, kind):
    """Read a typed, content-addressed report or policy from the retained run store."""
    if reference.get('kind') != kind or reference.get('bytes', 0) <= 0:
        raise ValueError('Offline artifact kind or size differs.')
    container, name = reference['blob'].split('/', 1)
    parts = name.split('/')
    if container != 'runs' or len(parts) != 3 or parts[:2] != [kind, reference['sha256']] or \
            not parts[2] or parts[2] in ('.', '..'):
        raise ValueError('Offline artifact reference is not content-addressed.')
    payload = service().get_blob_client(container, name).download_blob().readall()
    if digest(payload) != reference['sha256'] or len(payload) != reference['bytes']:
        raise ValueError('Retained offline artifact differs from its reference.')
    return payload


def validate_offline_addendum(addendum, relevance_report, baseline, candidate):
    expected = addendum['expected']
    if expected['baseline_fingerprint'] != baseline or expected['candidate_fingerprint'] != candidate or \
            expected['catalogue_sha256'] != relevance_report['baseline']['dataset_sha256'] or \
            expected['catalogue_sha256'] != relevance_report['candidate']['dataset_sha256'] or \
            expected['query_suite_sha256'] != relevance_report['suite_sha256'] or \
            expected['observation_sha256'] != relevance_report.get('observation_sha256'):
        raise ValueError('Offline evaluation belongs to another delivery execution.')
    report_bytes = read_offline(addendum['report'], 'evaluation-report')
    policy_bytes = read_offline(addendum['policy'], 'promotion-policy')
    pinned = Path(__file__).parent / 'delivery/policies/observation-evidence-v1.json'
    if digest(policy_bytes) != digest(pinned.read_bytes()):
        raise ValueError('Offline evaluation policy is not the pinned delivery policy.')
    return validate_offline_policy(report_bytes, policy_bytes, expected)


def check_report(report, mode, baseline, candidate, intent):
    if report['baseline']['fingerprint'] != baseline or report['candidate']['fingerprint'] != candidate:
        raise ValueError('Evaluation evidence belongs to a different baseline or candidate.')
    if mode == 'performance':
        if (report.get('kind') != 'paired-api-performance' or not report.get('valid') or
                not report.get('same_workload') or not report.get('warmup_ready') or
                report.get('verdict') != 'within-budget' or not report.get('measured_phases')):
            raise ValueError(performance_failure(report))
    else:
        if (report.get('mode') != mode or report.get('scope') != 'full' or not report.get('complete') or
                not report.get('query_count') or report.get('completed_query_count') != report['query_count']):
            raise ValueError('Full functional check is incomplete.')
        if mode == 'result-regression' and intent == 'preserve-results' and report.get('verdict') != 'unchanged':
            raise ValueError('Result-preserving promotion has changed query results.')
        if mode == 'relevance' and (report.get('verdict') != 'measured' or not report.get('judgement_sha256')):
            raise ValueError('Frozen relevance evidence is missing.')


def validate_evidence(reference, baseline, candidate, intent, expected_inputs=None, *, target=None,
                      baseline_deployment=None, candidate_deployment=None):
    if intent not in ('preserve-results', 'ranking-change'):
        evidence = read(reference)
        if evidence.get('kind') == 'delivery-variant-evidence':
            return validate_variant_evidence(evidence, baseline, candidate, expected_inputs, target,
                                             baseline_deployment, candidate_deployment)
        raise ValueError('Choose an explicit result-preserving or intentional ranking change.')
    evidence = read(reference)
    if (evidence.get('baseline') != baseline or evidence.get('candidate') != candidate or
            evidence.get('intent') != intent):
        raise ValueError('Evidence is stale for this deployment or intent.')
    selected = evidence.get('selected_inputs')
    if expected_inputs is not None and selected != expected_inputs:
        raise ValueError('Evidence selects different catalogue, query or judgement inputs.')
    measured = datetime.fromisoformat(evidence['completed_at'])
    now = datetime.now(timezone.utc)
    if measured > now or now - measured > timedelta(days=3):
        raise ValueError('Evaluation evidence is outside the three-day promotion window.')
    expected = {'result-regression', 'relevance', 'performance'}
    if set(evidence.get('reports', {})) != expected:
        raise ValueError('All three evaluation reports are required.')
    relevance = None
    for mode, report in evidence['reports'].items():
        value = read(report)
        check_report(value, mode, baseline, candidate, intent)
        if target == 'production' and mode == 'performance':
            validate_production_load(value)
        if selected and mode != 'performance':
            if (value.get('query_manifest_sha256') != selected['query_manifest_sha256'] or
                    (mode == 'relevance' and value.get('judgement_manifest_sha256') !=
                     selected['judgement_manifest_sha256'])):
                raise ValueError('Functional report uses different selected inputs.')
        if mode == 'relevance':
            relevance = value
    if evidence.get('offline_evaluation') is not None:
        validate_offline_addendum(evidence['offline_evaluation'], relevance, baseline, candidate)
    return evidence


def validate_variant_evidence(evidence, baseline, candidate, expected_inputs=None, target=None,
                              baseline_deployment=None, candidate_deployment=None):
    """Validate each selected runtime variant against one explicitly pinned baseline."""
    from delivery_variant_selection import configured_baseline, source_selection, with_variant

    if (evidence.get('format') != 1 or evidence.get('state') != 'pass' or
            evidence.get('baseline') != baseline or evidence.get('candidate') != candidate):
        raise ValueError('Per-variant delivery evidence is incomplete or belongs to another target.')
    measured = datetime.fromisoformat(evidence['completed_at'])
    now = datetime.now(timezone.utc)
    if measured > now or now - measured > timedelta(days=3):
        raise ValueError('Per-variant evidence is outside the three-day promotion window.')
    selected = source_selection(evidence.get('source_sha', ''))
    if (evidence.get('selection_sha256') != selected['selection_sha256'] or
            evidence.get('evaluation_sha256') != selected['evaluation_sha256'] or
            evidence.get('selected_inputs') != expected_inputs or
            evidence.get('candidate_configuration_sha256') != selected['configuration_sha256']):
        raise ValueError('Per-variant evidence differs from the exact source configuration or frozen inputs.')
    if candidate_deployment is None or baseline_deployment is None:
        raise ValueError('Per-variant evidence must be checked against both pinned deployments.')
    if (candidate_deployment.get('build_run') != evidence.get('candidate_build_run') or
            candidate_deployment['fields'].get('source_sha') != evidence.get('source_sha') or
            candidate_deployment['fields'].get('variant_config_json') !=
                json.dumps(selected['configuration'], sort_keys=True, separators=(',', ':'))):
        raise ValueError('Candidate build or deployed variant configuration differs from the evidence.')
    if not isinstance(evidence.get('checks'), list) or len(evidence['checks']) != len(selected['selection']):
        raise ValueError('Every selected source variant must have its own delivery check.')
    names = [item.get('variant') for item in evidence['checks']]
    if len(names) != len(set(names)) or set(names) != {item['variant'] for item in selected['selection']}:
        raise ValueError('Delivery checks do not cover the exact selected variant set.')
    source_intents = {item['variant']: item['intent'] for item in selected['selection']}
    if evidence.get('baseline_variant') != evidence.get('baseline_pin', {}).get('variant'):
        raise ValueError('The named baseline variant is not explicitly pinned.')
    baseline_pin = evidence['baseline_pin']
    if (baseline_pin.get('build_run') != evidence.get('baseline_build_run') or
            baseline_pin.get('deployment_fingerprint') != baseline or
            not baseline_pin.get('configuration_sha256')):
        raise ValueError('Baseline build, variant and configuration identity are incomplete.')
    if configured_baseline(baseline_deployment) != baseline_pin:
        raise ValueError('Baseline default variant or configuration changed after evaluation.')

    from promotion_query_sets import standard_inputs, frozen_sets, validate as validate_query_sets
    standard_inputs(candidate_deployment, expected_inputs)
    frozen = frozen_sets(selected, candidate_deployment)

    for check in evidence['checks']:
        name = check['variant']
        if check.get('intent') != source_intents[name] or check.get('state') != 'pass':
            raise ValueError('Variant ' + name + ' has no passing check for its declared intent.')
        baseline_probe = check.get('baseline_probe', {})
        candidate_probe = check.get('candidate_probe', {})
        if (baseline_probe.get('variant') != baseline_pin['variant'] or
                baseline_probe.get('configuration_sha256') != baseline_pin['configuration_sha256'] or
                candidate_probe.get('variant') != name or
                candidate_probe.get('configuration_sha256') != selected['configuration_sha256_by_variant'][name]):
            raise ValueError('A variant check does not match its pinned baseline or candidate configuration.')
        sub = check.get('evidence')
        if not isinstance(sub, dict):
            raise ValueError('A per-variant check is missing retained delivery evidence.')
        baseline_definition = with_variant(baseline_deployment, baseline_pin['variant'], baseline_pin['settings']) \
            if baseline_deployment else None
        # The immutable probe fingerprints are retained with each check and are
        # also validated against its exact report inputs below.
        validate_evidence(sub, baseline_probe.get('fingerprint'), candidate_probe.get('fingerprint'),
                          check['intent'], expected_inputs, target=target)
        retained = read(sub)
        if check.get('query_sets_report') != retained.get('query_sets_report'):
            raise ValueError('The query-set report link differs from its retained evidence.')
        if retained.get('query_sets_report') and check.get('query_set_outcomes') != read(retained['query_sets_report'])['gate_outcomes']:
            raise ValueError('The advertised query-set outcomes differ from their retained evidence.')
        observed = retained.get('variant_runtime', {})
        if (observed.get('baseline', {}).get('variant') != baseline_pin['variant'] or
                observed.get('baseline', {}).get('configuration_sha256') != baseline_pin['configuration_sha256'] or
                observed.get('candidate', {}).get('variant') != name or
                observed.get('candidate', {}).get('configuration_sha256') !=
                    selected['configuration_sha256_by_variant'][name]):
            raise ValueError('Public APIs served a different baseline or candidate configuration.')
        candidate_definition = with_variant(candidate_deployment, name, selected['configuration']['variants'][name])
        if candidate_definition['fingerprint'] != candidate_probe.get('fingerprint'):
            raise ValueError('The candidate probe differs from its source configuration.')
        validate_query_sets(sub, baseline_definition, candidate_definition, selected, frozen, check['intent'])
        if baseline_definition['fingerprint'] != baseline_probe.get('fingerprint'):
            raise ValueError('The baseline probe no longer represents the named active configuration.')
    return evidence


def evaluate_variants(baseline, candidate, profile='probe', target=None):
    """Run the complete delivery gates for each selected candidate variant."""
    from delivery_variant_selection import configured_baseline, source_selection, with_variant

    source_sha = candidate['fields']['source_sha']
    selection = source_selection(source_sha)
    configured = json.loads(candidate['fields'].get('variant_config_json', '{}'))
    if configured != selection['configuration']:
        raise ValueError('Candidate deployment does not pin the exact selected source variants.')
    selected_inputs = deployment_inputs(candidate)
    from promotion_query_sets import standard_inputs, frozen_sets, evaluate as evaluate_query_sets, validate as validate_query_sets
    standard_inputs(candidate, selected_inputs)
    frozen = frozen_sets(selection, candidate)
    baseline_pin = configured_baseline(baseline)
    baseline_probe = with_variant(baseline, baseline_pin['variant'], baseline_pin['settings'])
    checks = []
    for item in selection['selection']:
        name, intent = item['variant'], item['intent']
        candidate_probe = with_variant(candidate, name, selection['configuration']['variants'][name])
        print('Checking variant ' + name + ' (' + intent + ') against baseline ' +
              str(baseline['build_run']) + '/' + baseline_pin['variant'] + '...', flush=True)
        reference = None
        try:
            def check_query_sets(partial):
                updated = partial
                try:
                    updated = evaluate_query_sets(partial, baseline_probe, candidate_probe, selection, frozen, intent)
                    validate_query_sets(updated, baseline_probe, candidate_probe, selection, frozen, intent)
                except ValueError as error:
                    raise EvidenceFailure(str(error), updated) from error
                return updated
            reference = evaluate(baseline_probe, candidate_probe, intent, profile,
                                 **({'before_performance': check_query_sets} if frozen else {}))
            validate_evidence(reference, baseline_probe['fingerprint'], candidate_probe['fingerprint'],
                              intent, selected_inputs, target=target)
            measured = read(reference).get('variant_runtime', {})
            if (measured.get('baseline', {}).get('variant') != baseline_pin['variant'] or
                    measured.get('baseline', {}).get('configuration_sha256') != baseline_pin['configuration_sha256'] or
                    measured.get('candidate', {}).get('variant') != name or
                    measured.get('candidate', {}).get('configuration_sha256') !=
                        selection['configuration_sha256_by_variant'][name]):
                raise ValueError('Public APIs served a different baseline or candidate configuration.')
            checks.append({'variant': name, 'intent': intent, 'state': 'pass',
                'baseline_probe': {'fingerprint': baseline_probe['fingerprint'],
                    'variant': baseline_pin['variant'],
                    'configuration_sha256': baseline_pin['configuration_sha256']},
                'candidate_probe': {'fingerprint': candidate_probe['fingerprint'],
                    'variant': name,
                    'configuration_sha256': selection['configuration_sha256_by_variant'][name]},
                'evidence': {'sha256': reference['sha256'], 'blob': reference['blob']}})
        except EvidenceFailure as error:
            checks.append({'variant': name, 'intent': intent, 'state': 'failed',
                'baseline_probe': {'fingerprint': baseline_probe['fingerprint'],
                    'variant': baseline_pin['variant'],
                    'configuration_sha256': baseline_pin['configuration_sha256']},
                'candidate_probe': {'fingerprint': candidate_probe['fingerprint'],
                    'variant': name,
                    'configuration_sha256': selection['configuration_sha256_by_variant'][name]},
                'evidence': error.reference, 'error': str(error)[:240]})
        except Exception as error:
            checks.append({'variant': name, 'intent': intent, 'state': 'failed',
                'baseline_probe': {'fingerprint': baseline_probe['fingerprint'],
                    'variant': baseline_pin['variant'],
                    'configuration_sha256': baseline_pin['configuration_sha256']},
                'candidate_probe': {'fingerprint': candidate_probe['fingerprint'],
                    'variant': name,
                    'configuration_sha256': selection['configuration_sha256_by_variant'][name]},
                'evidence': ({'sha256': reference['sha256'], 'blob': reference['blob']}
                             if reference else None), 'error': str(error)[:240]})
    for check in checks:
        if check.get('evidence'):
            retained_check = read(check['evidence'])
            check['performance_status'] = retained_check.get('performance_status')
            suite_ref = retained_check.get('query_sets_report')
            if suite_ref:
                check['query_sets_report'] = suite_ref
                check['query_set_outcomes'] = read(suite_ref)['gate_outcomes']
    value = {'kind': 'delivery-variant-evidence', 'format': 1,
        'state': 'pass' if all(row['state'] == 'pass' for row in checks) else 'failed',
        'baseline': baseline['fingerprint'], 'baseline_build_run': baseline['build_run'],
        'baseline_variant': baseline_pin['variant'], 'baseline_pin': baseline_pin,
        'candidate': candidate['fingerprint'], 'candidate_build_run': candidate['build_run'],
        'source_sha': source_sha, 'selection_sha256': selection['selection_sha256'],
        'evaluation_sha256': selection['evaluation_sha256'],
        'candidate_configuration_sha256': selection['configuration_sha256'],
        'selected_inputs': selected_inputs, 'checks': checks,
        'completed_at': datetime.now(timezone.utc).isoformat()}
    reference = retain(value, 'delivery-variant-evidence.json')
    print('Retained per-variant evidence: ' + json.dumps(reference), flush=True)
    if value['state'] != 'pass':
        raise EvidenceFailure('Variant checks failed: ' + '; '.join(row['variant'] + ': ' + row.get('error','No passing evidence') for row in checks if row['state'] != 'pass')[:700], reference)
    validate_variant_evidence(value, baseline['fingerprint'], candidate['fingerprint'], selected_inputs, target,
                              baseline_deployment=baseline, candidate_deployment=candidate)
    return reference


def attach_offline(reference, report_reference, policy_reference, expected):
    """Retain a new evidence version; the prior delivery evidence stays unchanged."""
    evidence = read(reference)
    if 'offline_evaluation' in evidence:
        raise ValueError('Delivery evidence already selects an offline evaluation.')
    updated = {**evidence, 'offline_evaluation': {
        'report': report_reference, 'policy': policy_reference, 'expected': expected}}
    retained = retain(updated, 'delivery-evidence.json')
    validate_evidence(retained, evidence['baseline'], evidence['candidate'], evidence['intent'])
    return retained


def evaluate(baseline, candidate, intent='preserve-results', profile='probe', *, before_performance=None):
    """Validate functional and declared-set evidence before starting performance."""
    if baseline['fingerprint'] == candidate['fingerprint']:
        raise ValueError('Select two distinct frozen release definitions.')
    if baseline['fields']['dataset_release'] != candidate['fields']['dataset_release']:
        raise ValueError('Both environments must use the same frozen catalogue.')
    if baseline['fields']['dataset_sha256'] != candidate['fields']['dataset_sha256']:
        raise ValueError('Both environments must use the same frozen catalogue.')
    selected = deployment_inputs(candidate)
    from operation_telemetry import evaluation_progress
    evaluation_progress('Preparing baseline preview')
    first = preview(baseline)
    evaluation_progress('Preparing candidate preview')
    second = preview(candidate)
    evaluation_progress('Checking public API configurations')
    runtime = {'baseline': search(first['name'], 'running shoes'),
               'candidate': search(second['name'], 'running shoes')}
    if not runtime['baseline'] or not runtime['candidate']:
        raise ValueError('A public API could not confirm its selected runtime configuration.')
    runtime = {side: {'variant': answer.get('variant_id'),
                      'configuration_sha256': answer.get('configuration_sha256')}
               for side, answer in runtime.items()}
    reports = {}
    extra_fields = {}

    def retained():
        if definition(first['name'])['fingerprint'] != baseline['fingerprint'] or \
                definition(second['name'])['fingerprint'] != candidate['fingerprint']:
            raise ValueError('A preview changed during evaluation.')
        value = {'format': 1, 'baseline': baseline['fingerprint'], 'candidate': candidate['fingerprint'],
                 'intent': intent, 'completed_at': datetime.now(timezone.utc).isoformat(),
                 'dataset_release': baseline['fields']['dataset_release'], 'profile': profile,
                 'selected_inputs': selected, 'variant_runtime': runtime,
                 'reports': dict(reports), 'previews': [first['name'], second['name']],
                 'performance_status': 'completed' if 'performance' in reports else 'not_run', **extra_fields}
        return retain(value, 'delivery-evidence.json')

    for mode in ('result-regression', 'relevance'):
        print('Evaluating ' + mode + ' through both public APIs...', flush=True)
        summary = evaluate_pair(first, second, mode, scope='full',
            query_manifest_sha=selected['query_manifest_sha256'],
            judgement_manifest_sha=selected['judgement_manifest_sha256'] if mode == 'relevance' else None)
        reports[mode] = {'sha256': summary['report_sha256'], 'blob': summary['report_blob']}
        try:
            functional = read(reports[mode])
            check_report(functional, mode, baseline['fingerprint'], candidate['fingerprint'], intent)
            if (functional.get('query_manifest_sha256') != selected['query_manifest_sha256'] or
                    mode == 'relevance' and functional.get('judgement_manifest_sha256') != selected['judgement_manifest_sha256']):
                raise ValueError('Functional report uses different selected inputs.')
        except ValueError as error:
            evaluation_progress('Performance check skipped: required functional check failed')
            raise EvidenceFailure(str(error), retained()) from error
    if before_performance:
        evaluation_progress('Checking declared query sets before performance')
        reference = before_performance(retained())
        extra = read(reference)
        extra_fields = {key: extra[key] for key in ('query_sets_report',) if key in extra}
    evaluation_progress('Running Gatling performance checks')
    print('Evaluating performance through both public APIs...', flush=True)
    summary = evaluate_performance_pair(first, second, profile, owner='delivery')
    reports['performance'] = {'sha256': summary['report_sha256'], 'blob': summary['report_blob']}
    reference = retained()
    print('Retained evaluation reference: ' + json.dumps(reference), flush=True)
    try:
        validate_evidence(reference, baseline['fingerprint'], candidate['fingerprint'], intent, selected)
    except ValueError as error:
        raise EvidenceFailure(str(error), reference) from error
    return reference
