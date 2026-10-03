"""Exercise stored, inferred and rejected pairs against the deployed service."""

import json
from pathlib import Path
from urllib import error, request

from core import canonical
from service import read_rows


def post(context, pairs):
    call = request.Request('http://127.0.0.1:18086/v1/judgements:resolve',
                           canonical({'context': context, 'pairs': pairs}),
                           {'Content-Type': 'application/json'})
    with request.urlopen(call, timeout=15) as response:
        return json.loads(response.read())


def main():
    root = Path('/inputs')
    context = json.loads((root / 'context.json').read_bytes())
    queries = list(read_rows(root / 'queries.jsonl'))
    stored = list(read_rows(root / 'judgements.jsonl'))
    by_query = {row['query_id']: row for row in queries}
    first = stored[0]
    query = by_query[first['query_id']]
    known = {(row['query_id'], row['product_id']) for row in stored}
    product = None
    missing = None
    for value in read_rows(root / 'products.content'):
        if value['product_id'] == first['product_id']:
            product = value
        if missing is None and value['country'] == query['country'] and \
                value['currency'] == query['currency'] and \
                (query['query_id'], value['product_id']) not in known:
            missing = value
        if product is not None and missing is not None:
            break
    if product is None or missing is None:
        raise AssertionError('Frozen source has no stored and missing pair.')
    pair = {'query_id': first['query_id'], 'product_id': first['product_id'],
            'request': {key: query[key] for key in ('query', 'country', 'currency')},
            'product': product}
    pair['request']['filters'] = query.get('filters', {})
    labelled = post(context, [pair])['results'][0]
    assert labelled['outcome'] == 'labelled' and labelled['source'] == 'published' and labelled['gate_eligible'] is True
    gap = {**pair, 'product_id': missing['product_id'], 'product': missing}
    unknown = post(context, [gap])['results'][0]
    assert unknown['outcome'] == 'unjudged' and unknown['reason'] == 'model_abstained'
    try:
        post(context, [{**gap, 'product': {**missing, 'title': 'forged'}}])
    except error.HTTPError as failure:
        assert failure.code == 400
    else:
        raise AssertionError('Forged product was accepted.')
    print(json.dumps({'stored': labelled['label'], 'gap': unknown['outcome'],
                      'forged_record': 'rejected'}, sort_keys=True))


if __name__ == '__main__':
    main()
