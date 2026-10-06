"""Run a frozen functional suite in one scoped, finite Kubernetes Job."""
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

from common import ROOT, apply, guard, k
from operation_telemetry import correlation

NAMESPACE = 'lab-evaluation'
IMAGE = ('python:3.13.7-alpine3.22@sha256:'
         '9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844')
NAME = re.compile(r'lab-[a-z0-9-]{1,48}\Z')
SOURCE = ROOT / 'lab/evaluation_worker.py'
VARIANT_SOURCE = ROOT / 'lab/variant_capture_worker.py'
FILTER_SOURCE = ROOT / 'lab/search-app/search_filters.py'
PACING_SOURCE = ROOT / 'lab/adaptive_pacing.py'


def run(suite_bytes, baseline, candidate):
    guard()
    if not NAME.fullmatch(baseline) or not NAME.fullmatch(candidate):
        raise ValueError('Evaluator target name is invalid.')
    if len(suite_bytes) > 700_000:
        raise ValueError('Frozen suite exceeds the evaluator ConfigMap budget.')
    short = uuid.uuid4().hex[:8]
    job_name = 'evaluate-' + short
    trace_ids = correlation()
    config = job_name + '-input'
    apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE}})
    source = SOURCE.read_text(encoding='utf-8')
    payload = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': config, 'namespace': NAMESPACE},
               'data': {'worker.py': source, 'adaptive_pacing.py': PACING_SOURCE.read_text(encoding='utf-8'),
                        'search_filters.py': FILTER_SOURCE.read_text(encoding='utf-8'),
                        'queries.jsonl': suite_bytes.decode('utf-8')}}
    job = {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': job_name, 'namespace': NAMESPACE},
           'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300,
                    'template': {'metadata': {'labels': {'lab': 'evaluator'}},
                                 'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                                          'containers': [{'name': 'evaluator', 'image': IMAGE,
                                              'command': ['python', '/input/worker.py'],
                                              'env': [{'name': 'BASELINE', 'value': baseline},
                                                      {'name': 'CANDIDATE', 'value': candidate},
                                                      {'name': 'LAB_JOB_NAME', 'value': job_name},
                                                      *[{'name': 'LAB_' + key.upper(), 'value': value}
                                                        for key, value in trace_ids.items()]],
                                              'resources': {'requests': {'cpu': '100m', 'memory': '64Mi'},
                                                            'limits': {'cpu': '1', 'memory': '256Mi'}},
                                              'volumeMounts': [{'name': 'input', 'mountPath': '/input', 'readOnly': True}]}],
                                          'volumes': [{'name': 'input', 'configMap': {'name': config}}]}}}}
    started = time.monotonic()
    try:
        k('create', '-f', '-', body=payload)
        apply(job)
        k('wait', '--for=condition=complete', 'job/' + job_name, '-n', NAMESPACE, '--timeout=300s')
        # The first line is a bounded completion event for the log agent;
        # the second remains the order-stable result protocol.
        lines = k('logs', 'job/' + job_name, '-n', NAMESPACE).stdout.splitlines()
        rows = json.loads(lines[-1])
        expected = [json.loads(line)['query_id'] for line in suite_bytes.splitlines()]
        if not isinstance(rows, list) or [row['query_id'] for row in rows] != expected:
            raise ValueError('Evaluator output does not match the frozen query order.')
        return rows, {'execution': 'in-cluster evaluator Job', 'seconds': round(time.monotonic() - started, 3),
                      'worker_sha256': hashlib.sha256(source.encode()).hexdigest(),
                      'adaptive_pacing_sha256': hashlib.sha256(PACING_SOURCE.read_text(encoding='utf-8').encode()).hexdigest(),
                      'pacing': json.loads(lines[-2])['pacing'],
                      'request_contract_sha256': hashlib.sha256(FILTER_SOURCE.read_text(encoding='utf-8').encode()).hexdigest(), 'worker_image': IMAGE,
                      'worker_count': 8, 'job_name': job_name}
    finally:
        k('delete', 'job/' + job_name, '-n', NAMESPACE, '--ignore-not-found', '--wait=true', check=False)
        k('delete', 'configmap/' + config, '-n', NAMESPACE, '--ignore-not-found', check=False)


def run_variants(suite_bytes, variants):
    """Run a complete N-way capture without translating pair-shaped output."""
    guard()
    if not isinstance(variants, dict) or len(variants) < 2 or any(
            not NAME.fullmatch(target.get('environment', '')) or
            target.get('selection') not in ('default', 'explicit') or
            not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', target.get('service', 'search')) or
            not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', target.get('variant_id', 'default'))
            for target in variants.values()):
        raise ValueError('Variant targets are invalid.')
    if len(suite_bytes) > 700_000:
        raise ValueError('Frozen suite exceeds the capture ConfigMap budget.')
    job_name = 'variants-' + uuid.uuid4().hex[:8]
    config = job_name + '-input'
    source = VARIANT_SOURCE.read_text(encoding='utf-8')
    apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE}})
    k('create', '-f', '-', body={'apiVersion': 'v1', 'kind': 'ConfigMap',
        'metadata': {'name': config, 'namespace': NAMESPACE},
        'data': {'worker.py': source, 'adaptive_pacing.py': PACING_SOURCE.read_text(encoding='utf-8'),
                 'search_filters.py': FILTER_SOURCE.read_text(encoding='utf-8'),
                 'queries.jsonl': suite_bytes.decode('utf-8'),
                 'variants.json': json.dumps(variants, sort_keys=True)}})
    job = {'apiVersion': 'batch/v1', 'kind': 'Job',
           'metadata': {'name': job_name, 'namespace': NAMESPACE},
           'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300,
                    'template': {'metadata': {'labels': {'lab': 'evaluator'}},
                                 'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                                          'containers': [{'name': 'capture', 'image': IMAGE,
                                              'command': ['python', '/input/worker.py'],
                                              'env': [{'name': 'LAB_JOB_NAME', 'value': job_name},
                                                      *[{'name': 'LAB_' + key.upper(), 'value': value}
                                                        for key, value in correlation().items()]],
                                              'resources': {'requests': {'cpu': '100m', 'memory': '64Mi'},
                                                            'limits': {'cpu': '1', 'memory': '256Mi'}},
                                              'volumeMounts': [{'name': 'input', 'mountPath': '/input',
                                                                'readOnly': True}]}],
                                          'volumes': [{'name': 'input',
                                                       'configMap': {'name': config}}]}}}}
    started = time.monotonic()
    try:
        apply(job)
        k('wait', '--for=condition=complete', 'job/' + job_name, '-n', NAMESPACE,
          '--timeout=300s')
        lines = k('logs', 'job/' + job_name, '-n', NAMESPACE).stdout.splitlines()
        rows = json.loads(lines[-1])
        expected = [json.loads(line)['query_id'] for line in suite_bytes.splitlines()]
        if not isinstance(rows, list) or [row['query_id'] for row in rows] != expected:
            raise ValueError('Capture output does not match the frozen query order.')
        return rows, {'execution': 'in-cluster variant capture Job',
                      'seconds': round(time.monotonic() - started, 3),
                      'worker_sha256': hashlib.sha256(source.encode()).hexdigest(),
                      'adaptive_pacing_sha256': hashlib.sha256(PACING_SOURCE.read_text(encoding='utf-8').encode()).hexdigest(),
                      'pacing': json.loads(lines[-2])['pacing'],
                      'request_contract_sha256': hashlib.sha256(FILTER_SOURCE.read_text(encoding='utf-8').encode()).hexdigest(),
                      'worker_image': IMAGE, 'worker_count': 8, 'job_name': job_name}
    finally:
        k('delete', 'job/' + job_name, '-n', NAMESPACE, '--ignore-not-found',
          '--wait=true', check=False)
        k('delete', 'configmap/' + config, '-n', NAMESPACE, '--ignore-not-found', check=False)
