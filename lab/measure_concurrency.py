"""Measure live control-API environments sharing one frozen million-product release."""
import argparse
import math
import json
import time
import urllib.parse

from common import STATE, record
from lifecycle import parse_stamp
from verify_million_control import client

RELEASE = 'retail-gb-1m-v1'
STATE_FILE = STATE / 'concurrency-state.json'
THREE = (('lab-concurrency-baseline', 6, 'shared'),
         ('lab-concurrency-api', 11, 'shared'),
         ('lab-concurrency-index', 6, 'title-keyword-v1'))
FLEET = ['lab-fleet-' + str(index).zfill(2) for index in range(1, 41)]


def save(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')
    record('concurrency-state', state)


def create_three(call, owner):
    state = {'release': RELEASE, 'owner': owner, 'three': {}}
    for name, build_run, kind in THREE:
        started = time.monotonic()
        row = call('/api/environments', 'POST', {'name': name, 'build_run': build_run,
                   'index_kind': kind, 'release_id': RELEASE})
        state['three'][name] = {'id': row['id'], 'state': row['state'],
            'index_name': row['index_name'], 'fingerprint': row['fingerprint'],
            'create_seconds': round(time.monotonic() - started, 3), 'error': row['error']}
        save(state)
        if row['state'] != 'ready':
            raise RuntimeError(name + ' failed: ' + str(row['error']))
    print(json.dumps(state, indent=2))


def check_three(call, state):
    results = {}
    for name, evidence in state['three'].items():
        started = time.monotonic()
        answer = call('/api/environments/' + evidence['id'] + '/search?q=' +
                      urllib.parse.quote('running shoes'))
        results[name] = {'count': len(answer['ids']), 'first_id': answer['ids'][0],
                         'search_seconds': round(time.monotonic() - started, 3)}
        if len(answer['ids']) < 10:
            raise RuntimeError(name + ' returned too few products')
    state['three_searches'] = results
    save(state)
    print(json.dumps(results, indent=2))


def delete_three(call, state):
    for name, _, _ in reversed(THREE):
        evidence = state['three'][name]
        started = time.monotonic()
        row = call('/api/environments/' + evidence['id'], 'DELETE', {})
        evidence['final_state'] = row['state']
        evidence['delete_seconds'] = round(time.monotonic() - started, 3)
        save(state)
    print(json.dumps(state['three'], indent=2))


def delete_index(call, state):
    name = 'lab-concurrency-index'
    evidence = state['three'][name]
    started = time.monotonic()
    row = call('/api/environments/' + evidence['id'], 'DELETE', {})
    evidence['final_state'] = row['state']
    evidence['delete_seconds'] = round(time.monotonic() - started, 3)
    save(state)
    print(json.dumps(evidence, indent=2))


def check_survivors(call, state):
    results = {}
    for name in ('lab-concurrency-baseline', 'lab-concurrency-api'):
        answer = call('/api/environments/' + state['three'][name]['id'] + '/search?q=' +
                      urllib.parse.quote('running shoes'))
        results[name] = {'count': len(answer['ids']), 'first_id': answer['ids'][0]}
        assert len(answer['ids']) >= 10
    state['survivor_searches'] = results
    save(state)
    print(json.dumps(results, indent=2))


def create_forty(call, state):
    if 'forty' in state:
        state.setdefault('forty_attempts', []).append(state['forty'])
    started = time.monotonic()
    rows = call('/api/environments/batch', 'POST', {
        'names': FLEET, 'build_run': 6, 'release_id': RELEASE})
    wall = round(time.monotonic() - started, 3)
    rows_by_name = {row['name']: row for row in rows}
    samples = sorted((parse_stamp(row['updated_at']) - parse_stamp(row['created_at'])).total_seconds()
                     for row in rows if row['state'] == 'ready')
    state['forty'] = {'request_wall_seconds': wall, 'requested': len(FLEET),
        'ready': len(samples), 'failed': [name for name, row in rows_by_name.items()
                                        if row['state'] != 'ready'],
        'ready_p95_seconds': round(samples[math.ceil(0.95 * len(samples)) - 1], 3) if samples else None,
        'environments': {name: {'id': row['id'], 'state': row['state'],
                         'fingerprint': row['fingerprint'], 'index_name': row['index_name'],
                         'ready_seconds': round((parse_stamp(row['updated_at']) -
                                                 parse_stamp(row['created_at'])).total_seconds(), 3),
                         'error': row['error']} for name, row in rows_by_name.items()}}
    save(state)
    print(json.dumps({key: value for key, value in state['forty'].items()
                      if key != 'environments'}, indent=2))
    if len(samples) != len(FLEET):
        raise RuntimeError('Not all 40 environments became ready.')


def check_forty(call, state):
    results = {}
    for name in FLEET:
        evidence = state['forty']['environments'][name]
        started = time.monotonic()
        try:
            answer = call('/api/environments/' + evidence['id'] + '/search?q=' +
                          urllib.parse.quote('running shoes'))
            results[name] = {'count': len(answer['ids']), 'first_id': answer['ids'][0],
                             'seconds': round(time.monotonic() - started, 3)}
        except Exception as error:
            results[name] = {'error': type(error).__name__ + ': ' + str(error)}
        state['forty']['searches'] = results
        save(state)
    print(json.dumps({'searched': len(results), 'passed': sum(row.get('count', 0) >= 10
        for row in results.values()), 'errors': {name: row['error'] for name, row in results.items()
        if 'error' in row}}, indent=2))
    if not all(row.get('count', 0) >= 10 for row in results.values()):
        raise RuntimeError('One or more fleet searches failed.')


def delete_forty(call, state):
    rows = state['forty']['environments']
    started = time.monotonic()
    deleted = call('/api/environments/batch', 'DELETE', {'ids': [rows[name]['id'] for name in FLEET]})
    timing_key = 'retry_delete_seconds' if 'delete_seconds' in state['forty'] else 'delete_seconds'
    state['forty'][timing_key] = round(time.monotonic() - started, 3)
    state['forty']['deleted'] = sum(row['state'] == 'deleted' for row in deleted)
    save(state)
    print(json.dumps({'deleted': state['forty']['deleted'],
                      timing_key: state['forty'][timing_key]}, indent=2))
    if state['forty']['deleted'] != len(FLEET):
        raise RuntimeError('Not all 40 fleet environments were deleted.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('create-three', 'check-three', 'delete-index',
                                            'check-survivors', 'delete-three', 'create-forty',
                                            'check-forty', 'delete-forty'))
    args = parser.parse_args()
    call, identity = client()
    if args.action == 'create-three':
        create_three(call, identity['username'])
    else:
        state = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if args.action == 'check-three':
            check_three(call, state)
        elif args.action == 'delete-index':
            delete_index(call, state)
        elif args.action == 'check-survivors':
            check_survivors(call, state)
        elif args.action == 'create-forty':
            create_forty(call, state)
        elif args.action == 'check-forty':
            check_forty(call, state)
        elif args.action == 'delete-forty':
            delete_forty(call, state)
        else:
            delete_three(call, state)
