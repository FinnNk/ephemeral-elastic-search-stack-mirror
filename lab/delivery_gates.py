"""Frozen public-API evidence gates; provider approvals are a separate step."""
from datetime import datetime, timedelta, timezone
import json
import sys

sys.path.insert(0, '.lab/python-libs')
sys.path.insert(0, 'research/platform-spike')
from blob_config import service
from compare_search import definition, immutable_blob
from control_comparison import evaluate_pair
from performance_pair import evaluate_performance_pair
from delivery.ci.release import canonical, digest
from delivery_runtime import preview


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


def validate_evidence(reference, baseline, candidate, intent):
    if intent not in ('preserve-results', 'ranking-change'):
        raise ValueError('Choose an explicit result-preserving or intentional ranking change.')
    evidence = read(reference)
    if (evidence.get('baseline') != baseline or evidence.get('candidate') != candidate or
            evidence.get('intent') != intent):
        raise ValueError('Evidence is stale for this deployment or intent.')
    measured = datetime.fromisoformat(evidence['completed_at'])
    now = datetime.now(timezone.utc)
    if measured > now or now - measured > timedelta(days=3):
        raise ValueError('Evaluation evidence is outside the three-day promotion window.')
    expected = {'result-regression', 'relevance', 'performance'}
    if set(evidence.get('reports', {})) != expected:
        raise ValueError('All three evaluation reports are required.')
    for mode, report in evidence['reports'].items():
        check_report(read(report), mode, baseline, candidate, intent)
    return evidence


def evaluate(baseline, candidate, intent='preserve-results', profile='probe'):
    if baseline['fingerprint'] == candidate['fingerprint']:
        raise ValueError('Select two distinct frozen release definitions.')
    if baseline['fields']['dataset_release'] != candidate['fields']['dataset_release']:
        raise ValueError('Both environments must use the same synthetic dataset.')
    first, second = preview(baseline), preview(candidate)
    reports = {}
    for mode in ('result-regression', 'relevance', 'performance'):
        print('Evaluating ' + mode + ' through both public APIs...', flush=True)
        summary = (evaluate_performance_pair(first, second, profile) if mode == 'performance' else
                   evaluate_pair(first, second, mode, scope='full'))
        reports[mode] = {'sha256': summary['report_sha256'], 'blob': summary['report_blob']}
        # Retain failed evidence for inspection, but do not turn it into a passing gate.
    if definition(first['name'])['fingerprint'] != baseline['fingerprint'] or \
            definition(second['name'])['fingerprint'] != candidate['fingerprint']:
        raise ValueError('A preview changed during evaluation.')
    value = {'format': 1, 'baseline': baseline['fingerprint'], 'candidate': candidate['fingerprint'],
             'intent': intent, 'completed_at': datetime.now(timezone.utc).isoformat(),
             'dataset_release': baseline['fields']['dataset_release'], 'profile': profile,
             'reports': reports, 'previews': [first['name'], second['name']]}
    reference = retain(value, 'delivery-evidence.json')
    print('Retained evaluation reference: ' + json.dumps(reference), flush=True)
    validate_evidence(reference, baseline['fingerprint'], candidate['fingerprint'], intent)
    return reference
