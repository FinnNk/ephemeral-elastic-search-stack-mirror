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
            raise ValueError('Performance check failed or is incomplete.')
    else:
        if (report.get('mode') != mode or report.get('scope') != 'full' or not report.get('complete') or
                not report.get('query_count') or report.get('completed_query_count') != report['query_count']):
            raise ValueError('Full functional check is incomplete.')
        if mode == 'result-regression' and intent == 'preserve-results' and report.get('verdict') != 'unchanged':
            raise ValueError('Result-preserving promotion has changed query results.')
        if mode == 'relevance' and (report.get('verdict') != 'measured' or not report.get('judgement_sha256')):
            raise ValueError('Frozen relevance evidence is missing.')


def validate_evidence(reference, baseline, candidate, intent, expected_inputs=None):
    if intent not in ('preserve-results', 'ranking-change'):
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


def evaluate(baseline, candidate, intent='preserve-results', profile='probe'):
    if baseline['fingerprint'] == candidate['fingerprint']:
        raise ValueError('Select two distinct frozen release definitions.')
    if baseline['fields']['dataset_release'] != candidate['fields']['dataset_release']:
        raise ValueError('Both environments must use the same synthetic dataset.')
    if baseline['fields']['dataset_sha256'] != candidate['fields']['dataset_sha256']:
        raise ValueError('Both environments must use the same frozen catalogue.')
    selected = deployment_inputs(candidate)
    first, second = preview(baseline), preview(candidate)
    reports = {}
    for mode in ('result-regression', 'relevance', 'performance'):
        print('Evaluating ' + mode + ' through both public APIs...', flush=True)
        summary = (evaluate_performance_pair(first, second, profile, owner='delivery')
                   if mode == 'performance' else
                   evaluate_pair(first, second, mode, scope='full',
                       query_manifest_sha=selected['query_manifest_sha256'],
                       judgement_manifest_sha=selected['judgement_manifest_sha256']
                       if mode == 'relevance' else None))
        reports[mode] = {'sha256': summary['report_sha256'], 'blob': summary['report_blob']}
        # Retain failed evidence for inspection, but do not turn it into a passing gate.
    if definition(first['name'])['fingerprint'] != baseline['fingerprint'] or \
            definition(second['name'])['fingerprint'] != candidate['fingerprint']:
        raise ValueError('A preview changed during evaluation.')
    value = {'format': 1, 'baseline': baseline['fingerprint'], 'candidate': candidate['fingerprint'],
             'intent': intent, 'completed_at': datetime.now(timezone.utc).isoformat(),
             'dataset_release': baseline['fields']['dataset_release'], 'profile': profile,
             'selected_inputs': selected,
             'reports': reports, 'previews': [first['name'], second['name']]}
    reference = retain(value, 'delivery-evidence.json')
    print('Retained evaluation reference: ' + json.dumps(reference), flush=True)
    validate_evidence(reference, baseline['fingerprint'], candidate['fingerprint'], intent,
                      selected)
    return reference
