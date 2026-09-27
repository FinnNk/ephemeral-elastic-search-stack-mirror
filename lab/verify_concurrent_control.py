"""Exercise unrelated control requests while one real Gatling comparison runs."""
import json
import sys
import threading
import time
import urllib.error
import urllib.parse

sys.path.insert(0, 'research/platform-spike')
from common import STATE, record
from lifecycle import Store
from verify_million_control import client

RELEASE = 'retail-gb-1m-v1'


def main():
    state = json.loads((STATE / 'concurrency-state.json').read_text(encoding='utf-8'))
    baseline = state['three']['lab-concurrency-baseline']['id']
    candidate = state['three']['lab-concurrency-api']['id']
    result = {}
    started = threading.Event()

    def compare():
        call, _ = client()
        started.set()
        try:
            result['comparison'] = call('/api/comparisons', 'POST', {
                'baseline_id': baseline, 'candidate_id': candidate,
                'mode': 'performance', 'profile': 'probe'})
        except Exception as error:
            result['error'] = type(error).__name__ + ': ' + str(error)

    worker = threading.Thread(target=compare)
    worker.start()
    assert started.wait(10)
    store = Store(STATE / 'lifecycle.sqlite3')
    deadline = time.monotonic() + 30
    while not store.running_comparison_for(baseline) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert store.running_comparison_for(baseline), 'Comparison did not enter running state.'
    call, _ = client()
    observations = {'release': RELEASE, 'comparison_running': True}
    for name, operation in (
        ('activity', lambda: call('/api/environments/' + baseline + '/activity', 'POST', {})),
        ('search', lambda: call('/api/environments/' + baseline + '/search?q=' +
                                  urllib.parse.quote('running shoes'))),
        ('create', lambda: call('/api/environments', 'POST', {
            'name': 'lab-concurrency-independent', 'build_run': 6,
            'index_kind': 'shared', 'release_id': RELEASE})),
    ):
        start = time.monotonic()
        response = operation()
        observations[name + '_seconds'] = round(time.monotonic() - start, 3)
        if name == 'create':
            observations['independent_id'] = response['id']
            observations['independent_state'] = response['state']
        if name == 'search':
            observations['search_result_count'] = len(response['ids'])
    try:
        call('/api/environments/' + candidate, 'DELETE', {})
        observations['active_candidate_delete_status'] = 200
    except urllib.error.HTTPError as error:
        observations['active_candidate_delete_status'] = error.code
    worker.join(240)
    observations['comparison_finished'] = not worker.is_alive()
    if 'comparison' in result:
        observations['comparison_state'] = result['comparison']['state']
        observations['comparison_report_sha256'] = result['comparison']['report_sha256']
    if 'error' in result:
        observations['comparison_error'] = result['error']
    state['concurrent_control'] = observations
    (STATE / 'concurrency-state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    record('concurrency-control', observations)
    print(json.dumps(observations, indent=2))
    assert observations['comparison_finished'] and observations['comparison_state'] == 'complete'
    assert observations['independent_state'] == 'ready' and observations['search_result_count'] >= 10
    assert observations['active_candidate_delete_status'] == 409
    assert observations['create_seconds'] < 30


if __name__ == '__main__':
    main()
