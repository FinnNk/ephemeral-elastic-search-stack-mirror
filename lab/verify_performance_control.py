"""Exercise a paired Gatling probe through the authenticated environment control API."""
import http.cookiejar
import json
import time
import urllib.request

from common import STATE, record

URL = 'http://localhost:18082'


def main():
    credentials = json.loads((STATE / 'credentials.json').read_text())['agent']
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(path, method='GET', body=None):
        headers = {'X-Lab-Intent': '1'}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(URL + path, method=method,
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with client.open(request, timeout=1200) as response:
            return json.load(response)
    identity = call('/api/login', 'POST', {'username': credentials['username'], 'password': credentials['password']})
    evidence = {'owner': identity['username'], 'route': 'authenticated control HTTP API',
                'mode': 'performance', 'profile': 'probe'}
    created = []
    try:
        for name, build_run in (('lab-perf-baseline', 6), ('lab-perf-candidate', 5)):
            row = call('/api/environments', 'POST', {'name': name, 'build_run': build_run})
            created.append(row)
            evidence[name] = {'state': row['state'], 'source_sha': row['source_sha'],
                              'fingerprint': row['fingerprint']}
            if row['state'] != 'ready':
                raise RuntimeError(name + ' did not become ready: ' + str(row.get('error')))
        started = time.monotonic()
        row = call('/api/comparisons', 'POST', {'baseline_id': created[0]['id'],
            'candidate_id': created[1]['id'], 'mode': 'performance', 'profile': 'probe'})
        evidence['comparison'] = {'state': row['state'], 'verdict': row['verdict'],
            'profile': row['profile'], 'report_sha256': row['report_sha256'],
            'report_blob': row['report_blob'], 'summary': row['summary'],
            'wall_seconds': round(time.monotonic() - started, 3)}
        if row['state'] != 'complete':
            raise RuntimeError('Performance comparison did not complete.')
    finally:
        for row in reversed(created):
            deleted = call('/api/environments/' + row['id'], 'DELETE', {})
            evidence[row['name']]['final_state'] = deleted['state']
        record('performance-control', evidence)
        print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
