"""Durable named delivery requests; one coordinator executes them under its lock."""
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from common import STATE

FIELDS = {
    'suggest-release-plan': {'run', 'target', 'dataset', 'recipe', 'query_manifest', 'judgement_manifest'},
    'propose-release-plan': {'suggestion', 'edits'},
    'accept-release-plan': {'pr'},
    'set-preview-expiry': {'name', 'fingerprint', 'expires_at', 'new_expiry'},
    'expire-preview': {'name', 'fingerprint', 'expires_at'},
    'prepare-production': set(),
    'release-production': set(),
    'preview': {'run', 'dataset', 'recipe'},
    'build-preview': {'source_ref', 'dataset', 'recipe'},
    'compare': {'baseline_run', 'candidate_run', 'dataset', 'recipe', 'pr', 'source_sha', 'baseline_sha'},
    'promotion': {'target', 'run', 'dataset', 'recipe', 'query_manifest', 'judgement_manifest'},
    'gate-check': {'pr', 'source_sha'},
    'request-exception': {'pr', 'source_sha', 'variant', 'reason'},
    'merge-exception': {'pr'},
    'merge-reviewed': {'pr'},
    'verify': {'target'},
    'rollback': {'target', 'fingerprint'},
}
PUBLIC = 'https://control.localhost:34443'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def validate(payload):
    """Accept named operations, never arbitrary CLI arguments or filesystem paths."""
    if not isinstance(payload, dict) or payload.get('kind') not in FIELDS:
        raise ValueError('Choose a named delivery operation.')
    kind = payload['kind']
    if set(payload) - (FIELDS[kind] | {'kind'}):
        raise ValueError('Unknown delivery operation field.')
    required = {'suggest-release-plan': {'run','target'}, 'propose-release-plan': {'suggestion','edits'}, 'accept-release-plan': {'pr'}, 'set-preview-expiry': {'name', 'fingerprint', 'expires_at', 'new_expiry'}, 'expire-preview': {'name', 'fingerprint', 'expires_at'}, 'prepare-production': set(), 'preview': {'run'}, 'compare': {'pr', 'source_sha', 'baseline_sha'} if 'pr' in payload
                else {'baseline_run', 'candidate_run'},
                'build-preview': {'source_ref'},
                'promotion': {'target', 'run'}, 'release-production': set(), 'gate-check': {'pr', 'source_sha'},
                'request-exception': {'pr', 'source_sha', 'variant', 'reason'},
                'merge-exception': {'pr'},
                'merge-reviewed': {'pr'}, 'verify': {'target'},
                'rollback': {'target', 'fingerprint'}}[kind]
    if not required <= set(payload):
        raise ValueError('Required delivery operation fields are missing.')
    if kind == 'build-preview':
        from preview_build import valid_ref
        if not valid_ref(payload['source_ref']):
            raise ValueError('Enter a branch name or a full 40-character commit SHA.')
    if kind == 'propose-release-plan' and (not re.fullmatch('[a-f0-9]{32}',str(payload['suggestion'])) or not isinstance(payload['edits'],dict)):
        raise ValueError('Choose a saved release check suggestion and its review settings.')
    if kind in ('expire-preview', 'set-preview-expiry') and not re.fullmatch(r'lab-delivery-run-[1-9][0-9]*-[a-f0-9]{8}', str(payload['name'])):
        raise ValueError('Only delivery preview environments can expire early.')
    if kind in ('expire-preview', 'set-preview-expiry'):
        if not isinstance(payload['expires_at'], str) or len(payload['expires_at']) > 40 or \
                datetime.fromisoformat(payload['expires_at'].replace('Z', '+00:00')).tzinfo is None:
            raise ValueError('Preview expiry must identify its current lease.')
    for field in ('run', 'baseline_run', 'candidate_run', 'pr'):
        if field in payload and (type(payload[field]) is not int or payload[field] < 1):
            raise ValueError('Build and PR numbers must be positive integers.')
    if 'target' in payload and payload['target'] not in ('integration', 'staging', 'production'):
        raise ValueError('Delivery target is invalid.')
    if kind == 'promotion' and payload['target'] == 'production':
        raise ValueError('Use Prepare production candidate, then Check and release production.')
    if kind == 'set-preview-expiry':
        from lease_expiry import deadline
        deadline(payload['new_expiry'])
    if 'dataset' in payload and not re.fullmatch(r'(?:[a-z][a-z0-9-]{0,63}|[0-9]{4}-[0-9]{2}-[0-9]{2})', str(payload['dataset'])):
        raise ValueError('Dataset name is invalid.')
    for field, size in (('query_manifest', 64), ('judgement_manifest', 64), ('recipe', 64), ('fingerprint', 64), ('source_sha', 40), ('baseline_sha', 40)):
        if field in payload and not re.fullmatch('[0-9a-f]{' + str(size) + '}', str(payload[field])):
            raise ValueError('Frozen source or recipe identity is invalid.')
    if kind == 'compare' and 'pr' in payload and not {'source_sha', 'baseline_sha'} <= set(payload):
        raise ValueError('A source PR comparison needs exact head and baseline commits.')
    if kind == 'request-exception' and (
            not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', str(payload['variant'])) or
            not isinstance(payload['reason'], str) or not 20 <= len(payload['reason'].strip()) <= 4000):
        raise ValueError('Choose a variant and explain the decision in 20–4,000 characters.')
    return payload


class Operations:
    def __init__(self, path=None):
        self.path = Path(path or STATE / 'delivery-operations.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS operation_logs (operation_id TEXT, sequence INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, message TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS operations '
                       '(id TEXT PRIMARY KEY, owner TEXT, identity TEXT, request TEXT, state TEXT, '
                       'progress TEXT, result TEXT, error TEXT, created_at TEXT, updated_at TEXT)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def row(value):
        if value is None:
            return None
        result = dict(value)
        for key in ('request', 'identity', 'result'):
            result[key] = json.loads(result[key]) if result[key] else None
        result['url'] = PUBLIC + '/api/delivery/operations/' + result['id']
        result['report_url'] = result['url'] + '/report' if (result.get('result') or {}).get('report') else None
        result['decision_url'] = PUBLIC + '/relevance-decision?operation=' + result['id'] if \
            ((result.get('result') or {}).get('gate') or {}).get('state') == 'decision_required' else None
        return result

    def submit(self, payload, identity, key, *, release_binding=None):
        """Retry the same submission key safely; changed payloads require a new key."""
        validate(payload)
        if payload['kind'] == 'build-preview' and (
                not identity.get('is_admin') or identity.get('is_reader') or identity.get('is_delivery_service')):
            raise ValueError('A human lab administrator must request a source preview build.')
        from release_check_plans import KINDS as PLAN_KINDS
        if payload['kind'] in PLAN_KINDS and (not identity.get('is_admin') or identity.get('is_reader') or identity.get('is_delivery_service')):
            raise ValueError('A human administrator must review release check plans.')
        if payload['kind'] == 'request-exception' and (
                not identity.get('is_admin') or identity.get('is_delivery_service')):
            raise ValueError('A human lab administrator must request an exception.')
        if payload['kind'] in ('expire-preview', 'set-preview-expiry') and (
                not identity.get('is_admin') or identity.get('is_delivery_service')):
            raise ValueError('A human lab administrator must expire a delivery preview.')
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', key or ''):
            raise ValueError('Supply a stable Idempotency-Key of 1–128 characters.')
        owner = identity.get('issuer', '') + ':' + identity.get('subject', identity['username'])
        identifier = hashlib.sha256((owner + '\n' + key).encode()).hexdigest()[:32]
        public_payload = dict(payload)
        if payload['kind'] == 'build-preview':
            previous = self.get(identifier)
            if previous:
                original = {k: v for k, v in previous['request'].items() if not k.startswith('_')}
                if original != public_payload:
                    raise ValueError('Submission key already names a different operation.')
                return {**previous, 'submission_reused': True}
            from preview_build import prepare
            payload = {**payload, **prepare(payload['source_ref'])}
        if release_binding:
            payload = {**payload, '_release_binding': release_binding}
        if payload['kind'] == 'prepare-production':
            from production_release import preparation_context
            payload = {**payload, '_preparation_context': preparation_context()}
            if not release_binding:
                identifier = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT * FROM operations WHERE id=?', (identifier,)).fetchone()
            if previous:
                original = json.loads(previous['request'])
                if payload['kind'] == 'build-preview':
                    original = {k: v for k, v in original.items() if not k.startswith('_')}
                if original != (public_payload if payload['kind'] == 'build-preview' else json.loads(encoded)):
                    raise ValueError('Submission key already names a different operation.')
            else:
                db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (identifier, identity['username'], json.dumps(identity), encoded,
                            'accepted' if payload['kind'] in ('compare', 'gate-check') and payload.get('source_sha') else 'queued',
                            'Waiting for the delivery coordinator', None, None, stamp(), stamp()))
        # Submission metadata describes this HTTP attempt, not persisted work.
        return {**self.get(identifier), 'submission_reused': previous is not None}

    def get(self, identifier):
        with self.connect() as db:
            row = self.row(db.execute('SELECT * FROM operations WHERE id=?', (identifier,)).fetchone())
            if row and row['state'] == 'queued':
                active = db.execute("SELECT id,progress FROM operations WHERE state='running' ORDER BY created_at LIMIT 1").fetchone()
                ahead = db.execute("SELECT COUNT(*) FROM operations WHERE state='queued' AND updated_at < ?", (row['updated_at'],)).fetchone()[0]
                row['queue'] = {'position': ahead + 1, 'blocker': dict(active) if active else None}
            return row

    def active(self):
        """Return a bounded queue snapshot; the HTTP handler applies owner visibility."""
        with self.connect() as db:
            return [self.row(row) for row in db.execute(
                "SELECT * FROM operations WHERE state IN ('accepted','queued','running') ORDER BY updated_at LIMIT 50")]

    def log(self, identifier, message):
        """Retain safe step messages and structured events, never raw subprocess output."""
        with self.connect() as db:
            db.execute('INSERT INTO operation_logs(operation_id,at,message) VALUES (?,?,?)',
                       (identifier, stamp(), str(message)[:1000]))
            db.execute('DELETE FROM operation_logs WHERE operation_id=? AND sequence NOT IN '
                       '(SELECT sequence FROM operation_logs WHERE operation_id=? ORDER BY sequence DESC LIMIT 500)',
                       (identifier, identifier))

    def logs(self, identifier, after=0):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT sequence,at,message FROM operation_logs '
                'WHERE operation_id=? AND sequence>? ORDER BY sequence LIMIT 100', (identifier, after))]

    def next(self):
        """Claim one request while the caller holds the delivery writer lock."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM operations WHERE state='queued' ORDER BY updated_at LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE operations SET state='running', updated_at=? WHERE id=?", (stamp(), row['id']))
        return self.get(row['id']) if row else None

    def update(self, identifier, *, state='running', progress='', result=None, error=None):
        with self.connect() as db:
            db.execute('UPDATE operations SET state=?,progress=?,result=?,error=?,updated_at=? WHERE id=?',
                       (state, progress, json.dumps(result) if result is not None else None,
                        error, stamp(), identifier))

    def recover(self):
        """Mark interrupted operations explicitly; never replay a possible mutation."""
        with self.connect() as db:
            db.execute("UPDATE operations SET state='interrupted',error=?,updated_at=? WHERE state='running'",
                       ('Coordinator restarted. Inspect the recorded state before submitting a new operation.', stamp()))


def execute_next():
    """Execute one queued request; the existing delivery watcher owns the writer slot."""
    from delivery_cli import execute, parser
    from preview_routes import url
    store = Operations()
    row = store.next()
    if not row:
        return None
    identifier, request = row['id'], row['request']
    def progress(message):
        store.log(identifier, message)
        store.update(identifier, progress=message)
    from operation_telemetry import event_sink
    token = event_sink.set(lambda event: store.log(identifier, json.dumps(event, sort_keys=True)))
    if not (row.get('result') or {}).get('waiting'):
        store.log(identifier, 'Coordinator started this operation')
    try:
        if request.get('_release_binding'):
            from release_control import validate_binding
            validate_binding(request['_release_binding'])
        kind = request['kind']
        options = []
        for field in ('dataset', 'recipe', 'query_manifest', 'judgement_manifest'):
            if field in request:
                options += ['--' + field.replace('_', '-'), request[field]]
        if kind == 'suggest-release-plan':
            from release_check_plans import scope, suggest
            progress('Collecting accumulated source changes and query sets')
            baseline,candidate=scope(request['run'],request['target'],{
                field:request[key] for key,field in (
                    ('dataset','dataset_release'),('recipe','index_recipe_sha256'),
                    ('query_manifest','query_manifest_sha256'),('judgement_manifest','judgement_manifest_sha256')) if request.get(key)})
            result={'run':request['run'],'target':request['target'],'suggestion':suggest(baseline,candidate,request['target'])}
        elif kind == 'propose-release-plan':
            from release_check_plans import propose
            saved=store.get(request['suggestion'])
            if not saved or saved['state']!='complete' or saved['request']['kind']!='suggest-release-plan':
                raise ValueError('Choose a completed release check suggestion.')
            progress('Validating the reviewed selection and creating its plan PR')
            result=propose(saved['result']['suggestion'],request['edits'],row['identity'])
        elif kind == 'accept-release-plan':
            from release_check_plans import record
            progress('Checking exact-head approval and recording the plan in source control')
            result=record(request['pr'])
        elif kind == 'prepare-production':
            from production_release import prepare
            progress('Creating the reviewed inactive production candidate')
            from production_release import preparation_context
            if request.get('_preparation_context') != preparation_context():
                raise ValueError('Staging or production changed while this preparation was queued. Refresh and prepare again.')
            result = prepare()
        elif kind == 'release-production':
            from production_release import release
            result = release(progress=progress)
        elif kind == 'build-preview':
            from preview_build import advance
            result = advance(request, identifier, progress)
            if result.get('waiting'):
                store.update(identifier, state='queued', progress=result['progress'], result=result)
                return store.get(identifier)
        elif kind == 'preview':
            progress('Preparing the frozen preview')
            result = execute(parser().parse_args(['preview', '--run', str(request['run']), *options]))
            result['browser_url'] = url(result['name'])
        elif kind == 'gate-check':
            from delivery_source_comparison import recheck
            result = recheck(request, progress, identifier)
        elif kind in ('expire-preview', 'set-preview-expiry'):
            from preview_expiry import expire
            progress('Checking the preview identity and updating its lease')
            result = expire(request['name'], request['fingerprint'], request['expires_at'], request.get('new_expiry'))
        elif kind == 'compare':
            from delivery_source_comparison import compare
            result = compare(request, progress, identifier)
        elif kind == 'request-exception':
            from relevance_decisions import request_decision
            progress('Checking frozen evidence and creating the decision PR')
            result = request_decision(request, row['identity'])
        elif kind == 'merge-exception':
            from relevance_decisions import complete
            result = complete(request['pr'], progress, identifier)
        elif kind == 'merge-reviewed':
            progress('Checking the exact approval, merging and verifying deployment')
            result = execute(parser().parse_args(['merge-reviewed', str(request['pr'])]))
        elif kind == 'verify':
            progress('Verifying the currently declared deployment')
            result = execute(parser().parse_args(['verify', request['target']]))
        elif kind == 'rollback':
            progress('Evaluating the retained deployment against ' + request['target'])
            evaluation_args = ['evaluate-target', request['target'], '--fingerprint', request['fingerprint']]
            evidence = execute(parser().parse_args(evaluation_args))
            progress('Creating the reviewed rollback proposal')
            result = execute(parser().parse_args(['rollback', request['target'], '--fingerprint', request['fingerprint'],
                '--evidence', evidence['reference_file']]))
            result['url'] = 'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/' + str(result['pr'])
            result['report'] = {key: evidence[key] for key in ('sha256', 'blob')}
        else:
            target = request['target']
            if target == 'production':
                raise ValueError('Use Prepare production candidate, then Check and release production.')
            progress('Evaluating the candidate against ' + target)
            args = ['evaluate-target', target, '--run', str(request['run']), *options]
            evidence = execute(parser().parse_args(args))
            progress('Creating the reviewed deployment proposal')
            result = execute(parser().parse_args(['promote', target, '--run', str(request['run']),
                '--evidence', evidence['reference_file'], *options]))
            result['url'] = 'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/' + str(result['pr'])
            result['report'] = {key: evidence[key] for key in ('sha256', 'blob')}
        if kind in ('prepare-production', 'release-production') and result.get('pr'):
            from gitea import api
            from delivery_provider import DESIRED, endpoint
            result['url'] = 'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/' + str(result['pr'])
            body = '[Open release operation and evidence](https://control.localhost:34443/api/delivery/operations/' + identifier + '). '
            body += ('Review the final comparison before approving activation.' if kind == 'release-production'
                     else 'The active production route is unchanged.')
            api(endpoint(DESIRED, '/issues/' + str(result['pr']) + '/comments'), 'POST', {'body': body})
        store.update(identifier, state='complete', progress='Complete', result=result)
    except Exception as error:
        from delivery_source_comparison import BuildPending, ComparisonInputError
        if isinstance(error, BuildPending) and (
                datetime.now(timezone.utc) - datetime.fromisoformat(row['created_at'])).total_seconds() < 1800:
            store.update(identifier, state='queued', progress='Waiting for the exact source build')
            return store.get(identifier)
        # Detailed tracebacks stay in coordinator logs; no secrets or request
        # credentials are copied into the public operation record.
        import traceback
        traceback.print_exc()
        detail = type(error).__name__
        if isinstance(error, ComparisonInputError) or (isinstance(error, ValueError) and (getattr(error, 'reference', None) or
                request['kind'] in ('request-exception', 'merge-exception', 'prepare-production', 'release-production', 'expire-preview', 'set-preview-expiry', 'suggest-release-plan', 'propose-release-plan', 'accept-release-plan', 'promotion', 'rollback'))):
            # Decision validation errors contain public evidence/review facts,
            # never credentials or provider response bodies.
            detail += ': ' + str(error)[:600 if isinstance(error, ComparisonInputError) else 240]
        failed_reference = getattr(error, 'reference', None)
        store.log(identifier, detail)
        store.update(identifier, state='failed', progress='Operation failed', error=detail,
                     result={'report': failed_reference} if failed_reference else getattr(error, 'preview_result', None))
        if request.get('source_sha') and request['kind'] in ('compare', 'gate-check'):
            from delivery_source_comparison import status
            status(request['source_sha'], 'failure',
                   str(error) if isinstance(error, ComparisonInputError) else 'Comparison failed: ' + type(error).__name__,
                   identifier)
    finally:
        event_sink.reset(token)
    return store.get(identifier)
