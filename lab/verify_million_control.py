"""Walk the million-product lifecycle through the authenticated control API."""
import argparse
import http.cookiejar
import json
import sys
import time
import urllib.request

sys.path.insert(0, 'research/platform-spike')
from common import STATE, record

URL = 'http://localhost:18082'
STATE_FILE = STATE / 'million-control-state.json'
RELEASE = 'retail-gb-1m-v1'
DEFINITIONS = (('lab-million-baseline', 6, 'shared'),
               ('lab-million-api', 11, 'shared'),
               ('lab-million-index', 6, 'title-keyword-v1'))


def client():
    credentials = json.loads((STATE / 'credentials.json').read_text(encoding='utf-8'))['agent']
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(path, method='GET', body=None):
        headers = {'X-Lab-Intent': '1'}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(URL + path, method=method,
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with opener.open(request, timeout=7200) as response:
            return json.load(response)
    identity = call('/api/login', 'POST', {'username': credentials['username'],
                                          'password': credentials['password']})
    return call, identity


def save(evidence):
    STATE_FILE.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    record('million-control', evidence)


def create(call, identity):
    evidence = {'owner': identity['username'], 'release': RELEASE, 'environments': {},
                'comparisons': {}, 'execution': 'authenticated control HTTP API'}
    for name, build_run, kind in DEFINITIONS:
        started = time.monotonic()
        row = call('/api/environments', 'POST', {'name': name, 'build_run': build_run,
                                                'index_kind': kind, 'release_id': RELEASE})
        evidence['environments'][name] = {'id': row['id'], 'state': row['state'],
            'index': row['index_name'], 'dataset_sha256': row['dataset_sha256'],
            'mapping_sha256': row['mapping_sha256'], 'fingerprint': row['fingerprint'],
            'create_seconds': round(time.monotonic() - started, 3), 'error': row['error']}
        save(evidence)
        if row['state'] != 'ready':
            raise RuntimeError(name + ' did not become ready: ' + str(row['error']))
    print(json.dumps(evidence, indent=2))


def compare(call, evidence, target, mode, profile=None):
    names = {'api': 'lab-million-api', 'index': 'lab-million-index'}
    baseline = evidence['environments']['lab-million-baseline']['id']
    candidate = evidence['environments'][names[target]]['id']
    started = time.monotonic()
    request = {'baseline_id': baseline, 'candidate_id': candidate, 'mode': mode}
    if profile:
        request['profile'] = profile
    row = call('/api/comparisons', 'POST', request)
    key = target + '-' + mode + ('-' + profile if profile else '')
    if mode == 'performance':
        number = 1
        while key + '-' + str(number) in evidence['comparisons']:
            number += 1
        key += '-' + str(number)
    evidence['comparisons'][key] = {'state': row['state'],
        'verdict': row['verdict'], 'report_sha256': row['report_sha256'],
        'report_blob': row['report_blob'], 'summary': row['summary'],
        'seconds': round(time.monotonic() - started, 3), 'error': row['error']}
    save(evidence)
    summary = evidence['comparisons'][key]
    output = {'key': key, 'state': summary['state'], 'verdict': summary['verdict'],
              'seconds': summary['seconds'], 'report_sha256': summary['report_sha256']}
    if mode == 'performance':
        details = summary['summary'] or {}
        output.update({'profile': profile, 'baseline_run_id': details.get('baseline_run_id'),
                       'candidate_run_id': details.get('candidate_run_id'),
                       'valid': details.get('complete'),
                       'measured_phases': details.get('measured_phases')})
    else:
        output.update({'completed_query_count': summary['summary']['completed_query_count'],
                       'changed_query_count': len(summary['summary']['changed_query_ids']),
                       'error_count': len(summary['summary']['errors'])})
    print(json.dumps(output, indent=2))
    if row['state'] != 'complete':
        raise RuntimeError('Million-product comparison was incomplete.')


def delete(call, evidence):
    for name in reversed([row[0] for row in DEFINITIONS]):
        if name not in evidence['environments']:
            continue
        started = time.monotonic()
        row = call('/api/environments/' + evidence['environments'][name]['id'], 'DELETE', {})
        evidence['environments'][name]['final_state'] = row['state']
        evidence['environments'][name]['delete_seconds'] = round(time.monotonic() - started, 3)
        save(evidence)
    print(json.dumps(evidence['environments'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('create', 'compare', 'delete'))
    parser.add_argument('--target', choices=('api', 'index'))
    parser.add_argument('--mode', choices=('result-regression', 'relevance', 'performance'))
    parser.add_argument('--profile', choices=('probe', 'smoke', 'normal-full',
                                              'sustained-peak', 'stress-full'))
    args = parser.parse_args()
    call, identity = client()
    if args.action == 'create':
        create(call, identity)
    else:
        evidence = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if args.action == 'compare':
            if not args.target or not args.mode:
                parser.error('compare needs --target and --mode')
            if args.mode == 'performance' and not args.profile:
                parser.error('performance comparison needs --profile')
            compare(call, evidence, args.target, args.mode, args.profile)
        else:
            delete(call, evidence)
