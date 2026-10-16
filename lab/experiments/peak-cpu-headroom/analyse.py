"""Join diagnostic search traces with their Elasticsearch took measurements."""
import argparse
import json
from pathlib import Path
import re
import subprocess

import common


def query(sql, pod):
    result = subprocess.run(common.KUBE + ['exec', '-i', pod, '-n', 'lab-observability',
        '-c', 'clickhouse', '--', 'clickhouse-client', '--multiquery'],
        input=sql + ' FORMAT JSONEachRow', capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Trace query failed: ' + result.stderr[-1800:])
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def traces(run):
    namespace = run['namespace']
    if not re.fullmatch(r'lab-peak-cpu-[a-f0-9]{8}-(250m|1000m)', namespace):
        raise ValueError('Expected an owned diagnostic namespace.')
    start, end = (run['summary'][key] for key in ('started_at', 'ended_at'))
    # Validate the timestamps before embedding values read from the diagnostic receipt.
    from datetime import datetime
    datetime.fromisoformat(start); datetime.fromisoformat(end)
    return f"""SELECT trace_id,min(timestamp) AS trace_started_at,
        maxIf(duration_nano/1000000,name='search.request') AS request_ms,
        maxIf(duration_nano/1000000,name='search.elasticsearch') AS dependency_ms,
        maxIf(duration_nano/1000000,name='search.query_understanding') AS rewrite_ms,
        maxIf(attributes_number['elasticsearch.took_ms'],name='search.elasticsearch') AS took_ms,
        max(name='search.elasticsearch' AND mapContains(attributes_number,'elasticsearch.took_ms')) AS has_took
      FROM signoz_traces.signoz_index_v3
      WHERE timestamp>=parseDateTime64BestEffort('{start}') AND timestamp<=parseDateTime64BestEffort('{end}')
        AND resources_string['deployment.environment.name']='{namespace}'
      GROUP BY trace_id HAVING request_ms>0"""


def analyse(path, server, pod):
    common.KUBE += ['--server=' + server]
    experiment = json.loads(path.read_text(encoding='utf-8'))
    analysis = {'experiment': experiment['id'], 'arms': []}
    for run in experiment['runs']:
        source = traces(run)
        summary = query(f"""SELECT count() AS request_traces,countIf(has_took) AS timed_traces,
            quantileExact(.95)(request_ms) AS request_p95_ms,quantileExact(.99)(request_ms) AS request_p99_ms,
            quantileExact(.99)(dependency_ms) AS dependency_p99_ms,
            quantileExactIf(.95)(took_ms,has_took) AS took_p95_ms,
            quantileExactIf(.99)(took_ms,has_took) AS took_p99_ms,
            quantileExactIf(.99)(greatest(dependency_ms-took_ms,0),has_took) AS outside_took_p99_ms,
            quantileExact(.99)(rewrite_ms) AS rewrite_p99_ms,
            countIf(request_ms>800) AS requests_over800,
            countIf(took_ms>800 AND has_took) AS elasticsearch_execution_over800
            FROM ({source})""", pod)[0]
        minutes = query(f"""SELECT toStartOfMinute(trace_started_at) AS minute,count() AS requests,
            quantileExact(.99)(request_ms) AS request_p99_ms,
            quantileExactIf(.99)(took_ms,has_took) AS took_p99_ms,
            quantileExactIf(.99)(greatest(dependency_ms-took_ms,0),has_took) AS outside_took_p99_ms
            FROM ({source}) GROUP BY minute ORDER BY minute""", pod)
        examples = query(f"SELECT * FROM ({source}) ORDER BY request_ms DESC LIMIT 5", pod)
        analysis['arms'].append({'namespace': run['namespace'], 'quota': run['quota'],
                                  'summary': summary, 'minutes': minutes, 'slow_examples': examples})
    output = path.with_name('trace-analysis.json')
    output.write_text(json.dumps(analysis, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(analysis, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    parser.add_argument('--server', required=True)
    parser.add_argument('--clickhouse-pod', default='chi-signoz-clickhouse-cluster-0-0-0')
    args = parser.parse_args()
    analyse(args.result, args.server, args.clickhouse_pod)
