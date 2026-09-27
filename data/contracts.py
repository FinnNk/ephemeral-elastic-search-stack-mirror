"""Versioned, content-addressed synthetic input contracts.

This package has no dependency on the search API or lab control runtime.
"""

import csv
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

VERSION = 1
KINDS = {'catalogue', 'query-suite', 'judgement-set', 'traffic-trace'}
FILES = {'catalogue': ('products.jsonl', 'products.jsonl.gz'),
         'query-suite': ('queries.jsonl',),
         'judgement-set': ('judgements.jsonl',),
         'traffic-trace': ('traffic.csv',)}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f'Blank record at {path}:{number}.')
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f'Non-object record at {path}:{number}.')
            yield value


def input_files(directory):
    directory = Path(directory)
    selected = {}
    for kind in ('catalogue', 'query-suite', 'judgement-set'):
        matches = [directory / name for name in FILES[kind] if (directory / name).is_file()]
        if len(matches) != 1:
            raise ValueError(f'Expected one {kind} file in {directory}.')
        path = matches[0]
        selected[kind] = path
    return selected


def validate_records(files, traffic=None):
    """Stream records through a temporary identity index, including 1M inputs."""
    with tempfile.TemporaryDirectory(prefix='synthetic-contract-') as temporary:
        database = sqlite3.connect(Path(temporary) / 'ids.sqlite3')
        try:
            database.executescript('CREATE TABLE products(id TEXT PRIMARY KEY);'
                                   'CREATE TABLE queries(id TEXT PRIMARY KEY, query TEXT NOT NULL);'
                                   'CREATE TABLE judgements(query_id TEXT, product_id TEXT,'
                                   ' PRIMARY KEY(query_id,product_id));')
            counts = {'catalogue': 0, 'query-suite': 0, 'judgement-set': 0}
            market_currency = {}
            for value in rows(files['catalogue']):
                if not all(isinstance(value.get(key), str) and value[key]
                           for key in ('product_id', 'title', 'country', 'currency')):
                    raise ValueError('Catalogue record lacks a stable ID, title or market.')
                if not isinstance(value.get('price_minor'), int) or value['price_minor'] < 0:
                    raise ValueError('Catalogue price must be a non-negative minor-unit integer.')
                previous = market_currency.setdefault(value['country'], value['currency'])
                if previous != value['currency']:
                    raise ValueError('A country has more than one currency.')
                try:
                    database.execute('INSERT INTO products VALUES (?)', (value['product_id'],))
                except sqlite3.IntegrityError:
                    raise ValueError('Duplicate product ID: ' + value['product_id']) from None
                counts['catalogue'] += 1
            database.commit()
            for value in rows(files['query-suite']):
                if not all(isinstance(value.get(key), str) and value[key]
                           for key in ('query_id', 'query', 'country', 'currency')):
                    raise ValueError('Query lacks a stable ID or original market request.')
                if 'filters' in value and not isinstance(value['filters'], dict):
                    raise ValueError('Query filters must be an object.')
                if market_currency.get(value['country']) != value['currency']:
                    raise ValueError('Query market is absent from its catalogue.')
                try:
                    database.execute('INSERT INTO queries VALUES (?,?)',
                                     (value['query_id'], value['query']))
                except sqlite3.IntegrityError:
                    raise ValueError('Duplicate query ID: ' + value['query_id']) from None
                counts['query-suite'] += 1
            database.commit()
            for value in rows(files['judgement-set']):
                query_id, product_id = value.get('query_id'), value.get('product_id')
                if not isinstance(query_id, str) or not isinstance(product_id, str):
                    raise ValueError('Judgement needs query and product IDs.')
                if type(value.get('grade')) is not int or value['grade'] not in range(4):
                    raise ValueError('Judgement grade must be 0, 1, 2 or 3.')
                if not database.execute('SELECT 1 FROM queries WHERE id=?', (query_id,)).fetchone():
                    raise ValueError('Judgement refers to an unknown query: ' + query_id)
                if not database.execute('SELECT 1 FROM products WHERE id=?', (product_id,)).fetchone():
                    raise ValueError('Judgement refers to an unknown product: ' + product_id)
                try:
                    database.execute('INSERT INTO judgements VALUES (?,?)', (query_id, product_id))
                except sqlite3.IntegrityError:
                    raise ValueError('Duplicate judgement: ' + query_id + '/' + product_id) from None
                counts['judgement-set'] += 1
            if traffic is not None:
                counts['traffic-trace'] = 0
                with Path(traffic).open(encoding='utf-8', newline='') as source:
                    for value in csv.DictReader(source):
                        query = database.execute('SELECT query FROM queries WHERE id=?',
                                                 (value.get('query_id'),)).fetchone()
                        if not query or query[0] != value.get('query') or not value.get('timestamp'):
                            raise ValueError('Traffic event differs from its query reference.')
                        counts['traffic-trace'] += 1
            return counts
        finally:
            database.close()


def envelope(kind, path, producer, dependencies=None, record_count=None, provenance=None):
    if kind not in KINDS or not producer or not isinstance(producer, str):
        raise ValueError('Unknown artifact kind or producer.')
    path = Path(path)
    digest = sha_file(path)
    manifest = {'kind': kind, 'schema_version': VERSION,
                'content': {'sha256': digest, 'bytes': path.stat().st_size,
                            'format': 'csv' if kind == 'traffic-trace' else 'jsonl',
                            'compression': 'gzip' if path.suffix == '.gz' else 'none',
                            'object': f'{kind}/{digest}/{path.name}'},
                'dependencies': dict(sorted((dependencies or {}).items())),
                'producer': {'name': producer, 'synthetic': True, **(provenance or {})}}
    if record_count is not None:
        manifest['record_count'] = record_count
    validate_envelope(manifest)
    return manifest


def validate_envelope(manifest):
    if manifest.get('kind') not in KINDS or manifest.get('schema_version') != VERSION:
        raise ValueError('Unsupported artifact kind or schema version.')
    content = manifest.get('content', {})
    digest = content.get('sha256', '')
    if len(digest) != 64 or any(char not in '0123456789abcdef' for char in digest):
        raise ValueError('Invalid artifact SHA-256.')
    if content.get('bytes', 0) <= 0 or not content.get('object', '').startswith(
            manifest['kind'] + '/' + digest + '/'):
        raise ValueError('Content address or size differs.')
    if manifest.get('producer', {}).get('synthetic') is not True:
        raise ValueError('This lab accepts synthetic input artifacts only.')
    if not manifest['producer'].get('name') or not manifest['producer'].get('source_release'):
        raise ValueError('Producer provenance is incomplete.')
    required = {'catalogue': set(), 'query-suite': set(),
                'judgement-set': {'catalogue', 'query-suite'},
                'traffic-trace': {'query-suite'}}[manifest['kind']]
    if set(manifest.get('dependencies', {})) != required:
        raise ValueError('Artifact dependencies are missing or unexpected.')
    for dependency in manifest['dependencies'].values():
        if len(dependency) != 64 or any(char not in '0123456789abcdef' for char in dependency):
            raise ValueError('Invalid dependency SHA-256.')
    return manifest
