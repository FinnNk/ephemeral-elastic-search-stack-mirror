"""Run three paired million-release smoke checks with alternating order."""
import hashlib
import json
import time

from common import STATE, record
from aggregate_smoke import aggregate
from compare_search import immutable_blob
from run_gatling_job import run

RELEASE = 'retail-gb-1m-v1'
ENVIRONMENTS = {'baseline': 'lab-million-baseline', 'candidate': 'lab-million-index'}
ORDERS = (('baseline', 'candidate'), ('candidate', 'baseline'),
          ('baseline', 'candidate'))
STATE_FILE = STATE / 'million-smoke-state.json'


def save(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')
    record('million-smoke-state', state)


def main():
    state = (json.loads(STATE_FILE.read_text(encoding='utf-8')) if STATE_FILE.exists()
             else {'release': RELEASE, 'profile': 'smoke',
                   'orders': [list(x) for x in ORDERS], 'cooldown_seconds': 30,
                   'pairs': [{}, {}, {}]})
    if state['release'] != RELEASE or state['profile'] != 'smoke' or state['orders'] != [list(x) for x in ORDERS]:
        raise ValueError('Existing smoke run state has different inputs.')
    for index, order in enumerate(ORDERS):
        pair = state['pairs'][index]
        if index > 0 and not pair:
            time.sleep(state['cooldown_seconds'])
        for side in order:
            if side in pair:
                continue
            summary = run('smoke', side, ENVIRONMENTS[side], release_id=RELEASE)
            pair[side] = summary['run_id']
            save(state)
    pairs = [(row['baseline'], row['candidate']) for row in state['pairs']]
    report = aggregate(pairs, execution='job')
    payload = (json.dumps(report, sort_keys=True, indent=2) + '\n').encode()
    digest = hashlib.sha256(payload).hexdigest()
    report['report_sha256'] = digest
    report['report_blob'] = immutable_blob('runs', digest + '/million-three-pair-smoke.json', payload)
    record('million-three-pair-smoke', report)
    print(json.dumps({'orders': ORDERS, 'pairs': pairs, 'valid': report['valid'],
                      'verdict': report['verdict'], 'baseline_p95_spread_percent':
                      report['baseline_p95_spread_percent'],
                      'median_candidate_p95_increase_percent':
                      report['median_candidate_p95_increase_percent'],
                      'report_sha256': digest}, indent=2))


if __name__ == '__main__':
    main()
