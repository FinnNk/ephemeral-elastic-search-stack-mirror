"""Compare one frozen API workload with 40 idle and then 40 busy API neighbours."""
import hashlib
import json
import time

from common import STATE, apply, k, record
from run_gatling_job import run

RELEASE = 'retail-gb-1m-v1'
BASELINE = 'lab-concurrency-baseline'
CONTENDER = 'search-neighbour-load'
NAMES = ['lab-fleet-' + str(index).zfill(2) for index in range(1, 41)]
RATE = 25
SECONDS = 210
CODE = '''import json,os,time,urllib.parse,urllib.request
names=json.loads(os.environ["NAMES"])
queries=json.loads(os.environ["QUERIES"])
rate=int(os.environ["RATE"])
seconds=int(os.environ["SECONDS"])
started=time.monotonic()
ok=0
failed=0
for index in range(rate*seconds):
    delay=started+index/rate-time.monotonic()
    if delay>0: time.sleep(delay)
    url="http://search."+names[index%len(names)]+".svc.cluster.local:8080/search?q="+urllib.parse.quote(queries[index%len(queries)])
    try:
        with urllib.request.urlopen(url,timeout=3) as response:
            result=json.load(response)
            if response.status==200 and isinstance(result.get("ids"),list): ok+=1
            else: failed+=1
    except Exception: failed+=1
print(json.dumps({"planned":rate*seconds,"ok":ok,"failed":failed,"seconds":round(time.monotonic()-started,3),"rate":rate}))
'''


def phase(summary):
    row = summary['phases']['normal']
    return {'run_id': summary['run_id'], 'valid': summary['valid'],
            'normal_requests': row['requests'], 'failed': row['failed'],
            'p95_ms': row['p95_ms'], 'p99_ms': row['p99_ms'],
            'workload_sha256': summary['workload_sha256'],
            'native_report_sha256': summary['native_report_sha256']}


def main():
    queries = [json.loads(line)['query'] for line in
               (STATE / 'releases' / RELEASE / 'queries.jsonl').read_text(encoding='utf-8').splitlines()[:50]]
    evidence_path = STATE / 'evidence/concurrency-contention.json'
    evidence = (json.loads(evidence_path.read_text(encoding='utf-8')) if evidence_path.exists()
                else {'release': RELEASE, 'baseline_environment': BASELINE,
                      'neighbours': len(NAMES), 'contender_rate': RATE,
                      'contender_seconds': SECONDS,
                      'contender_queries_sha256': hashlib.sha256(json.dumps(queries).encode()).hexdigest()})
    if 'idle' in evidence:
        idle_path = STATE / 'evidence' / ('gatling-job-normal-baseline-' + evidence['idle']['run_id'] + '.json')
        idle = json.loads(idle_path.read_text(encoding='utf-8'))
        if phase(idle) != evidence['idle'] or idle['environment'] != BASELINE:
            raise ValueError('Saved idle evidence differs from the requested workload.')
    else:
        idle = run('normal', 'baseline', BASELINE, release_id=RELEASE)
        evidence['idle'] = phase(idle)
        record('concurrency-contention', evidence)
    job = {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': CONTENDER,
        'namespace': 'platform', 'labels': {'lab': 'search-contention'}},
        'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': SECONDS + 120,
            'template': {'metadata': {'labels': {'lab': 'search-contention'}},
                'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                    'containers': [{'name': 'load', 'image': 'python:3.13.7-alpine3.22',
                        'command': ['python', '-c', CODE],
                        'env': [{'name': 'NAMES', 'value': json.dumps(NAMES)},
                                {'name': 'QUERIES', 'value': json.dumps(queries)},
                                {'name': 'RATE', 'value': str(RATE)},
                                {'name': 'SECONDS', 'value': str(SECONDS)}],
                        'resources': {'requests': {'cpu': '100m', 'memory': '64Mi'},
                                      'limits': {'cpu': '1', 'memory': '256Mi'}}}]}}}}
    try:
        apply(job)
        deadline = time.monotonic() + 120
        pods = []
        while not pods and time.monotonic() < deadline:
            pods = json.loads(k('get', 'pods', '-l', 'lab=search-contention',
                                '-n', 'platform', '-o', 'json').stdout)['items']
            if not pods:
                time.sleep(1)
        if len(pods) != 1:
            raise TimeoutError('Expected one synthetic neighbour-load Pod.')
        k('wait', '--for=condition=Ready', 'pod/' + pods[0]['metadata']['name'],
          '-n', 'platform', '--timeout=120s')
        busy = run('normal', 'baseline', BASELINE, release_id=RELEASE)
        evidence['busy'] = phase(busy)
        k('wait', '--for=condition=complete', 'job/' + CONTENDER, '-n', 'platform',
          '--timeout=' + str(SECONDS + 120) + 's')
        logs = k('logs', 'job/' + CONTENDER, '-n', 'platform').stdout.strip()
        evidence['contender'] = json.loads(logs.splitlines()[-1])
        evidence['candidate_p95_change_percent'] = round(
            (evidence['busy']['p95_ms'] / evidence['idle']['p95_ms'] - 1) * 100, 3)
        record('concurrency-contention', evidence)
        print(json.dumps(evidence, indent=2))
        assert idle['workload_sha256'] == busy['workload_sha256']
        assert idle['fingerprint'] == busy['fingerprint']
        assert evidence['contender']['failed'] == 0
        assert evidence['contender']['ok'] == evidence['contender']['planned']
    finally:
        k('delete', 'job/' + CONTENDER, '-n', 'platform', '--ignore-not-found', '--wait=true', check=False)


if __name__ == '__main__':
    main()
