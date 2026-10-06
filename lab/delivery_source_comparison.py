"""Fresh source comparisons, immutable evidence and exact-commit PR links."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import re
import urllib.error
from urllib.parse import quote

from common import ROOT
from delivery_provider import SOURCE, api, endpoint, git, ensure_checkout
from delivery_release import from_run_bytes
from delivery_runtime import resolve, preview
from input_selection import select
from blob_config import service, settings
from compare_search import immutable_blob
from evaluation_job import run_variants
from nexus import publish, request as nexus_request
from variant_gate import attest, check, canonical, sha
from variant_gate_issue import operator_key
from preview_routes import url

sys.path[:0] = [str(ROOT / 'evaluation'), str(ROOT / 'lab/search-app')]
from query_sets import freeze  # noqa: E402
from delivery.ci.relevance_scope import classify  # noqa: E402

STATUS = 'relevance-lab/merge-gate'


class BuildPending(RuntimeError):
    """A source build is still queued or running; release the coordinator slot."""


def approvals_for(revision, selection_bytes):
    """Read immutable receipts for the exact selected variants; no mutable index."""
    approvals = []
    for item in json.loads(selection_bytes)['selected']:
        variant = item['variant']
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', variant):
            raise ValueError('Selected approval variant is invalid.')
        try:
            approvals.append(json.loads(nexus_request('/repository/lab-releases/variant-gates/' +
                revision + '/approvals/' + variant + '.json', identity='reader')))
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
    return approvals


def source_bytes(path, revision):
    """Read exact repository bytes, preserving their original encoding and newlines."""
    value = api(endpoint(SOURCE, '/contents/' + quote(path, safe='/') + '?ref=' + revision))
    if value.get('type') != 'file' or value.get('encoding') != 'base64':
        raise ValueError('Source input is not a bounded file.')
    payload = base64.b64decode(value['content'], validate=False)
    if len(payload) > 4_000_000:
        raise ValueError('Source input is too large.')
    return payload


def build_for(revision, event):
    runs = api(endpoint(SOURCE, '/actions/runs?limit=100'))['workflow_runs']
    matching = [row for row in runs if row['head_sha'] == revision and row['event'] == event
                and row['path'].partition('@')[0] == 'release.yaml']
    if not matching:
        raise BuildPending('Waiting for the exact source build')
    newest = max(matching, key=lambda row: row['id'])
    if newest['status'] != 'completed':
        raise BuildPending('Waiting for the exact source build')
    if newest['conclusion'] != 'success':
        raise ValueError('The exact source release build failed.')
    return newest['id']


def status(source_sha, state, detail, operation_id):
    api(endpoint(SOURCE, '/statuses/' + source_sha), 'POST', {
        'context': STATUS, 'state': state, 'description': detail[:140],
        'target_url': 'https://control.localhost:34443/api/delivery/operations/' + operation_id})


def comment(number, source_sha, operation_id, first, second, report=None, gate=None):
    marker = '<!-- delivery-comparison:' + source_sha + ' -->'
    body = (marker + '\n### Search comparison\n\nSource `' + source_sha + '`.\n\n'
            '- [Baseline storefront](' + url(first['name']) + ')\n'
            '- [Candidate storefront](' + url(second['name']) + ')\n'
            '- [Comparison progress and report](https://control.localhost:34443/api/delivery/operations/' + operation_id + ')\n\n'
            'Baseline expires ' + first['expires_at'] + '; candidate expires ' + second['expires_at'] + '.\n')
    if report:
        body += '\n[Evaluation report](https://control.localhost:34443/api/delivery/operations/' + operation_id + '/report). '
        body += 'Report SHA-256 `' + report['sha256'] + '`. Review label coverage beside the scores.\n'
        if gate:
            body += '\n**Merge gate: ' + gate['state'].replace('_', ' ') + '.**\n'
        if gate and gate['state'] == 'decision_required':
            body += '\n[Review required relevance decision](https://control.localhost:34443/relevance-decision?operation=' + operation_id + '). Only variants requiring a bounded decision can be accepted.\n'
    comments = api(endpoint(SOURCE, '/issues/' + str(number) + '/comments?limit=100'))
    old = next((row for row in comments if marker in row['body'] and
                row.get('user', {}).get('login') == 'elastic-agent'), None)
    if old:
        api(endpoint(SOURCE, '/issues/comments/' + str(old['id'])), 'PATCH', {'body': body})
    else:
        api(endpoint(SOURCE, '/issues/' + str(number) + '/comments'), 'POST', {'body': body})


def retained_bytes(manifest):
    payload = service().get_blob_client(settings()[1], manifest['content']['object']).download_blob().readall()
    if sha(payload) != manifest['content']['sha256']:
        raise ValueError('Frozen input bytes differ.')
    return payload


def current_pr(number, head, baseline):
    pr = api(endpoint(SOURCE, '/pulls/' + str(number)))
    if (pr['state'] != 'open' or pr['head']['sha'] != head or pr['base']['sha'] != baseline
            or pr['base']['ref'] != 'main'
            or pr['head']['repo']['full_name'] != 'elastic-agent/delivery-source'):
        raise ValueError('Source PR head, baseline or repository changed.')
    return pr


def retain_input(payload, filename):
    return {'sha256': sha(payload), 'blob': immutable_blob('runs', sha(payload) + '/' + filename, payload)}


def compare(request, progress, operation_id):
    """Build previews, capture every suite freshly, then publish signed gate evidence."""
    number = request.get('pr')
    if number:
        current_pr(number, request['source_sha'], request['baseline_sha'])
        ensure_checkout(SOURCE)
        git(SOURCE, 'fetch', '--no-tags', 'origin', request['baseline_sha'], request['source_sha'])
        changes = git(SOURCE, 'diff', '--raw', '--no-abbrev', '--no-renames', '-z',
                      request['baseline_sha'] + '...' + request['source_sha'], raw=True)
        scope = classify(changes)
        if scope['documentation_only']:
            current_pr(number, request['source_sha'], request['baseline_sha'])
            reference = retain_input(canonical({'kind': 'documentation-exemption',
                'source_sha': request['source_sha'], 'baseline_sha': request['baseline_sha'],
                'changes_sha256': sha(changes), **scope}), 'documentation-exemption.json')
            status(request['source_sha'], 'success', scope['reason'], operation_id)
            return {'report': reference, 'scope': scope}
        baseline_run = build_for(request['baseline_sha'], 'push')
        candidate_run = build_for(request['source_sha'], 'pull_request')
    else:
        baseline_run, candidate_run = request['baseline_run'], request['candidate_run']
    receipt, _, _, receipt_bytes = from_run_bytes(candidate_run)
    baseline_receipt, _, _, _ = from_run_bytes(baseline_run)
    revision = receipt['source_sha']
    if number and (revision != request['source_sha'] or baseline_receipt['source_sha'] != request['baseline_sha']):
        raise ValueError('Build receipts belong to different source revisions.')
    selection_bytes = source_bytes('gate/selection.json', revision)
    selection = json.loads(selection_bytes)
    layout = json.loads(source_bytes('gate/evaluation.json', revision))
    names = {choice['variant'] for choice in selection['selected']}
    names.update((layout['default_variant'], layout['baseline_variant']))
    if layout['baseline_variant'] in {choice['variant'] for choice in selection['selected']}:
        raise ValueError('The baseline cannot be selected as a candidate.')
    configs = {}
    for name in sorted(names):
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', name):
            raise ValueError('Invalid variant name.')
        ref = baseline_receipt['source_sha'] if name == layout['baseline_variant'] else revision
        config = json.loads(source_bytes('configurations/' + name + '.json', ref))
        configs[name] = config['variants'][name]
    configuration = {'default_variant': layout['default_variant'], 'variants': configs}
    dataset = request.get('dataset', 'esci-gb-v1')
    baseline = resolve(baseline_run, dataset, request.get('recipe'), variant_config=configuration)
    candidate = resolve(candidate_run, dataset, request.get('recipe'), merged=False, variant_config=configuration)
    progress('Preparing baseline and candidate previews')
    first, second = preview(baseline), preview(candidate)
    if number:
        comment(number, revision, operation_id, first, second)
    pins, targets = {}, {}
    for name in sorted(names):
        deployment, environment = (baseline, first) if name == layout['baseline_variant'] else (candidate, second)
        config_sha = sha(json.dumps(configs[name], sort_keys=True, separators=(',', ':')).encode())
        pins[name] = {'image': deployment['fields']['image'],
                      'environment_fingerprint': deployment['fingerprint'], 'configuration_sha256': config_sha}
        targets[name] = {'environment': environment['name'], 'configuration_sha256': config_sha, 'selection': 'explicit'}
    inputs = select(dataset, candidate['fields']['dataset_sha256'],
                    candidate['fields']['query_manifest_sha256'],
                    candidate['fields']['judgement_manifest_sha256'], relevance=True)
    spec_bytes = (ROOT / 'evaluation/specs/proxy-v2.json').read_bytes()
    extra = freeze(selection, lambda path: source_bytes(path, revision))
    captured = {}
    def capture(payload, label):
        progress('Capturing fresh results: ' + label)
        rows, execution = run_variants(payload, targets)
        if any('error' in row for row in rows):
            raise ValueError('A search request failed; capture is incomplete.')
        requests = {row['query_id']: row for row in map(json.loads, payload.splitlines())}
        value = {'kind': 'search-variant-observation-set', 'schema_version': 1,
                'default_variant': layout['default_variant'], 'baseline_variant': layout['baseline_variant'],
                'variants': pins, 'variant_set_sha256': sha(canonical({'variants': pins, **layout})),
                'catalogue_sha256': candidate['fields']['dataset_sha256'], 'query_suite_sha256': sha(payload),
                'captured_at': datetime.now(timezone.utc).isoformat(), 'request_adapter': 'search-api-variant-v1',
                'execution': execution, 'errors': [], 'captured_depth': 10,
                'observations': [{'query_id': row['query_id'], 'request': {
                    key: requests[row['query_id']].get(key, {} if key == 'filters' else None)
                    for key in ('query', 'country', 'currency', 'filters')}, 'results': row['results']} for row in rows]}
        captured[label] = retain_input(canonical(value), 'observations.json')
        return value
    query_bytes = retained_bytes(inputs['query_manifest'])
    observations = capture(query_bytes, 'standard')
    values = {'observations': canonical(observations), 'judgements': retained_bytes(inputs['judgement_manifest']),
              'specification': spec_bytes, 'catalogue': canonical(inputs['catalogue']),
              'queries': canonical(inputs['query_manifest'])}
    content = service().get_blob_client(settings()[1], 'manifests/judgement-set/' +
                inputs['judgement_manifest_sha256'] + '.json').download_blob().readall()
    if sha(content) != inputs['judgement_manifest_sha256']:
        raise ValueError('Frozen judgement manifest differs.')
    values['manifest'] = content
    extra_observations = {item['name']: capture(item['query_bytes'], item['name']) for item in extra}
    from comparison_evaluator import evaluate_comparison
    progress('Evaluating the captured comparison')
    report, extra = evaluate_comparison(values, extra_observations, extra, inputs['catalogue'],
        spec_bytes, inputs['queries'], selection, retain_input, progress)
    report['source_context'] = {'source_sha': revision, 'baseline_sha': baseline_receipt['source_sha'],
                                'pr': number, 'build_run': candidate_run}
    report['frozen_inputs'] = {'selection': retain_input(selection_bytes, 'selection.json'),
        'specification': retain_input(spec_bytes, 'specification.json'),
        'build_receipt': retain_input(receipt_bytes, 'build-receipt.json'),
        'observations': captured, 'additional_query_sets': {item['name']: {
            'queries': retain_input(item['query_bytes'], 'queries.jsonl'),
            'judgements': retain_input(item['judgement_bytes'], 'judgements.jsonl')
                if item.get('judgement_bytes') else None,
            'resolution': item['resolved_references']['resolution']} for item in extra}}
    report_bytes = canonical(report)
    report_sha = sha(report_bytes)
    blob = immutable_blob('runs', report_sha + '/variant-evaluation-report.json', report_bytes)
    reference = {'sha256': report_sha, 'blob': blob}
    if number:
        current_pr(number, revision, request['baseline_sha'])
    verdict = None
    if number:
        progress('Signing the report and checking the merge gate')
        policy_bytes = (ROOT / 'lab/delivery/policies/variant-merge-v1.json').read_bytes()
        evidence_key = operator_key('LAB_VARIANT_EVIDENCE_KEY')
        approval_key = operator_key('LAB_VARIANT_APPROVAL_KEY')
        signed = attest(report_bytes, revision, receipt_bytes, evidence_key,
                        datetime.now(timezone.utc).isoformat(), json.loads(policy_bytes))
        approvals = approvals_for(revision, selection_bytes)
        verdict = check(report_bytes, policy_bytes, selection_bytes, signed, approvals,
                        evidence_key, approval_key, sha(policy_bytes), revision, receipt_bytes,
                        'elastic-agent/delivery-source')
        publish('variant-gates/' + revision + '/report.json', report_bytes)
        publish('variant-gates/' + revision + '/attestation.json', canonical(signed))
        current_pr(number, revision, request['baseline_sha'])
        status(revision, 'success' if verdict['state'] in ('pass', 'approved_exception') else 'failure',
               'Comparison complete: ' + verdict['state'], operation_id)
        comment(number, revision, operation_id, first, second, reference, verdict)
    return {'report': reference, 'source_pr': number, 'source_sha': revision, 'baseline_source_sha': baseline_receipt['source_sha'],
            'baseline_url': url(first['name']), 'candidate_url': url(second['name']),
            'gate': verdict, 'summary': {'metrics': report['metrics'], 'coverage': report['coverage'],
                'ndcg_significance': report['ndcg_significance'],
                'result_changes': report['result_changes'], 'combined': report['combined'],
                'result_similarity': {name: {key: value for key, value in scores.items() if key != 'per_query'}
                    for name, scores in report['result_similarity'].items()}}}


def recheck(request, progress, operation_id):
    """Check signed frozen evidence after an approval; this performs no new evaluation."""
    revision = request['source_sha']
    base = '/repository/lab-releases/variant-gates/' + revision + '/'
    report_bytes = nexus_request(base + 'report.json', identity='reader')
    report = json.loads(report_bytes)
    context = report['source_context']
    if context['source_sha'] != revision or context['pr'] != request['pr']:
        raise ValueError('Frozen report belongs to another source PR.')
    current_pr(request['pr'], revision, context['baseline_sha'])
    progress('Checking the recorded decision against frozen evidence')
    reference = report['frozen_inputs']['build_receipt']
    container, name = reference['blob'].split('/', 1)
    receipt = service().get_blob_client(container, name).download_blob().readall()
    if sha(receipt) != reference['sha256']:
        raise ValueError('Frozen build receipt differs.')
    policy = (ROOT / 'lab/delivery/policies/variant-merge-v1.json').read_bytes()
    attestation = json.loads(nexus_request(base + 'attestation.json', identity='reader'))
    selection_bytes = source_bytes('gate/selection.json', revision)
    approvals = approvals_for(revision, selection_bytes)
    verdict = check(report_bytes, policy, selection_bytes,
                    attestation, approvals, operator_key('LAB_VARIANT_EVIDENCE_KEY'),
                    operator_key('LAB_VARIANT_APPROVAL_KEY'), sha(policy), revision, receipt,
                    'elastic-agent/delivery-source')
    current_pr(request['pr'], revision, context['baseline_sha'])
    status(revision, 'success' if verdict['state'] in ('pass', 'approved_exception') else 'failure',
           'Frozen evidence checked: ' + verdict['state'], operation_id)
    return {'gate': verdict, 'source_pr': request['pr'], 'source_sha': revision, 'report': {'sha256': sha(report_bytes),
        'blob': 'runs/' + sha(report_bytes) + '/variant-evaluation-report.json'}}
