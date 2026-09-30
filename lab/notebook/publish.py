"""Publish the open source Papermill runner as a pinned multi-architecture Nexus image."""

import json
import os
from pathlib import Path
import re
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get('LAB_STATE_DIR', ROOT / '.lab'))


def call(args, environment, input_text=None):
    result = subprocess.run(args, cwd=ROOT, env=environment, input=input_text,
                            text=True, capture_output=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(' '.join(args[:3]) + ': ' + result.stderr[-1000:])
    return result.stdout


def main():
    credentials = json.loads((STATE / 'nexus.json').read_text(encoding='utf-8'))['publisher']
    config = STATE / 'notebook-docker-config'
    config.mkdir(exist_ok=True)
    environment = {**os.environ, 'DOCKER_CONFIG': str(config.resolve())}
    call(['docker', 'login', '127.0.0.1:18185', '--username', credentials['username'],
          '--password-stdin'], environment, credentials['password'] + '\n')
    tag = '127.0.0.1:18185/lab-notebook:explore-' + uuid.uuid4().hex[:16]
    variants = []
    for architecture in ('amd64', 'arm64'):
        local = 'lab-notebook:' + architecture + '-local'
        variant = tag + '-' + architecture
        call(['docker', 'buildx', 'build', '--platform', 'linux/' + architecture,
              '--provenance=false', '--load', '-t', local,
              '-f', 'lab/notebook/Dockerfile', '.'], environment)
        call(['docker', 'tag', local, variant], environment)
        call(['docker', 'push', variant], environment)
        variants.append(variant)
    call(['docker', 'manifest', 'create', '--insecure', tag, *variants], environment)
    output = call(['docker', 'manifest', 'push', '--insecure', '--purge', tag], environment)
    match = re.search(r'sha256:[a-f0-9]{64}', output)
    if match is None:
        raise ValueError('Nexus did not return a multi-platform notebook image digest.')
    value = {'image': 'nexus.localhost:18185/lab-notebook@' + match.group(0),
             'tag': tag, 'platforms': ['linux/amd64', 'linux/arm64']}
    (STATE / 'notebook-image.json').write_text(json.dumps(value, indent=2), encoding='utf-8')
    print(value['image'])


if __name__ == '__main__':
    main()
