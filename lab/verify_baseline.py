"""Check every frozen query through the deployed black-box API."""
import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path('.lab/releases/retail-gb-10k-v1')


def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.status, response.read(), response.headers.get('Content-Type', '')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:18080')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    status, body, content_type = fetch(base + '/')
    assert status == 200 and b'<html' in body.lower() and 'text/html' in content_type
    status, body, _ = fetch(base + '/health')
    assert status == 200 and json.loads(body)['ready'] is True
    queries = [json.loads(line) for line in (DATA / 'queries.jsonl').read_text().splitlines()]
    totals = []
    for row in queries:
        url = base + '/search?' + urllib.parse.urlencode({
            'q': row['query'], 'country': row['country'], 'currency': row['currency']})
        status, body, _ = fetch(url)
        result = json.loads(body)
        assert status == 200 and result['query'] == row['query']
        assert (result['country'], result['currency']) == ('GB', 'GBP')
        assert len(result['ids']) == len(result['results']) == len(set(result['ids']))
        assert all(item['available'] and item['currency'] == 'GBP' for item in result['results'])
        totals.append(result['total'])
    assert len(queries) == 50 and all(total > 0 for total in totals)
    bad = base + '/search?' + urllib.parse.urlencode({'q': 'shoes', 'country': 'US', 'currency': 'USD'})
    try:
        fetch(bad)
        raise AssertionError('Unsupported market was accepted')
    except urllib.error.HTTPError as error:
        assert error.code == 400
    print(json.dumps({'query_count': len(queries), 'zero_result_queries': 0,
        'min_total': min(totals), 'max_total': max(totals),
        'market_rejection': 400, 'ui_status': 200}, indent=2))


if __name__ == '__main__':
    main()
