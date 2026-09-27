"""Run a frozen functional suite in one scoped, finite Kubernetes Job."""
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

from common import ROOT, apply, guard, k

NAMESPACE = 'lab-evaluation'
IMAGE = ('python:3.13.7-alpine3.22@sha256:'
         '9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844')
NAME = re.compile(r'lab-[a-z0-9-]{1,48}\Z')
SOURCE = ROOT / 'lab/evaluation_worker.py'


def run(suite_bytes, baseline, candidate):
    guard()
    if not NAME.fullmatch(baseline) or not NAME.fullmatch(candidate):
        raise ValueError('Evaluator target name is invalid.')
    if len(suite_bytes) > 700_000:
        raise ValueError('Frozen suite exceeds the evaluator ConfigMap budget.')
    short = uuid.uuid4().hex[:8]
    job_name = 'evaluate-' + short
    config = job_name + '-input'
    apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE}})
    source = SOURCE.read_text(encoding='utf-8')
    payload = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': config, 'namespace': NAMESPACE},
               'data': {'worker.py': source, 'queries.jsonl': suite_bytes.decode('utf-8')}}
    job = {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': job_name, 'namespace': NAMESPACE},
           'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300,
                    'template': {'metadata': {'labels': {'lab': 'evaluator'}},
                                 'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                                          'containers': [{'name': 'evaluator', 'image': IMAGE,
                                              'command': ['python', '/input/worker.py'],
                                              'env': [{'name': 'BASELINE', 'value': baseline},
                                                      {'name': 'CANDIDATE', 'value': candidate}],
                                              'resources': {'requests': {'cpu': '100m', 'memory': '64Mi'},
                                                            'limits': {'cpu': '1', 'memory': '256Mi'}},
                                              'volumeMounts': [{'name': 'input', 'mountPath': '/input', 'readOnly': True}]}],
                                          'volumes': [{'name': 'input', 'configMap': {'name': config}}]}}}}
    started = time.monotonic()
    try:
        k('create', '-f', '-', body=payload)
        apply(job)
        k('wait', '--for=condition=complete', 'job/' + job_name, '-n', NAMESPACE, '--timeout=300s')
        rows = json.loads(k('logs', 'job/' + job_name, '-n', NAMESPACE).stdout)
        expected = [json.loads(line)['query_id'] for line in suite_bytes.splitlines()]
        if not isinstance(rows, list) or [row['query_id'] for row in rows] != expected:
            raise ValueError('Evaluator output does not match the frozen query order.')
        return rows, {'execution': 'in-cluster evaluator Job', 'seconds': round(time.monotonic() - started, 3),
                      'worker_sha256': hashlib.sha256(source.encode()).hexdigest(), 'worker_image': IMAGE,
                      'worker_count': 8, 'job_name': job_name}
    finally:
        k('delete', 'job/' + job_name, '-n', NAMESPACE, '--ignore-not-found', '--wait=true', check=False)
        k('delete', 'configmap/' + config, '-n', NAMESPACE, '--ignore-not-found', check=False)
