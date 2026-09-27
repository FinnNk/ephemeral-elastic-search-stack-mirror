"""Exercise dedicated-index create, compare and delete through the local control API."""
import http.cookiejar
import json
import time
import urllib.request

from common import STATE, record
from lifecycle import INDEX_KIND

URL = 'http://localhost:18082'


def main():
    credentials = json.loads((STATE / 'credentials.json').read_text())['agent']
    run = json.loads((STATE / 'evidence/retail-deployment.json').read_text())['build_run']
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(path, method='GET', body=None):
        headers = {'X-Lab-Intent': '1'}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(URL + path, method=method,
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with client.open(request, timeout=400) as response:
            return json.load(response)
    identity = call('/api/login', 'POST', {'username': credentials['username'], 'password': credentials['password']})
    evidence = {'owner': identity['username'], 'route': 'authenticated control HTTP API', 'build_run': run}
    created = []
    try:
        for name, kind in (('lab-http-baseline', 'shared'), ('lab-http-index', INDEX_KIND)):
            started = time.monotonic()
            row = call('/api/environments', 'POST', {'name': name, 'build_run': run, 'index_kind': kind})
            created.append(row)
            evidence[name] = {'state': row['state'], 'index': row['index_name'],
                              'mapping_sha256': row['mapping_sha256'],
                              'create_seconds': round(time.monotonic() - started, 3)}
            if row['state'] != 'ready':
                raise RuntimeError(name + ' did not become ready: ' + str(row.get('error')))
        result = call('/api/comparisons', 'POST', {'baseline_id': created[0]['id'],
            'candidate_id': created[1]['id'], 'mode': 'result-regression'})
        evidence['comparison'] = {'state': result['state'], 'verdict': result['verdict'],
                                  'report_sha256': result['report_sha256'],
                                  'report_blob': result['report_blob'],
                                  'changed_queries': len(result['summary']['changed_query_ids'])}
        if result['state'] != 'complete':
            raise RuntimeError('Control API comparison was incomplete.')
    finally:
        for row in reversed(created):
            started = time.monotonic()
            deleted = call('/api/environments/' + row['id'], 'DELETE', {})
            evidence[row['name']]['final_state'] = deleted['state']
            evidence[row['name']]['delete_seconds'] = round(time.monotonic() - started, 3)
        record('index-http', evidence)
        print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
