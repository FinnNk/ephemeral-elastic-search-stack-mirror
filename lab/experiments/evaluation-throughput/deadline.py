"""Verify that an expired finite Job has no successful capture output."""
import argparse
import json
from pathlib import Path
import uuid
from run import Experiment, IMAGE
from common import apply, k


def check(instance):
    name = 'deadline-' + uuid.uuid4().hex[:10]
    try:
        apply({'apiVersion': 'batch/v1', 'kind': 'Job',
            'metadata': {'name': name, 'namespace': instance.namespace},
            'spec': {'activeDeadlineSeconds': 3, 'backoffLimit': 0, 'template': {'spec': {
                'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                'containers': [{'name': 'blocked', 'image': IMAGE, 'imagePullPolicy': 'Never',
                    'command': ['python', '-c', 'import time; time.sleep(120)'],
                    'resources': instance.metadata['worker_resources']}]}}}})
        k('wait', '--for=condition=failed', 'job/' + name, '-n', instance.namespace, '--timeout=60s')
        status = json.loads(k('get', 'job/' + name, '-n', instance.namespace, '-o', 'json').stdout)['status']
        failed = [item for item in status.get('conditions', []) if item['type'] == 'Failed']
        logs = k('logs', 'job/' + name, '-n', instance.namespace, check=False).stdout
        if not failed or failed[0]['reason'] != 'DeadlineExceeded' or status.get('succeeded') or logs.strip():
            raise AssertionError('Expired Job was not an empty failed capture.')
        value = {'kind': 'capture-deadline-check', 'deadline_seconds': 3,
                 'condition': failed[0], 'successful_capture_output': False}
        (instance.directory / 'deadline.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(value), flush=True)
    finally:
        k('delete', 'job/' + name, '-n', instance.namespace, '--ignore-not-found', check=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    check(Experiment(parser.parse_args().directory))
