"""Run a frozen functional suite in one scoped, finite Kubernetes Job."""
import hashlib
import math
import json
import re
import subprocess
import time
import uuid
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar

from common import ROOT, apply, guard, k
from operation_telemetry import correlation

NAMESPACE = 'lab-evaluation'
IMAGE = ('python:3.13.7-alpine3.22@sha256:'
         '9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844')
NAME = re.compile(r'lab-[a-z0-9-]{1,48}\Z')
SOURCE = Path(__file__).with_name('evaluation_worker.py')
VARIANT_SOURCE = ROOT / 'lab/variant_capture_worker.py'
FILTER_SOURCE = ROOT / 'lab/search-app/search_filters.py'
PACING_SOURCE = ROOT / 'lab/adaptive_pacing.py'
PROGRESS_SOURCE = ROOT / 'lab/capture_progress.py'
LABEL = ContextVar('evaluation_suite_label', default='Query set')



@contextmanager
def capture_scope(label):
    token = LABEL.set(label)
    try:
        yield
    finally:
        LABEL.reset(token)


def wait_for_capture(name, total):
    """Publish bounded worker snapshots while retaining the existing finite deadline."""
    from operation_telemetry import event_sink, evaluation_progress
    if event_sink.get() is None:
        return k('wait','--for=condition=complete','job/'+name,'-n',NAMESPACE,'--timeout=300s')
    started = time.monotonic()
    latest = None
    read_failures = 0
    while time.monotonic()-started < 300:
        # A kubectl request-timeout override disables this client's in-cluster
        # configuration fallback. Bound the child process without changing it.
        try:
            result = k('get','job/'+name,'-n',NAMESPACE,'-o','json',check=False,timeout=10)
            if result.returncode:
                raise ValueError('Job status request failed')
            status = json.loads(result.stdout).get('status', {})
            if not isinstance(status, dict):
                raise ValueError('Invalid Job status')
        except (subprocess.TimeoutExpired, ValueError, KeyError):
            read_failures += 1
            if read_failures >= 3:
                raise RuntimeError('Evaluation capture Job status could not be read after three attempts. '
                                   'Check coordinator Kubernetes access.') from None
            evaluation_progress('Waiting for Kubernetes Job status',suite=LABEL.get(),job=name,
                elapsed_seconds=round(time.monotonic()-started),unit='queries',
                metrics=latest,metrics_stale=latest is not None)
            time.sleep(5)
            continue
        read_failures = 0
        if status.get('succeeded'): return
        if status.get('failed'): raise RuntimeError('Evaluation capture Job failed; inspect its retained operation evidence.')
        try:
            logs = k('logs','job/'+name,'-n',NAMESPACE,'--tail=4','--limit-bytes=16384',check=False,timeout=10)
            lines = logs.stdout.splitlines() if logs.returncode == 0 else []
        except subprocess.TimeoutExpired:
            lines = []
        sample = None
        for line in lines:
            if line.startswith('LAB_EVALUATION_PROGRESS '):
                try:
                    value=json.loads(line.split(' ',1)[1])
                    if not isinstance(value,dict): continue
                    if (value.get('total') == total and type(value.get('completed')) is int and
                        0 <= value['completed'] <= total and type(value.get('failed')) is int and
                        0 <= value['failed'] <= value['completed']):
                        sample={key:value[key] for key in ('total','completed','failed','retries','pacing_wait_seconds')
                                if type(value.get(key)) in (int,float) and math.isfinite(value[key]) and value[key]>=0}
                except (ValueError,TypeError):
                    pass
        latest = sample or latest
        evaluation_progress('Capturing query results' if latest else 'Waiting for capture worker',
            suite=LABEL.get(),job=name,elapsed_seconds=round(time.monotonic()-started),
            unit='queries',metrics=latest,metrics_stale=sample is None and latest is not None)
        time.sleep(5)
    raise TimeoutError('Evaluation capture Job did not finish within 300 seconds.')


def completed_capture(rows, started, name):
    from operation_telemetry import evaluation_progress
    evaluation_progress('Capture complete',suite=LABEL.get(),job=name,unit='queries',
        elapsed_seconds=round(time.monotonic()-started),
        metrics={'total':len(rows),'completed':len(rows),'failed':sum('error' in row for row in rows)})

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
               'data': {'capture_progress.py': PROGRESS_SOURCE.read_text(encoding='utf-8'), 'worker.py': source, 'search_target.py': Path(__file__).with_name('search_target.py').read_text(encoding='utf-8'), 'adaptive_pacing.py': PACING_SOURCE.read_text(encoding='utf-8'),
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
        wait_for_capture(job_name, len(suite_bytes.splitlines()))
        # Progress precedes the final two lines: completion counters and the
        # order-stable result protocol. No sampled counter is scoring evidence.
        lines = k('logs', 'job/' + job_name, '-n', NAMESPACE).stdout.splitlines()
        rows = json.loads(lines[-1])
        expected = [json.loads(line)['query_id'] for line in suite_bytes.splitlines()]
        if not isinstance(rows, list) or [row['query_id'] for row in rows] != expected:
            raise ValueError('Evaluator output does not match the frozen query order.')
        completed_capture(rows, started, job_name)
        return rows, {'progress_sha256': hashlib.sha256(PROGRESS_SOURCE.read_text(encoding='utf-8').encode()).hexdigest(), 'execution': 'in-cluster evaluator Job', 'seconds': round(time.monotonic() - started, 3),
                      'worker_sha256': hashlib.sha256(source.encode()).hexdigest(),
                      'target_routing_sha256': hashlib.sha256(Path(__file__).with_name('search_target.py').read_bytes()).hexdigest(),
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
        'data': {'capture_progress.py': PROGRESS_SOURCE.read_text(encoding='utf-8'), 'worker.py': source, 'adaptive_pacing.py': PACING_SOURCE.read_text(encoding='utf-8'),
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
        wait_for_capture(job_name, len(suite_bytes.splitlines()))
        lines = k('logs', 'job/' + job_name, '-n', NAMESPACE).stdout.splitlines()
        rows = json.loads(lines[-1])
        expected = [json.loads(line)['query_id'] for line in suite_bytes.splitlines()]
        if not isinstance(rows, list) or [row['query_id'] for row in rows] != expected:
            raise ValueError('Capture output does not match the frozen query order.')
        completed_capture(rows, started, job_name)
        return rows, {'progress_sha256': hashlib.sha256(PROGRESS_SOURCE.read_text(encoding='utf-8').encode()).hexdigest(), 'execution': 'in-cluster variant capture Job',
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
