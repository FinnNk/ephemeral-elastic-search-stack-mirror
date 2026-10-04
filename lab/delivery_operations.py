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
    'preview': {'run', 'dataset', 'recipe'},
    'compare': {'baseline_run', 'candidate_run', 'dataset', 'recipe', 'pr', 'source_sha', 'baseline_sha'},
    'promotion': {'target', 'run', 'dataset', 'recipe', 'intent'},
    'gate-check': {'pr', 'source_sha'},
}
PUBLIC = 'https://control.localhost:34443'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def validate(payload):
    """Accept named operations, never arbitrary CLI arguments or filesystem paths."""
    if not isinstance(payload, dict) or payload.get('kind') not in FIELDS:
        raise ValueError('Choose preview, compare, promotion or gate-check.')
    kind = payload['kind']
    if set(payload) - (FIELDS[kind] | {'kind'}):
        raise ValueError('Unknown delivery operation field.')
    required = {'preview': {'run'}, 'compare': {'pr', 'source_sha', 'baseline_sha'} if 'pr' in payload
                else {'baseline_run', 'candidate_run'},
                'promotion': {'target', 'run', 'intent'}, 'gate-check': {'pr', 'source_sha'}}[kind]
    if not required <= set(payload):
        raise ValueError('Required delivery operation fields are missing.')
    for field in ('run', 'baseline_run', 'candidate_run', 'pr'):
        if field in payload and (type(payload[field]) is not int or payload[field] < 1):
            raise ValueError('Build and PR numbers must be positive integers.')
    if kind == 'promotion' and (payload['target'] not in ('integration', 'staging', 'production')
            or payload['intent'] not in ('ranking-change', 'preserve-results')):
        raise ValueError('Promotion target or intent is invalid.')
    if 'dataset' in payload and not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', str(payload['dataset'])):
        raise ValueError('Dataset name is invalid.')
    for field, size in (('recipe', 64), ('source_sha', 40), ('baseline_sha', 40)):
        if field in payload and not re.fullmatch('[0-9a-f]{' + str(size) + '}', str(payload[field])):
            raise ValueError('Frozen source or recipe identity is invalid.')
    if kind == 'compare' and 'pr' in payload and not {'source_sha', 'baseline_sha'} <= set(payload):
        raise ValueError('A source PR comparison needs exact head and baseline commits.')
    return payload


class Operations:
    def __init__(self, path=None):
        self.path = Path(path or STATE / 'delivery-operations.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
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
        return result

    def submit(self, payload, identity, key):
        """Retry the same submission key safely; changed payloads require a new key."""
        validate(payload)
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', key or ''):
            raise ValueError('Supply a stable Idempotency-Key of 1–128 characters.')
        owner = identity.get('issuer', '') + ':' + identity.get('subject', identity['username'])
        identifier = hashlib.sha256((owner + '\n' + key).encode()).hexdigest()[:32]
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
                            'accepted' if payload.get('pr') else 'queued',
                            'Waiting for the delivery coordinator', None, None, stamp(), stamp()))
        return self.get(identifier)

    def get(self, identifier):
        with self.connect() as db:
            return self.row(db.execute('SELECT * FROM operations WHERE id=?', (identifier,)).fetchone())

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
        store.update(identifier, progress=message)
    try:
        kind = request['kind']
        options = []
        for field in ('dataset', 'recipe'):
            if field in request:
                options += ['--' + field, request[field]]
        if kind == 'preview':
            progress('Preparing the frozen preview')
            result = execute(parser().parse_args(['preview', '--run', str(request['run']), *options]))
            result['browser_url'] = url(result['name'])
        elif kind == 'gate-check':
            from delivery_source_comparison import recheck
            result = recheck(request, progress, identifier)
        elif kind == 'compare':
            from delivery_source_comparison import compare
            result = compare(request, progress, identifier)
        else:
            target = request['target']
            progress('Evaluating the candidate against ' + target)
            args = ['evaluate-target', target, '--run', str(request['run']),
                    '--intent', request['intent'], *options]
            evidence = execute(parser().parse_args(args))
            progress('Creating the reviewed deployment proposal')
            result = execute(parser().parse_args(['promote', target, '--run', str(request['run']),
                '--intent', request['intent'], '--evidence', evidence['reference_file'], *options]))
            result['url'] = 'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/' + str(result['pr'])
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
        store.update(identifier, state='failed', progress='Operation failed', error=type(error).__name__)
        if request.get('pr'):
            from delivery_source_comparison import status
            status(request['source_sha'], 'failure', 'Comparison failed: ' + type(error).__name__, identifier)
    return store.get(identifier)
