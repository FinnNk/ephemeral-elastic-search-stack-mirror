"""Judgement API: stored labels first, bounded KServe inference on gaps."""

import argparse
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


class JudgementService:
    def __init__(self, database, source_rows, query_rows, product_rows,
                 context, model, predict):
        self.database = sqlite3.connect(database, check_same_thread=False)
        self.lock = threading.RLock()
        self.context = context
        self.model = model
        self.predict = predict
        self.scope = digest(canonical(context))
        self.database.executescript('''
            CREATE TABLE IF NOT EXISTS labels (
                scope TEXT NOT NULL, query_id TEXT NOT NULL, product_id TEXT NOT NULL,
                model_version TEXT NOT NULL, label TEXT NOT NULL, source TEXT NOT NULL,
                PRIMARY KEY (scope, query_id, product_id, model_version));
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, scope TEXT NOT NULL, query_id TEXT NOT NULL,
                product_id TEXT NOT NULL, model_version TEXT NOT NULL,
                input_sha256 TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT);
            CREATE TABLE IF NOT EXISTS queries (
                scope TEXT NOT NULL, query_id TEXT NOT NULL, request_sha256 TEXT NOT NULL,
                PRIMARY KEY(scope, query_id));
            CREATE TABLE IF NOT EXISTS products (
                scope TEXT NOT NULL, product_id TEXT NOT NULL, document_sha256 TEXT NOT NULL,
                PRIMARY KEY(scope, product_id));
            CREATE TABLE IF NOT EXISTS imports (
                scope TEXT PRIMARY KEY, complete INTEGER NOT NULL);
        ''')
        with self.database:
            imported = self.database.execute('SELECT complete FROM imports WHERE scope=?',
                                             (self.scope,)).fetchone()
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
                    self.database.execute('INSERT OR IGNORE INTO labels VALUES (?,?,?,?,?,?)',
                                          (self.scope, row['query_id'], row['product_id'], '',
                                           GRADE_TO_LABEL[grade], 'stored'))
                    stored = self.database.execute('''SELECT label FROM labels WHERE
                        scope=? AND query_id=? AND product_id=? AND model_version='' ''',
                        (self.scope, row['query_id'], row['product_id'])).fetchone()
                    if stored[0] != GRADE_TO_LABEL[grade]:
                        raise ValueError('Stored label conflicts with source bytes.')
                self.database.execute('INSERT INTO imports VALUES (?,1)', (self.scope,))

    def lookup(self, query_id, product_id):
        with self.lock:
            row = self.database.execute('''SELECT label,source,model_version FROM labels
                WHERE scope=? AND query_id=? AND product_id=? AND
                model_version IN ('',?) ORDER BY model_version ASC LIMIT 1''',
                (self.scope, query_id, product_id, self.model['version'])).fetchone()
        if row:
            return {'outcome': 'labelled', 'label': row[0], 'grade': LABEL_TO_GRADE[row[0]],
                    'source': row[1], 'model_version': row[2] or None}
        return None

    def resolve(self, context, pairs):
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
            known = self.lookup(*key)
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
                    self.database.execute('INSERT INTO attempts '
                        '(scope,query_id,product_id,model_version,input_sha256,outcome,detail) '
                        'VALUES (?,?,?,?,?,?,?)',
                        (self.scope, *key, self.model['version'], digest(canonical(pair)),
                         state, str(outcome.get('detail', ''))[:120]))
                    if state == 'labelled':
                        self.database.execute('INSERT OR IGNORE INTO labels VALUES (?,?,?,?,?,?)',
                            (self.scope, *key, self.model['version'], label, 'model'))
                        results[position] = self.lookup(*key)
                    else:
                        results[position] = {'outcome': 'unjudged' if state == 'abstain'
                                             else 'inference_error',
                                             'reason': 'model_abstained' if state == 'abstain'
                                             else 'model_failed'}
        return {'results': results, 'model': self.model}


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
            if self.path != '/v1/judgements:resolve':
                self.send_error(404)
                return
            with telemetry.span('judgement.http', self.headers, kind='server'):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 2_000_000:
                        raise ValueError('Resolution request is too large.')
                    body = json.loads(self.rfile.read(length))
                    with telemetry.span('judgement.lookup'):
                        value = service.resolve(body['context'], body['pairs'])
                    telemetry.count_results(service.model['version'], value['results'])
                    telemetry.attributes(http_response_status_code=200,
                                         lab_model_version=str(service.model['version']),
                                         lab_judgement_pairs=len(value['results']))
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
                                    json.loads(args.model.read_bytes()), timeout=model_timeout))
    serve(instance)
