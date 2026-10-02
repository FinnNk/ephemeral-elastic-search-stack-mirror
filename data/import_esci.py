"""Import pinned English ESCI products and test labels, with ESCI-S metadata."""

import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import urllib.request

from contracts import canonical, sha_file

LOCK = Path(__file__).with_name('esci-sources.json')
GRADES = {'E': 3, 'S': 2, 'C': 1, 'I': 0}
DEFAULT_RELEASE = 'esci-gb-v1'
DEMO_RELEASE = 'esci-gb-demo-v1'


def sources(directory, download=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    lock = json.loads(LOCK.read_text(encoding='utf-8'))
    for entry in lock['files']:
        path = directory / entry['file']
        if not path.exists() and download:
            temporary = path.with_suffix(path.suffix + '.download')
            with urllib.request.urlopen(entry['url'], timeout=120) as remote, temporary.open('wb') as local:
                for block in iter(lambda: remote.read(1024 * 1024), b''):
                    local.write(block)
            if temporary.stat().st_size != entry['bytes'] or sha_file(temporary) != entry['sha256']:
                raise ValueError('Downloaded source checksum differs: ' + entry['file'])
            temporary.replace(path)
        if not path.is_file() or path.stat().st_size != entry['bytes'] or sha_file(path) != entry['sha256']:
            raise ValueError('Missing or altered pinned source: ' + str(path))
    return lock


def parquet_rows(path):
    import pyarrow.parquet as pq
    for batch in pq.ParquetFile(path).iter_batches(batch_size=4096):
        yield from batch.to_pylist()


def extended_rows(path):
    import zstandard
    with Path(path).open('rb') as source, zstandard.ZstdDecompressor().stream_reader(source) as stream:
        for line in io.TextIOWrapper(stream, encoding='utf-8'):
            row = json.loads(line)
            if row.get('type') == 'product' and row.get('locale') == 'us':
                yield row


def price_minor(value):
    """Use the lower displayed USD amount; the lab relabels it as GBP."""
    if not isinstance(value, str):
        return None
    match = re.search(r'\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)(?![0-9.])', value)
    if not match:
        return None
    amount = Decimal(match[1].replace(',', '')) * 100
    return int(amount) if amount == amount.to_integral_value() and amount <= 2_147_483_647 else None


def number(value, integer=False):
    match = re.search(r'[0-9][0-9,]*(?:\.[0-9]+)?', str(value or ''))
    return (int(float(match[0].replace(',', ''))) if integer else float(match[0].replace(',', ''))) if match else None


def product(original, extended, counts):
    """Preserve canonical ESCI text; add metadata without using relevance labels."""
    extended = extended or {}
    asin = original['product_id']
    attrs, info = extended.get('attrs') or {}, extended.get('info') or {}
    if not isinstance(attrs, dict) or not isinstance(info, dict):
        raise ValueError('Extended attributes must be objects: ' + asin)
    price = price_minor(extended.get('price'))
    price_source = 'esci-s'
    if price is None:
        price = 199 + int(hashlib.sha256(('lab-price-v1:' + asin).encode()).hexdigest()[:8], 16) % 49801
        price_source = 'synthetic'
    counts['price_' + price_source] += 1
    categories = extended.get('category') or []
    if not isinstance(categories, list) or any(not isinstance(x, str) for x in categories):
        raise ValueError('Extended category must be a string array: ' + asin)
    title = original.get('product_title') or extended.get('title')
    if not title:
        raise ValueError('Source product has no title: ' + asin)
    counts['title_esci' if original.get('product_title') else 'title_esci-s'] += 1
    result = {'product_id': asin, 'sku': asin, 'title': title,
              'description': original.get('product_description'),
              'bullets': original.get('product_bullet_point'),
              'brand': original.get('product_brand') or '',
              'colour': original.get('product_color') or attrs.get('Color') or info.get('Color') or info.get('Colour') or '',
              'material': attrs.get('Material') or info.get('Material') or '',
              'category': categories[0] if categories else 'Uncategorised',
              'category_path': categories, 'product_type': extended.get('template') or '',
              'country': 'GB', 'currency': 'GBP', 'price_minor': price,
              'available': True, 'popularity': 0.0,
              'rating': number(extended.get('stars')), 'review_count': number(extended.get('ratings'), True),
              'attrs': {'source_locale': 'us', 'source_attributes': attrs,
                        'price_source': price_source, 'price_policy': 'numeric-USD-as-GBP',
                        'stock_source': 'synthetic', 'popularity_source': 'synthetic'}}
    return result


def import_records(originals, examples, extended, output, release, query_count, product_limit, provenance):
    """Stream source records through a bounded SQLite staging database."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Import output must be empty; frozen releases cannot be overwritten.')
    if query_count < 1 or (product_limit is not None and product_limit < 1):
        raise ValueError('Query count and product limit must be positive.')
    with tempfile.TemporaryDirectory(prefix='esci-import-', dir=output.parent) as temporary:
        db = sqlite3.connect(Path(temporary) / 'stage.sqlite3')
        try:
            db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                'CREATE TABLE products(id TEXT PRIMARY KEY, original TEXT NOT NULL, extra TEXT);'
                'CREATE TABLE queries(id TEXT PRIMARY KEY, text TEXT NOT NULL, selection TEXT NOT NULL);'
                'CREATE TABLE labels(query_id TEXT, product_id TEXT, label TEXT, PRIMARY KEY(query_id,product_id));')
            print('Reading English ESCI products', flush=True)
            for row in originals:
                if row['product_locale'] == 'us':
                    db.execute('INSERT INTO products VALUES (?,?,NULL)', (row['product_id'], json.dumps(row)))
            db.commit()
            print('Selecting ESCI test queries', flush=True)
            for row in examples:
                if row['product_locale'] != 'us' or not row['large_version'] or row['split'] != 'test':
                    continue
                query_id = str(row['query_id'])
                text = ' '.join(row['query'].split())
                if not text:
                    raise ValueError('Empty source query: ' + query_id)
                prior = db.execute('SELECT text FROM queries WHERE id=?', (query_id,)).fetchone()
                if prior and prior[0] != text:
                    raise ValueError('Source query ID has different text: ' + query_id)
                db.execute('INSERT OR IGNORE INTO queries VALUES (?,?,?)',
                           (query_id, text, hashlib.sha256(('esci-test-v1:' + query_id).encode()).hexdigest()))
                label = row['esci_label']
                if label not in GRADES:
                    raise ValueError('Unknown ESCI label: ' + str(label))
                db.execute('INSERT INTO labels VALUES (?,?,?)', (query_id, row['product_id'], label))
            db.commit()
            db.execute('CREATE TABLE selected_queries AS SELECT * FROM queries ORDER BY selection,id LIMIT ?', (query_count,))
            if db.execute('SELECT count(*) FROM selected_queries').fetchone()[0] != query_count:
                raise ValueError('Not enough source test queries for the requested suite.')
            db.execute('DELETE FROM labels WHERE query_id NOT IN (SELECT id FROM selected_queries)')
            if db.execute('SELECT 1 FROM labels WHERE product_id NOT IN (SELECT id FROM products) LIMIT 1').fetchone():
                raise ValueError('Source label refers to an absent English product.')
            if product_limit is not None:
                required = db.execute('SELECT count(DISTINCT product_id) FROM labels').fetchone()[0]
                if required > product_limit:
                    raise ValueError(f'Demo limit {product_limit} cannot hold {required} judged products; reduce queries or increase products.')
                db.execute('CREATE TABLE selected_products(id TEXT PRIMARY KEY)')
                db.execute('INSERT INTO selected_products SELECT DISTINCT product_id FROM labels')
                db.execute('INSERT INTO selected_products SELECT id FROM products WHERE id NOT IN '
                           '(SELECT id FROM selected_products) ORDER BY id LIMIT ?', (product_limit-required,))
                db.execute('DELETE FROM products WHERE id NOT IN (SELECT id FROM selected_products)')
            db.commit()
            print('Joining ESCI-S metadata', flush=True)
            matched = 0
            for row in extended:
                asin = row.get('asin')
                # Metadata only: do not retain reviews, images or duplicated long text.
                metadata = {key: row.get(key) for key in ('title', 'price', 'stars', 'ratings', 'attrs', 'info', 'category', 'template')}
                changed = db.execute('UPDATE products SET extra=? WHERE id=? AND extra IS NULL',
                                     (json.dumps(metadata), asin)).rowcount
                matched += changed
                if matched and matched % 100000 == 0 and changed:
                    db.commit()
                    print(f'Metadata matched: {matched:,}', flush=True)
            db.commit()
            counts = Counter()
            with (output / 'products.jsonl.gz').open('xb') as raw:
                with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6) as zipped:
                    for original, extra in db.execute('SELECT original,extra FROM products ORDER BY id'):
                        zipped.write(canonical(product(json.loads(original), json.loads(extra) if extra else None, counts)))
            with (output / 'queries.jsonl').open('xb') as target:
                for query_id, text in db.execute('SELECT id,text FROM selected_queries ORDER BY id'):
                    target.write(canonical({'query_id': query_id, 'query': text, 'country': 'GB', 'currency': 'GBP', 'split': 'test'}))
            with (output / 'judgements.jsonl').open('xb') as target:
                for query_id, asin, label in db.execute('SELECT query_id,product_id,label FROM labels ORDER BY query_id,product_id'):
                    target.write(canonical({'query_id': query_id, 'product_id': asin, 'assessment': label, 'grade': GRADES[label]}))
            files = ('products.jsonl.gz', 'queries.jsonl', 'judgements.jsonl')
            manifest = {'release': release, 'count': db.execute('SELECT count(*) FROM products').fetchone()[0],
                        'query_count': query_count, 'judgement_count': db.execute('SELECT count(*) FROM labels').fetchone()[0],
                        'country': 'GB', 'currency': 'GBP', 'locale': 'en-US', 'compression': 'gzip',
                        'selection': {'query_count': query_count, 'product_limit': product_limit, 'split': 'test', 'algorithm': 'esci-test-v1'},
                        'producer': {'synthetic': False, 'sources': provenance,
                                     'augmentation': {'price_policy': 'numeric-USD-as-GBP', 'missing_price': 'ASIN-hash-v1:GBP1.99-499.99',
                                                      'available': True, 'popularity': 0.0, 'counts': dict(counts)}},
                        'metadata_matched': matched,
                        'importer_sha256': sha_file(__file__),
                        'sha256': {name: sha_file(output / name) for name in files},
                        'bytes': {name: (output / name).stat().st_size for name in files}}
            (output / 'manifest.json').write_bytes(canonical(manifest))
            return manifest
        finally:
            db.close()


def build(source, output, release=DEFAULT_RELEASE, query_count=1000, product_limit=None, download=False):
    lock = sources(source, download)
    output = Path(output)
    manifest_path = output / 'manifest.json'
    if manifest_path.exists():
        frozen = json.loads(manifest_path.read_text(encoding='utf-8'))
        expected_selection = {'query_count': query_count, 'product_limit': product_limit, 'split': 'test', 'algorithm': 'esci-test-v1'}
        if frozen['release'] != release or frozen['selection'] != expected_selection or frozen['producer']['sources'] != lock or frozen['importer_sha256'] != sha_file(__file__):
            raise ValueError('Existing frozen release has different source or importer inputs.')
        if any(sha_file(output / name) != digest for name, digest in frozen['sha256'].items()):
            raise ValueError('Existing frozen release bytes differ.')
        return frozen
    source = Path(source)
    return import_records(parquet_rows(source / 'products.parquet'), parquet_rows(source / 'examples.parquet'),
                          extended_rows(source / 'esci-s.json.zst'), output, release, query_count, product_limit, lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--release', default=DEFAULT_RELEASE)
    parser.add_argument('--queries', type=int, default=1000)
    parser.add_argument('--products', type=int, help='Optional demo limit; includes every selected judgement product')
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.release, args.queries, args.products, args.download), indent=2))


if __name__ == '__main__':
    main()
