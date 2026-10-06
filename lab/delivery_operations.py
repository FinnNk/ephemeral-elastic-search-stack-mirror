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
    'prepare-production': set(),
    'release-production': {'intent'},
    'preview': {'run', 'dataset', 'recipe'},
    'compare': {'baseline_run', 'candidate_run', 'dataset', 'recipe', 'pr', 'source_sha', 'baseline_sha'},
    'promotion': {'target', 'run', 'dataset', 'recipe', 'intent'},
    'gate-check': {'pr', 'source_sha'},
    'request-exception': {'pr', 'source_sha', 'variant', 'reason'},
    'merge-exception': {'pr'},
    'merge-reviewed': {'pr'},
    'verify': {'target'},
    'rollback': {'target', 'fingerprint', 'intent'},
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
    required = {'prepare-production': set(), 'release-production': {'intent'}, 'preview': {'run'}, 'compare': {'pr', 'source_sha', 'baseline_sha'} if 'pr' in payload
                else {'baseline_run', 'candidate_run'},
                'promotion': {'target', 'run', 'intent'}, 'gate-check': {'pr', 'source_sha'},
                'request-exception': {'pr', 'source_sha', 'variant', 'reason'},
                'merge-exception': {'pr'},
                'merge-reviewed': {'pr'}, 'verify': {'target'},
                'rollback': {'target', 'fingerprint', 'intent'}}[kind]
    if not required <= set(payload):
        raise ValueError('Required delivery operation fields are missing.')
    for field in ('run', 'baseline_run', 'candidate_run', 'pr'):
        if field in payload and (type(payload[field]) is not int or payload[field] < 1):
            raise ValueError('Build and PR numbers must be positive integers.')
    if 'target' in payload and payload['target'] not in ('integration', 'staging', 'production'):
        raise ValueError('Delivery target is invalid.')
    if 'intent' in payload and payload['intent'] not in ('ranking-change', 'preserve-results'):
        raise ValueError('Promotion target or intent is invalid.')
    if 'dataset' in payload and not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', str(payload['dataset'])):
        raise ValueError('Dataset name is invalid.')
    for field, size in (('recipe', 64), ('fingerprint', 64), ('source_sha', 40), ('baseline_sha', 40)):
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

    def submit(self, payload, identity, key):
        """Retry the same submission key safely; changed payloads require a new key."""
        validate(payload)
        if payload['kind'] == 'request-exception' and (
                not identity.get('is_admin') or identity.get('is_delivery_service')):
            raise ValueError('A human lab administrator must request an exception.')
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', key or ''):
            raise ValueError('Supply a stable Idempotency-Key of 1–128 characters.')
        owner = identity.get('issuer', '') + ':' + identity.get('subject', identity['username'])
        identifier = hashlib.sha256((owner + '\n' + key).encode()).hexdigest()[:32]
        if payload['kind'] == 'prepare-production':
            from production_release import preparation_context
            payload = {**payload, '_preparation_context': preparation_context()}
            identifier = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT * FROM operations WHERE id=?', (identifier,)).fetchone()
            if previous:
                if previous['request'] != encoded:
                    raise ValueError('Submission key already names a different operation.')
            else:
                db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (identifier, identity['username'], json.dumps(identity), encoded,
                            'accepted' if payload['kind'] in ('compare', 'gate-check') and payload.get('source_sha') else 'queued',
                            'Waiting for the delivery coordinator', None, None, stamp(), stamp()))
        return self.get(identifier)

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
    store.log(identifier, 'Coordinator started this operation')
    try:
        kind = request['kind']
        options = []
        for field in ('dataset', 'recipe'):
            if field in request:
                options += ['--' + field, request[field]]
        if kind == 'prepare-production':
            from production_release import prepare
            progress('Creating the reviewed inactive production candidate')
            from production_release import preparation_context
            if request.get('_preparation_context') != preparation_context():
                raise ValueError('Staging or production changed while this preparation was queued. Refresh and prepare again.')
            result = prepare()
        elif kind == 'release-production':
            from production_release import release
            result = release(request['intent'], progress)
        elif kind == 'preview':
            progress('Preparing the frozen preview')
            result = execute(parser().parse_args(['preview', '--run', str(request['run']), *options]))
            result['browser_url'] = url(result['name'])
        elif kind == 'gate-check':
            from delivery_source_comparison import recheck
            result = recheck(request, progress, identifier)
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
            evidence = execute(parser().parse_args(['evaluate-target', request['target'],
                '--fingerprint', request['fingerprint'], '--intent', request['intent']]))
            progress('Creating the reviewed rollback proposal')
            result = execute(parser().parse_args(['rollback', request['target'],
                '--fingerprint', request['fingerprint'], '--intent', request['intent'],
                '--evidence', evidence['reference_file']]))
            result['url'] = 'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/' + str(result['pr'])
            result['report'] = {key: evidence[key] for key in ('sha256', 'blob')}
        else:
            target = request['target']
            if target == 'production':
                raise ValueError('Use Prepare production candidate, then Check and release production.')
            progress('Evaluating the candidate against ' + target)
            args = ['evaluate-target', target, '--run', str(request['run']),
                    '--intent', request['intent'], *options]
            evidence = execute(parser().parse_args(args))
            progress('Creating the reviewed deployment proposal')
            result = execute(parser().parse_args(['promote', target, '--run', str(request['run']),
                '--intent', request['intent'], '--evidence', evidence['reference_file'], *options]))
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
        from delivery_source_comparison import BuildPending
        if isinstance(error, BuildPending) and (
                datetime.now(timezone.utc) - datetime.fromisoformat(row['created_at'])).total_seconds() < 1800:
            store.update(identifier, state='queued', progress='Waiting for the exact source build')
            return store.get(identifier)
        # Detailed tracebacks stay in coordinator logs; no secrets or request
        # credentials are copied into the public operation record.
        import traceback
        traceback.print_exc()
        detail = type(error).__name__
        if isinstance(error, ValueError) and (getattr(error, 'reference', None) or
                request['kind'] in ('request-exception', 'merge-exception', 'prepare-production', 'release-production')):
            # Decision validation errors contain public evidence/review facts,
            # never credentials or provider response bodies.
            detail += ': ' + str(error)[:240]
        failed_reference = getattr(error, 'reference', None)
        store.log(identifier, detail)
        store.update(identifier, state='failed', progress='Operation failed', error=detail,
                     result={'report': failed_reference} if failed_reference else None)
        if request.get('source_sha') and request['kind'] in ('compare', 'gate-check'):
            from delivery_source_comparison import status
            status(request['source_sha'], 'failure', 'Comparison failed: ' + type(error).__name__, identifier)
    finally:
        event_sink.reset(token)
    return store.get(identifier)
