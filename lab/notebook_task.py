"""Run a selected exploratory notebook after a comparison; never change its verdict."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

from blob_config import signed_read_url
from common import ROOT, STATE, k
from compare_search import immutable_blob

NAMESPACE = 'lab-notebooks'
NOTEBOOKS = ROOT / 'lab/notebooks'
NAME = re.compile(r'[a-z][a-z0-9-]{0,62}\.ipynb\Z')
MAX_OUTPUT_BYTES = 1_500_000


def available():
    return sorted(path.name for path in NOTEBOOKS.glob('*.ipynb') if NAME.fullmatch(path.name))


def source(name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or name not in available():
        raise ValueError('Select a packaged exploratory notebook.')
    payload = (NOTEBOOKS / name).read_bytes()
    notebook = json.loads(payload)
    if notebook.get('nbformat') != 4 or not any(
            'parameters' in cell.get('metadata', {}).get('tags', [])
            for cell in notebook.get('cells', [])):
        raise ValueError('Exploratory notebook needs a Papermill parameters cell.')
    if len(payload) > 500_000:
        raise ValueError('Exploratory notebook exceeds the Job input budget.')
    return payload


def image():
    path = STATE / 'notebook-image.json'
    value = os.environ.get('LAB_NOTEBOOK_IMAGE') or (
        json.loads(path.read_text(encoding='utf-8'))['image'] if path.exists() else '')
    if not re.fullmatch(r'nexus\.localhost:18185/lab-notebook@sha256:[a-f0-9]{64}', value):
        raise ValueError('Publish and pin the lab-notebook image first.')
    return value


def run(name, report_sha256, report_blob):
    """Return retained notebook evidence or raise; caller keeps the comparison verdict."""
    payload = source(name)
    if not re.fullmatch('[a-f0-9]{64}', report_sha256):
        raise ValueError('Comparison report hash is invalid.')
    container, blob_name = report_blob.split('/', 1)
    if container != 'runs' or not blob_name:
        raise ValueError('Comparison report Blob is invalid.')
    selected_image = image()
    namespace = json.loads(k('get', 'namespace', NAMESPACE, '-o', 'json').stdout)
    if namespace['metadata'].get('labels', {}).get('lab/owner') != 'exploratory-notebooks' or \
            namespace['metadata'].get('annotations', {}).get('lab/notebook-policy') != 'v1':
        raise ValueError('Install the lab-notebooks namespace before running notebooks.')
    if k('get', 'secret/nexus-read', '-n', NAMESPACE, check=False).returncode:
        raise ValueError('Install the notebook Nexus pull secret first.')
    short = uuid.uuid4().hex[:8]
    job_name = 'explore-' + short
    config_name = job_name + '-source'
    expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
    url = signed_read_url(blob_name, expiry, container='runs')
    k('create', '-f', '-', body={'apiVersion': 'v1', 'kind': 'ConfigMap',
      'metadata': {'name': config_name, 'namespace': NAMESPACE},
      'data': {'source.ipynb': payload.decode('utf-8')}})
    job = {'apiVersion': 'batch/v1', 'kind': 'Job',
           'metadata': {'name': job_name, 'namespace': NAMESPACE},
           'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300,
                    'template': {'metadata': {'labels': {'app': 'lab-notebook'}},
                                 'spec': {'restartPolicy': 'Never',
                                          'automountServiceAccountToken': False,
                                          'imagePullSecrets': [{'name': 'nexus-read'}],
                                          'securityContext': {'runAsUser': 10001, 'runAsGroup': 10001},
                                          'containers': [{'name': 'notebook', 'image': selected_image,
                                              'env': [{'name': 'LAB_REPORT_URL', 'value': url},
                                                      {'name': 'LAB_REPORT_SHA256', 'value': report_sha256}],
                                              'resources': {'requests': {'cpu': '100m', 'memory': '256Mi'},
                                                            'limits': {'cpu': '1', 'memory': '1Gi'}},
                                              'volumeMounts': [{'name': 'source', 'mountPath': '/input',
                                                                'readOnly': True}]}],
                                          'volumes': [{'name': 'source', 'configMap': {'name': config_name}}]}}}}
    started = time.monotonic()
    try:
        k('create', '-f', '-', body=job)
        result = k('wait', '--for=condition=complete', 'job/' + job_name, '-n', NAMESPACE,
                   '--timeout=300s', check=False)
        logs = k('logs', 'job/' + job_name, '-n', NAMESPACE, check=False)
        if result.returncode or logs.returncode:
            raise RuntimeError('Notebook Job failed: ' + (logs.stdout or result.stderr)[-800:])
        lines = logs.stdout.splitlines()
        if not lines or not lines[-1].startswith('LAB_NOTEBOOK_RESULT='):
            raise ValueError('Notebook Job did not return executed notebook bytes.')
        output = base64.b64decode(lines[-1].split('=', 1)[1], validate=True)
        if len(output) > MAX_OUTPUT_BYTES:
            raise ValueError('Executed notebook exceeds the retention limit.')
        output_sha = hashlib.sha256(output).hexdigest()
        source_sha = hashlib.sha256(payload).hexdigest()
        location = immutable_blob('runs', 'notebooks/' + output_sha + '/executed.ipynb', output)
        receipt = {'kind': 'exploratory-notebook-run', 'schema_version': 1,
                   'source': name, 'source_sha256': source_sha, 'image': selected_image,
                   'report_sha256': report_sha256, 'report_blob': report_blob,
                   'executed_sha256': output_sha, 'executed_blob': location}
        receipt_payload = (json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n').encode()
        receipt_sha = hashlib.sha256(receipt_payload).hexdigest()
        receipt_blob = immutable_blob('runs', 'notebooks/' + receipt_sha + '/receipt.json',
                                      receipt_payload)
        return {'state': 'complete', **receipt, 'receipt_sha256': receipt_sha,
                'receipt_blob': receipt_blob,
                'seconds': round(time.monotonic() - started, 3)}
    finally:
        k('delete', 'job/' + job_name, '-n', NAMESPACE,
          '--ignore-not-found', '--wait=true', check=False)
        k('delete', 'configmap/' + config_name, '-n', NAMESPACE,
          '--ignore-not-found', check=False)
