"""Durable 72-hour leases and idempotent local lab environment reconciliation."""
import json
import re
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import STATE, guard, k
from data_contract import elastic
from environments import REPO, build_record, define, git, provision_access, publish
from measure import search
from deploy_candidate import wait_healthy

LEASE = timedelta(hours=72)
NAME_PATTERN = re.compile(r'lab-[a-z0-9](?:[a-z0-9-]{0,42}[a-z0-9])?\Z')
DATASET = 'retail-gb-10k-v1'
INDEX = 'retail-gb-10k-v1'


def utcnow():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS environments (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, owner TEXT NOT NULL,
                build_run INTEGER NOT NULL, source_sha TEXT NOT NULL, image TEXT NOT NULL,
                dataset_sha256 TEXT NOT NULL, fingerprint TEXT,
                state TEXT NOT NULL, created_at TEXT NOT NULL, last_activity_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                error TEXT, deleted_at TEXT)''')
            db.execute('''CREATE TABLE IF NOT EXISTS comparisons (
                id TEXT PRIMARY KEY, baseline_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
                mode TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, report_sha256 TEXT, report_blob TEXT,
                verdict TEXT, summary TEXT, error TEXT)''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, row):
        columns = list(row)
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO environments (' + ','.join(columns) + ') VALUES (' +
                       ','.join('?' for _ in columns) + ')', [row[key] for key in columns])
        return row

    def get(self, instance_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM environments WHERE id=?', (instance_id,)).fetchone()
        return dict(row) if row else None

    def active_name(self, name):
        with self.connection() as db:
            row = db.execute("SELECT * FROM environments WHERE name=? AND state!='deleted' ORDER BY created_at DESC LIMIT 1",
                             (name,)).fetchone()
        return dict(row) if row else None

    def all(self):
        with self.connection() as db:
            rows = db.execute('SELECT * FROM environments ORDER BY created_at DESC').fetchall()
        return [dict(row) for row in rows]

    def update(self, instance_id, **fields):
        assert fields
        with self.connection() as db:
            db.execute('UPDATE environments SET ' + ','.join(key + '=?' for key in fields) + ' WHERE id=?',
                       [*fields.values(), instance_id])
        return self.get(instance_id)

    def claim_delete(self, instance_id, now):
        stale = stamp(now - timedelta(minutes=2))
        with self.connection() as db:
            result = db.execute('''UPDATE environments SET state='deleting', updated_at=?, error=NULL
                WHERE id=? AND (state NOT IN ('deleting','deleted')
                OR (state='deleting' AND (error IS NOT NULL OR updated_at<=?)))''',
                (stamp(now), instance_id, stale))
        return result.rowcount == 1

    def put_comparison(self, row):
        columns = list(row)
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO comparisons (' + ','.join(columns) + ') VALUES (' +
                       ','.join('?' for _ in columns) + ')', [row[key] for key in columns])
        return row

    def get_comparison(self, comparison_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM comparisons WHERE id=?', (comparison_id,)).fetchone()
        value = dict(row) if row else None
        if value and value['summary']:
            value['summary'] = json.loads(value['summary'])
        return value

    def all_comparisons(self):
        with self.connection() as db:
            rows = db.execute('SELECT id FROM comparisons ORDER BY created_at DESC').fetchall()
        return [self.get_comparison(row['id']) for row in rows]

    def update_comparison(self, comparison_id, **fields):
        with self.connection() as db:
            db.execute('UPDATE comparisons SET ' + ','.join(key + '=?' for key in fields) + ' WHERE id=?',
                       [*fields.values(), comparison_id])
        return self.get_comparison(comparison_id)


class LabBackend:
    def build(self, run_id):
        return build_record(run_id)

    def provision(self, row):
        guard()
        assert not git('status', '--porcelain'), 'Environment state checkout has local changes'
        provision_access(row['name'], INDEX)
        definition = define(row['name'], row['image'], INDEX, row['dataset_sha256'])
        if git('status', '--porcelain'):
            publish('Provision ' + row['name'])
        wait_healthy(row['name'])
        answer = search(row['name'], 'running shoes')
        assert answer is not None and len(answer['ids']) >= 10
        return definition['fingerprint']

    def delete(self, row):
        guard()
        assert not git('status', '--porcelain'), 'Environment state checkout has local changes'
        name = row['name']
        definition = REPO / 'environments' / (name + '.json')
        if definition.exists():
            definition.unlink()
            publish('Delete ' + name)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if not k('get', 'namespace', name, '--ignore-not-found', '-o', 'name').stdout.strip():
                break
            time.sleep(2)
        else:
            raise TimeoutError('Namespace deletion did not finish')
        for path in ('/_security/user/' + name, '/_security/role/' + name):
            elastic(path, 'DELETE')
        # This batch creates API-only environments over the shared frozen index.
        # The shared index and canonical release intentionally remain.


class Lifecycle:
    def __init__(self, store, backend, clock=utcnow, comparator=None):
        self.store, self.backend, self.clock = store, backend, clock
        self.lock = threading.RLock()
        self.comparator = comparator

    def create(self, name, build_run, owner='local-operator'):
        if not NAME_PATTERN.fullmatch(name):
            raise ValueError('Environment name must start with lab- and contain lowercase letters, digits or hyphens.')
        if not isinstance(build_run, int) or build_run <= 0:
            raise ValueError('A successful numeric Gitea build run is required.')
        with self.lock:
            existing = self.store.active_name(name)
            if existing and self.clock() >= parse_stamp(existing['expires_at']):
                existing = self.delete(existing['id'])
                if existing['state'] != 'deleted':
                    return existing
                existing = None
            if existing:
                if existing['build_run'] != build_run or existing['owner'] != owner:
                    raise ValueError('An active environment already uses this name with different inputs.')
                return self.reconcile(existing['id'])
            build = self.backend.build(build_run)
            manifest = json.loads((STATE / 'releases' / DATASET / 'manifest.json').read_text())
            now = self.clock()
            row = {'id': str(uuid.uuid4()), 'name': name, 'owner': owner, 'build_run': build_run,
                   'source_sha': build['source_sha'], 'image': build['image'],
                   'dataset_sha256': manifest['sha256']['products.jsonl'], 'fingerprint': None,
                   'state': 'requested', 'created_at': stamp(now), 'last_activity_at': stamp(now),
                   'expires_at': stamp(now + LEASE), 'updated_at': stamp(now),
                   'error': None, 'deleted_at': None}
            self.store.put(row)
            return self.reconcile(row['id'])

    def reconcile(self, instance_id):
        with self.lock:
            row = self.store.get(instance_id)
            if row is None:
                raise KeyError(instance_id)
            if row['state'] == 'deleted':
                return row
            if row['state'] == 'deleting':
                return self.delete(instance_id)
            if row['state'] == 'ready':
                return row
            self.store.update(instance_id, state='provisioning', updated_at=stamp(self.clock()), error=None)
            try:
                fingerprint = self.backend.provision(row)
            except Exception as error:
                return self.store.update(instance_id, state='failed', error=type(error).__name__ + ': ' + str(error),
                                         updated_at=stamp(self.clock()))
            return self.store.update(instance_id, state='ready', fingerprint=fingerprint,
                                     updated_at=stamp(self.clock()), error=None)

    def activity(self, instance_id):
        with self.lock:
            row = self.store.get(instance_id)
            if row is None or row['state'] != 'ready':
                raise ValueError('Only a ready environment can record activity.')
            now = self.clock()
            if now >= parse_stamp(row['expires_at']):
                raise ValueError('The environment lease has expired.')
            return self.store.update(instance_id, last_activity_at=stamp(now), expires_at=stamp(now + LEASE),
                                     updated_at=stamp(now))

    def delete(self, instance_id):
        with self.lock:
            row = self.store.get(instance_id)
            if row is None:
                raise KeyError(instance_id)
            if row['state'] == 'deleted':
                return row
            if not self.store.claim_delete(instance_id, self.clock()):
                return self.store.get(instance_id)
            try:
                self.backend.delete(row)
            except Exception as error:
                return self.store.update(instance_id, error=type(error).__name__ + ': ' + str(error),
                                         updated_at=stamp(self.clock()))
            now = stamp(self.clock())
            return self.store.update(instance_id, state='deleted', deleted_at=now, updated_at=now, error=None)

    def expire(self):
        expired = []
        for row in self.store.all():
            if row['state'] != 'deleted' and self.clock() >= parse_stamp(row['expires_at']):
                expired.append(self.delete(row['id']))
            elif row['state'] == 'deleting':
                expired.append(self.delete(row['id']))
            elif row['state'] in ('requested', 'provisioning'):
                expired.append(self.reconcile(row['id']))
        return expired

    def compare(self, baseline_id, candidate_id, mode):
        if baseline_id == candidate_id:
            raise ValueError('Select two distinct environments.')
        with self.lock:
            baseline = self.store.get(baseline_id)
            candidate = self.store.get(candidate_id)
            if baseline is None or candidate is None:
                raise KeyError('Environment not found.')
            if baseline['state'] != 'ready' or candidate['state'] != 'ready':
                raise ValueError('Both environments must be ready.')
            if self.clock() >= parse_stamp(baseline['expires_at']) or self.clock() >= parse_stamp(candidate['expires_at']):
                raise ValueError('An environment lease has expired.')
            if mode not in ('result-regression', 'relevance'):
                raise ValueError('Unknown comparison mode.')
            self.activity(baseline_id)
            self.activity(candidate_id)
            now = stamp(self.clock())
            comparison_id = str(uuid.uuid4())
            self.store.put_comparison({'id': comparison_id, 'baseline_id': baseline_id,
                'candidate_id': candidate_id, 'mode': mode, 'state': 'running',
                'created_at': now, 'updated_at': now, 'report_sha256': None,
                'report_blob': None, 'verdict': None, 'summary': None, 'error': None})
            try:
                if self.comparator is None:
                    from control_comparison import evaluate_pair
                    summary = evaluate_pair(baseline, candidate, mode)
                else:
                    summary = self.comparator(baseline, candidate, mode)
            except Exception as error:
                return self.store.update_comparison(comparison_id, state='failed',
                    updated_at=stamp(self.clock()), error=type(error).__name__ + ': ' + str(error))
            return self.store.update_comparison(comparison_id,
                state='complete' if summary['complete'] else 'incomplete',
                updated_at=stamp(self.clock()), report_sha256=summary['report_sha256'],
                report_blob=summary['report_blob'], verdict=summary['verdict'],
                summary=json.dumps(summary, sort_keys=True))


def local_lifecycle():
    return Lifecycle(Store(STATE / 'lifecycle.sqlite3'), LabBackend())
