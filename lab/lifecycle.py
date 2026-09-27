"""Durable 72-hour leases and idempotent local lab environment reconciliation."""
import json
import re
import sqlite3
import sys
import threading
import time
import uuid
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import STATE, guard, k
from data_contract import elastic
from environments import REPO, build_record, define, git, provision_access, publish
from measure import search
from deploy_candidate import wait_healthy
from index_candidate import KIND as INDEX_KIND, available_kinds, index_name, mapping_contract, ensure_candidate_index, remove_candidate_index
from index_recipe import (catalogue_recipe, digest as recipe_digest, load as load_index_recipe,
                          publish as publish_index_recipe, validate as validate_index_recipe,
                          verify_catalogue_manifest, shared_index_name)
from shared_index import ensure_shared_index
from input_selection import DEFAULTS, HASH, fetch_manifest

LEASE = timedelta(hours=72)
NAME_PATTERN = re.compile(r'lab-[a-z0-9](?:[a-z0-9-]{0,42}[a-z0-9])?\Z')
DATASET = 'retail-gb-10k-v1'
INDEX = 'retail-gb-10k-v1'
RELEASES = (DATASET, 'retail-gb-1m-v1')


def wait_correct_search(name, search_fn=search, timeout_seconds=60):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        answer = search_fn(name, 'running shoes')
        if answer is not None and len(answer.get('ids', [])) >= 10:
            return answer
        time.sleep(1)
    raise TimeoutError('Environment did not return a correct search after becoming healthy.')


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
            columns = {row['name'] for row in db.execute('PRAGMA table_info(environments)')}
            for name, field_type in [('index_kind', 'TEXT'), ('index_name', 'TEXT'),
                                     ('mapping_sha256', 'TEXT'), ('release_id', 'TEXT'),
                                     ('index_recipe_sha256', 'TEXT'),
                                     ('catalogue_manifest_sha256', 'TEXT'),
                                     ('index_materialisation', 'TEXT'),
                                     ('index_seconds', 'REAL'),
                                     ('index_recovery_errors', 'TEXT')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE environments ADD COLUMN {name} {field_type}')
            comparison_columns = {row['name'] for row in db.execute('PRAGMA table_info(comparisons)')}
            if 'profile' not in comparison_columns:
                db.execute('ALTER TABLE comparisons ADD COLUMN profile TEXT')
            if 'scope' not in comparison_columns:
                db.execute('ALTER TABLE comparisons ADD COLUMN scope TEXT')
            for name in ('observation_sha256', 'observation_blob',
                         'query_manifest_sha256', 'judgement_manifest_sha256'):
                if name not in comparison_columns:
                    db.execute(f'ALTER TABLE comparisons ADD COLUMN {name} TEXT')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS active_environment_name "
                       "ON environments(name) WHERE state!='deleted'")

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

    def recipe_record(self, recipe_sha256):
        with self.connection() as db:
            row = db.execute('SELECT * FROM environments WHERE index_recipe_sha256=? LIMIT 1',
                             (recipe_sha256,)).fetchone()
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

    def heartbeat_deleting(self, instance_ids, now):
        if not instance_ids:
            return
        placeholders = ','.join('?' for _ in instance_ids)
        with self.connection() as db:
            db.execute("UPDATE environments SET updated_at=? WHERE state='deleting' AND id IN (" +
                       placeholders + ')', [stamp(now), *instance_ids])

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

    def running_comparison_for(self, instance_id):
        with self.connection() as db:
            row = db.execute("SELECT id FROM comparisons WHERE state='running' AND "
                             '(baseline_id=? OR candidate_id=?) LIMIT 1',
                             (instance_id, instance_id)).fetchone()
        return row['id'] if row else None

    def interrupt_running_comparisons(self, now):
        with self.connection() as db:
            result = db.execute("UPDATE comparisons SET state='failed', updated_at=?, "
                                "error='Controller restarted before the comparison completed.' "
                                "WHERE state='running'", (stamp(now),))
        return result.rowcount


class ActiveComparisonError(ValueError):
    """An environment is pinned by a running comparison."""


class LabBackend:
    def build(self, run_id):
        return build_record(run_id)

    def pin_index_recipe(self, release_id, index_kind, recipe_sha256=None):
        engine = elastic('/')['version']['number']
        if recipe_sha256:
            recipe = load_index_recipe(recipe_sha256)
        else:
            catalogue = fetch_manifest('catalogue', DEFAULTS[release_id]['catalogue'])
            recipe = catalogue_recipe(release_id, index_kind, catalogue, engine,
                None if index_kind == 'shared' else mapping_contract(release_id, index_kind)[0])
        if recipe['format'] == 2:
            verify_catalogue_manifest(recipe)
            validate_index_recipe(recipe, release_id=release_id, engine_version=engine)
        else:
            manifest = json.loads((STATE / 'releases' / release_id / 'manifest.json').read_text(encoding='utf-8'))
            validate_index_recipe(recipe, release_id, manifest, engine)
        if recipe['index_kind'] != index_kind:
            raise ValueError('Frozen index recipe has a different index kind.')
        pinned_sha = recipe_sha256 or publish_index_recipe(recipe)
        return {'sha256': pinned_sha, 'mapping_sha256': recipe_digest(recipe['index_definition']),
                'product_sha256': recipe['product_sha256'],
                'catalogue_manifest_sha256': recipe.get('catalogue_manifest_sha256'),
                'shared_index': shared_index_name(recipe, pinned_sha) if index_kind == 'shared' else None}

    def provision(self, row):
        guard()
        assert not git('status', '--porcelain'), 'Environment state checkout has local changes'
        index = row['index_name'] or INDEX
        release_id = row.get('release_id') or DATASET
        mapping_sha = row['mapping_sha256']
        built = None
        if row['index_kind'] == 'shared' and row.get('index_recipe_sha256'):
            built = ensure_shared_index(release_id, row['dataset_sha256'], row['index_recipe_sha256'])
            if built['index'] != index:
                raise ValueError('Shared index differs from the pinned environment request.')
        elif row['index_kind'] != 'shared':
            built = ensure_candidate_index(row['name'], row['dataset_sha256'], release_id=release_id,
                                           recipe_sha256=row.get('index_recipe_sha256'),
                                           index_kind=row['index_kind'])
            if built['index'] != index or built['mapping_sha256'] != mapping_sha:
                raise ValueError('Candidate index differs from the pinned environment request.')
        provision_access(row['name'], index)
        definition = define(row['name'], row['image'], index, row['dataset_sha256'], mapping_sha,
                            row.get('index_recipe_sha256'))
        if git('status', '--porcelain'):
            publish('Provision ' + row['name'])
        wait_healthy(row['name'])
        wait_correct_search(row['name'])
        return {'fingerprint': definition['fingerprint'], 'index': built}

    def provision_many(self, rows):
        guard()
        assert not git('status', '--porcelain'), 'Environment state checkout has local changes'
        index_results = {}
        for release_id, dataset_sha, recipe_sha in {
                (row['release_id'], row['dataset_sha256'], row['index_recipe_sha256']) for row in rows
                if row.get('index_recipe_sha256')}:
            index_results[(release_id, dataset_sha, recipe_sha)] = ensure_shared_index(
                release_id, dataset_sha, recipe_sha)
        prepared = {}
        results = {}
        for row in rows:
            try:
                if row['index_kind'] != 'shared':
                    raise ValueError('Bulk provisioning is for shared-index API environments.')
                key = (row['release_id'], row['dataset_sha256'], row['index_recipe_sha256'])
                if index_results[key]['index'] != row['index_name']:
                    raise ValueError('Shared index differs from the pinned environment request.')
                provision_access(row['name'], row['index_name'])
                prepared[row['name']] = define(row['name'], row['image'], row['index_name'],
                    row['dataset_sha256'], row['mapping_sha256'], row.get('index_recipe_sha256'))['fingerprint']
            except Exception as error:
                results[row['name']] = {'error': type(error).__name__ + ': ' + str(error)}
        if git('status', '--porcelain'):
            publish('Provision ' + str(len(prepared)) + ' shared search environments')

        def ready(name):
            wait_healthy(name)
            wait_correct_search(name)
            return prepared[name]

        with ThreadPoolExecutor(max_workers=min(8, len(prepared)) or 1) as workers:
            futures = {workers.submit(ready, name): name for name in prepared}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    row = next(item for item in rows if item['name'] == name)
                    key = (row['release_id'], row['dataset_sha256'], row['index_recipe_sha256'])
                    results[name] = {'fingerprint': future.result(), 'index': index_results.get(key)}
                except Exception as error:
                    results[name] = {'error': type(error).__name__ + ': ' + str(error)}
        return results

    def delete(self, row, heartbeat=None):
        guard()
        assert not git('status', '--porcelain'), 'Environment state checkout has local changes'
        name = row['name']
        definition = REPO / 'environments' / (name + '.json')
        if definition.exists():
            definition.unlink()
            publish('Delete ' + name)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if heartbeat:
                heartbeat()
            if not k('get', 'namespace', name, '--ignore-not-found', '-o', 'name').stdout.strip():
                break
            time.sleep(2)
        else:
            raise TimeoutError('Namespace deletion did not finish')
        for path in ('/_security/user/' + name, '/_security/role/' + name):
            try:
                elastic(path, 'DELETE')
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
        if row['index_kind'] != 'shared':
            remove_candidate_index(name)
        # The shared index, canonical release and immutable reports remain.

    def delete_many(self, rows, heartbeat=None):
        guard()
        assert not git('status', '--porcelain'), 'Environment state checkout has local changes'
        for row in rows:
            definition = REPO / 'environments' / (row['name'] + '.json')
            if definition.exists():
                definition.unlink()
        if git('status', '--porcelain'):
            publish('Delete ' + str(len(rows)) + ' search environments')
        pending = {row['name'] for row in rows}
        deadline = time.monotonic() + 180
        while pending and time.monotonic() < deadline:
            if heartbeat:
                heartbeat()
            namespaces = json.loads(k('get', 'namespaces', '-o', 'json').stdout)['items']
            present = {item['metadata']['name'] for item in namespaces}
            pending &= present
            if pending:
                time.sleep(2)
        if pending:
            raise TimeoutError('Namespace deletion did not finish: ' + ', '.join(sorted(pending)))
        for row in rows:
            if heartbeat:
                heartbeat()
            for path in ('/_security/user/' + row['name'], '/_security/role/' + row['name']):
                try:
                    elastic(path, 'DELETE')
                except urllib.error.HTTPError as error:
                    if error.code != 404:
                        raise
            if row['index_kind'] != 'shared':
                remove_candidate_index(row['name'])


class Lifecycle:
    def __init__(self, store, backend, clock=utcnow, comparator=None):
        self.store, self.backend, self.clock = store, backend, clock
        self.lock = threading.RLock()
        self.performance_lock = threading.Lock()
        self.comparator = comparator

    def create(self, name, build_run, owner='local-operator', index_kind='shared', release_id=DATASET,
               index_recipe_sha256=None):
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            raise ValueError('Environment name must start with lab- and contain lowercase letters, digits or hyphens.')
        if type(build_run) is not int or build_run <= 0:
            raise ValueError('A successful numeric Gitea build run is required.')
        if not isinstance(owner, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', owner):
            raise ValueError('A valid owner identity is required.')
        if index_kind != 'shared' and index_kind not in available_kinds(release_id) and not index_recipe_sha256:
            raise ValueError('Choose a shared index or a versioned index kind available for this release.')
        if release_id not in RELEASES:
            raise ValueError('Choose a frozen release supported by this lab.')
        if index_recipe_sha256 and not self.store.recipe_record(index_recipe_sha256):
            from azure.core.exceptions import ResourceNotFoundError
            try:
                selected_recipe = load_index_recipe(index_recipe_sha256)
            except ResourceNotFoundError:
                raise ValueError('Historical index recipe is not pinned by a lab environment.') from None
            if selected_recipe.get('format') != 2:
                raise ValueError('Historical index recipe is not pinned by a lab environment.')
        with self.lock:
            existing = self.store.active_name(name)
            if existing and self.clock() >= parse_stamp(existing['expires_at']):
                existing = self.delete(existing['id'])
                if existing['state'] != 'deleted':
                    return existing
                existing = None
            if existing:
                if existing['build_run'] != build_run or existing['owner'] != owner or \
                        (existing['index_kind'] or 'shared') != index_kind or \
                        (existing.get('release_id') or DATASET) != release_id or \
                        (index_recipe_sha256 and existing.get('index_recipe_sha256') != index_recipe_sha256):
                    raise ValueError('An active environment already uses this name with different inputs.')
                return self.reconcile(existing['id'])
            build = self.backend.build(build_run)
            pinned = self.backend.pin_index_recipe(release_id, index_kind, index_recipe_sha256)
            mapping_sha = pinned['mapping_sha256']
            target_index = index_name(name) if index_kind != 'shared' else pinned['shared_index']
            now = self.clock()
            row = {'id': str(uuid.uuid4()), 'name': name, 'owner': owner, 'build_run': build_run,
                   'source_sha': build['source_sha'], 'image': build['image'],
                   'dataset_sha256': pinned['product_sha256'], 'fingerprint': None,
                   'release_id': release_id,
                   'index_kind': index_kind, 'index_name': target_index, 'mapping_sha256': mapping_sha,
                   'index_recipe_sha256': pinned['sha256'],
                   'catalogue_manifest_sha256': pinned['catalogue_manifest_sha256'],
                   'state': 'requested', 'created_at': stamp(now), 'last_activity_at': stamp(now),
                   'expires_at': stamp(now + LEASE), 'updated_at': stamp(now),
                   'error': None, 'deleted_at': None}
            self.store.put(row)
            return self.reconcile(row['id'])

    def create_many(self, names, build_run, owner='local-operator', release_id=DATASET):
        if not isinstance(names, list) or not 1 <= len(names) <= 40 or \
                any(not isinstance(name, str) for name in names) or len(set(names)) != len(names):
            raise ValueError('Provide 1–40 distinct environment names.')
        if any(not isinstance(name, str) or not NAME_PATTERN.fullmatch(name) for name in names):
            raise ValueError('Environment names must use the lab- lowercase format.')
        if type(build_run) is not int or build_run <= 0:
            raise ValueError('A successful numeric Gitea build run is required.')
        if not isinstance(owner, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', owner):
            raise ValueError('A valid owner identity is required.')
        if release_id not in RELEASES:
            raise ValueError('Choose a frozen release supported by this lab.')
        with self.lock:
            if any(self.store.active_name(name) for name in names):
                raise ValueError('An active environment already uses a requested name.')
            build = self.backend.build(build_run)
            pinned = self.backend.pin_index_recipe(release_id, 'shared')
            now = self.clock()
            rows = []
            for name in names:
                row = {'id': str(uuid.uuid4()), 'name': name, 'owner': owner, 'build_run': build_run,
                       'source_sha': build['source_sha'], 'image': build['image'],
                       'dataset_sha256': pinned['product_sha256'], 'fingerprint': None,
                       'release_id': release_id, 'index_kind': 'shared', 'index_name': pinned['shared_index'],
                       'mapping_sha256': pinned['mapping_sha256'],
                       'index_recipe_sha256': pinned['sha256'],
                       'catalogue_manifest_sha256': pinned['catalogue_manifest_sha256'],
                       'state': 'requested', 'created_at': stamp(now),
                       'last_activity_at': stamp(now), 'expires_at': stamp(now + LEASE),
                       'updated_at': stamp(now), 'error': None, 'deleted_at': None}
                rows.append(self.store.put(row))
            try:
                results = self.backend.provision_many(rows)
            except Exception as error:
                results = {row['name']: {'error': type(error).__name__ + ': ' + str(error)} for row in rows}
            updated = []
            for row in rows:
                result = results[row['name']]
                if 'error' in result:
                    updated.append(self.store.update(row['id'], state='failed', error=result['error'],
                                                     updated_at=stamp(self.clock())))
                else:
                    fields = {'state': 'ready', 'fingerprint': result['fingerprint'],
                              'updated_at': stamp(self.clock())}
                    built = result.get('index')
                    if built:
                        fields.update(index_materialisation=built['materialisation'],
                                      index_seconds=built.get('seconds', built.get('build_seconds', 0)),
                                      index_recovery_errors=json.dumps(built.get('recovery_errors', [])))
                    updated.append(self.store.update(row['id'], **fields))
            return updated

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
                result = self.backend.provision(row)
            except Exception as error:
                return self.store.update(instance_id, state='failed', error=type(error).__name__ + ': ' + str(error),
                                         updated_at=stamp(self.clock()))
            fingerprint = result['fingerprint'] if isinstance(result, dict) else result
            built = result.get('index') if isinstance(result, dict) else None
            fields = {'state': 'ready', 'fingerprint': fingerprint,
                      'updated_at': stamp(self.clock()), 'error': None}
            if built:
                fields.update(index_materialisation=built['materialisation'],
                              index_seconds=built.get('seconds', built.get('build_seconds', 0)),
                              index_recovery_errors=json.dumps(built.get('recovery_errors', [])))
            return self.store.update(instance_id, **fields)

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
            if self.store.running_comparison_for(instance_id):
                raise ActiveComparisonError('A running comparison uses this environment.')
            if not self.store.claim_delete(instance_id, self.clock()):
                return self.store.get(instance_id)
            try:
                self.backend.delete(row, heartbeat=lambda: self.store.heartbeat_deleting(
                    [instance_id], self.clock()))
            except Exception as error:
                return self.store.update(instance_id, error=type(error).__name__ + ': ' + str(error),
                                         updated_at=stamp(self.clock()))
            now = stamp(self.clock())
            return self.store.update(instance_id, state='deleted', deleted_at=now, updated_at=now, error=None)

    def delete_many(self, instance_ids):
        if not isinstance(instance_ids, list) or not 1 <= len(instance_ids) <= 40 or \
                any(not isinstance(value, str) for value in instance_ids) or \
                len(set(instance_ids)) != len(instance_ids):
            raise ValueError('Provide 1–40 distinct environment IDs.')
        with self.lock:
            rows = []
            for instance_id in instance_ids:
                row = self.store.get(instance_id)
                if row is None:
                    raise KeyError(instance_id)
                if self.store.running_comparison_for(instance_id):
                    raise ActiveComparisonError('A running comparison uses this environment.')
                rows.append(row)
            active = [row for row in rows if row['state'] != 'deleted']
            claimed = [row for row in active if self.store.claim_delete(row['id'], self.clock())]
            if claimed:
                try:
                    self.backend.delete_many(claimed, heartbeat=lambda: self.store.heartbeat_deleting(
                        [row['id'] for row in claimed], self.clock()))
                except Exception as error:
                    for row in claimed:
                        if self.store.get(row['id'])['state'] != 'deleted':
                            self.store.update(row['id'], error=type(error).__name__ + ': ' + str(error),
                                              updated_at=stamp(self.clock()))
                else:
                    now = stamp(self.clock())
                    for row in claimed:
                        if self.store.get(row['id'])['state'] != 'deleted':
                            self.store.update(row['id'], state='deleted', deleted_at=now,
                                              updated_at=now, error=None)
            return [self.store.get(instance_id) for instance_id in instance_ids]

    def expire(self):
        expired = []
        for row in self.store.all():
            if row['state'] != 'deleted' and self.clock() >= parse_stamp(row['expires_at']):
                expired.append(self.delete(row['id']))
            elif row['state'] == 'deleting':
                expired.append(self.delete(row['id']))
            elif row['state'] in ('requested', 'provisioning') and \
                    self.clock() >= parse_stamp(row['updated_at']) + timedelta(minutes=2):
                expired.append(self.reconcile(row['id']))
        return expired

    def compare(self, baseline_id, candidate_id, mode, profile='probe', scope='full',
                query_manifest_sha=None, judgement_manifest_sha=None):
        if baseline_id == candidate_id:
            raise ValueError('Select two distinct environments.')
        with self.lock:
            baseline = self.store.get(baseline_id)
            candidate = self.store.get(candidate_id)
            if baseline is None or candidate is None:
                raise KeyError('Environment not found.')
            if baseline['state'] != 'ready' or candidate['state'] != 'ready':
                raise ValueError('Both environments must be ready.')
            if baseline['dataset_sha256'] != candidate['dataset_sha256']:
                raise ValueError('Comparisons require the same frozen catalogue.')
            if mode == 'performance' and baseline['release_id'] != candidate['release_id']:
                raise ValueError('Performance requires the same frozen workload release.')
            if self.clock() >= parse_stamp(baseline['expires_at']) or self.clock() >= parse_stamp(candidate['expires_at']):
                raise ValueError('An environment lease has expired.')
            if mode not in ('result-regression', 'relevance', 'performance'):
                raise ValueError('Unknown comparison mode.')
            if scope not in ('quick', 'full') or (mode == 'performance' and scope != 'full'):
                raise ValueError('Unknown or unsupported comparison scope.')
            if mode == 'performance' and profile not in (
                    'probe', 'smoke', 'normal', 'peak', 'stress',
                    'normal-full', 'sustained-peak', 'stress-full'):
                raise ValueError('Unknown performance profile.')
            if mode == 'performance' and (query_manifest_sha or judgement_manifest_sha):
                raise ValueError('Performance uses its pinned workload rather than functional input selection.')
            if mode != 'performance':
                defaults = DEFAULTS[baseline.get('release_id') or DATASET]
                query_manifest_sha = query_manifest_sha or defaults['query-suite']
                if mode == 'relevance':
                    judgement_manifest_sha = judgement_manifest_sha or defaults['judgement-set']
                elif judgement_manifest_sha:
                    raise ValueError('Judgements can only be selected for relevance.')
                for selected_sha in (query_manifest_sha, judgement_manifest_sha):
                    if selected_sha is not None and (not isinstance(selected_sha, str) or
                                                     not HASH.fullmatch(selected_sha)):
                        raise ValueError('Select a valid independent input manifest SHA-256.')
            self.activity(baseline_id)
            self.activity(candidate_id)
            now = stamp(self.clock())
            comparison_id = str(uuid.uuid4())
            self.store.put_comparison({'id': comparison_id, 'baseline_id': baseline_id,
                'candidate_id': candidate_id, 'mode': mode, 'profile': profile if mode == 'performance' else None,
                'scope': scope if mode != 'performance' else None,
                'query_manifest_sha256': query_manifest_sha,
                'judgement_manifest_sha256': judgement_manifest_sha,
                'state': 'running',
                'created_at': now, 'updated_at': now, 'report_sha256': None,
                'report_blob': None, 'verdict': None, 'summary': None, 'error': None})
        try:
            if mode == 'performance' and self.comparator is None:
                with self.performance_lock:
                    from performance_pair import evaluate_performance_pair
                    summary = evaluate_performance_pair(baseline, candidate, profile)
            elif self.comparator is None:
                from control_comparison import evaluate_pair
                summary = evaluate_pair(baseline, candidate, mode, scope=scope,
                                        query_manifest_sha=query_manifest_sha,
                                        judgement_manifest_sha=judgement_manifest_sha)
            else:
                summary = self.comparator(baseline, candidate, mode)
        except Exception as error:
            return self.store.update_comparison(comparison_id, state='failed',
                updated_at=stamp(self.clock()), error=type(error).__name__ + ': ' + str(error))
        return self.store.update_comparison(comparison_id,
            state='complete' if summary['complete'] else 'incomplete',
            updated_at=stamp(self.clock()), report_sha256=summary['report_sha256'],
            report_blob=summary['report_blob'],
            observation_sha256=summary.get('observation_sha256'),
            observation_blob=summary.get('observation_blob'), verdict=summary['verdict'],
            summary=json.dumps(summary, sort_keys=True))


def local_lifecycle(recover_comparisons=False):
    store = Store(STATE / 'lifecycle.sqlite3')
    if recover_comparisons:
        store.interrupt_running_comparisons(utcnow())
    return Lifecycle(store, LabBackend())
