"""Judgement API: stored labels first, bounded KServe inference on gaps."""

import argparse
from datetime import datetime, timezone
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
from urllib import request

from core import GRADE_TO_LABEL, LABEL_TO_GRADE, canonical, digest
from telemetry import telemetry
from evidence import EvidenceStore, validate


class JudgementService:
    def __init__(self, database, source_rows, query_rows, product_rows,
                 context, model, predict, source_identity=None, model_policy=None):
        self.database = sqlite3.connect(database, check_same_thread=False)
        self.lock = threading.RLock()
        self.context = context
        self.model = model
        self.predict = predict
        self.scope = digest(canonical(context))
        if source_identity is None:
            source_rows = list(source_rows)
        self.source_identity = source_identity or {'kind': 'published',
            'source_id': digest(canonical(source_rows))}
        self.model_policy = model_policy or {'pass_id': digest(canonical(model)),
            'policy_sha256': digest(canonical({'qualification': 'pending'})),
            'gate_eligible': False}
        if type(self.model_policy.get('gate_eligible')) is not bool:
            raise ValueError('Model policy eligibility must be explicit.')
        self.model_provenance = {'kind': 'model', 'source_id': digest(canonical(
            {'model': model, 'policy': self.model_policy})), 'model': model,
            **{k: v for k, v in self.model_policy.items() if k != 'gate_eligible'}}
        existing = self.database.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        version = self.database.execute('PRAGMA user_version').fetchone()[0]
        if existing and version != 2:
            raise ValueError('Recreate the disposable judgement database for the current schema.')
        self.database.execute('PRAGMA user_version=2')
        self.evidence = EvidenceStore(self.database, self.scope)
        self.database.executescript('''
            CREATE TABLE IF NOT EXISTS queries (
                scope TEXT NOT NULL, query_id TEXT NOT NULL, request_sha256 TEXT NOT NULL,
                PRIMARY KEY(scope, query_id));
            CREATE TABLE IF NOT EXISTS products (
                scope TEXT NOT NULL, product_id TEXT NOT NULL, document_sha256 TEXT NOT NULL,
                PRIMARY KEY(scope, product_id));
            CREATE TABLE IF NOT EXISTS imports (
                scope TEXT NOT NULL, source_id TEXT NOT NULL, complete INTEGER NOT NULL,
                PRIMARY KEY(scope,source_id));
        ''')
        with self.database:
            imported = self.database.execute('SELECT complete FROM imports WHERE scope=? AND source_id=?',
                                             (self.scope, self.source_identity['source_id'])).fetchone()
            if not imported:
                for row in query_rows:
                    original = {key: row[key] for key in ('query', 'country', 'currency')}
                    original['filters'] = row.get('filters', {})
                    self.database.execute('INSERT OR IGNORE INTO queries VALUES (?,?,?)',
                        (self.scope, row['query_id'], digest(canonical(original))))
                for row in product_rows:
                    self.database.execute('INSERT OR IGNORE INTO products VALUES (?,?,?)',
                        (self.scope, row['product_id'], digest(canonical(row))))
                for row in source_rows:
                    grade = row.get('grade')
                    if type(grade) is not int or grade not in GRADE_TO_LABEL:
                        raise ValueError('Source judgement has an invalid grade.')
                    if 'provenance' in row:
                        record = {k: v for k, v in row.items() if k not in
                                  ('query_id', 'product_id', 'grade', 'source', 'scope', 'evidence_sha256')}
                        record.update(outcome='labelled', label=GRADE_TO_LABEL[grade])
                        validate(record)
                    else:
                        if row.get('source') == 'model':
                            raise ValueError('Model source labels require explicit provenance.')
                        record = {'outcome': 'labelled', 'label': GRADE_TO_LABEL[grade],
                                  'gate_eligible': True, 'provenance': self.source_identity}
                    old = self.evidence.select(row['query_id'], row['product_id'], 'gate')
                    if old and old['label'] != record['label']:
                        raise ValueError('Stored label conflicts with source bytes.')
                    self.evidence.append(row['query_id'], row['product_id'], record)
                self.database.execute('INSERT INTO imports VALUES (?,?,1)',
                    (self.scope, self.source_identity['source_id']))

    def lookup(self, query_id, product_id, selection='gate'):
        with self.lock:
            return self.evidence.select(query_id, product_id, selection)

    def records(self, context, pairs):
        if context != self.context or not isinstance(pairs, list) or not 0 < len(pairs) <= 128:
            raise ValueError('Evidence request scope or pair count is invalid.')
        with self.lock:
            return {'results': [{'query_id': pair['query_id'], 'product_id': pair['product_id'],
                'evidence': self.evidence.records(pair['query_id'], pair['product_id'])}
                for pair in pairs]}

    def import_pass(self, payload):
        if payload.get('context') != self.context or payload.get('kind') != 'judgement-pass':
            raise ValueError('Judgement pass scope or kind is invalid.')
        rows = payload.get('records')
        if not isinstance(rows, list) or not 0 < len(rows) <= 128:
            raise ValueError('Import accepts 1 to 128 evidence records.')
        with self.lock, self.database:
            identities = []
            for row in rows:
                if row.get('gate_eligible') is not False or row.get('provenance', {}).get('kind') != 'model':
                    raise ValueError('Imported predictions must be unqualified model evidence.')
                query = self.database.execute('SELECT 1 FROM queries WHERE scope=? AND query_id=?',
                    (self.scope, row['query_id'])).fetchone()
                product = self.database.execute('SELECT 1 FROM products WHERE scope=? AND product_id=?',
                    (self.scope, row['product_id'])).fetchone()
                if not query or not product:
                    raise ValueError('Imported pair is outside the frozen sources.')
                record = {k: v for k, v in row.items() if k not in ('query_id', 'product_id')}
                identities.append(self.evidence.append(row['query_id'], row['product_id'], record))
        return {'evidence_sha256': identities}

    def resolve(self, context, pairs, selection='gate'):
        if selection not in ('gate', 'exploratory'):
            raise ValueError('Judgement selection must be gate or exploratory.')
        if context != self.context:
            raise ValueError('Requested source or rubric differs from this service.')
        if not isinstance(pairs, list) or not 0 < len(pairs) <= 128:
            raise ValueError('Resolve accepts 1 to 128 pairs.')
        seen = set()
        results = [None] * len(pairs)
        pending = []
        positions = []
        for index, pair in enumerate(pairs):
            key = (pair.get('query_id'), pair.get('product_id'))
            if not all(isinstance(value, str) and value for value in key) or key in seen:
                raise ValueError('Pair IDs are missing or duplicated.')
            seen.add(key)
            product = pair.get('product')
            original = pair.get('request')
            if not isinstance(product, dict) or product.get('product_id') != key[1] or \
                    not isinstance(original, dict) or \
                    product.get('country') != original.get('country') or \
                    product.get('currency') != original.get('currency'):
                raise ValueError('Pair source record or market is invalid.')
            with self.lock:
                query = self.database.execute('SELECT request_sha256 FROM queries WHERE scope=? AND query_id=?',
                    (self.scope, key[0])).fetchone()
                document = self.database.execute('SELECT document_sha256 FROM products WHERE scope=? AND product_id=?',
                    (self.scope, key[1])).fetchone()
            if query is None or document is None or \
                    query[0] != digest(canonical(original)) or \
                    document[0] != digest(canonical(product)):
                raise ValueError('Pair differs from the frozen query or catalogue.')
            known = self.lookup(*key, selection)
            if known:
                results[index] = known
            else:
                pending.append(pair)
                positions.append(index)
        if pending:
            try:
                predicted = self.predict(pending)
                if not isinstance(predicted, list) or len(predicted) != len(pending):
                    raise ValueError('Inference count differs from request count.')
            except Exception as error:
                predicted = [{'outcome': 'error', 'detail': type(error).__name__}
                             for _ in pending]
            with self.lock, self.database:
                for position, pair, outcome in zip(positions, pending, predicted):
                    state = outcome.get('outcome')
                    label = outcome.get('label')
                    if state == 'labelled' and label not in LABEL_TO_GRADE:
                        raise ValueError('Model returned an invalid ESCI label.')
                    if state not in ('labelled', 'abstain', 'error'):
                        raise ValueError('Model returned an invalid outcome.')
                    key = (pair['query_id'], pair['product_id'])
                    record = {**outcome, 'recorded_at': datetime.now(timezone.utc).isoformat(),
                        'input_sha256': digest(canonical(pair)),
                        'gate_eligible': self.model_policy['gate_eligible'],
                        'provenance': self.model_provenance}
                    record.pop('detail', None)
                    if state == 'error':
                        record['detail'] = str(outcome.get('detail', 'inference_error'))[:120]
                    self.evidence.append(*key, record)
                    selected = self.lookup(*key, selection)
                    results[position] = selected or {**record,
                        'outcome': 'inference_error' if state == 'error' else 'unjudged',
                        'reason': 'model_failed' if state == 'error' else
                                  'unqualified_prediction' if state == 'labelled' else 'model_abstained',
                        'provenance': self.model_provenance, 'gate_eligible': False}
        return {'results': results, 'model': self.model, 'selection': selection}


def kserve_predict(url, pairs, model, timeout=8):
    if not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ValueError('Model timeout must be between zero and 600 seconds.')
    payload = canonical({'instances': pairs})
    with telemetry.span('kserve.predict', kind='client'):
        headers = {'Content-Type': 'application/json'}
        telemetry.inject(headers)
        call = request.Request(url, payload, headers)
        with request.urlopen(call, timeout=timeout) as response:
            answer = json.loads(response.read())
    if answer.get('model') != model:
        raise ValueError('KServe responded from another registered model version.')
    return answer['predictions']


def serve(service, host='0.0.0.0', port=18086):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/health':
                self.send_error(404)
                return
            self.reply(200, {'ready': True, 'model': service.model})

        def do_POST(self):
            if self.path not in ('/v1/judgements:resolve', '/v1/judgements:records',
                                 '/v1/judgements:import'):
                self.send_error(404)
                return
            with telemetry.span('judgement.http', self.headers, kind='server'):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 2_000_000:
                        raise ValueError('Resolution request is too large.')
                    body = json.loads(self.rfile.read(length))
                    with telemetry.span('judgement.lookup'):
                        if self.path.endswith(':import'):
                            value = service.import_pass(body)
                        elif self.path.endswith(':records'):
                            value = service.records(body['context'], body['pairs'])
                        else:
                            value = service.resolve(body['context'], body['pairs'],
                                                    body.get('selection', 'gate'))
                    if self.path.endswith(':resolve'):
                        telemetry.count_results(service.model['version'], value['results'])
                    telemetry.attributes(http_response_status_code=200,
                                         lab_model_version=str(service.model['version']),
                                         lab_judgement_pairs=len(body.get('pairs', body.get('records', []))))
                    self.reply(200, value)
                except (ValueError, KeyError, TypeError) as error:
                    telemetry.attributes(http_response_status_code=400,
                                         error_type=type(error).__name__)
                    self.reply(400, {'error': str(error)})

        def reply(self, status, value):
            body = canonical(value)
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    ThreadingHTTPServer((host, port), Handler).serve_forever()


def read_rows(path):
    path = Path(path)
    with path.open('rb') as probe:
        compressed = probe.read(2) == b'\x1f\x8b'
    opener = gzip.open if compressed else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--source-judgements', type=Path, required=True)
    parser.add_argument('--catalogue', type=Path, required=True)
    parser.add_argument('--queries', type=Path, required=True)
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--predict-url', required=True)
    parser.add_argument('--model-policy', type=Path)
    parser.add_argument('--port', type=int, default=18086)
    parser.add_argument('--host', default='0.0.0.0')
    args = parser.parse_args()
    model_timeout = float(os.environ.get('JUDGEMENT_PREDICT_TIMEOUT_SECONDS', '8'))
    if not math.isfinite(model_timeout) or not 0 < model_timeout <= 600:
        raise ValueError('Model timeout must be between zero and 600 seconds.')
    telemetry.configure('judgement-service')
    args.database.parent.mkdir(parents=True, exist_ok=True)
    instance = JudgementService(args.database, read_rows(args.source_judgements),
        read_rows(args.queries), read_rows(args.catalogue),
        json.loads(args.context.read_bytes()), json.loads(args.model.read_bytes()),
        lambda pairs: kserve_predict(args.predict_url, pairs,
                                    json.loads(args.model.read_bytes()), timeout=model_timeout),
        source_identity={'kind': 'published', 'source_id': digest(args.source_judgements.read_bytes())},
        model_policy=json.loads(args.model_policy.read_bytes()) if args.model_policy else None)
    serve(instance, host=args.host, port=args.port)
